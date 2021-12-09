#!/usr/bin/env python3

# Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
#                         Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2005-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2006 Junglecow <junglecow AT gmail.com>
#                    Travis Shirk <travis AT pobox.com>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2007 Julien Pivotto <roidelapluie AT gmail.com>
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

# gajim-remote help will show you the D-BUS API of Gajim

import os
import sys
import locale
import signal

from gajim.common import exceptions
from gajim.common.i18n import _
from gajim.common.i18n import Q_

signal.signal(signal.SIGINT, signal.SIG_DFL) # ^C exits the application

try:
    PREFERRED_ENCODING = locale.getpreferredencoding()
except Exception:
    PREFERRED_ENCODING = 'UTF-8'

def send_error(error_message):
    '''Writes error message to stderr and exits'''
    print(error_message, file=sys.stderr)
    sys.exit(1)

try:
    import dbus
    import dbus.service
#    import dbus.glib
    # test if dbus-x11 is installed
    bus = dbus.SessionBus()
except Exception:
    print(_('D-Bus is not present on this machine or python module is missing'))
    sys.exit(1)

OBJ_PATH = '/org/gajim/dbus/RemoteObject'
INTERFACE = 'org.gajim.dbus.RemoteInterface'
SERVICE = 'org.gajim.Gajim'
BASENAME = 'gajim-remote'

class GajimRemote:

    def __init__(self):
        self.argv_len = len(sys.argv)
        # define commands dict. Prototype :
        # {
        #       'command': [comment, [list of arguments] ]
        # }
        #
        # each argument is defined as a tuple:
        #    (argument name, help on argument, is mandatory)
        #
        self.commands = {
                'help': [
                                _('Shows a help on specific command'),
                                [
                                        #User gets help for the command, specified by this parameter
                                        (_('command'),
                                        _('show help on command'), False)
                                ]
                        ],
                'list_contacts': [
                                _('Lists all contacts in the contact list, one for each line'),
                                [
                                    (Q_('?CLI:account'), _('show only contacts of the given account'),
                                                False)
                                ]

                        ],
                'list_accounts': [
                                _('Prints a list of registered accounts'),
                                []
                        ],
                'change_status': [
                                _('Changes the status of account(s)'),
                                [
#offline, online, chat, away, xa, dnd should not be translated
                                    (Q_('?CLI:status'), _('one of: offline, online, chat, away, xa, dnd. If not set, use account\'s previous status'), False),
                                    (Q_('?CLI:message'), _('status message'), False),
                                    (Q_('?CLI:account'), _('change status of account "account". '
        'If not specified, try to change status of all accounts that have '
        '"sync with global status" option set'), False)
                                ]
                        ],
                'set_priority': [
                                _('Changes the priority of account(s)'),
                                [
                                    (Q_('?CLI:priority'), _('priority you want to give to the account'),
                                                True),
                                    (Q_('?CLI:account'), _('change the priority of the given account. '
                                                'If not specified, change status of all accounts that have'
                                                ' "sync with global status" option set'), False)
                                ]
                        ],
                'send_chat_message': [
                                _('Sends new chat message to a contact in the contact list. Account is optional.'),
                                [
                                        ('jid', _('XMPP Address of the contact that will receive the message'), True),
                                        (Q_('?CLI:message'), _('message contents'), True),
                                        (Q_('?CLI:account'), _('if specified, the message will be sent '
                                                'using this account'), False),
                                ]
                        ],
                'send_single_message': [
                                _('Sends a chat message to someone on your contact list. '
                                  'Account is optional.'),
                                [
                                        ('jid', _('XMPP Address of the contact that will receive the message'), True),
                                        (_('subject'), _('message subject'), True),
                                        (Q_('?CLI:message'), _('message contents'), True),
                                        (Q_('?CLI:account'), _('if specified, the message will be sent '
                                                'using this account'), False),
                                ]
                        ],
                'send_groupchat_message': [
                                _('Sends new message to a group chat you\'ve joined.'),
                                [
                                        ('room_jid', _('XMPP Address of the group chat that will receive the message'), True),
                                        (Q_('?CLI:message'), _('message contents'), True),
                                        (Q_('?CLI:account'), _('if specified, the message will be sent '
                                                'using this account'), False),
                                ]
                        ],
                'contact_info': [
                                _('Gets detailed info on a contact'),
                                [
                                        ('jid', _('XMPP Address of the contact'), True)
                                ]
                        ],
                'account_info': [
                                _('Gets detailed info on a account'),
                                [
                                        ('account', _('Name of the account'), True)
                                ]
                        ],
                'send_file': [
                                _('Sends file to a contact'),
                                [
                                        (_('file'), _('File path'), True),
                                        ('jid', _('XMPP Address of the contact'), True),
                                        (Q_('?CLI:account'), _('if specified, file will be sent using this '
                                                'account'), False)
                                ]
                        ],
                'remove_contact': [
                                _('Removes contact from contact list'),
                                [
                                        ('jid', _('XMPP Address of the contact'), True),
                                        (Q_('?CLI:account'), _('if specified, contact is taken from the '
                                                'contact list of this account'), False)

                                ]
                        ],

                'get_status': [
                        _('Returns current status (the global one unless account is specified)'),
                                [
                                        (Q_('?CLI:account'), '', False)
                                ]
                        ],

                'get_status_message': [
                        _('Returns current status message (the global one unless account is specified)'),
                                [
                                        (Q_('?CLI:account'), '', False)
                                ]
                        ],

                'get_unread_msgs_number': [
                        _('Returns number of unread messages'),
                                []
                        ],

                'send_xml': [
                                _('Sends custom XML'),
                                [
                                        ('xml', _('XML to send'), True),
                                        ('account', _('Account to which the XML will be sent; '
                                        'if not specified, XML will be sent to all accounts'),
                                                False)
                                ]
                        ],

                'check_gajim_running': [
                                _('Check if Gajim is running'),
                                []
                        ],

                }

        self.sbus = None
        if self.argv_len < 2 or sys.argv[1] not in self.commands:
            # no args or bad args
            send_error(self.compose_help())
        self.command = sys.argv[1]
        if self.command == 'help':
            if self.argv_len == 3:
                print(self.help_on_command(sys.argv[2]).encode(
                    PREFERRED_ENCODING))
            else:
                print(self.compose_help().encode(PREFERRED_ENCODING))
            sys.exit(0)
        if self.command == 'check_gajim_running':
            print(self.check_gajim_running())
            sys.exit(0)
        self.init_connection()
        self.check_arguments()

        if self.command == 'contact_info':
            if self.argv_len < 3:
                send_error(_('Missing argument "contact_jid"'))

        try:
            res = self.call_remote_method()
        except exceptions.ServiceNotAvailable:
            # At this point an error message has already been displayed
            sys.exit(1)
        else:
            self.print_result(res)

    def print_result(self, res):
        """
        Print retrieved result to the output
        """
        if res is not None:
            if self.command in ('send_chat_message', 'send_single_message'):
                self.argv_len -= 2

                if res is False:
                    if self.argv_len < 4:
                        send_error(_('\'%s\' is not in your contact list.\n'
                'Please specify account for sending the message.') % sys.argv[2])
                    else:
                        send_error(_('You have no active account'))
            elif self.command == 'list_accounts':
                if isinstance(res, list):
                    for account in res:
                        print(account)
            elif self.command == 'account_info':
                if res:
                    print(self.print_info(0, res, True))
            elif self.command == 'list_contacts':
                for account_dict in res:
                    print(self.print_info(0, account_dict, True))
            elif self.command == 'prefs_list':
                pref_keys = sorted(res.keys())
                for pref_key in pref_keys:
                    result = '%s = %s' % (pref_key, res[pref_key])
                    print(result)
            elif self.command == 'contact_info':
                print(self.print_info(0, res, True))
            elif res:
                print(res)

    def check_gajim_running(self):
        if not self.sbus:
            try:
                self.sbus = dbus.SessionBus()
            except Exception:
                raise exceptions.SessionBusNotPresent

        test = False
        if hasattr(self.sbus, 'name_has_owner'):
            if self.sbus.name_has_owner(SERVICE):
                test = True
        elif dbus.dbus_bindings.bus_name_has_owner(self.sbus.get_connection(),
        SERVICE):
            test = True
        return test

    def init_connection(self):
        """
        Create the connection to the session dbus, or exit if it is not possible
        """
        try:
            self.sbus = dbus.SessionBus()
        except Exception:
            raise exceptions.SessionBusNotPresent

        if not self.check_gajim_running():
        	#Do not translate "gajim-remote"
            send_error(_('It seems Gajim is not running. So you can\'t use gajim-remote.'))
        obj = self.sbus.get_object(SERVICE, OBJ_PATH)
        interface = dbus.Interface(obj, INTERFACE)

        # get the function asked
        self.method = interface.__getattr__(self.command)

    def make_arguments_row(self, args):
        """
        Return arguments list. Mandatory arguments are enclosed with:
        '<', '>', optional arguments - with '[', ']'
        """
        s = ''
        for arg in args:
            if arg[2]:
                s += ' <' + arg[0] + '>'
            else:
                s += ' [' + arg[0] + ']'
        return s

    def help_on_command(self, command):
        """
        Return help message for a given command
        """
        if command in self.commands:
            command_props = self.commands[command]
            arguments_str = self.make_arguments_row(command_props[1])
            str_ = _('Usage: %(basename)s %(command)s %(arguments)s \n\t %(help)s')\
                    % {'basename': BASENAME, 'command': command,
                    'arguments': arguments_str, 'help': command_props[0]}
            if command_props[1]:
                str_ += '\n\n' + _('Arguments:') + '\n'
                for argument in command_props[1]:
                    str_ += ' ' + argument[0] + ' - ' + argument[1] + '\n'
            return str_
        send_error(_('%s not found') % command)

    def compose_help(self):
        """
        Print usage, and list available commands
        """
        s = _('Usage:\n  %s command [arguments]\n\nCommand is one of:\n') % (
            BASENAME)
        for command in sorted(self.commands):
            s += '  ' + command
            for arg in self.commands[command][1]:
                if arg[2]:
                    s += ' <' + arg[0] + '>'
                else:
                    s += ' [' + arg[0] + ']'
            s += '\n'
        return s

    def print_info(self, level, prop_dict, encode_return=False):
        """
        Return formatted string from data structure
        """
        if prop_dict is None or not isinstance(prop_dict, (dict, list, tuple)):
            return ''
        ret_str = ''
        if isinstance(prop_dict, (list, tuple)):
            ret_str = ''
            spacing = ' ' * level * 4
            for val in prop_dict:
                if val is None:
                    ret_str += '\t'
                elif isinstance(val, int):
                    ret_str += '\t' + str(val)
                elif isinstance(val, str):
                    ret_str += '\t' + val
                elif isinstance(val, (list, tuple)):
                    res = ''
                    for items in val:
                        res += self.print_info(level+1, items)
                    if res != '':
                        ret_str += '\t' + res
                elif isinstance(val, dict):
                    ret_str += self.print_info(level+1, val)
            ret_str = '%s(%s)\n' % (spacing, ret_str[1:])
        elif isinstance(prop_dict, dict):
            for key in prop_dict.keys():
                val = prop_dict[key]
                spacing = ' ' * level * 4
                if isinstance(val, (int, str)):
                    if val is not None:
                        val = val.strip()
                        ret_str += '%s%-10s: %s\n' % (spacing, key, val)
                elif isinstance(val, (list, tuple)):
                    res = ''
                    for items in val:
                        res += self.print_info(level+1, items)
                    if res != '':
                        ret_str += '%s%s: \n%s' % (spacing, key, res)
                elif isinstance(val, dict):
                    res = self.print_info(level+1, val)
                    if res != '':
                        ret_str += '%s%s: \n%s' % (spacing, key, res)
        if encode_return:
            try:
                ret_str = ret_str.encode(PREFERRED_ENCODING)
            except Exception:
                pass
        return ret_str

    def check_arguments(self):
        """
        Make check if all necessary arguments are given
        """
        argv_len = self.argv_len - 2
        args = self.commands[self.command][1]
        if len(args) < argv_len:
            send_error(_('Too many arguments. \n'
                    'Type "%(basename)s help %(command)s" for more info') % {
                    'basename': BASENAME, 'command': self.command})
        if len(args) > argv_len:
            if args[argv_len][2]:
                send_error(_('Argument "%(arg)s" is not specified. \n'
                        'Type "%(basename)s help %(command)s" for more info') %
                        {'arg': args[argv_len][0], 'basename': BASENAME,
                        'command': self.command})
        self.arguments = []
        i = 0
        for arg in sys.argv[2:]:
            i += 1
            if i < len(args):
                self.arguments.append(arg)
            else:
                # it's latest argument with spaces
                self.arguments.append(' '.join(sys.argv[i+1:]))
                break
        # add empty string for missing args
        self.arguments += ['']*(len(args)-i)

    def call_remote_method(self):
        """
        Calls self.method with arguments from sys.argv[2:]
        """
        args = [dbus.String(i) for i in self.arguments]
        try:
            res = self.method(*args)
            return res
        except Exception:
            raise exceptions.ServiceNotAvailable
        return None


def main():
    if os.geteuid() == 0:
        sys.exit("You must not launch gajim as root, it is insecure.")

    GajimRemote()


if __name__ == '__main__':
    main()
