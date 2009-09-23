# Copyright (C) 2009  red-agent <hell.director@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Provides an actual implementation of the standard commands.
"""

import dialogs
from common import gajim
from common import helpers
from common.exceptions import GajimGeneralException

from framework import command, CommandError
from middleware import ChatMiddleware

class CommonCommands(ChatMiddleware):
    """
    Here defined commands will be common to all, chat, private chat and group
    chat. Keep in mind that self is set to an instance of either ChatControl,
    PrivateChatControl or GroupchatControl when command is being called.
    """

    @command
    def clear(self):
        """
        Clear the text window
        """
        self.conv_textview.clear()

    @command
    def compact(self):
        """
        Hide the chat buttons
        """
        self.chat_buttons_set_visible(not self.hide_chat_buttons)

    @command(overlap=True)
    def help(self, command=None, all=False):
        """
        Show help on a given command or a list of available commands if -(-a)ll is
        given
        """
        if command:
            command = self.retrieve_command(command)

            doc = _(command.extract_doc())
            usage = command.extract_arg_usage()

            if doc:
                return (doc + '\n\n' + usage) if command.usage else doc
            else:
                return usage
        elif all:
            for command in self.list_commands():
                names = ', '.join(command.names)
                description = command.extract_description()

                self.echo("%s - %s" % (names, description))
        else:
            self.echo(self._help_(self, 'help'))

    @command(raw=True)
    def say(self, message):
        """
        Send a message to the contact
        """
        self.send(message)

    @command(raw=True)
    def me(self, action):
        """
        Send action (in the third person) to the current chat
        """
        self.send("/me %s" % action)

class ChatCommands(CommonCommands):
    """
    Here defined commands will be unique to a chat. Use it as a hoster to provide
    commands which should be unique to a chat. Keep in mind that self is set to
    an instance of ChatControl when command is being called.
    """

    DISPATCH = True
    INHERIT = True

    @command
    def ping(self):
        """
        Send a ping to the contact
        """
        if self.account == gajim.ZEROCONF_ACC_NAME:
            raise CommandError(_('Command is not supported for zeroconf accounts'))
        gajim.connections[self.account].sendPing(self.contact)

class PrivateChatCommands(CommonCommands):
    """
    Here defined commands will be unique to a private chat. Use it as a hoster to
    provide commands which should be unique to a private chat. Keep in mind that
    self is set to an instance of PrivateChatControl when command is being called.
    """

    DISPATCH = True
    INHERIT = True

class GroupChatCommands(CommonCommands):
    """
    Here defined commands will be unique to a group chat. Use it as a hoster to
    provide commands which should be unique to a group chat. Keep in mind that
    self is set to an instance of GroupchatControl when command is being called.
    """

    DISPATCH = True
    INHERIT = True

    @command(raw=True)
    def nick(self, new_nick):
        """
        Change your nickname in a group chat
        """
        try:
            new_nick = helpers.parse_resource(new_nick)
        except Exception:
            raise CommandError(_("Invalid nickname"))
        self.connection.join_gc(new_nick, self.room_jid, None, change_nick=True)
        self.new_nick = new_nick

    @command('query', raw=True)
    def chat(self, nick):
        """
        Open a private chat window with a specified occupant
        """
        nicks = gajim.contacts.get_nick_list(self.account, self.room_jid)
        if nick in nicks:
            self.on_send_pm(nick=nick)
        else:
            raise CommandError(_("Nickname not found"))

    @command('msg', raw=True)
    def message(self, nick, a_message):
        """
        Open a private chat window with a specified occupant and send him a
        message
        """
        nicks = gajim.contacts.get_nick_list(self.account, self.room_jid)
        if nick in nicks:
            self.on_send_pm(nick=nick, msg=a_message)
        else:
            raise CommandError(_("Nickname not found"))

    @command(raw=True, empty=True)
    def topic(self, new_topic):
        """
        Display or change a group chat topic
        """
        if new_topic:
            self.connection.send_gc_subject(self.room_jid, new_topic)
        else:
            return self.subject

    @command(raw=True, empty=True)
    def invite(self, jid, reason):
        """
        Invite a user to a room for a reason
        """
        self.connection.send_invite(self.room_jid, jid, reason)
        return _("Invited %s to %s") % (jid, self.room_jid)

    @command(raw=True, empty=True)
    def join(self, jid, nick):
        """
        Join a group chat given by a jid, optionally using given nickname
        """
        if not nick:
            nick = self.nick

        if '@' not in jid:
            jid = jid + '@' + gajim.get_server_from_jid(self.room_jid)

        try:
            gajim.interface.instances[self.account]['join_gc'].window.present()
        except KeyError:
            try:
                dialogs.JoinGroupchatWindow(account=self.account, room_jid=jid, nick=nick)
            except GajimGeneralException:
                pass

    @command('part', 'close', raw=True, empty=True)
    def leave(self, reason):
        """
        Leave the groupchat, optionally giving a reason, and close tab or window
        """
        self.parent_win.remove_tab(self, self.parent_win.CLOSE_COMMAND, reason)

    @command(raw=True, empty=True)
    def ban(self, who, reason):
        """
        Ban user by a nick or a jid from a groupchat

        If given nickname is not found it will be treated as a jid.
        """
        if who in gajim.contacts.get_nick_list(self.account, self.room_jid):
            contact = gajim.contacts.get_gc_contact(self.account, self.room_jid, who)
            who = contact.jid
        self.connection.gc_set_affiliation(self.room_jid, who, 'outcast', reason or str())

    @command(raw=True, empty=True)
    def kick(self, who, reason):
        """
        Kick user by a nick from a groupchat
        """
        if not who in gajim.contacts.get_nick_list(self.account, self.room_jid):
            raise CommandError(_("Nickname not found"))
        self.connection.gc_set_role(self.room_jid, who, 'none', reason or str())

    @command
    def names(self, verbose=False):
        """
        Display names of all group chat occupants
        """
        get_contact = lambda nick: gajim.contacts.get_gc_contact(self.account, self.room_jid, nick)
        nicks = gajim.contacts.get_nick_list(self.account, self.room_jid)

        # First we do alpha-numeric sort and then role-based one.
        nicks.sort()
        nicks.sort(key=lambda nick: get_contact(nick).role)

        if verbose:
            for nick in nicks:
                contact = get_contact(nick)

                role = helpers.get_uf_role(contact.role)
                affiliation = helpers.get_uf_affiliation(contact.affiliation)

                self.echo("%s - %s - %s" % (nick, role, affiliation))
        else:
            return ', '.join(nicks)

    @command(raw=True)
    def block(self, who):
        """
        Forbid an occupant to send you public or private messages
        """
        self.on_block(None, who)

    @command(raw=True)
    def unblock(self, who):
        """
        Allow an occupant to send you public or privates messages
        """
        self.on_unblock(None, who)
