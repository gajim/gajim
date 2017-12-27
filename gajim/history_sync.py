# -*- coding: utf-8 -*-
#
# Copyright (C) 2017 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of Gajim.
#
# Gajim is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

import logging
from enum import IntEnum
from datetime import datetime, timedelta

import nbxmpp
from gi.repository import Gtk, GLib

from gajim.common import app
from gajim.common import ged
from gajim.gtkgui_helpers import get_icon_pixmap
from gajim.common.const import ArchiveState

log = logging.getLogger('gajim.c.message_archiving')


class Pages(IntEnum):
    TIME = 0
    SYNC = 1
    SUMMARY = 2


class HistorySyncAssistant(Gtk.Assistant):
    def __init__(self, account, parent):
        Gtk.Assistant.__init__(self)
        self.set_title(_('Synchronise History'))
        self.set_resizable(False)
        self.set_default_size(300, -1)
        self.set_name('HistorySyncAssistant')
        self.set_transient_for(parent)
        self.account = account
        self.con = app.connections[self.account]
        self.timedelta = None
        self.now = datetime.utcnow()
        self.query_id = None
        self.start = None
        self.end = None
        self.next = None
        self.hide_buttons()
        self.event_id = id(self)

        own_jid = self.con.get_own_jid().getStripped()

        mam_start = ArchiveState.NEVER
        archive = app.logger.get_archive_timestamp(own_jid)
        if archive is not None and archive.oldest_mam_timestamp is not None:
            mam_start = int(float(archive.oldest_mam_timestamp))

        if mam_start == ArchiveState.NEVER:
            self.current_start = self.now
        elif mam_start == ArchiveState.ALL:
            self.current_start = datetime.utcfromtimestamp(0)
        else:
            self.current_start = datetime.fromtimestamp(mam_start)

        self.select_time = SelectTimePage(self)
        self.append_page(self.select_time)
        self.set_page_type(self.select_time, Gtk.AssistantPageType.INTRO)

        self.download_history = DownloadHistoryPage(self)
        self.append_page(self.download_history)
        self.set_page_type(self.download_history,
                           Gtk.AssistantPageType.PROGRESS)
        self.set_page_complete(self.download_history, True)

        self.summary = SummaryPage(self)
        self.append_page(self.summary)
        self.set_page_type(self.summary, Gtk.AssistantPageType.SUMMARY)
        self.set_page_complete(self.summary, True)

        app.ged.register_event_handler('archiving-count-received',
                                       ged.GUI1,
                                       self._received_count)
        app.ged.register_event_handler('archiving-query-id',
                                       ged.GUI1,
                                       self._new_query_id)
        app.ged.register_event_handler('archiving-interval-finished',
                                       ged.GUI1,
                                       self._received_finished)
        app.ged.register_event_handler('raw-mam-message-received',
                                       ged.PRECORE,
                                       self._nec_mam_message_received)

        self.connect('prepare', self.on_page_change)
        self.connect('destroy', self.on_destroy)
        self.connect("cancel", self.on_close_clicked)
        self.connect("close", self.on_close_clicked)

        if mam_start == ArchiveState.ALL:
            self.set_current_page(Pages.SUMMARY)
            self.summary.nothing_to_do()

        # if self.con.mam_query_ids:
        #     self.set_current_page(Pages.SUMMARY)
        #     self.summary.query_already_running()

        self.show_all()

    def hide_buttons(self):
        '''
        Hide some of the standard buttons that are included in Gtk.Assistant
        '''
        if self.get_property('use-header-bar'):
            action_area = self.get_children()[1]
        else:
            box = self.get_children()[0]
            content_box = box.get_children()[1]
            action_area = content_box.get_children()[1]
        for button in action_area.get_children():
            button_name = Gtk.Buildable.get_name(button)
            if button_name == 'back':
                button.connect('show', self._on_show_button)
            elif button_name == 'forward':
                self.next = button
                button.connect('show', self._on_show_button)

    @staticmethod
    def _on_show_button(button):
        button.hide()

    def prepare_query(self):
        if self.timedelta:
            self.start = self.now - self.timedelta
        self.end = self.current_start

        log.info('get mam_start_date: %s', self.current_start)
        log.info('now: %s', self.now)
        log.info('start: %s', self.start)
        log.info('end: %s', self.end)

        self.con.request_archive_count(self.event_id, self.start, self.end)

    def _received_count(self, event):
        if event.event_id != self.event_id:
            return
        if event.count is not None:
            self.download_history.count = int(event.count)
        self.con.request_archive_interval(self.event_id, self.start, self.end)

    def _received_finished(self, event):
        if event.event_id != self.event_id:
            return
        log.info('query finished')
        GLib.idle_add(self.download_history.finished)
        self.set_current_page(Pages.SUMMARY)
        self.summary.finished()

    def _new_query_id(self, event):
        if event.event_id != self.event_id:
            return
        self.query_id = event.query_id

    def _nec_mam_message_received(self, obj):
        if obj.conn.name != self.account:
            return

        if obj.result.getAttr('queryid') != self.query_id:
            return

        log.debug('received message')
        GLib.idle_add(self.download_history.set_fraction)

    def on_row_selected(self, listbox, row):
        self.timedelta = row.get_child().get_delta()
        if row:
            self.set_page_complete(self.select_time, True)
        else:
            self.set_page_complete(self.select_time, False)

    def on_page_change(self, assistant, page):
        if page == self.download_history:
            self.next.hide()
            self.prepare_query()

    def on_destroy(self, *args):
        app.ged.remove_event_handler('archiving-count-received',
                                     ged.GUI1,
                                     self._received_count)
        app.ged.remove_event_handler('archiving-query-id',
                                     ged.GUI1,
                                     self._new_query_id)
        app.ged.remove_event_handler('archiving-interval-finished',
                                     ged.GUI1,
                                     self._received_finished)
        app.ged.remove_event_handler('raw-mam-message-received',
                                     ged.PRECORE,
                                     self._nec_mam_message_received)
        del app.interface.instances[self.account]['history_sync']

    def on_close_clicked(self, *args):
        self.destroy()


class SelectTimePage(Gtk.Box):
    def __init__(self, assistant):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(18)
        self.assistant = assistant
        label = Gtk.Label(label=_('How far back do you want to go?'))

        listbox = Gtk.ListBox()
        listbox.set_hexpand(False)
        listbox.set_halign(Gtk.Align.CENTER)
        listbox.add(TimeOption(_('One Month'), 1))
        listbox.add(TimeOption(_('Three Months'), 3))
        listbox.add(TimeOption(_('One Year'), 12))
        listbox.add(TimeOption(_('Everything')))
        listbox.connect('row-selected', assistant.on_row_selected)

        for row in listbox.get_children():
            option = row.get_child()
            if not option.get_delta():
                continue
            if assistant.now - option.get_delta() > assistant.current_start:
                row.set_activatable(False)
                row.set_selectable(False)

        self.pack_start(label, True, True, 0)
        self.pack_start(listbox, False, False, 0)


class DownloadHistoryPage(Gtk.Box):
    def __init__(self, assistant):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(18)
        self.assistant = assistant
        self.count = 0
        self.received = 0

        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)
        self.progress.set_text(_('Connecting...'))
        self.progress.set_pulse_step(0.1)
        self.progress.set_vexpand(True)
        self.progress.set_valign(Gtk.Align.CENTER)

        image = Gtk.Image.new_from_icon_name(
            'folder-download-symbolic', Gtk.IconSize.DIALOG)
        self.pack_start(image, False, False, 0)
        self.pack_start(self.progress, False, False, 0)

    def set_fraction(self):
        self.received += 1
        if self.count:
            self.progress.set_fraction(self.received / self.count)
            self.progress.set_text(_('%(received)s of %(max)s' % {
                'received': self.received, 'max': self.count}))
        else:
            self.progress.pulse()
            self.progress.set_text(_('Downloaded %s Messages' % self.received))

    def finished(self):
        self.progress.set_fraction(1)


class SummaryPage(Gtk.Box):
    def __init__(self, assistant):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(18)
        self.assistant = assistant

        self.label = Gtk.Label()
        self.label.set_name('FinishedLabel')
        self.label.set_valign(Gtk.Align.CENTER)

        self.pack_start(self.label, True, True, 0)

    def finished(self):
        received = self.assistant.download_history.received
        finished = _('''
        Finshed synchronising your History.
        {received} Messages downloaded.
        '''.format(received=received))
        self.label.set_text(finished)

    def nothing_to_do(self):
        nothing_to_do = _('''
        Gajim is fully synchronised
        with the Archive.
        ''')
        self.label.set_text(nothing_to_do)

    def query_already_running(self):
        already_running = _('''
        There is already a synchronisation in
        progress. Please try later.
        ''')
        self.label.set_text(already_running)


class TimeOption(Gtk.Label):
    def __init__(self, label, months=None):
        super().__init__(label=label)
        self.date = months
        if months:
            self.date = timedelta(days=30*months)

    def get_delta(self):
        return self.date
