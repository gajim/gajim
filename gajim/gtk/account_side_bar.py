# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common import ged
from gajim.common.client import Client
from gajim.common.const import AvatarSize
from gajim.common.events import AccountDisabled
from gajim.common.events import AccountEnabled
from gajim.common.events import ShowChanged
from gajim.common.helpers import get_uf_show
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact

from gajim.gtk.avatar import get_show_circle
from gajim.gtk.util import EventHelper
from gajim.gtk.util import GajimPopover


class AccountSideBar(Gtk.EventBox):
    def __init__(self) -> None:
        Gtk.EventBox.__init__(self)
        self.get_style_context().add_class('account-sidebar')

        self.connect('button-press-event', self._on_button_press)
        self.connect('enter-notify-event', self._on_hover)
        self.connect('leave-notify-event', self._on_hover)

        container = Gtk.Box()
        self.add(container)

        self._selection_bar = Gtk.Box(
            width_request=6,
            margin_start=1
        )
        self._selection_bar.get_style_context().add_class('selection-bar')
        container.add(self._selection_bar)

        self._account_avatar = AccountAvatar()
        container.add(self._account_avatar)

        self.show_all()

    def select(self) -> None:
        self._selection_bar.get_style_context().add_class('selection-bar-selected')

    def unselect(self) -> None:
        self._selection_bar.get_style_context().remove_class('selection-bar-selected')

    def _on_hover(self,
                  _widget: AccountSideBar,
                  event: Gdk.EventCrossing
                  ) -> bool:

        style_context = self._selection_bar.get_style_context()
        if event.type == Gdk.EventType.ENTER_NOTIFY:
            style_context.add_class('selection-bar-hover')
        else:
            style_context.remove_class('selection-bar-hover')
        return True

    def _on_button_press(self,
                         _widget: AccountSideBar,
                         event: Gdk.EventButton
                         ) -> bool:

        accounts = app.settings.get_active_accounts()

        if event.button == Gdk.BUTTON_PRIMARY:
            # Left click
            # Show current account's page if only one account is active
            # If more than one account is active, a popover containing
            # all accounts is shown (clicking one opens the account's page)
            if len(accounts) == 1:
                app.window.show_account_page(accounts[0])
                return True

            self._display_accounts_menu(event)

        elif event.button == Gdk.BUTTON_SECONDARY:
            # Right click
            # Show account context menu containing account status selector
            # Global status selector if multiple accounts are active
            self._display_status_selector(event)

        return True

    def _display_accounts_menu(self, event: Gdk.EventButton):
        popover_scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            propagate_natural_height=True
        )

        popover = GajimPopover(relative_to=self, event=event)
        popover.add(popover_scrolled)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        box.get_style_context().add_class('margin-3')
        popover_scrolled.add(box)

        for account in app.settings.get_active_accounts():
            account_color_bar = Gtk.Box(
                width_request=6
            )
            color_class = app.css_config.get_dynamic_class(account)
            style_context = account_color_bar.get_style_context()
            style_context.add_class('account-identifier-bar')
            style_context.add_class(color_class)

            avatar = Gtk.Image()
            label = Gtk.Label(
                halign=Gtk.Align.START,
                label=app.settings.get_account_setting(account, 'account_label')
            )

            surface = app.app.avatar_storage.get_account_button_surface(
                account,
                AvatarSize.ACCOUNT_SIDE_BAR,
                self.get_scale_factor())
            avatar.set_from_surface(surface)

            account_box = Gtk.Box(spacing=6)
            account_box.add(account_color_bar)
            account_box.add(avatar)
            account_box.add(label)

            button = Gtk.Button(relief=Gtk.ReliefStyle.NONE)
            button.add(account_box)
            button.connect(
                'clicked',
                self._on_account_clicked,
                account,
                popover)
            box.add(button)

        popover.show_all()
        popover.popup()

    def _on_account_clicked(self,
                            _button: Gtk.MenuButton,
                            account: str,
                            popover: Gtk.Popover) -> None:

        popover.popdown()
        app.window.show_account_page(account)

    def _display_status_selector(self, event: Gdk.EventButton) -> None:
        accounts = app.settings.get_active_accounts()
        account = accounts[0] if len(accounts) == 1 else None

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        box.get_style_context().add_class('margin-3')

        popover = GajimPopover(relative_to=self, event=event)
        popover.add(box)

        popover_items = [
            'online',
            'away',
            'xa',
            'dnd',
            'separator',
            'offline',
        ]

        for item in popover_items:
            if item == 'separator':
                box.add(Gtk.Separator())
                continue

            show_icon = Gtk.Image()
            show_label = Gtk.Label(halign=Gtk.Align.START)

            surface = get_show_circle(
                item, AvatarSize.SHOW_CIRCLE, self.get_scale_factor())
            show_icon.set_from_surface(surface)
            show_label.set_text_with_mnemonic(
                get_uf_show(item, use_mnemonic=True))

            show_box = Gtk.Box(spacing=6)
            show_box.add(show_icon)
            show_box.add(show_label)

            button = Gtk.Button(
                relief=Gtk.ReliefStyle.NONE
            )
            button.add(show_box)
            button.connect(
                'clicked',
                self._on_change_status,
                item,
                account,
                popover
            )
            box.add(button)

        popover.show_all()
        popover.popup()

    def _on_change_status(self,
                          _button: Gtk.Button,
                          item: str,
                          account: str | None,
                          popover: Gtk.Popover
                          ) -> None:

        popover.popdown()
        app.app.change_status(status=item, account=account)


class AccountAvatar(Gtk.Image, EventHelper):
    def __init__(self) -> None:
        Gtk.Image.__init__(self)
        EventHelper.__init__(self)

        self._client: Client | None = None
        self._contact: BareContact | None = None

        self.register_event('account-enabled',
                            ged.GUI1,
                            self._on_account_changed)
        self.register_event('account-disabled',
                            ged.GUI1,
                            self._on_account_changed)
        self.register_event('our-show', ged.GUI1, self._on_our_show)

        self._update_image()

    def _on_account_changed(self,
                            _event: AccountEnabled | AccountDisabled
                            ) -> None:

        if self._client is not None:
            self._client.disconnect_all_from_obj(self)
        if self._contact is not None:
            self._contact.disconnect_all_from_obj(self)

        accounts = app.settings.get_active_accounts()

        if len(accounts) == 1:
            account = accounts[0]
            self._client = app.get_client(account)
            self._client.connect_signal('state-changed', self._on_event)

            jid = app.get_jid_from_account(account)
            contact = self._client.get_module('Contacts').get_contact(jid)
            assert isinstance(contact, BareContact)
            self._contact = contact
            self._contact.connect('avatar-update', self._on_event)
            self._contact.connect('presence-update', self._on_event)

        self._update_image()

    def _on_our_show(self, _event: ShowChanged) -> None:
        self._update_image()

    def _on_event(self, *args: Any) -> None:
        self._update_image()

    def _update_image(self) -> None:
        accounts = app.settings.get_active_accounts()

        if len(accounts) == 1:
            account = accounts[0]
            account_label = app.settings.get_account_setting(
                account, 'account_label')
            self.set_tooltip_text(_('Account: %s') % account_label)
        else:
            account = None
            self.set_tooltip_text(_('Accounts'))

        surface = app.app.avatar_storage.get_account_button_surface(
            account,
            AvatarSize.ACCOUNT_SIDE_BAR,
            self.get_scale_factor())
        self.set_from_surface(surface)
