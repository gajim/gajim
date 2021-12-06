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

from typing import Dict
from typing import Tuple
from typing import Optional
from typing import Generator

import logging

from gi.repository import GLib
from gi.repository import Gtk

from nbxmpp import JID

from gajim.common import app
from gajim.common import ged
from gajim.common.i18n import _

from .controls.chat import ChatControl
from .controls.groupchat import GroupchatControl
from .controls.private import PrivateChatControl

from .types import ControlType
from .util import EventHelper

log = logging.getLogger('gajim.gui.chatstack')


class ChatStack(Gtk.Stack, EventHelper):
    def __init__(self):
        Gtk.Stack.__init__(self)
        EventHelper.__init__(self)

        self.set_vexpand(True)
        self.set_hexpand(True)

        self.add_named(ChatPlaceholderBox(), 'empty')

        self.register_events([
            ('account-enabled', ged.GUI2, self._on_account_changed),
            ('account-disabled', ged.GUI2, self._on_account_changed),
        ])

        self.show_all()
        self._controls: Dict[Tuple[str, JID], ControlType] = {}
        self._active_control: Optional[ControlType] = None

    def get_control(self, account: str, jid: JID) -> Optional[ControlType]:
        try:
            return self._controls[(account, jid)]
        except KeyError:
            return None

    def get_controls(self, account: Optional[str]
                     ) -> Generator[ControlType, None, None]:
        if account is None:
            for control in self._controls.values():
                yield control
            return

        for key, control in self._controls.items():
            if key[0] == account:
                yield control

    def add_chat(self, account: str, jid: JID) -> None:
        if self._controls.get((account, jid)) is not None:
            # Control is already in the Stack
            return

        chat_control = ChatControl(account, jid)
        self._controls[(account, jid)] = chat_control
        self.add_named(chat_control.widget, f'{account}:{jid}')
        chat_control.widget.show_all()

    def add_group_chat(self, account: str, jid: JID) -> None:
        if self._controls.get((account, jid)) is not None:
            return

        control = GroupchatControl(account, jid)
        self._controls[(account, jid)] = control
        self.add_named(control.widget, f'{account}:{jid}')
        control.widget.show_all()

    def add_private_chat(self, account: str, jid: JID) -> None:
        control = PrivateChatControl(account, jid)
        self._controls[(account, jid)] = control
        self.add_named(control.widget, f'{account}:{jid}')
        control.widget.show_all()

    def remove_chat(self, account: str, jid: JID) -> None:
        control = self._controls.pop((account, jid))
        if control == self._active_control:
            self._active_control = None
        self.remove(control.widget)
        control.shutdown()

    def show_chat(self, account: str, jid: JID) -> None:
        self.set_visible_child_name(f'{account}:{jid}')
        control = self.get_control(account, jid)
        if control is None:
            log.warning('No Control found for %s, %s', account, jid)
            return
        if control != self._active_control:
            if self._active_control is not None:
                self._active_control.reset_view()
        self._active_control = control
        GLib.idle_add(control.focus)

    def clear(self) -> None:
        self.set_visible_child_name('empty')

    def process_event(self, event):
        control = self.get_control(event.account, event.jid)
        control.process_event(event)

    def remove_chats_for_account(self, account: str) -> None:
        for chat_account, jid in list(self._controls.keys()):
            if chat_account != account:
                continue
            self.remove_chat(account, jid)

    def _on_account_changed(self, *args):
        for control in self._controls.values():
            control.update_account_badge()


class ChatPlaceholderBox(Gtk.Box):
    def __init__(self):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL,
                         spacing=18)
        self.set_valign(Gtk.Align.CENTER)
        pixbuf = Gtk.IconTheme.load_icon_for_scale(
            Gtk.IconTheme.get_default(),
            'org.gajim.Gajim-symbolic',
            100,
            self.get_scale_factor(),
            0)
        image = Gtk.Image.new_from_pixbuf(pixbuf)
        image.get_style_context().add_class('dim-label')
        self.add(image)

        button = Gtk.Button(label=_('Start Chatting…'))
        button.set_halign(Gtk.Align.CENTER)
        button.connect('clicked', self._on_start_chatting)
        self.add(button)

    def _on_start_chatting(self, _button):
        app.app.activate_action('start-chat', GLib.Variant('s', ''))
