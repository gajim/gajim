# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from functools import partial
from unittest.mock import MagicMock

from gi.repository import Gtk
from nbxmpp.modules.dataforms import create_field
from nbxmpp.modules.dataforms import SimpleDataForm

from gajim.common import app

from gajim.gtk.change_password import ChangePassword

from . import util

app.get_client = MagicMock()

fields = [
    create_field(typ="text-single", label="Username", var="username"),
    create_field(typ="text-single", label="Old Password", var="old_password"),
    create_field(typ="text-single", label="Mothers name", var="mother", required=True),
]

form = SimpleDataForm(type_="form", fields=fields)


def _apply(self: ChangePassword, next_stage: bool = False) -> None:
    if next_stage:
        self.get_page("next_stage").get_submit_form()
    else:
        self.get_page("next_stage").set_form(form)
        self.show_page("next_stage", Gtk.StackTransitionType.SLIDE_LEFT)


window = ChangePassword("")
window._on_apply = partial(_apply, window)  # type: ignore
window.show()

util.run_app()
