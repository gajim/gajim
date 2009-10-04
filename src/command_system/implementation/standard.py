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
Provides an actual implementation for the standard commands.
"""

import dialogs
from common import gajim
from common import helpers
from common.exceptions import GajimGeneralException

from ..framework import CommandContainer, command, documentation
from ..mapping import generate_usage

from hosts import ChatCommands, PrivateChatCommands, GroupChatCommands

class StandardCommonCommands(CommandContainer):
    """
    This command container contains standard commands which are common to all -
    chat, private chat, group chat.
    """

    HOSTS = (ChatCommands, PrivateChatCommands, GroupChatCommands)

    @documentation(_("Clear the text window"))
    @command
    def clear(self):
        self.conv_textview.clear()

    @documentation(_("Hide the chat buttons"))
    @command
    def compact(self):
        new_status = not self.hide_chat_buttons
        self.chat_buttons_set_visible(new_status)

    @documentation(_("Show help on a given command or a list of available commands if -(-a)ll is given"))
    @command(overlap=True)
    def help(self, command=None, all=False):
        if command:
            command = self.get_command(command)

            documentation = _(command.extract_documentation())
            usage = generate_usage(command)

            text = []

            if documentation:
                text.append(documentation)
            if command.usage:
                text.append(usage)

            return '\n\n'.join(text)
        elif all:
            for command in self.list_commands():
                names = ', '.join(command.names)
                description = command.extract_description()

                self.echo("%s - %s" % (names, description))
        else:
            help = self.get_command('help')
            self.echo(help(self, 'help'))

    @documentation(_("Send a message to the contact"))
    @command(raw=True)
    def say(self, message):
        self.send(message)

    @documentation(_("Send action (in the third person) to the current chat"))
    @command(raw=True)
    def me(self, action):
        self.send("/me %s" % action)

class StandardChatCommands(CommandContainer):
    """
    This command container contains standard command which are unique to a chat.
    """

    HOSTS = (ChatCommands,)

    @documentation(_("Send a ping to the contact"))
    @command
    def ping(self):
        if self.account == gajim.ZEROCONF_ACC_NAME:
            raise CommandError(_('Command is not supported for zeroconf accounts'))
        gajim.connections[self.account].sendPing(self.contact)

class StandardPrivateChatCommands(CommandContainer):
    """
    This command container contains standard command which are unique to a
    private chat.
    """

    HOSTS = (PrivateChatCommands,)

class StandardGroupchatCommands(CommandContainer):
    """
    This command container contains standard command which are unique to a group
    chat.
    """

    HOSTS = (GroupChatCommands,)

    @documentation(_("Change your nickname in a group chat"))
    @command(raw=True)
    def nick(self, new_nick):
        try:
            new_nick = helpers.parse_resource(new_nick)
        except Exception:
            raise CommandError(_("Invalid nickname"))
        self.connection.join_gc(new_nick, self.room_jid, None, change_nick=True)
        self.new_nick = new_nick

    @documentation(_("Open a private chat window with a specified occupant"))
    @command('query', raw=True)
    def chat(self, nick):
        nicks = gajim.contacts.get_nick_list(self.account, self.room_jid)
        if nick in nicks:
            self.on_send_pm(nick=nick)
        else:
            raise CommandError(_("Nickname not found"))

    @documentation(_("Open a private chat window with a specified occupant and send him a message"))
    @command('msg', raw=True)
    def message(self, nick, a_message):
        nicks = gajim.contacts.get_nick_list(self.account, self.room_jid)
        if nick in nicks:
            self.on_send_pm(nick=nick, msg=a_message)
        else:
            raise CommandError(_("Nickname not found"))

    @documentation(_("Display or change a group chat topic"))
    @command(raw=True, empty=True)
    def topic(self, new_topic):
        if new_topic:
            self.connection.send_gc_subject(self.room_jid, new_topic)
        else:
            return self.subject

    @documentation(_("Invite a user to a room for a reason"))
    @command(raw=True, empty=True)
    def invite(self, jid, reason):
        self.connection.send_invite(self.room_jid, jid, reason)
        return _("Invited %s to %s") % (jid, self.room_jid)

    @documentation(_("Join a group chat given by a jid, optionally using given nickname"))
    @command(raw=True, empty=True)
    def join(self, jid, nick):
        if not nick:
            nick = self.nick

        if '@' not in jid:
            jid = jid + '@' + gajim.get_server_from_jid(self.room_jid)

        try:
            gajim.interface.instances[self.account]['join_gc'].window.present()
        except KeyError:
            try:
                dialogs.JoinGroupchatWindow(account=None, room_jid=jid, nick=nick)
            except GajimGeneralException:
                pass

    @documentation(_("Leave the groupchat, optionally giving a reason, and close tab or window"))
    @command('part', 'close', raw=True, empty=True)
    def leave(self, reason):
        self.parent_win.remove_tab(self, self.parent_win.CLOSE_COMMAND, reason)

    @documentation(_("""
    Ban user by a nick or a jid from a groupchat

    If given nickname is not found it will be treated as a jid.
    """))
    @command(raw=True, empty=True)
    def ban(self, who, reason):
        if who in gajim.contacts.get_nick_list(self.account, self.room_jid):
            contact = gajim.contacts.get_gc_contact(self.account, self.room_jid, who)
            who = contact.jid
        self.connection.gc_set_affiliation(self.room_jid, who, 'outcast', reason or str())

    @documentation(_("Kick user by a nick from a groupchat"))
    @command(raw=True, empty=True)
    def kick(self, who, reason):
        if not who in gajim.contacts.get_nick_list(self.account, self.room_jid):
            raise CommandError(_("Nickname not found"))
        self.connection.gc_set_role(self.room_jid, who, 'none', reason or str())

    @documentation(_("Display names of all group chat occupants"))
    @command
    def names(self, verbose=False):
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

    @documentation(_("Forbid an occupant to send you public or private messages"))
    @command('ignore', raw=True)
    def block(self, who):
        self.on_block(None, who)

    @documentation(_("Allow an occupant to send you public or private messages"))
    @command('unignore', raw=True)
    def unblock(self, who):
        self.on_unblock(None, who)
