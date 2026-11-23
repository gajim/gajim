# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from base64 import b64decode
from unittest.mock import MagicMock

from gi.repository import Gtk
from nbxmpp.modules.dataforms import extend_form
from nbxmpp.modules.dataforms import SimpleDataForm
from nbxmpp.simplexml import Node

from gajim.common import app
from tests.gtk import util
from tests.gtk.data import TEST_DATA_FORM_XML
from tests.gtk.data import TEST_IMAGE
from tests.gtk.data import TEST_READ_ONLY_DATA_FORM_XML
from tests.gtk.data import TEST_SINGLE_CHOICE_DATA_FORM_XML

from gajim.gtk.dataform_page import DataFormPage
from gajim.gtk.window import GajimAppWindow


class TestDataFormPageWindow(GajimAppWindow):
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

        box = Gtk.Box(orientation="vertical")
        form = extend_form(node=Node(node=TEST_DATA_FORM_XML))
        assert isinstance(form, SimpleDataForm)
        self._widget = DataFormPage(form)

        single_choice_form = extend_form(
            node=Node(node=TEST_SINGLE_CHOICE_DATA_FORM_XML)
        )
        assert isinstance(single_choice_form, SimpleDataForm)
        self._single_choice_widget = DataFormPage(single_choice_form)

        read_only_form = extend_form(node=Node(node=TEST_READ_ONLY_DATA_FORM_XML))
        assert isinstance(read_only_form, SimpleDataForm)
        self._read_only_widget = DataFormPage(read_only_form, read_only=True)

        self._button = Gtk.Button(label="Print Dataform", halign="center")
        self._button.connect("clicked", self._on_click)
        # Double clicking an option of the single choice form activates it
        self.set_default_widget(self._button)

        pages_box = Gtk.Box(orientation="vertical")
        for page in (
            self._widget,
            self._single_choice_widget,
            self._read_only_widget,
        ):
            # Scroll all pages together instead of each page on its own
            scrolled = page.get_first_child()
            assert isinstance(scrolled, Gtk.ScrolledWindow)
            scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)
            pages_box.append(page)

        box.append(Gtk.ScrolledWindow(child=pages_box, vexpand=True))
        box.append(self._button)
        self.set_child(box)

    def _on_click(self, _button: Gtk.Button) -> None:
        form = self._widget.get_submit_form()
        print(form.topretty())
        form = self._single_choice_widget.get_submit_form()
        print(form.topretty())

    def _cleanup(self) -> None:
        pass


app.bob_cache["sha1+8f35fef110ffc5df08d579a50083ff9308fb6242"] = b64decode(TEST_IMAGE)  # noqa: E501
app.css_config = MagicMock()
app.css_config.get_value = MagicMock(return_value="rgb(100, 100, 255)")

util.init_settings()

window = TestDataFormPageWindow()
window.show()

util.run_app()
