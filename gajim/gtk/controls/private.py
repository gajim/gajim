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

from gajim.common import helpers
from gajim.common.i18n import _

from gajim.gui.controls.chat import ChatControl
from gajim.command_system.implementation.hosts import PrivateChatCommands

from gajim.gui.dialogs import ErrorDialog
from gajim.gui.const import ControlType


class PrivateChatControl(ChatControl):

    _type = ControlType.PRIVATECHAT

    # Set a command host to bound to. Every command given through a private chat
    # will be processed with this command host.
    COMMAND_HOST = PrivateChatCommands

    def __init__(self, account, jid):
        self._room_contact = self._client.get_module('Contacts').get_contact(
            jid.bare)

        ChatControl.__init__(self, account, jid)

        # self.register_events([
        #     ('update-gc-avatar', ged.GUI1, self._on_update_gc_avatar),
        #     ('caps-update', ged.GUI1, self._on_caps_update),

    def _connect_contact_signals(self):
        self.contact.multi_connect({
            'user-avatar-update': self._on_user_avatar_update,
            'user-joined': self._on_user_joined,
            'user-left': self._on_user_left,
            'user-status-show-changed': self._on_user_status_show_changed,
            'user-nickname-changed': self._on_user_nickname_changed,
            # 'room-kicked': self._on_room_kicked,
            # 'room-destroyed': self._on_room_destroyed,
            'room-joined': self._on_room_joined,
            # 'room-left': self._on_room_left
            'chatstate-update': self._on_chatstate_update,
        })

    @property
    def room_name(self):
        return self._room_contact.name

    def get_our_nick(self):
        muc_data = self._client.get_module('MUC').get_muc_data(
            self._room_contact.jid)
        return muc_data.nick

    def _on_user_nickname_changed(self,
                                  _contact,
                                  _signal_name,
                                  _user_contact,
                                  properties):

        nick = properties.muc_nickname
        new_nick = properties.muc_user.nick
        if properties.is_muc_self_presence:
            message = _('You are now known as %s') % new_nick
        else:
            message = _('{nick} is now known '
                        'as {new_nick}').format(nick=nick, new_nick=new_nick)

        self.add_info_message(message)

        self.draw_banner()
        self.update_ui()

    def _on_user_status_show_changed(self,
                                     _contact,
                                     _signal_name,
                                     _user_contact,
                                     properties):
        nick = properties.muc_nickname
        status = properties.status
        status = '' if status is None else ' - %s' % status
        show = helpers.get_uf_show(properties.show.value)

        if not self._room_contact.settings.get('print_status'):
            self.update_ui()
            return

        if properties.is_muc_self_presence:
            message = _('You are now {show}{status}').format(show=show,
                                                             status=status)

        else:
            message = _('{nick} is now {show}{status}').format(nick=nick,
                                                               show=show,
                                                               status=status)
        self.add_info_message(message)
        self.update_ui()

    # def _on_disconnected(self, event):
    #     if event.properties.jid != self.gc_contact.get_full_jid():
    #         return
    #     self.got_disconnected()

    def _on_user_left(self, *args):
        self.got_disconnected()

    def _on_user_joined(self, *args):
        self.got_connected()

    def _on_room_joined(self, *args):
        if not self.contact.is_available:
            return
        self.got_connected()

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
        if not self.contact.is_available:
            ErrorDialog(
                _('Sending private message failed'),
                #in second %s code replaces with nickname
                _('You are no longer in group chat "%(room)s" or '
                  '"%(nick)s" has left.') % {
                      'room': self.room_name, 'nick': self.contact.name})
            return

        ChatControl.send_message(self, message,
                                 xhtml=xhtml,
                                 process_commands=process_commands,
                                 attention=attention)

    def update_ui(self):
        ChatControl.update_ui(self)

    def _on_user_avatar_update(self, *args):
        self._update_avatar()
