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
from gajim.common.i18n import _
from gajim.gtk.dialogs import ErrorDialog
from gajim.gtk.dialogs import InformationDialog

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

    'invalid-jid': Message(
        _('Invalid JID'),
        _('It is not possible to send a message '
          'to %s, this JID is not valid.'),
        ErrorDialog),

    'unread-events-on-remove-account': Message(
        _('Unread events'),
        _('Read all pending events before removing this account.'),
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

    'invalid-answer': Message(
        _('Invalid answer'),
        _('Transport %(name)s answered wrongly to '
          'register request: %(error)s'),
        ErrorDialog),

    'invalid-custom-hostname': Message(
        _('Wrong Custom Hostname'),
        _('Wrong custom hostname "%s". Ignoring it.'),
        ErrorDialog),

    'privacy-list-error': Message(
        _('Error while removing privacy list'),
        _('Privacy list %s has not been removed. '
          'It is maybe active in one of your connected resources. '
          'Deactivate it and try again.'),
        ErrorDialog),

    'invisibility-not-supported': Message(
        _('Invisibility not supported'),
        _('Account %s doesn\'t support invisibility.'),
        ErrorDialog),

    'unregister-error': Message(
        _('Unregister failed'),
        _('Unregistration with server %(server)s failed: %(error)s'),
        ErrorDialog),

    'agent-register-success': Message(
        _('Registration succeeded'),
        _('Registration with agent %s succeeded'),
        InformationDialog),

    'agent-register-error': Message(
        _('Registration failed'),
        _('Registration with agent %(agent)s failed with error %(error)s: '
          '%(error_msg)s'),
        ErrorDialog),

    'unable-join-groupchat': Message(
        _('Unable to join Groupchat'),
        '%s',
        ErrorDialog),

    'gstreamer-error': Message(
        _('GStreamer error'),
        _('Error: %(error)s\nDebug: %(debug)s'),
        ErrorDialog),

    'wrong-host': Message(
        _('Wrong host'),
        _('Invalid local address? :-O'),
        ErrorDialog),

    'avahi-error': Message(
        _('Avahi error'),
        _('%s\nLink-local messaging might not work properly.'),
        ErrorDialog),

    'request-upload-slot-error': Message(
        _('Could not request upload slot'),
        '%s',
        ErrorDialog),

    'request-upload-slot-error2': Message(
        _('Could not request upload slot'),
        _('Got unexpected response from server (see log)'),
        ErrorDialog),

    'open-file-error': Message(
        _('Could not open file'),
        _('Exception raised while opening file (see log)'),
        ErrorDialog),

    'open-file-error2': Message(
        _('Could not open file'),
        '%s',
        ErrorDialog),

    'unsecure-error': Message(
        _('Unsecure'),
        _('Server returned unsecure transport (HTTP)'),
        ErrorDialog),

    'httpupload-response-error': Message(
        _('Could not upload file'),
        _('HTTP response code from server: %s'),
        ErrorDialog),

    'httpupload-error': Message(
        _('Upload Error'),
        '%s',
        ErrorDialog),

    'httpupload-encryption-not-available': Message(
        _('Encryption Error'),
        _('For the chosen encryption there is no encryption method available'),
        ErrorDialog),

    'avatar-upload-error': Message(
        _('Avatar upload failed'),
        '%s',
        ErrorDialog),
    }


def get_dialog(dialog_name, *args, **kwargs):
    message = messages.get(dialog_name, None)
    if message is None:
        raise ValueError('Dialog %s does not exist' % dialog_name)

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
