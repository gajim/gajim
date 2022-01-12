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

from typing import Optional

import logging

from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app
from gajim.common.i18n import _

from .builder import get_builder
from .gstreamer import create_gtk_widget

try:
    from gi.repository import Gst  # pylint: disable=ungrouped-imports
except Exception:
    pass


log = logging.getLogger('gajim.gui.preview')


class VideoPreview:
    def __init__(self) -> None:

        self._ui = get_builder('video_preview.ui')

        self._active = False

        self._av_pipeline: Optional[Gst.Pipeline] = None
        self._av_src: Optional[Gst.Bin] = None
        self._av_sink: Optional[Gst.Element] = None
        self._av_widget: Optional[Gtk.Widget] = None

    @property
    def widget(self) -> Gtk.Box:
        return self._ui.video_preview_box

    @property
    def is_active(self) -> bool:
        return self._active

    def toggle_preview(self, value: bool) -> None:
        self._active = value
        if value:
            return self._enable_preview()
        return self._disable_preview()

    def _enable_preview(self) -> None:
        src_name = app.settings.get('video_input_device')
        try:
            self._av_src = Gst.parse_bin_from_description(src_name, True)
        except GLib.Error as error:
            log.error(error)
            log.error('Failed to parse "%s" as Gstreamer element', src_name)
            self._set_error_text()
            return

        gtk_widget = create_gtk_widget()
        if gtk_widget is None:
            log.error('Failed to obtain a working Gstreamer GTK+ sink, '
                      'video support will be disabled')
            self._set_error_text()
            return

        sink, widget, name = gtk_widget
        self._set_sink_text(name)

        if self._av_pipeline is None:
            self._av_pipeline = Gst.Pipeline.new('preferences-pipeline')
        else:
            self._av_pipeline.set_state(Gst.State.NULL)

        self._av_pipeline.add(sink)
        self._av_sink = sink

        if self._av_widget is not None:
            self._ui.video_preview_box.remove(self._av_widget)

        self._ui.video_preview_placeholder.set_visible(False)
        self._ui.video_preview_box.pack_end(widget, True, True, 0)
        self._av_widget = widget

        assert self._av_src is not None
        self._av_pipeline.add(self._av_src)
        self._av_src.link(self._av_sink)
        self._av_pipeline.set_state(Gst.State.PLAYING)

    def _disable_preview(self) -> None:
        if self._av_pipeline is not None:
            self._av_pipeline.set_state(Gst.State.NULL)
            if self._av_src is not None:
                self._av_pipeline.remove(self._av_src)
            if self._av_sink is not None:
                self._av_pipeline.remove(self._av_sink)

        self._av_src = None
        self._av_sink = None

        if self._av_widget is not None:
            self._ui.video_preview_box.remove(self._av_widget)
            self._ui.video_preview_placeholder.set_visible(True)
            self._av_widget = None
        self._av_pipeline = None

    def _set_sink_text(self, sink_name: str) -> None:
        text = ''
        if sink_name == 'gtkglsink':
            text = _('<span color="green" font-weight="bold">'
                     'OpenGL</span> accelerated')

        elif sink_name == 'gtksink':
            text = _('<span color="yellow" font-weight="bold">'
                     'Not accelerated</span>')

        self._ui.video_source_label.set_markup(text)

    def _set_error_text(self) -> None:
        self._ui.video_source_label.set_text(
            _('Something went wrong. Video feature disabled.'))

    def refresh(self) -> None:
        self.toggle_preview(False)
        self.toggle_preview(True)
