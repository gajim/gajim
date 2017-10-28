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

import sys
from gajim.dialogs import PopupNotificationWindow
from gi.repository import GLib
from gi.repository import Gio
from gajim import gtkgui_helpers

from gajim.common import app
from gajim.common import helpers
from gajim.common import ged

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

def popup(event_type, jid, account, type_='', icon_name=None, title=None,
text=None, timeout=-1):
    """
    Notify a user of an event using GNotification and GApplication under linux,
    the older style PopupNotificationWindow method under windows
    """
    if timeout < 0:
        timeout = app.config.get('notification_timeout')

    if sys.platform == 'win32':
        instance = PopupNotificationWindow(event_type, jid, account, type_,
                                           icon_name, title, text, timeout)
        app.interface.roster.popup_notification_windows.append(instance)
        return

    notification = Gio.Notification()
    if title is not None:
        notification.set_title(title)
    if text is not None:
        notification.set_body(text)
    notification.set_icon(Gio.ThemedIcon(icon_name))
    notif_id = None
    if event_type in (_('Contact Signed In'), _('Contact Signed Out'),
    _('New Message'), _('New Single Message'), _('New Private Message'),
    _('Contact Changed Status'), _('File Transfer Request'),
    _('File Transfer Error'), _('File Transfer Completed'),
    _('File Transfer Stopped'), _('Groupchat Invitation'),
    _('Connection Failed'), _('Subscription request'), _('Unsubscribed')):
        # Create Variant Dict
        dict_ = {'account': GLib.Variant('s', account),
                 'jid': GLib.Variant('s', jid),
                 'type_': GLib.Variant('s', type_)}
        variant_dict = GLib.Variant('a{sv}', dict_)
        action = 'app.{}-open-event'.format(account)
        notification.add_button_with_target('Open', action, variant_dict)
        notification.set_default_action_and_target(action, variant_dict)
        if event_type in (_('New Message'), _('New Single Message'),
        _('New Private Message')):
            # Only one notification per JID
            notif_id = jid
    notification.set_priority(Gio.NotificationPriority.NORMAL)
    notification.set_urgent(False)
    app.app.send_notification(notif_id, notification)


class Notification:
    """
    Handle notifications
    """
    def __init__(self):
        app.ged.register_event_handler('notification', ged.GUI2,
            self._nec_notification)

    def _nec_notification(self, obj):
        if obj.do_popup:
            popup(obj.popup_event_type, obj.jid, obj.conn.name,
                obj.popup_msg_type, icon_name=obj.icon_name,
                title=obj.popup_title, text=obj.popup_text,
                timeout=obj.popup_timeout)

        if obj.do_sound:
            if obj.sound_file:
                helpers.play_sound_file(obj.sound_file)
            elif obj.sound_event:
                helpers.play_sound(obj.sound_event)

        if obj.do_command:
            try:
                helpers.exec_command(obj.command, use_shell=True)
            except Exception:
                pass
