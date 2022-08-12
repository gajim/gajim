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
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

from typing import Any
from typing import NoReturn
from typing import Callable
from typing import Optional

import io
import argparse
import shlex
import operator

from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.helpers import Observable, is_role_change_allowed
from gajim.common.helpers import is_affiliation_change_allowed
from gajim.common.modules.contacts import GroupchatContact


def split_argument_string(string: str) -> list[str]:
    '''
    Split a string with shlex.split
    '''

    lex = shlex.shlex(string, posix=True)
    lex.whitespace_split = True
    lex.commenters = ''
    result: list[str] = []

    try:
        for token in lex:
            result.append(token)
    except ValueError:
        # If end-of-string is reached and there is a invalid state
        # ValueError is raised. Still add the partial token to the result.
        result.append(lex.token)

    return result


def get_usage_from_command(cmd: argparse.ArgumentParser) -> str:
    with io.StringIO() as output:
        cmd.print_usage(file=output)
        usage = output.getvalue()

    usage = usage.split('[-h] ')[1]
    return usage.strip()


class ArgumentParserError(Exception):
    pass


class CommandError(Exception):
    pass


class CommandNotFoundError(Exception):
    pass


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise ArgumentParserError(message)


class ChatCommands(Observable):
    def __init__(self) -> None:
        Observable.__init__(self)
        self._parser = ArgumentParser(prog='ChatCommands')
        self._sub_parser = self._parser.add_subparsers()
        self._commands: dict[str, tuple[list[str], str]] = {}

        self._create_commands()

    def get_commands(self, used_in: str) -> list[tuple[str, str]]:
        commands: list[tuple[str, str]] = []
        for cmd_name, cmd in self._commands.items():
            if used_in in cmd[0]:
                commands.append((cmd_name, cmd[1]))
        commands.sort(key=operator.itemgetter(0))
        return commands

    def make_parser(self,
                    command_name: str,
                    callback: Callable[..., Any],
                    **kwargs: Any) -> ArgumentParser:

        '''Add and return a subparser and initialize
        it with the command name.
        '''

        parser = self._sub_parser.add_parser(command_name, **kwargs)
        parser.set_defaults(command_name=command_name)
        self.connect(command_name, callback)
        return parser

    def add_command(self,
                    command_name: str,
                    used_in: list[str],
                    cmd: argparse.ArgumentParser
                    ) -> None:

        usage = get_usage_from_command(cmd)
        self._commands[command_name] = (used_in, usage)

    def parse(self, type_: str, arg_string: str) -> None:
        arg_list = split_argument_string(arg_string[1:])

        command_name = arg_list[0]
        command = self._commands.get(command_name)
        if command is None or type_ not in command[0]:
            raise CommandNotFoundError(_('Unknown command: %s' % command_name))

        args = self._parser.parse_args(arg_list)

        self.notify(args.command_name, args)

    def _create_commands(self) -> None:
        parser = self.make_parser('status', self._status_command)
        parser.add_argument('status',
                            choices=['online', 'away', 'xa', 'dnd'])
        parser.add_argument('message', default=None, nargs='?')
        self.add_command('status', ['chat', 'groupchat', 'pm'], parser)

        parser = self.make_parser('invite', self._invite_command)
        parser.add_argument('address')
        parser.add_argument('reason', default=None, nargs='?')
        self.add_command('invite', ['groupchat'], parser)

        parser = self.make_parser('ban', self._ban_command)
        parser.add_argument('who')
        parser.add_argument('reason', default=None, nargs='?')
        self.add_command('ban', ['groupchat'], parser)

        parser = self.make_parser('affiliate', self._affiliate_command)
        parser.add_argument('who')
        parser.add_argument('affiliation',
                            choices=['owner', 'admin', 'member', 'none'])
        self.add_command('affiliate', ['groupchat'], parser)

        parser = self.make_parser('kick', self._kick_command)
        parser.add_argument('who')
        parser.add_argument('reason', default=None, nargs='?')
        self.add_command('kick', ['groupchat'], parser)

        parser = self.make_parser('role', self._role_command)
        parser.add_argument('who')
        parser.add_argument('role',
                            choices=['moderator', 'participant', 'visitor'])
        self.add_command('role', ['groupchat'], parser)

    def _status_command(self,
                        chat_commands: Any,
                        signal_name: str,
                        args: Any
                        ) -> None:

        for client in app.get_clients():
            if not app.settings.get_account_setting(client.account,
                                                    'sync_with_global_status'):
                continue

            if not client.state.is_available:
                continue

            client.change_status(args.status,
                                 args.message or client.status_message)

    def _check_if_joined(self) -> GroupchatContact:
        contact = app.window.get_control().contact
        assert isinstance(contact, GroupchatContact)
        if not contact.is_joined:
            raise CommandError(_('You are currently not '
                                 'joined this group chat'))
        return contact

    def _invite_command(self,
                        chat_commands: Any,
                        signal_name: str,
                        args: Any
                        ) -> None:

        contact = self._check_if_joined()

        try:
            jid = JID.from_string(args.address)
        except Exception:
            raise CommandError(_('Invalid address: %s' % args.address))

        if jid.is_full or jid.localpart is None:
            raise CommandError(_('Invalid address: %s' % args.address))

        client = app.get_client(contact.account)
        client.get_module('MUC').invite(contact.jid, args.address, args.reason)

    def _change_affiliation(self,
                            nick_or_address: str,
                            affiliation: str,
                            reason: Optional[str]) -> None:

        contact = self._check_if_joined()

        nick_list = contact.get_user_nicknames()
        if nick_or_address in nick_list:
            participant = contact.get_resource(nick_or_address)
            self_contact = contact.get_self()
            assert self_contact is not None
            if not is_affiliation_change_allowed(self_contact,
                                                 participant,
                                                 'outcast'):
                raise CommandError(_('You have insufficient permissions'))

            jid = participant.real_jid

        else:
            try:
                jid = JID.from_string(nick_or_address)
            except Exception:
                raise CommandError(_('Invalid address: %s' % nick_or_address))

            if jid.is_full or jid.localpart is None:
                raise CommandError(_('Invalid address: %s' % nick_or_address))

        client = app.get_client(contact.account)
        client.get_module('MUC').set_affiliation(
            contact.jid,
            {jid: {'affiliation': affiliation,
                   'reason': reason}})

    def _ban_command(self,
                     chat_commands: Any,
                     signal_name: str,
                     args: Any
                     ) -> None:

        self._change_affiliation(args.who, 'outcast', args.reason)

    def _affiliate_command(self,
                           chat_commands: Any,
                           signal_name: str,
                           args: Any
                           ) -> None:

        self._change_affiliation(args.who, args.affiliation, None)

    def _change_role(self, nick: str, role: str, reason: Optional[str]) -> None:

        contact = self._check_if_joined()

        nick_list = contact.get_user_nicknames()
        if nick not in nick_list:
            raise CommandError(_('User %s not found' % nick))

        participant = contact.get_resource(nick)
        self_contact = contact.get_self()
        assert self_contact is not None
        if not is_role_change_allowed(self_contact, participant):
            raise CommandError(_('You have insufficient permissions'))

        client = app.get_client(contact.account)
        client.get_module('MUC').set_role(contact.jid,
                                          nick,
                                          role,
                                          reason)

    def _kick_command(self,
                      chat_commands: Any,
                      signal_name: str,
                      args: Any
                      ) -> None:

        self._change_role(args.who, 'none', args.reason)

    def _role_command(self,
                      chat_commands: Any,
                      signal_name: str,
                      args: Any
                      ) -> None:

        self._change_role(args.who, args.role, None)
