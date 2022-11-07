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

from typing import Optional

import logging
from pathlib import Path

from gi.repository import GLib
from gi.repository import Gtk
try:
    from gi.repository import Gst
except Exception:
    pass

from gajim.common.i18n import _

from .util import get_cursor

log = logging.getLogger('gajim.gui.preview_audio')


class AudioWidget(Gtk.Box):
    def __init__(self, file_path: Path) -> None:
        Gtk.Box.__init__(self,
                         orientation=Gtk.Orientation.HORIZONTAL,
                         spacing=6)
        self._playbin: Optional[Gst.Element] = Gst.ElementFactory.make(
            'playbin', 'bin')
        if self._playbin is None:
            label = Gtk.Label(label=_('Audio preview is not available'))
            self.add(label)
            log.debug('Could not create GST playbin')
            return

        self._query: Gst.Query = Gst.Query.new_position(Gst.Format.TIME)
        self._has_timeout: bool = False

        self._build_audio_widget()
        self._setup_audio_player(file_path)

    def _build_audio_widget(self) -> None:
        play_button = Gtk.Button()
        play_button.get_style_context().add_class('flat')
        play_button.get_style_context().add_class('border')
        play_button.set_tooltip_text(_('Start/stop playback'))
        self._play_icon = Gtk.Image.new_from_icon_name(
            'media-playback-start-symbolic',
            Gtk.IconSize.BUTTON)
        play_button.add(self._play_icon)
        play_button.connect('clicked', self._on_play_clicked)
        event_box = Gtk.EventBox()
        event_box.connect('realize', self._on_realize)
        event_box.add(play_button)
        self.add(event_box)

        self._seek_bar = Gtk.Scale(
            orientation=Gtk.Orientation.HORIZONTAL)
        self._seek_bar.set_range(0.0, 1.0)
        self._seek_bar.set_size_request(300, -1)
        self._seek_bar.set_value_pos(Gtk.PositionType.RIGHT)
        self._seek_bar.connect('change-value', self._on_seek)
        self._seek_bar.connect(
            'format-value', self._format_audio_timestamp)
        event_box = Gtk.EventBox()
        event_box.connect('realize', self._on_realize)
        event_box.add(self._seek_bar)
        self.add(event_box)

        self.connect('destroy', self._on_destroy)
        self.show_all()

    def _setup_audio_player(self, file_path: Path) -> None:
        assert self._playbin is not None
        self._playbin.set_property('uri', file_path.as_uri())
        state_return = self._playbin.set_state(Gst.State.PAUSED)
        if state_return == Gst.StateChangeReturn.FAILURE:
            log.debug('Could not setup GST playbin')
            return

        bus: Optional[Gst.Bus] = self._playbin.get_bus()
        if bus is None:
            log.debug('Could not get GST Bus')
            return
        bus.add_signal_watch()
        bus.connect('message', self._on_bus_message)

    def _on_bus_message(self, _bus: Gst.Bus, message: Gst.Message) -> None:
        assert self._playbin is not None
        if message.type == Gst.MessageType.EOS:
            self._set_pause(True)
            self._playbin.seek_simple(
                Gst.Format.TIME, Gst.SeekFlags.FLUSH, 0)
        elif message.type == Gst.MessageType.STATE_CHANGED:
            success, duration = self._playbin.query_duration(
                Gst.Format.TIME)
            if not success:
                return
            assert duration is not None
            if duration > 0:
                self._seek_bar.set_range(0.0, duration)

            is_paused = self._get_paused()
            if (duration > 0 and not is_paused and
                    not self._has_timeout):
                GLib.timeout_add(50, self._update_seek_bar)
                self._has_timeout = True

    def _on_seek(self,
                 _range: Gtk.Range,
                 _scroll: Gtk.ScrollType,
                 value: float
                 ) -> bool:
        assert self._playbin is not None
        self._playbin.seek_simple(
            Gst.Format.TIME, Gst.SeekFlags.FLUSH, int(value))
        return False

    def _on_play_clicked(self, _button: Gtk.Button) -> None:
        self._set_pause(not self._get_paused())

    def _on_destroy(self, _widget: Gtk.Widget) -> None:
        assert self._playbin is not None
        self._playbin.set_state(Gst.State.NULL)

    def _get_paused(self) -> bool:
        assert self._playbin is not None
        _, state, _ = self._playbin.get_state(20)
        return state == Gst.State.PAUSED

    def _set_pause(self, paused: bool) -> None:
        assert self._playbin is not None
        if paused:
            self._playbin.set_state(Gst.State.PAUSED)
            self._play_icon.set_from_icon_name(
                'media-playback-start-symbolic',
                Gtk.IconSize.BUTTON)
        else:
            self._playbin.set_state(Gst.State.PLAYING)
            self._play_icon.set_from_icon_name(
                'media-playback-pause-symbolic',
                Gtk.IconSize.BUTTON)

    def _update_seek_bar(self) -> bool:
        if self._get_paused():
            self._has_timeout = False
            return False

        assert self._playbin is not None
        if self._playbin.query(self._query):
            _fmt, cur_pos = self._query.parse_position()
            if cur_pos is not None:
                self._seek_bar.set_value(cur_pos)
        return True

    @staticmethod
    def _format_audio_timestamp(_widget: Gtk.Scale, ns: float) -> str:
        seconds = ns / 1000000000
        minutes = seconds / 60
        hours = minutes / 60

        i_seconds = int(seconds) % 60
        i_minutes = int(minutes) % 60
        i_hours = int(hours)

        if i_hours > 0:
            return f'{i_hours:d}:{i_minutes:02d}:{i_seconds:02d}'
        return f'{i_minutes:d}:{i_seconds:02d}'

    @staticmethod
    def _on_realize(event_box: Gtk.EventBox) -> None:
        window = event_box.get_window()
        if window is not None:
            window.set_cursor(get_cursor('pointer'))
