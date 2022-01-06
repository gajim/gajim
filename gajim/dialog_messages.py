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
