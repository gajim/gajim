# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
#                    Alex Mauer <hawke AT hawkesnest.net>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
#                         Travis Shirk <travis AT pobox.com>
# Copyright (C) 2007-2008 Julien Pivotto <roidelapluie AT gmail.com>
#                         Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
#                    Jonathan Schleifer <js-gajim AT webkeks.org>
# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

import nbxmpp

from gajim import message_control

from gajim.common import app
from gajim.common import helpers
from gajim.common import ged
from gajim.common.i18n import _
from gajim.common.const import AvatarSize

from gajim.chat_control import ChatControl
from gajim.command_system.implementation.hosts import PrivateChatCommands

from gajim.gtk.dialogs import ErrorDialog


class PrivateChatControl(ChatControl):
    TYPE_ID = message_control.TYPE_PM

    # Set a command host to bound to. Every command given through a private chat
    # will be processed with this command host.
    COMMAND_HOST = PrivateChatCommands

    def __init__(self, parent_win, gc_contact, contact, account, session):
        room_jid = gc_contact.room_jid
        self.room_ctrl = app.interface.msg_win_mgr.get_gc_control(
            room_jid, account)
        if room_jid in app.interface.minimized_controls[account]:
            self.room_ctrl = app.interface.minimized_controls[account][room_jid]
        if self.room_ctrl:
            self.room_name = self.room_ctrl.name
        else:
            self.room_name = room_jid
        self.gc_contact = gc_contact
        ChatControl.__init__(self, parent_win, contact, account, session)
        self.TYPE_ID = 'pm'
        app.ged.register_event_handler('update-gc-avatar', ged.GUI1,
                                       self._nec_update_avatar)
        app.ged.register_event_handler('caps-update', ged.GUI1,
                                       self._nec_caps_received_pm)
        app.ged.register_event_handler('gc-presence-received', ged.GUI1,
                                       self._nec_gc_presence_received)

    def get_our_nick(self):
        return self.room_ctrl.nick

    def shutdown(self):
        super(PrivateChatControl, self).shutdown()
        app.ged.remove_event_handler('update-gc-avatar', ged.GUI1,
                                     self._nec_update_avatar)
        app.ged.remove_event_handler('caps-update', ged.GUI1,
                                     self._nec_caps_received_pm)
        app.ged.remove_event_handler('gc-presence-received', ged.GUI1,
                                     self._nec_gc_presence_received)

    def _nec_caps_received_pm(self, obj):
        if obj.conn.name != self.account or \
        obj.fjid != self.gc_contact.get_full_jid():
            return
        self.update_contact()

    def _nec_gc_presence_received(self, obj):
        if obj.conn.name != self.account:
            return
        if obj.fjid != self.full_jid:
            return
        if '303' in obj.status_code:
            self.print_conversation(
                _('%(nick)s is now known as %(new_nick)s') % {
                    'nick': obj.nick, 'new_nick': obj.new_nick},
                'status')
            gc_c = app.contacts.get_gc_contact(obj.conn.name, obj.room_jid,
                obj.new_nick)
            c = gc_c.as_contact()
            self.gc_contact = gc_c
            self.contact = c
            self.draw_banner()
            old_jid = obj.room_jid + '/' + obj.nick
            new_jid = obj.room_jid + '/' + obj.new_nick
            app.interface.msg_win_mgr.change_key(
                old_jid, new_jid, obj.conn.name)
        else:
            self.contact.show = obj.show
            self.contact.status = obj.status
            self.gc_contact.show = obj.show
            self.gc_contact.status = obj.status
            uf_show = helpers.get_uf_show(obj.show)
            self.print_conversation(
                _('%(nick)s is now %(status)s') % {'nick': obj.nick,
                                                   'status': uf_show},
                'status')
            if obj.status:
                self.print_conversation(' (', 'status', simple=True)
                self.print_conversation(
                    '%s' % (obj.status), 'status', simple=True)
                self.print_conversation(')', 'status', simple=True)
            self.parent_win.redraw_tab(self)
            self.update_ui()

    def send_message(self, message, xhtml=None, process_commands=True,
                     attention=False):
        """
        Call this method to send the message
        """
        message = helpers.remove_invalid_xml_chars(message)
        if not message:
            return

        # We need to make sure that we can still send through the room and that
        # the recipient did not go away
        contact = app.contacts.get_first_contact_from_jid(
            self.account, self.contact.jid)
        if not contact:
            # contact was from pm in MUC
            room, nick = app.get_room_and_nick_from_fjid(self.contact.jid)
            gc_contact = app.contacts.get_gc_contact(self.account, room, nick)
            if not gc_contact:
                ErrorDialog(
                    _('Sending private message failed'),
                    #in second %s code replaces with nickname
                    _('You are no longer in group chat "%(room)s" or '
                      '"%(nick)s" has left.') % {
                          'room': '\u200E' + room, 'nick': nick},
                    transient_for=self.parent_win.window)
                return

        ChatControl.send_message(self, message,
                                 xhtml=xhtml,
                                 process_commands=process_commands,
                                 attention=attention)

    def update_ui(self):
        if self.contact.show == 'offline':
            self.got_disconnected()
        else:
            self.got_connected()
        ChatControl.update_ui(self)

    def _nec_update_avatar(self, obj):
        if obj.contact != self.gc_contact:
            return
        self.show_avatar()

    def show_avatar(self):
        if not app.config.get('show_avatar_in_chat'):
            return

        scale = self.parent_win.window.get_scale_factor()
        surface = app.interface.get_avatar(
            self.gc_contact.avatar_sha, AvatarSize.CHAT, scale)
        image = self.xml.get_object('avatar_image')
        image.set_from_surface(surface)

    def update_contact(self):
        self.contact = self.gc_contact.as_contact()

    def got_disconnected(self):
        ChatControl.got_disconnected(self)
