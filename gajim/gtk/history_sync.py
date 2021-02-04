# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

import logging
from enum import IntEnum
from datetime import datetime, timedelta

from gi.repository import Gtk
from gi.repository import GLib

from nbxmpp.errors import StanzaError
from nbxmpp.errors import MalformedStanzaError

from gajim.common import app
from gajim.common import ged
from gajim.common.i18n import _
from gajim.common.const import ArchiveState
from gajim.common.helpers import event_filter

from .util import load_icon
from .util import EventHelper

log = logging.getLogger('gajim.gui.history_sync')


class Pages(IntEnum):
    TIME = 0
    SYNC = 1
    SUMMARY = 2


class HistorySyncAssistant(Gtk.Assistant, EventHelper):
    def __init__(self, account, parent):
        Gtk.Assistant.__init__(self)
        EventHelper.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_name('HistorySyncAssistant')
        self.set_default_size(300, -1)
        self.set_resizable(False)
        self.set_transient_for(parent)

        self.account = account
        self.con = app.connections[self.account]
        self.timedelta = None
        self.now = datetime.utcnow()
        self.query_id = None
        self.start = None
        self.end = None
        self.next = None

        self._hide_buttons()

        own_jid = self.con.get_own_jid().bare

        mam_start = ArchiveState.NEVER
        archive = app.storage.archive.get_archive_infos(own_jid)
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

        # pylint: disable=line-too-long
        self.register_events([
            ('archiving-count-received', ged.GUI1, self._received_count),
            ('archiving-interval-finished', ged.GUI1, self._received_finished),
            ('raw-mam-message-received', ged.PRECORE, self._nec_mam_message_received),
        ])
        # pylint: enable=line-too-long

        self.connect('prepare', self._on_page_change)
        self.connect('cancel', self._on_close_clicked)
        self.connect('close', self._on_close_clicked)

        if mam_start == ArchiveState.ALL:
            self.set_current_page(Pages.SUMMARY)
            self.summary.nothing_to_do()

        self.show_all()
        self.set_title(_('Synchronise History'))

    def _hide_buttons(self):
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

    def _prepare_query(self):
        if self.timedelta:
            self.start = self.now - self.timedelta
        self.end = self.current_start

        log.info('Get mam_start_date: %s', self.current_start)
        log.info('Now: %s', self.now)
        log.info('Start: %s', self.start)
        log.info('End: %s', self.end)

        jid = self.con.get_own_jid().bare

        self.con.get_module('MAM').make_query(jid,
                                              start=self.start,
                                              end=self.end,
                                              max_=0,
                                              callback=self._received_count)

    def _received_count(self, task):
        try:
            result = task.finish()
        except (StanzaError, MalformedStanzaError):
            return

        if result.rsm.count is not None:
            self.download_history.count = int(result.rsm.count)
        self.query_id = self.con.get_module('MAM').request_archive_interval(
            self.start, self.end)

    @event_filter(['account'])
    def _received_finished(self, event):
        if event.query_id != self.query_id:
            return
        self.query_id = None
        log.info('Query finished')
        GLib.idle_add(self.download_history.finished)
        self.set_current_page(Pages.SUMMARY)
        self.summary.finished()

    @event_filter(['account'])
    def _nec_mam_message_received(self, event):
        if self.query_id != event.properties.mam.query_id:
            return

        log.debug('Received message')
        GLib.idle_add(self.download_history.set_fraction)

    def on_row_selected(self, _listbox, row):
        self.timedelta = row.get_child().get_delta()
        if row:
            self.set_page_complete(self.select_time, True)
        else:
            self.set_page_complete(self.select_time, False)

    def _on_page_change(self, _assistant, page):
        if page == self.download_history:
            self.next.hide()
            self._prepare_query()
        self.set_title(_('Synchronise History'))

    def _on_close_clicked(self, *args):
        self.destroy()


class SelectTimePage(Gtk.Box):
    def __init__(self, assistant):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(18)
        self.assistant = assistant
        label = Gtk.Label(
            label=_('How far back should the chat history be synchronised?'))

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

        surface = load_icon('folder-download-symbolic', self, size=64)
        image = Gtk.Image.new_from_surface(surface)

        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)
        self.progress.set_text(_('Connecting...'))
        self.progress.set_pulse_step(0.1)
        self.progress.set_vexpand(True)
        self.progress.set_valign(Gtk.Align.CENTER)

        self.pack_start(image, False, False, 0)
        self.pack_start(self.progress, False, False, 0)

    def set_fraction(self):
        self.received += 1
        if self.count:
            self.progress.set_fraction(self.received / self.count)
            self.progress.set_text(_('%(received)s of %(max)s') % {
                'received': self.received, 'max': self.count})
        else:
            self.progress.pulse()
            self.progress.set_text(_('Downloaded %s messages') % self.received)

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
        self.label.set_text(_('Finished synchronising chat history:\n'
                              '%s messages downloaded') % received)

    def nothing_to_do(self):
        self.label.set_text(_('Gajim is fully synchronised with the archive.'))

    def query_already_running(self):
        self.label.set_text(_('There is already a synchronisation in '
                              'progress. Please try again later.'))


class TimeOption(Gtk.Label):
    def __init__(self, label, months=None):
        super().__init__(label=label)
        self.date = months
        if months:
            self.date = timedelta(days=30 * months)

    def get_delta(self):
        return self.date
