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

from __future__ import annotations

from typing import cast
from typing import Optional

import logging
from datetime import datetime
from datetime import timedelta

from gi.repository import Gtk
from gi.repository import GLib

from nbxmpp.errors import StanzaError
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.task import Task

from gajim.common import app
from gajim.common import ged
from gajim.common.i18n import _
from gajim.common.const import ArchiveState
from gajim.common.events import ArchivingIntervalFinished
from gajim.common.events import RawMamMessageReceived
from gajim.common.helpers import event_filter

from .assistant import Assistant
from .assistant import Page
from .assistant import SuccessPage
from .util import load_icon_surface
from .util import EventHelper

log = logging.getLogger('gajim.gui.history_sync')


class HistorySyncAssistant(Assistant, EventHelper):
    def __init__(self, account: str) -> None:
        Assistant.__init__(self, width=600, transient_for=app.window)
        EventHelper.__init__(self)
        self.set_name('HistorySyncAssistant')

        self.account = account
        self._client = app.get_client(account)

        self._timedelta: Optional[timedelta] = None
        self._now = datetime.utcnow()
        self._query_id: Optional[str] = None
        self._start: Optional[datetime] = None
        self._end: Optional[datetime] = None

        mam_start = ArchiveState.NEVER
        archive = app.storage.archive.get_archive_infos(
            self._client.get_own_jid().bare)
        if archive is not None and archive.oldest_mam_timestamp is not None:
            mam_start = int(float(archive.oldest_mam_timestamp))

        if mam_start == ArchiveState.NEVER:
            self._current_start = self._now
        elif mam_start == ArchiveState.ALL:
            self._current_start = datetime.utcfromtimestamp(0)
        else:
            self._current_start = datetime.fromtimestamp(mam_start)

        self.add_button('synchronize', _('Synchronize'), 'suggested-action')
        self.add_button('close', _('Close'))
        self.set_button_visible_func(self._visible_func)

        self.add_pages({
            'select': SelectTime(self._now, self._current_start),
            'progress': Progress(),
        })

        self.add_default_page('success')
        success_page = cast(SuccessPage, self.get_page('success'))
        success_page.set_title(_('Synchronize Chat History'))
        success_page.set_heading(_('Finished'))

        self.connect('button-clicked', self._on_button_clicked)

        # pylint: disable=line-too-long
        self.register_events([
            ('archiving-count-received', ged.GUI1, self._received_count),
            ('archiving-interval-finished', ged.GUI1, self._received_finished),
            ('raw-mam-message-received', ged.PRECORE, self._mam_message_received),
        ])
        # pylint: enable=line-too-long

        if mam_start == ArchiveState.ALL:
            success_page.set_text(
                _('Gajim is fully synchronised with the archive.'))
            self.show_page('success')

        self.show_all()

    @staticmethod
    def _visible_func(_assistant: Assistant, page_name: str) -> list[str]:
        if page_name == 'select':
            return ['close', 'synchronize']

        if page_name == 'progress':
            return ['close']

        if page_name == 'success':
            return ['close']

        raise ValueError(f'page {page_name} unknown')

    def _on_button_clicked(self,
                           _assistant: Assistant,
                           button_name: str
                           ) -> None:
        if button_name == 'synchronize':
            self._prepare_query()
            self.show_page('progress', Gtk.StackTransitionType.SLIDE_LEFT)
            return

        if button_name == 'close':
            self.destroy()

    def _prepare_query(self) -> None:
        select_time_page = cast(SelectTime, self.get_page('select'))
        self._timedelta = select_time_page.get_timedelta()
        if self._timedelta is not None:
            self._start = self._now - self._timedelta
        self._end = self._current_start

        log.info('Get mam_start_date: %s', self._current_start)
        log.info('Now: %s', self._now)
        log.info('Start: %s', self._start)
        log.info('End: %s', self._end)

        self._client.get_module('MAM').make_query(
            self._client.get_own_jid().bare,
            start=self._start,
            end=self._end,
            max_=0,
            callback=self._received_count)

    def _received_count(self, task: Task) -> None:
        try:
            result = task.finish()
        except (StanzaError, MalformedStanzaError):
            return

        if result.rsm.count is not None:
            progress_page = cast(Progress, self.get_page('progress'))
            progress_page.set_count(int(result.rsm.count))
        mam_module = self._client.get_module('MAM')
        self._query_id = mam_module.request_archive_interval(
            self._start, self._end)

    @event_filter(['account'])
    def _received_finished(self, event: ArchivingIntervalFinished) -> None:
        if event.query_id != self._query_id:
            return
        self._query_id = None
        log.info('Query finished')
        progress_page = cast(Progress, self.get_page('progress'))
        GLib.idle_add(progress_page.set_finished)
        received_count = progress_page.get_received_count()
        success_page = cast(SuccessPage, self.get_page('success'))
        success_page.set_text(_('Finished synchronising chat history:\n'
                                '%s messages downloaded') % received_count)
        self.show_page('success')

    @event_filter(['account'])
    def _mam_message_received(self, event: RawMamMessageReceived) -> None:
        if self._query_id != event.properties.mam.query_id:
            return

        log.debug('Received message')
        progress_page = cast(Progress, self.get_page('progress'))
        GLib.idle_add(progress_page.set_fraction)


class SelectTime(Page):
    def __init__(self,
                 now: datetime,
                 current_start: datetime
                 ) -> None:
        Page.__init__(self)
        self.title = _('Synchronize Chat History')

        self.complete = False
        self._timedelta: Optional[timedelta] = None

        heading = Gtk.Label()
        heading.get_style_context().add_class('large-header')
        heading.set_max_width_chars(30)
        heading.set_line_wrap(True)
        heading.set_halign(Gtk.Align.CENTER)
        heading.set_justify(Gtk.Justification.CENTER)
        heading.set_text(_('Synchronize Chat History'))

        label = Gtk.Label(
            label=_('How far back should the chat history be synchronised?'))
        label.set_halign(Gtk.Align.CENTER)
        label.set_line_wrap(True)
        label.set_max_width_chars(40)

        listbox = Gtk.ListBox()
        listbox.set_hexpand(False)
        listbox.set_halign(Gtk.Align.CENTER)
        listbox.add(TimeOption(_('One Month'), timedelta(days=30)))
        listbox.add(TimeOption(_('Three Months'), timedelta(days=90)))
        listbox.add(TimeOption(_('One Year'), timedelta(days=365)))
        listbox.add(TimeOption(_('Everything')))
        listbox.connect('row-selected', self._on_row_selected)

        for row in cast(list[TimeOption], listbox.get_children()):
            delta = row.get_timedelta()
            if delta is None:
                continue
            if now - delta > current_start:
                row.set_activatable(False)
                row.set_selectable(False)

        self.add(heading)
        self.add(label)
        self.add(listbox)

        self.show_all()

    def _on_row_selected(self, _listbox: Gtk.ListBox, row: TimeOption) -> None:
        self._timedelta = row.get_timedelta()
        self.complete = row is not None
        self.update_page_complete()

    def get_timedelta(self) -> Optional[timedelta]:
        return self._timedelta

    def get_default_button(self) -> str:
        return 'synchronize'


class Progress(Page):
    def __init__(self) -> None:
        Page.__init__(self)
        self.title = _('Synchronizing Chat History…')

        self._count = 0
        self._received = 0

        surface = load_icon_surface('folder-download-symbolic', size=64)
        image = Gtk.Image.new_from_surface(surface)

        self._progress_bar = Gtk.ProgressBar()
        self._progress_bar.set_show_text(True)
        self._progress_bar.set_text(_('Connecting...'))
        self._progress_bar.set_pulse_step(0.1)
        self._progress_bar.set_vexpand(True)
        self._progress_bar.set_valign(Gtk.Align.CENTER)

        self.add(image)
        self.add(self._progress_bar)
        self.show_all()

    def set_fraction(self) -> None:
        self._received += 1
        if self._count:
            self._progress_bar.set_fraction(self._received / self._count)
            self._progress_bar.set_text(
                _('%(received)s of %(max)s') % {
                    'received': self._received,
                    'max': self._count})
        else:
            self._progress_bar.pulse()
            self._progress_bar.set_text(
                _('Downloaded %s messages') % self._received)

    def set_count(self, count: int) -> None:
        self._count = count

    def set_finished(self) -> None:
        self._progress_bar.set_fraction(1)

    def get_received_count(self) -> int:
        return self._received


class TimeOption(Gtk.ListBoxRow):
    def __init__(self, text: str, months: Optional[timedelta] = None) -> None:
        Gtk.ListBoxRow.__init__(self)
        label = Gtk.Label(label=text)
        self.add(label)

        self._timedelta = months

    def get_timedelta(self) -> Optional[timedelta]:
        return self._timedelta
