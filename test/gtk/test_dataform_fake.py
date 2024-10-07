# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gajim.gtk.dataform import FakeDataFormWidget
from gajim.gtk.widgets import GajimAppWindow

from . import util

fake_form = {
    'instructions': ('This is the a long long long long long ' 'long test instruction'),
    'username': '',
    'nick': '',
    'password': '',
    'name': '',
    'first': '',
    'last': '',
    'email': '',
    'address': '',
    'city': '',
    'state': '',
    'zip': '',
    'phone': '',
    'url': '',
    'date': '',
    'misc': '',
    'text': '',
    'key': '',
}

fake_form2 = {
    'instructions': 'To register, visit https://jabber.at/account/register/',
    'redirect-url': 'https://jabber.at/account/register/',
}


class DataFormWindow(GajimAppWindow):
    def __init__(self):
        GajimAppWindow.__init__(
            self, name='', title='Data Form Test', default_width=600, default_height=600
        )

        self._widget = FakeDataFormWidget(fake_form2)
        self.set_child(self._widget)


window = DataFormWindow()
window.show()

util.run_app()
