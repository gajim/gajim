# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Gtk
from nbxmpp.modules.vcard4 import VCard
from nbxmpp.protocol import Iq

from gajim.gtk.vcard_grid import VCardGrid
from gajim.gtk.widgets import GajimAppWindow

from . import util

VCARD_NODE = """
<vcard xmlns="urn:ietf:params:xml:ns:vcard-4.0">
    <fn><text>Peter Saint-Andre</text></fn>
    <n><surname>Saint-Andre</surname><given>Peter</given><additional></additional></n>
    <nickname><text>stpeter</text></nickname>
    <nickname><text>psa</text></nickname>
    <photo><uri>https://stpeter.im/images/stpeter_oscon.jpg</uri></photo>
    <bday><date>1966-08-06</date></bday>
    <adr>
        <parameters>
        <type><text>work</text><text>voice</text></type>
        <pref><integer>1</integer></pref>
        </parameters>
        <ext>Suite 600</ext>
        <street>1899 Wynkoop Street</street>
        <locality>Denver</locality>
        <region>CO</region>
        <code>80202</code>
        <country>USA</country>
    </adr>
    <adr>
        <parameters><type><text>home</text></type></parameters>
        <ext></ext>
        <street></street>
        <locality>Parker</locality>
        <region>CO</region>
        <code>80138</code>
        <country>USA</country>
    </adr>
    <tel>
        <parameters>
        <type><text>work</text><text>voice</text></type>
        <pref><integer>1</integer></pref>
        </parameters>
        <uri>tel:+1-303-308-3282</uri>
    </tel>
    <tel>
        <parameters><type><text>work</text><text>fax</text></type></parameters>
        <uri>tel:+1-303-308-3219</uri>
    </tel>
    <tel>
        <parameters>
        <type><text>cell</text><text>voice</text><text>text</text></type>
        </parameters>
        <uri>tel:+1-720-256-6756</uri>
    </tel>
    <tel>
        <parameters><type><text>home</text><text>voice</text></type></parameters>
        <uri>tel:+1-303-555-1212</uri>
    </tel>
    <geo><uri>geo:39.59,-105.01</uri></geo>
    <title><text>Executive Director</text></title>
    <role><text>Patron Saint</text></role>
    <org>
        <parameters><type><text>work</text></type></parameters>
        <text>XMPP Standards Foundation</text>
    </org>
    <url><uri>https://stpeter.im/</uri></url>
    <note>
        <text>More information about me is located on my personal website: https://stpeter.im/</text>
    </note>
    <gender><sex><text>M</text></sex></gender>
    <lang>
        <parameters><pref>1</pref></parameters>
        <language-tag>en</language-tag>
    </lang>
    <email>
        <parameters><type><text>work</text></type></parameters>
        <text>psaintan@cisco.com</text>
    </email>
    <email>
        <parameters><type><text>home</text></type></parameters>
        <text>stpeter@jabber.org</text>
    </email>
    <impp>
        <parameters><type><text>work</text></type></parameters>
        <uri>xmpp:psaintan@cisco.com</uri>
    </impp>
    <impp>
        <parameters><type><text>home</text></type></parameters>
        <uri>xmpp:stpeter@jabber.org</uri>
    </impp>
    <key>
        <uri>https://stpeter.im/stpeter.asc</uri>
    </key>
</vcard>
"""

VCARD = VCard.from_node(Iq(node=VCARD_NODE))  # type: ignore
ACCOUNT = "test"


class TestVCardGrid(GajimAppWindow):
    def __init__(self):
        GajimAppWindow.__init__(
            self,
            name="",
            title=__class__.__name__,
            default_width=800,
            default_height=700,
        )

        self._is_editable = False

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        main_box.set_valign(Gtk.Align.FILL)
        self.set_child(main_box)

        scrolled_window = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        main_box.append(scrolled_window)

        buttons_box = Gtk.Box(halign=Gtk.Align.CENTER)
        main_box.append(buttons_box)

        edit_toggle = Gtk.Button(label="Toggle Edit")
        edit_toggle.connect("clicked", self._on_edit_toggled)
        buttons_box.append(edit_toggle)

        self._vcard_grid = VCardGrid(ACCOUNT)
        self._vcard_grid.set_hexpand(True)
        self._vcard_grid.set_vcard(VCARD)
        scrolled_window.set_child(self._vcard_grid)

    def _on_edit_toggled(self, _button: Gtk.Button) -> None:
        self._vcard_grid.set_editable(not self._is_editable)
        self._is_editable = not self._is_editable


window = TestVCardGrid()
window.show()

util.run_app()
