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
from gajim.gui.dialogs import ErrorDialog
from gajim.gui.dialogs import InformationDialog

Message = namedtuple('Message', ['title', 'text', 'dialog'])

messages = {
    'invalid-jid-with-error': Message(
        _('Invalid XMPP Address'),
        '%s',
        ErrorDialog),

    'invalid-jid': Message(
        _('Invalid XMPP Address'),
        _('It is not possible to send a message '
          'to %s. This XMPP Address is not valid.'),
        ErrorDialog),

    'unread-events-on-remove-account': Message(
        _('Unread Events'),
        _('Read or acknowledge all pending events before '
          'removing this account.'),
        ErrorDialog),

    'invalid-form': Message(
        _('Invalid Form'),
        _('The form is not filled correctly.'),
        ErrorDialog),

    'not-connected-while-sending': Message(
        _('No Connection Available'),
        _('Your message can not be sent until you are connected.'),
        ErrorDialog),

    'jid-in-list': Message(
        _('XMPP Address Already in List'),
        _('The XMPP Address you entered is already in the list. '
          'Please choose another one.'),
        ErrorDialog),

    'invalid-answer': Message(
        _('Invalid Answer'),
        _('Transport %(name)s answered wrongly to '
          'register request: %(error)s'),
        ErrorDialog),

    'invalid-custom-hostname': Message(
        _('Wrong Custom Hostname'),
        _('Custom hostname "%s" is wrong. It will be ignored.'),
        ErrorDialog),

    'agent-register-success': Message(
        _('Registration Succeeded'),
        _('Registration with agent %s succeeded.'),
        InformationDialog),

    'agent-register-error': Message(
        _('Registration Failed'),
        _('Registration with agent %(agent)s failed with error %(error)s: '
          '%(error_msg)s'),
        ErrorDialog),

    'gstreamer-error': Message(
        _('GStreamer Error'),
        _('Error: %(error)s\nDebug: %(debug)s'),
        ErrorDialog),

    'wrong-host': Message(
        _('Wrong Host'),
        _('Invalid local address? :-O'),
        ErrorDialog),

    'avahi-error': Message(
        _('Avahi Error'),
        _('%s\nLink-local messaging might not work properly.'),
        ErrorDialog),

    'request-upload-slot-error': Message(
        _('Could not request upload slot for HTTP File Upload'),
        '%s',
        ErrorDialog),

    'open-file-error': Message(
        _('Could not Open File'),
        _('Exception raised while trying to open file (see log).'),
        ErrorDialog),

    'open-file-error2': Message(
        _('Could not Open File'),
        '%s',
        ErrorDialog),

    'unsecure-error': Message(
        _('Not Secure'),
        _('The server returned an insecure transport (HTTP).'),
        ErrorDialog),

    'httpupload-response-error': Message(
        _('Could not Upload File'),
        _('HTTP response code from server: %s'),
        ErrorDialog),

    'httpupload-error': Message(
        _('Upload Error'),
        '%s',
        ErrorDialog),

    'httpupload-encryption-not-available': Message(
        _('Encryption Error'),
        _('There is no encryption method available '
          'for the chosen encryption.'),
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
