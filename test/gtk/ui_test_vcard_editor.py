# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Gtk
from nbxmpp.modules.vcard4 import VCard
from nbxmpp.protocol import Iq

from gajim.gtk.vcard_editor import VCardEditor
from gajim.gtk.window import GajimAppWindow

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
    <gender><sex>M</sex></gender>
    <lang>
        <parameters><pref><integer>1</integer></pref></parameters>
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


class TestVCardListBox(GajimAppWindow):
    def __init__(self):
        GajimAppWindow.__init__(
            self,
            name="",
            title=__class__.__name__,
            default_width=800,
            default_height=700,
            add_window_padding=True,
            header_bar=True,
        )

        self._is_editable = False

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        main_box.set_valign(Gtk.Align.FILL)
        self.set_child(main_box)

        button_box = Gtk.Box(spacing=12)
        enable_button = Gtk.Button(label="Enable")
        disable_button = Gtk.Button(label="Disable")
        error_button = Gtk.Button(label="Set Error")
        success_button = Gtk.Button(label="Save Successful")
        button_box.append(enable_button)
        button_box.append(disable_button)
        button_box.append(error_button)
        button_box.append(success_button)

        main_box.append(button_box)

        self._scrolled = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        main_box.append(self._scrolled)

        self._vcard_editor = VCardEditor()
        self._vcard_editor.set_vcard(VCARD)
        self._scrolled.set_child(self._vcard_editor)

        self._vcard_editor.connect("scroll-to", self._scroll_to_row)

        enable_button.connect(
            "clicked", lambda *x: self._vcard_editor.set_enabled(True)
        )
        disable_button.connect(
            "clicked",
            lambda *x: self._vcard_editor.set_enabled(False, "Not connected to server"),
        )
        error_button.connect(
            "clicked",
            lambda *x: self._vcard_editor.set_error(
                "Some Error", "Server not reachable"
            ),
        )
        success_button.connect(
            "clicked", lambda *x: self._vcard_editor.set_save_successful()
        )

    def _cleanup(self) -> None:
        pass

    def _scroll_to_row(self, _editor: VCardEditor, row: Gtk.ListBoxRow) -> None:
        success, bounds = row.compute_bounds(self._scrolled)
        if not success:
            return

        adjustment = self._scrolled.get_vadjustment()
        row_top = bounds.get_y()
        row_bottom = row_top + bounds.get_height()
        value = adjustment.get_value()
        if row_top < 0:
            value += row_top
        elif row_bottom > adjustment.get_page_size():
            value += row_bottom - adjustment.get_page_size()

        upper = adjustment.get_upper() - adjustment.get_page_size()
        adjustment.set_value(max(adjustment.get_lower(), min(value, upper)))


util.init_settings()
window = TestVCardListBox()
window.present()

util.run_app()
