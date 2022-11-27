from unittest.mock import MagicMock

import time

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from nbxmpp.protocol import Iq
from nbxmpp.modules.discovery import parse_disco_info
from nbxmpp.structs import MucSubject

from gajim.common import app
from gajim.common.const import CSSPriority

from gajim import gui
gui.init('gtk')

from test.gtk import util
from gajim.gui.groupchat_info import GroupChatInfoScrolled

util.load_style('gajim.css', CSSPriority.APPLICATION)

stanza = Iq(node='''
<iq xmlns="jabber:client" xml:lang="de-DE" to="user@user.us" from="asd@conference.temptatio.dev" type="result" id="67284933-e526-41f3-8309-9d9475cf9c74">
<query xmlns="http://jabber.org/protocol/disco#info">
<identity name="ipsum dolor sit amet, consetetur sadipscing elitr sed diam nonumy eirmod tempor invidunt" type="text" category="conference" />
<feature var="vcard-temp" />
<feature var="http://jabber.org/protocol/muc" />
<feature var="http://jabber.org/protocol/disco#info" />
<feature var="http://jabber.org/protocol/disco#items" />
<feature var="muc_temporary" />
<feature var="muc_moderated" />
<feature var="muc_open" />
<feature var="muc_hidden" />
<feature var="muc_nonanonymous" />
<feature var="muc_passwordprotected" />
<feature var="urn:xmpp:mam:2" />
<feature var="muc_public" />
<feature var="muc_persistent" />
<feature var="muc_membersonly" />
<feature var="muc_semianonymous" />
<feature var="muc_unmoderated" />
<feature var="muc_unsecured" />
<x type="result" xmlns="jabber:x:data">
<field var="FORM_TYPE" type="hidden">
<value>http://jabber.org/protocol/muc#roominfo</value>
</field>
<field var="muc#roominfo_occupants" type="text-single" label="Number of occupants">
<value>1</value>
</field>
<field var="muc#roomconfig_roomname" type="text-single" label="Natural-Language Room Name">
<value>ipsum dolor sit amet, consetetur sadipscing elitr sed diam nonumy eirmod tempor invidunt</value>
</field>
<field var="muc#roominfo_description" type="text-single" label="Raum Beschreibung">
<value>Lorem ipsum dolor sit amet, consetetur sadipscing elitr sed diam nonumy eirmod tempor invidunt ut labore et dolore magna</value>
</field>
<field var="muc#roominfo_contactjid" type="jid-multi" label="Contact Addresses (normally, room owner or owners)">
<value>userA@user.us</value>
<value>userB@user.us</value>
</field>
<field var="muc#roominfo_changesubject" type="boolean" label="Occupants May Change the Subject">
<value>1</value>
</field>
<field var="muc#roomconfig_allowinvites" type="boolean" label="Occupants are allowed to invite others">
<value>1</value>
</field>
<field var="muc#roomconfig_allowpm" type="list-single" label="Roles that May Send Private Messages">
<value>anyone</value>
<option label="Anyone">
<value>anyone</value>
</option>
<option label="Anyone with Voice">
<value>participants</value>
</option>
<option label="Moderators Only">
<value>moderators</value>
</option>
<option label="Nobody">
<value>none</value>
</option>
</field>
<field var="muc#roominfo_lang" type="text-single" label="Natural Language for Room Discussions">
<value>de</value>
</field>
<field type="text-single" var="muc#roominfo_logs">
<value>https://logs.xmpp.org/xsf/</value>
</field>
</x>
</query>
</iq>''')


subject = ('Lorem ipsum dolor sit amet, consetetur sadipscing elitr sed '
           'diam nonumy eirmod tempor invidunt ut labore et dolore magna')

disco_info = parse_disco_info(stanza)

app.css_config = MagicMock()
app.css_config.get_value = MagicMock(return_value='rgb(100, 100, 255)')

class GroupchatInfo(Gtk.ApplicationWindow):
    def __init__(self):
        Gtk.ApplicationWindow.__init__(self)
        self.set_name('GroupchatJoin')
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_title('Test Group chat info')

        self._main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                 spacing=18)
        self._main_box.set_valign(Gtk.Align.FILL)

        self._muc_info_box = GroupChatInfoScrolled()
        self._muc_info_box.set_vexpand(True)

        self._main_box.add(self._muc_info_box)

        self.add(self._main_box)
        self._muc_info_box.set_from_disco_info(disco_info)
        self._muc_info_box.set_subject(MucSubject(text=subject,
                                                  author='someone',
                                                  timestamp=None))
        self.show_all()


win = GroupchatInfo()
win.connect('destroy', Gtk.main_quit)
win.show_all()
Gtk.main()
