# Copyright (C) 2009-2010  Alexander Cherniuk <ts33kr@gmail.com>
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

from time import localtime
from time import strftime
from datetime import date

from gi.repository import GLib

from gajim.common import app
from gajim.common import helpers
from gajim.common.i18n import _
from gajim.common.const import KindConstant

from gajim.command_system.errors import CommandError
from gajim.command_system.framework import CommandContainer
from gajim.command_system.framework import command
from gajim.command_system.framework import doc
from gajim.command_system.mapping import generate_usage

from gajim.command_system.implementation.hosts import ChatCommands
from gajim.command_system.implementation.hosts import PrivateChatCommands
from gajim.command_system.implementation.hosts import GroupChatCommands


class StandardCommonCommands(CommandContainer):
    """
    This command container contains standard commands which are common
    to all - chat, private chat, group chat.
    """

    AUTOMATIC = True
    HOSTS = ChatCommands, PrivateChatCommands, GroupChatCommands

    @command(overlap=True)
    @doc(_("Show help on a given command or a list of available commands if "
           "-a is given"))
    def help(self, cmd=None, all_=False):
        if cmd:
            cmd = self.get_command(cmd)

            documentation = _(cmd.extract_documentation())
            usage = generate_usage(cmd)

            text = []

            if documentation:
                text.append(documentation)
            if cmd.usage:
                text.append(usage)

            return '\n\n'.join(text)

        if all_:
            for cmd_ in self.list_commands():
                names = ', '.join(cmd_.names)
                description = cmd_.extract_description()

                self.echo("%s - %s" % (names, description))
        else:
            help_ = self.get_command('help')
            self.echo(help_(self, 'help'))

    @command(raw=True)
    @doc(_("Send a message to the contact"))
    def say(self, message):
        self.send(message)

    @command(raw=True)
    @doc(_("Send action (in the third person) to the current chat"))
    def me(self, action):
        self.send("/me %s" % action)

    @command('lastlog', overlap=True)
    @doc(_("Show logged messages which mention given text"))
    def grep(self, text, limit=None):
        results = app.storage.archive.search_log(self.account, self.contact.jid, text)

        if not results:
            raise CommandError(_("%s: Nothing found") % text)

        if limit:
            try:
                results = results[len(results) - int(limit):]
            except ValueError:
                raise CommandError(_("Limit must be an integer"))

        for row in results:
            contact = row.contact_name
            if not contact:
                if row.kind == KindConstant.CHAT_MSG_SENT:
                    contact = app.nicks[self.account]
                else:
                    contact = self.contact.name

            time_obj = localtime(row.time)
            date_obj = date.fromtimestamp(row.time)
            date_ = strftime('%Y-%m-%d', time_obj)
            time_ = strftime('%H:%M:%S', time_obj)

            if date_obj == date.today():
                formatted = "[%s] %s: %s" % (time_, contact, row.message)
            else:
                formatted = "[%s, %s] %s: %s" % (
                    date_, time_, contact, row.message)

            self.echo(formatted)

    @command(raw=True, empty=True)
    # Do not translate online, away, chat, xa, dnd
    @doc(_("""
    Set the current status

    Status can be given as one of the following values:
    online, away, chat, xa, dnd.
    """))
    def status(self, status, message):
        if status not in ('online', 'away', 'chat', 'xa', 'dnd'):
            raise CommandError("Invalid status given")
        for connection in app.connections.values():
            if not app.settings.get_account_setting(connection.name,
                                                    'sync_with_global_status'):
                continue
            if not connection.state.is_available:
                continue
            connection.change_status(status, message)

    @command(raw=True, empty=True)
    @doc(_("Set the current status to away"))
    def away(self, message):
        if not message:
            message = _("Away")

        for connection in app.connections.values():
            if not app.settings.get_account_setting(connection.name,
                                                    'sync_with_global_status'):
                continue
            if not connection.state.is_available:
                continue
            connection.change_status('away', message)

    @command('back', raw=True, empty=True)
    @doc(_("Set the current status to online"))
    def online(self, message):
        if not message:
            message = _("Available")

        for connection in app.connections.values():
            if not app.settings.get_account_setting(connection.name,
                                                    'sync_with_global_status'):
                continue
            if not connection.state.is_available:
                continue
            connection.change_status('online', message)

    @command
    @doc(_("Send a disco info request"))
    def disco(self):
        client = app.get_client(self.account)
        if not client.state.is_available:
            return

        client.get_module('Discovery').disco_contact(self.contact)


class StandardCommonChatCommands(CommandContainer):
    """
    This command container contains standard commands, which are common
    to a chat and a private chat only.
    """

    AUTOMATIC = True
    HOSTS = ChatCommands, PrivateChatCommands

    @command
    @doc(_("Clear the text window"))
    def clear(self):
        self.conv_textview.clear()

    @command
    @doc(_("Send a ping to the contact"))
    def ping(self):
        if self.account == app.ZEROCONF_ACC_NAME:
            raise CommandError(
                _('Command is not supported for zeroconf accounts'))
        app.connections[self.account].get_module('Ping').send_ping(self.contact)

    @command
    @doc(_("Send DTMF sequence through an open voice chat"))
    def dtmf(self, sequence):
        if not self.audio_sid:
            raise CommandError(_("No open voice chats with the contact"))
        for tone in sequence:
            if not (tone in ("*", "#") or tone.isdigit()):
                raise CommandError(_("%s is not a valid tone") % tone)
        gjs = self.connection.get_module('Jingle').get_jingle_session
        session = gjs(self.full_jid, self.audio_sid)
        content = session.get_content("audio")
        content.batch_dtmf(sequence)

    @command
    @doc(_("Toggle Voice Chat"))
    def audio(self):
        if not self.audio_available:
            raise CommandError(_("Voice chats are not available"))
        # An audio session is toggled by inverting the state of the
        # appropriate button.
        state = self._audio_button.get_active()
        self._audio_button.set_active(not state)

    @command
    @doc(_("Toggle Video Chat"))
    def video(self):
        if not self.video_available:
            raise CommandError(_("Video chats are not available"))
        # A video session is toggled by inverting the state of the
        # appropriate button.
        state = self._video_button.get_active()
        self._video_button.set_active(not state)

    @command(raw=True)
    @doc(_("Send a message to the contact that will attract their attention"))
    def attention(self, message):
        self.send_message(message, process_commands=False, attention=True)


class StandardChatCommands(CommandContainer):
    """
    This command container contains standard commands which are unique
    to a chat.
    """

    AUTOMATIC = True
    HOSTS = (ChatCommands,)


class StandardPrivateChatCommands(CommandContainer):
    """
    This command container contains standard commands which are unique
    to a private chat.
    """

    AUTOMATIC = True
    HOSTS = (PrivateChatCommands,)


class StandardGroupChatCommands(CommandContainer):
    """
    This command container contains standard commands which are unique
    to a group chat.
    """

    AUTOMATIC = True
    HOSTS = (GroupChatCommands,)

    @command
    @doc(_("Clear the text window"))
    def clear(self):
        self.conv_textview.clear()

    @command(raw=True)
    @doc(_("Change your nickname in a group chat"))
    def nick(self, new_nick):
        try:
            new_nick = helpers.parse_resource(new_nick)
        except Exception:
            raise CommandError(_("Invalid nickname"))
        # FIXME: Check state of MUC
        self.connection.get_module('MUC').change_nick(
            self.room_jid, new_nick)
        self.new_nick = new_nick

    @command('query', raw=True)
    @doc(_("Open a private chat window with a specified participant"))
    def chat(self, nick):
        nicks = app.contacts.get_nick_list(self.account, self.room_jid)
        if nick in nicks:
            self.send_pm(nick)
        else:
            raise CommandError(_("Nickname not found"))

    @command('msg', raw=True)
    @doc(_("Open a private chat window with a specified participant and send "
           "him a message"))
    def message(self, nick, message):
        nicks = app.contacts.get_nick_list(self.account, self.room_jid)
        if nick in nicks:
            self.send_pm(nick, message)
        else:
            raise CommandError(_("Nickname not found"))

    @command(raw=True, empty=True)
    @doc(_("Display or change a group chat topic"))
    def topic(self, new_topic):
        if new_topic:
            self.connection.get_module('MUC').set_subject(
                self.room_jid, new_topic)
        else:
            return self.subject

    @command(raw=True, empty=True)
    @doc(_("Invite a user to a group chat for a reason"))
    def invite(self, jid, reason):
        control = app.get_groupchat_control(self.account, self.room_jid)
        if control is not None:
            control.invite(jid)

    @command(raw=True, empty=True)
    @doc(_("Join a group chat given by an XMPP Address"))
    def join(self, jid):
        if '@' not in jid:
            jid = jid + '@' + app.get_server_from_jid(self.room_jid)

        app.app.activate_action(
            'groupchat-join',
            GLib.Variant('as', [self.account, jid]))

    @command('part', 'close', raw=True, empty=True)
    @doc(_("Leave the group chat, optionally giving a reason, and close tab or "
           "window"))
    def leave(self, reason):
        self.leave(reason=reason)

    @command(raw=True, empty=True)
    @doc(_("""
    Ban user by a nick or a JID from a groupchat

    If given nickname is not found it will be treated as a JID.
    """))
    def ban(self, who, reason=''):
        if who in app.contacts.get_nick_list(self.account, self.room_jid):
            contact = app.contacts.get_gc_contact(
                self.account, self.room_jid, who)
            who = contact.jid
        self.connection.get_module('MUC').set_affiliation(
            self.room_jid,
            {who: {'affiliation': 'outcast',
                   'reason': reason}})

    @command(raw=True, empty=True)
    @doc(_("Kick user from group chat by nickname"))
    def kick(self, who, reason):
        if who not in app.contacts.get_nick_list(self.account, self.room_jid):
            raise CommandError(_("Nickname not found"))
        self.connection.get_module('MUC').set_role(
            self.room_jid, who, 'none', reason)

    @command(raw=True)
    # Do not translate moderator, participant, visitor, none
    @doc(_("""Set participant role in group chat.
    Role can be given as one of the following values:
    moderator, participant, visitor, none"""))
    def role(self, who, role):
        if role not in ('moderator', 'participant', 'visitor', 'none'):
            raise CommandError(_("Invalid role given"))
        if who not in app.contacts.get_nick_list(self.account, self.room_jid):
            raise CommandError(_("Nickname not found"))
        self.connection.get_module('MUC').set_role(self.room_jid, who, role)

    @command(raw=True)
    # Do not translate owner, admin, member, outcast, none
    @doc(_("""Set participant affiliation in group chat.
    Affiliation can be given as one of the following values:
    owner, admin, member, outcast, none"""))
    def affiliate(self, who, affiliation):
        if affiliation not in ('owner', 'admin', 'member', 'outcast', 'none'):
            raise CommandError(_("Invalid affiliation given"))
        if who not in app.contacts.get_nick_list(self.account, self.room_jid):
            raise CommandError(_("Nickname not found"))
        contact = app.contacts.get_gc_contact(self.account, self.room_jid, who)

        self.connection.get_module('MUC').set_affiliation(
            self.room_jid,
            {contact.jid: {'affiliation': affiliation}})

    @command
    @doc(_("Display names of all group chat participants"))
    def names(self, verbose=False):
        ggc = app.contacts.get_gc_contact
        gnl = app.contacts.get_nick_list

        get_contact = lambda nick: ggc(self.account, self.room_jid, nick)
        get_role = lambda nick: get_contact(nick).role
        nicks = gnl(self.account, self.room_jid)

        nicks = sorted(nicks)
        nicks = sorted(nicks, key=get_role)

        if not verbose:
            return ", ".join(nicks)

        for nick in nicks:
            contact = get_contact(nick)
            role = helpers.get_uf_role(contact.role)
            affiliation = helpers.get_uf_affiliation(contact.affiliation)
            self.echo("%s - %s - %s" % (nick, role, affiliation))

    @command('ignore', raw=True)
    @doc(_("Forbid a participant to send you public or private messages"))
    def block(self, who):
        self.on_block(None, who)

    @command('unignore', raw=True)
    @doc(_("Allow a participant to send you public or private messages"))
    def unblock(self, who):
        self.on_unblock(None, who)

    @command
    @doc(_("Send a ping to the contact"))
    def ping(self, nick):
        if self.account == app.ZEROCONF_ACC_NAME:
            raise CommandError(
                _('Command is not supported for zeroconf accounts'))
        gc_c = app.contacts.get_gc_contact(self.account, self.room_jid, nick)
        if gc_c is None:
            raise CommandError(_("Unknown nickname"))
        app.connections[self.account].get_module('Ping').send_ping(gc_c)
