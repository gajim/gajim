# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import typing

import logging

from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app
from gajim.common.i18n import _

from gajim.gtk.builder import get_builder
from gajim.gtk.gstreamer import create_gtk_widget

try:
    from gi.repository import Gst
except Exception:
    if typing.TYPE_CHECKING:
        from gi.repository import Gst


log = logging.getLogger('gajim.gtk.preview')


class VideoPreview(Gtk.Box):
    def __init__(self) -> None:
        Gtk.Box.__init__(self)

        self._active = False

        self._av_pipeline: Gst.Pipeline | None = None
        self._av_src: Gst.Bin | None = None
        self._av_sink: Gst.Element | None = None
        self._av_widget: Gtk.Widget | None = None

        self._ui = get_builder('video_preview.ui')
        self.add(self._ui.video_preview_box)
        self.show_all()

        self.connect('destroy', self._on_destroy)

    def _on_destroy(self, widget: VideoPreview) -> None:
        self._disable_preview()

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
        label_markup = '<span color="%s" font-weight="bold">%s</span>'
        color = 'black'
        label_text = ''
        if sink_name == 'gtkglsink':
            color = 'green'
            label_text = _('OpenGL accelerated')

        elif sink_name == 'gtksink':
            color = 'orange'
            label_text = _('Not accelerated')

        label_markup = label_markup % (color, label_text)
        self._ui.video_source_label.set_markup(label_markup)

    def _set_error_text(self) -> None:
        self._ui.video_source_label.set_text(
            _('Something went wrong. Video feature disabled.'))

    def refresh(self) -> None:
        self.toggle_preview(False)
        self.toggle_preview(True)
