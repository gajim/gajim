# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import Any

from unittest.mock import MagicMock

import gi

from gajim.common.file_transfer_manager import FileTransferManager
from gajim.common.util.preview import GeoPreview
from gajim.common.util.preview import get_preview_data
from gajim.common.util.preview import UrlPreview

gi.require_version("Gst", "1.0")
gi.require_version("GstPbutils", "1.0")

from gi.repository import Adw
from gi.repository import Gst
from gi.repository import Gtk

from gajim.common import app
from gajim.common import configpaths
from gajim.common import logging_helpers
from gajim.common.const import CSSPriority

from gajim.gtk.dropdown import GajimDropDown
from gajim.gtk.dropdown import KeyValueItem
from gajim.gtk.preview.geo import GeoPreviewWidget
from gajim.gtk.preview.preview import PreviewWidget
from gajim.gtk.window import GajimAppWindow

from . import util

util.load_style("gajim.css", CSSPriority.APPLICATION)

ACCOUNT = "me@example.org"

PREVIEW_TYPES = {
    "geo: URI": "geo:50.3333,24.5555",
    "Image URL": "https://gajim.org/img/screenshots/server-info.png",
    "Animated Gif URL": "https://gajim.org/img/gajim-test.gif",
    "Animated WebP URL": "https://gajim.org/img/gajim-test.webp",
    "Animated Avif URL": "https://gajim.org/img/gajim-test.avif",
    "Animated PNG URL": "https://gajim.org/img/gajim-test.png",
    "Audio URL": "https://dev.gajim.org/gajim/gajim/-/wikis/uploads/dec966d89848453df07e0bd9b2ebc3d3/Gajim.ogg",
    "PDF URL": "https://www.rfc-editor.org/rfc/pdfrfc/rfc6120.txt.pdf",
}


class TestPreview(GajimAppWindow):
    def __init__(self) -> None:
        GajimAppWindow.__init__(
            self,
            name="",
            title=__class__.__name__,
            default_width=600,
            default_height=600,
            add_window_padding=True,
            header_bar=True,
        )

        self._box = Gtk.Box(
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            orientation=Gtk.Orientation.VERTICAL,
            hexpand=True,
            spacing=12,
        )
        self.set_child(self._box)

        self._preview_widget = None

        drop_down: GajimDropDown[str] = GajimDropDown(list(PREVIEW_TYPES.keys()))
        drop_down.connect("notify::selected", self._on_preview_type_selected)
        drop_down.select_key(list(PREVIEW_TYPES.keys())[1])
        self._box.append(drop_down)

    def _on_preview_type_selected(
        self, drop_down: GajimDropDown[str], *args: Any
    ) -> None:
        selected_type = drop_down.get_selected_item()
        assert isinstance(selected_type, KeyValueItem)
        uri_data = PREVIEW_TYPES[selected_type.key]

        is_outgoing = True
        muc_context = None

        if self._preview_widget is not None:
            self._box.remove(self._preview_widget)

        match preview := get_preview_data(uri_data, []):
            case GeoPreview():
                print("geo")
                self._preview_widget = GeoPreviewWidget(preview)
            case UrlPreview():
                print("url")
                self._preview_widget = PreviewWidget(
                    ACCOUNT, preview, is_outgoing, muc_context
                )
            case _:
                print(None)
                self._preview_widget = None

        if self._preview_widget is not None:
            self._box.prepend(self._preview_widget)

    def _cleanup(self) -> None:
        pass


Gst.init()
Adw.init()

app.init_process_pool()
app.window = Gtk.Window()
app.is_installed = MagicMock(return_value=True)

logging_helpers.set_loglevels("gajim=DEBUG")

util.init_settings()
app.settings.add_account(ACCOUNT)
app.settings.set("preview_size", 400)
app.settings.set("preview_allow_all_images", True)

configpaths.set_config_root(str(configpaths.get_temp_dir()))
configpaths.init()
configpaths.create_paths()

app.ftm = FileTransferManager()

window = TestPreview()
window.show()

util.run_app()
