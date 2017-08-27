# -*- coding:utf-8 -*-
## src/notify.py
##
## Copyright (C) 2005 Sebastian Estienne
## Copyright (C) 2005-2006 Andrew Sayman <lorien420 AT myrealbox.com>
## Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2005-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2006 Travis Shirk <travis AT pobox.com>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007 Julien Pivotto <roidelapluie AT gmail.com>
##                    Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
##                    Jonathan Schleifer <js-gajim AT webkeks.org>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

from gi.repository import Gio
from gajim import gtkgui_helpers

from gajim.common import app

def get_show_in_roster(event, account, contact, session=None):
    """
    Return True if this event must be shown in roster, else False
    """
    if event == 'gc_message_received':
        return True
    if event == 'message_received':
        if session and session.control:
            return False
    return True

def get_show_in_systray(event, account, contact, type_=None):
    """
    Return True if this event must be shown in systray, else False
    """
    if type_ == 'printed_gc_msg' and not app.config.get(
    'notify_on_all_muc_messages') and not app.config.get_per('rooms',
    contact.jid, 'notify_on_all_messages'):
        # it's not an highlighted message, don't show in systray
        return False
    return app.config.get('trayicon_notification_on_events')

def popup(event_type, jid, account, msg_type='', path_to_image=None, title=None,
text=None):
    """
    Notify the user of an event using GNotification and GApplication.
    """
    # TODO: Remove unused arguments.

    # default image
    if not path_to_image:
        path_to_image = gtkgui_helpers.get_icon_path('gajim-chat_msg_recv', 48)

    # TODO: Move to standard GTK+ icons here.
    icon = Gio.FileIcon.new(Gio.File.new_for_path(path_to_image))

    notification = Gio.Notification()
    if title is not None:
        notification.set_title(title)
    if text is not None:
        notification.set_body(text)
    notification.set_icon(icon)

    # TODO: Modify the API to allow setting that.
    #notification.set_priority(Gio.NotificationPriority.NORMAL)
    #notification.set_urgent(False)

    app.app.send_notification(msg_type, notification)
