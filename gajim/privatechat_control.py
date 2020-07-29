# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
#                    Alex Mauer <hawke AT hawkesnest.net>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
#                         Travis Shirk <travis AT pobox.com>
# Copyright (C) 2007-2008 Julien Pivotto <roidelapluie AT gmail.com>
#                         Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
#                    Jonathan Schleifer <js-gajim AT webkeks.org>
# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
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

from gajim.common import app
from gajim.common import helpers
from gajim.common import ged
from gajim.common.i18n import _
from gajim.common.const import AvatarSize
from gajim.common.helpers import event_filter

from gajim.chat_control import ChatControl
from gajim.command_system.implementation.hosts import PrivateChatCommands

from gajim.gtk.dialogs import ErrorDialog
from gajim.gtk.const import ControlType


class PrivateChatControl(ChatControl):

    _type = ControlType.PRIVATECHAT

    # Set a command host to bound to. Every command given through a private chat
    # will be processed with this command host.
    COMMAND_HOST = PrivateChatCommands

    def __init__(self, parent_win, gc_contact, contact, account, session):
        room_jid = gc_contact.room_jid
        self.room_ctrl = app.interface.msg_win_mgr.get_gc_control(
            room_jid, account)
        if room_jid in app.interface.minimized_controls[account]:
            self.room_ctrl = app.interface.minimized_controls[account][room_jid]

        self.gc_contact = gc_contact
        ChatControl.__init__(self, parent_win, contact, account, session)

        # pylint: disable=line-too-long
        self.register_events([
            ('update-gc-avatar', ged.GUI1, self._on_update_gc_avatar),
            ('caps-update', ged.GUI1, self._on_caps_update),
            ('muc-user-joined', ged.GUI1, self._on_user_joined),
            ('muc-user-left', ged.GUI1, self._on_user_left),
            ('muc-nickname-changed', ged.GUI1, self._on_nickname_changed),
            ('muc-self-presence', ged.GUI1, self._on_self_presence),
            ('muc-self-kicked', ged.GUI1, self._on_disconnected),
            ('muc-user-status-show-changed', ged.GUI1, self._on_status_show_changed),
            ('muc-destroyed', ged.GUI1, self._on_disconnected),
        ])
        # pylint: enable=line-too-long

    @property
    def contact(self):
        return self.gc_contact.as_contact()

    @contact.setter
    def contact(self, _value):
        # TODO: remove all code that sets the contact here
        return

    @property
    def room_name(self):
        if self.room_ctrl is not None:
            return self.room_ctrl.room_name
        return self.gc_contact.room_jid

    def get_our_nick(self):
        return self.room_ctrl.nick

    @event_filter(['account'])
    def _on_caps_update(self, event):
        if event.fjid != self.gc_contact.get_full_jid():
            return
        self.update_contact()

    @event_filter(['account'])
    def _on_nickname_changed(self, event):
        if event.properties.new_jid != self.gc_contact.get_full_jid():
            return

        nick = event.properties.muc_nickname
        new_nick = event.properties.muc_user.nick
        if event.properties.is_muc_self_presence:
            message = _('You are now known as %s') % new_nick
        else:
            message = _('{nick} is now known '
                        'as {new_nick}').format(nick=nick, new_nick=new_nick)

        self.add_info_message(message)

        self.draw_banner()
        app.interface.msg_win_mgr.change_key(str(event.properties.jid),
                                             str(event.properties.new_jid),
                                             self.account)

        self.parent_win.redraw_tab(self)
        self.update_ui()

    @event_filter(['account'])
    def _on_status_show_changed(self, event):
        if event.properties.jid != self.gc_contact.get_full_jid():
            return

        nick = event.properties.muc_nickname
        status = event.properties.status
        status = '' if status is None else ' - %s' % status
        show = helpers.get_uf_show(event.properties.show.value)

        status_default = app.settings.get('gc_print_status_default')
        if not app.config.get_per('rooms', self.gc_contact.room_jid,
                                  'print_status', status_default):
            self.parent_win.redraw_tab(self)
            self.update_ui()
            return

        if event.properties.is_muc_self_presence:
            message = _('You are now {show}{status}').format(show=show,
                                                             status=status)

        else:
            message = _('{nick} is now {show}{status}').format(nick=nick,
                                                               show=show,
                                                               status=status)
        self.add_status_message(message)
        self.parent_win.redraw_tab(self)
        self.update_ui()

    @event_filter(['account'])
    def _on_disconnected(self, event):
        if event.properties.jid != self.gc_contact.get_full_jid():
            return

        self.got_disconnected()

    @event_filter(['account'])
    def _on_user_left(self, event):
        if event.properties.jid != self.gc_contact.get_full_jid():
            return

        self.got_disconnected()

    @event_filter(['account'])
    def _on_user_joined(self, event):
        if event.properties.jid != self.gc_contact.get_full_jid():
            return

        self.gc_contact = app.contacts.get_gc_contact(
            self.account, self.gc_contact.room_jid, self.gc_contact.name)
        self.parent_win.redraw_tab(self)
        self.got_connected()

    @event_filter(['account'])
    def _on_self_presence(self, event):
        if event.properties.jid != self.gc_contact.get_full_jid():
            return

        self.parent_win.redraw_tab(self)
        self.got_connected()

    def _on_update_gc_avatar(self, event):
        if event.contact != self.gc_contact:
            return
        self.show_avatar()

    def send_message(self, message, xhtml=None, process_commands=True,
                     attention=False):
        """
        Call this method to send the message
        """
        message = helpers.remove_invalid_xml_chars(message)
        if not message:
            return

        # We need to make sure that we can still send through the room and that
        # the recipient did not go away
        if self.gc_contact.presence.is_unavailable:
            ErrorDialog(
                _('Sending private message failed'),
                #in second %s code replaces with nickname
                _('You are no longer in group chat "%(room)s" or '
                  '"%(nick)s" has left.') % {
                      'room': self.room_name, 'nick': self.gc_contact.name},
                transient_for=self.parent_win.window)
            return

        ChatControl.send_message(self, message,
                                 xhtml=xhtml,
                                 process_commands=process_commands,
                                 attention=attention)

    def update_ui(self):
        if self.gc_contact.presence.is_unavailable:
            self.got_disconnected()
        else:
            self.got_connected()

    def show_avatar(self):
        if not app.settings.get('show_avatar_in_chat'):
            return

        scale = self.parent_win.window.get_scale_factor()
        surface = self.gc_contact.get_avatar(AvatarSize.CHAT,
                                             scale,
                                             self.gc_contact.show.value)

        self.xml.avatar_image.set_from_surface(surface)

    def get_tab_image(self):
        if self.gc_contact.presence.is_unavailable:
            show = 'offline'
        else:
            show = self.gc_contact.show.value
        scale = self.parent_win.window.get_scale_factor()
        return self.gc_contact.get_avatar(AvatarSize.ROSTER,
                                          scale,
                                          show)

    def update_contact(self):
        self.contact = self.gc_contact.as_contact()

    def got_disconnected(self):
        ChatControl.got_disconnected(self)
        self.parent_win.redraw_tab(self)
        ChatControl.update_ui(self)

    def got_connected(self):
        ChatControl.got_connected(self)
        ChatControl.update_ui(self)
