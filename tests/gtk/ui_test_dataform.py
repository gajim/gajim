# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from base64 import b64decode
from unittest.mock import MagicMock

from gi.repository import Gtk
from nbxmpp.modules.dataforms import extend_form
from nbxmpp.simplexml import Node

from gajim.common import app
from tests.gtk import util
from tests.gtk.data import TEST_DATA_FORM_XML
from tests.gtk.data import TEST_IMAGE

from gajim.gtk.dataform import DataFormWidget
from gajim.gtk.window import GajimAppWindow


class TestDataFormWindow(GajimAppWindow):
    def __init__(self):
        GajimAppWindow.__init__(
            self,
            name="",
            title=__class__.__name__,
            default_width=1000,
            default_height=600,
            add_window_padding=True,
            header_bar=True,
        )
        options = {
            "left-width": 100,
            "form-width": 435,
        }
        box = Gtk.Box(orientation="vertical")
        self._widget = DataFormWidget(
            extend_form(node=Node(node=TEST_DATA_FORM_XML)), options
        )

        self._button = Gtk.Button(label="Print Dataform", halign="center")
        self._button.connect("clicked", self._on_click)

        box.append(self._widget)
        box.append(self._button)
        self.set_child(box)

    def _on_click(self, _button: Gtk.Button) -> None:
        form = self._widget.get_submit_form()
        print(form.topretty())

    def _cleanup(self) -> None:
        pass


app.bob_cache["sha1+8f35fef110ffc5df08d579a50083ff9308fb6242"] = b64decode(TEST_IMAGE)  # noqa: E501
app.css_config = MagicMock()
app.css_config.get_value = MagicMock(return_value="rgb(100, 100, 255)")

util.init_settings()

window = TestDataFormWindow()
window.show()

util.run_app()
