# -*- coding: utf-8 -*-
#
# Copyright (C) 2017 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of Gajim.
#
# Gajim is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

from collections import namedtuple

from gi.repository import GLib

from gajim.common.app import app
from gajim.dialogs import ErrorDialog

Message = namedtuple('Message', ['title', 'text', 'dialog'])

messages = {
    'start-chat-not-connected': Message(
        _('You are not connected to the server'),
        _('You can not start a new conversation unless you are connected.'),
        ErrorDialog),

    'invalid-jid-with-error': Message(
        _('Invalid JID'),
        '%s',
        ErrorDialog),

    'unread-events-on-remove-account': Message(
        _('Unread events'),
        _('Read all pending events before removing this account.'),
        ErrorDialog),

    'connected-on-disable-account': Message(
        _('You are currently connected to the server'),
        _('To disable the account, you must be disconnected.'),
        ErrorDialog),

    'invalid-form': Message(
        _('Invalid Form'),
        _('The form is not filled correctly.'),
        ErrorDialog),

    'join-while-invisible': Message(
        _('Invisible'),
        _('You cannot join a group chat while you are invisible'),
        ErrorDialog),

    'not-connected-while-sending': Message(
        _('A connection is not available'),
        _('Your message can not be sent until you are connected.'),
        ErrorDialog),

    'jid-in-list': Message(
        _('JID already in list'),
        _('The JID you entered is already in the list. Choose another one.'),
        ErrorDialog),

    }


def get_dialog(name, *args, **kwargs):
    message = messages.get(name, None)
    if message is None:
        raise ValueError('Dialog %s does not exist' % name)

    # Set transient window
    transient_for = kwargs.get('transient_for', None)
    if transient_for is None:
        transient_for = app.get_active_window()
    else:
        del kwargs['transient_for']

    if args:
        message_text = message.text % args
    elif kwargs:
        message_text = message.text % kwargs
    else:
        message_text = message.text
    dialog = message.dialog(message.title,
                            GLib.markup_escape_text(message_text),
                            transient_for=transient_for)
    return dialog
