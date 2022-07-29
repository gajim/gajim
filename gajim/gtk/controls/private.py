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

from nbxmpp import JID
from nbxmpp.structs import PresenceProperties

from gajim.common import app
from gajim.common import helpers
from gajim.common.i18n import _
from gajim.common.modules.contacts import GroupchatParticipant

from gajim.gui.controls.chat import ChatControl
from gajim.command_system.implementation.hosts import PrivateChatCommands

from gajim.gui.const import ControlType


class PrivateChatControl(ChatControl):

    _type = ControlType.PRIVATECHAT

    # Set a command host to bound to. Every command given through a private chat
    # will be processed with this command host.
    COMMAND_HOST = PrivateChatCommands

    def __init__(self, account: str, jid: JID) -> None:
        self._client = app.get_client(account)
        self._room_contact = self._client.get_module('Contacts').get_contact(
            jid.bare)

        ChatControl.__init__(self, account, jid)

    def _connect_contact_signals(self) -> None:
        self.contact.multi_connect({
            'user-status-show-changed': self._on_user_status_show_changed,
            'user-nickname-changed': self._on_user_nickname_changed,
            # 'room-kicked': self._on_room_kicked,
            # 'room-destroyed': self._on_room_destroyed,
        })

    def get_our_nick(self) -> str:
        muc_data = self._client.get_module('MUC').get_muc_data(
            self._room_contact.jid)
        return muc_data.nick

    def _on_user_nickname_changed(self,
                                  _user_contact: GroupchatParticipant,
                                  _signal_name: str,
                                  properties: PresenceProperties,
                                  ) -> None:
        # TODO
        nick = properties.muc_nickname

        assert properties.muc_user is not None
        new_nick = properties.muc_user.nick
        if properties.is_muc_self_presence:
            message = _('You are now known as %s') % new_nick
        else:
            message = _('{nick} is now known '
                        'as {new_nick}').format(nick=nick, new_nick=new_nick)

        self.add_info_message(message)

    def _on_user_status_show_changed(self,
                                     _user_contact: GroupchatParticipant,
                                     _signal_name: str,
                                     properties: PresenceProperties
                                     ) -> None:
        nick = properties.muc_nickname
        status = properties.status
        status = '' if not status else f' - {status}'
        assert properties.show is not None
        show = helpers.get_uf_show(properties.show.value)

        if not self._room_contact.settings.get('print_status'):
            return

        if properties.is_muc_self_presence:
            message = _('You are now {show}{status}').format(show=show,
                                                             status=status)

        else:
            message = _('{nick} is now {show}{status}').format(nick=nick,
                                                               show=show,
                                                               status=status)
        self.add_info_message(message)
