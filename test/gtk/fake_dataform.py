import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from gajim import gui
gui.init('gtk')

from gajim.common.const import CSSPriority

from gajim.gui.dataform import FakeDataFormWidget

from test.gtk import util
util.load_style('gajim.css', CSSPriority.APPLICATION)


fake_form = {
    'instructions': 'This is the a long long long long long long test instruction',
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
    'redirect-url': 'https://jabber.at/account/register/'
}

class DataFormWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title="Data Form Test")
        self.set_default_size(600, 600)
        self._widget = FakeDataFormWidget(fake_form2)
        self.add(self._widget)
        self.show()

win = DataFormWindow()
win.connect('destroy', Gtk.main_quit)
win.show_all()
Gtk.main()
