# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import Any

from unittest.mock import MagicMock

import gi

gi.require_version("Gst", "1.0")
gi.require_version("GstPbutils", "1.0")

from gi.repository import Gst
from gi.repository import Gtk

from gajim.common import app
from gajim.common import configpaths
from gajim.common import logging_helpers
from gajim.common.const import CSSPriority
from gajim.common.preview import PreviewManager

from gajim.gtk.dropdown import GajimDropDown
from gajim.gtk.dropdown import KeyValueItem
from gajim.gtk.preview import PreviewWidget
from gajim.gtk.widgets import GajimAppWindow

from . import util

util.load_style("gajim.css", CSSPriority.APPLICATION)

ACCOUNT = "me@example.org"

PREVIEW_TYPES = {
    "geo: URI": "geo:50.3333,24.5555",
    "Image URL": "https://gajim.org/img/screenshots/server-info.png",
    "Audio URL": "https://dev.gajim.org/gajim/gajim/-/wikis/uploads/dec966d89848453df07e0bd9b2ebc3d3/Gajim.ogg",
    "PDF URL": "https://www.rfc-editor.org/rfc/pdfrfc/rfc6120.txt.pdf",
    "Regular URL": "https://gajim.org",
}


class TestPreview(GajimAppWindow):
    def __init__(self) -> None:
        GajimAppWindow.__init__(
            self,
            name="",
            title=__class__.__name__,
            default_width=600,
            default_height=600,
        )

        self._box = Gtk.Box(
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            orientation=Gtk.Orientation.VERTICAL,
            hexpand=True,
            spacing=12,
        )
        self.set_child(self._box)

        self._preview_widget = PreviewWidget(ACCOUNT)
        self._box.append(self._preview_widget)

        drop_down = GajimDropDown(list(PREVIEW_TYPES.keys()))
        drop_down.connect("notify::selected", self._on_preview_type_selected)
        self._box.append(drop_down)

    def _on_preview_type_selected(self, drop_down: GajimDropDown, *args: Any) -> None:
        selected_type = drop_down.get_selected_item()
        assert isinstance(selected_type, KeyValueItem)
        uri_data = PREVIEW_TYPES[selected_type.key]

        is_outgoing = True
        muc_context = None

        self._box.remove(self._preview_widget)

        self._preview_widget = PreviewWidget(ACCOUNT)
        self._box.prepend(self._preview_widget)

        app.preview_manager.create_preview(
            uri_data, self._preview_widget, is_outgoing, muc_context
        )

    def _cleanup(self) -> None:
        pass


Gst.init()

app.get_client = MagicMock()
app.window = MagicMock()
app.is_installed = MagicMock(return_value=True)

logging_helpers.set_loglevels("gajim=DEBUG")

util.init_settings()
app.settings.add_account(ACCOUNT)
app.settings.set("preview_size", 400)

configpaths.set_separation(True)
configpaths.set_config_root(str(configpaths.get_temp_dir()))
configpaths.init()
configpaths.create_paths()

app.preview_manager = PreviewManager()

window = TestPreview()
window.show()

util.run_app()
