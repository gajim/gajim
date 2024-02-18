# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Literal
from typing import overload

import sys

from gi.repository import GLib
from gi.repository import Gtk
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common import events
from gajim.common.const import AvatarSize
from gajim.common.helpers import open_uri
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import ResourceContact

from gajim.gtk import structs
from gajim.gtk.activity_list import ActivityListRow
from gajim.gtk.activity_list import ActivityRowType
from gajim.gtk.activity_list import GajimPluginUpdateFinishedRow
from gajim.gtk.activity_list import GajimPluginUpdateRow
from gajim.gtk.activity_list import GajimUpdatePermissionRow
from gajim.gtk.activity_list import GajimUpdateRow
from gajim.gtk.activity_list import MucInvitationDeclinedRow
from gajim.gtk.activity_list import MucInvitationReceivedRow
from gajim.gtk.activity_list import SubscribeRow
from gajim.gtk.activity_list import UnsubscribedRow
from gajim.gtk.builder import get_builder
from gajim.gtk.groupchat_invitation import GroupChatInvitation
from gajim.gtk.menus import get_subscription_menu


class ActivityPage(Gtk.Stack):
    def __init__(self) -> None:
        Gtk.Stack.__init__(self)
        self.get_style_context().add_class('activity-page')

        self.set_hexpand(True)

        self.add_named(DefaultPage(), 'default')
        self.add_named(UpdatePage(), 'gajim-update')
        self.add_named(SubscriptionPage(), 'subscription')
        self.add_named(InvitationPage(), 'muc-invitation')

    @overload
    def get_page(self, name: Literal['default']) -> DefaultPage: ...

    @overload
    def get_page(self, name: Literal['gajim-update']) -> UpdatePage: ...

    @overload
    def get_page(self, name: Literal['subscription']) -> SubscriptionPage: ...

    @overload
    def get_page(self, name: Literal['muc-invitation']) -> InvitationPage: ...

    def get_page(self, name: str) -> Gtk.Widget | None:
        return self.get_child_by_name(name)

    def show_page(self, name: str) -> None:
        self.set_visible_child_name(name)

    def process_row_activated(self, row: ActivityListRow) -> None:
        if row.type == ActivityRowType.GAJIM_UPDATE:
            page = self.get_page('gajim-update')
        elif row.type == ActivityRowType.SUBSCRIPTION:
            page = self.get_page('subscription')
        elif row.type == ActivityRowType.MUC_INVITATION:
            page = self.get_page('muc-invitation')
        else:
            raise ValueError('Invalid row type: %s', row.type)

        page.update_content(row)
        self.set_visible_child(page)


class BaseActivityPage(Gtk.Box):
    def __init__(self) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._ui = get_builder('activity_page.ui')

    def update_content(self, row: ActivityListRow) -> None:
        pass


class DefaultPage(BaseActivityPage):
    def __init__(self) -> None:
        BaseActivityPage.__init__(self)
        self.add(self._ui.default_page)


class UpdatePage(BaseActivityPage):
    def __init__(self) -> None:
        BaseActivityPage.__init__(self)
        self.add(self._ui.gajim_update_page)

        self._row = None

    def update_content(self, row: ActivityListRow) -> None:
        self._row = row

        for child in self._ui.update_actions_box.get_children():
            child.destroy()

        assert isinstance(
            row,
            GajimUpdatePermissionRow
            | GajimUpdateRow
            | GajimPluginUpdateRow
            | GajimPluginUpdateFinishedRow,
        )
        self._ui.update_title_label.set_text(row.get_title_text())
        icon_name = 'software-update-available-symbolic'

        if isinstance(row, GajimUpdatePermissionRow):
            self._ui.update_text_label.set_text(
                _('Search for Gajim updates periodically?')
            )
            icon_name = 'dialog-question-symbolic'
            self._ui.update_image.set_from_icon_name(
                'dialog-question-symbolic', Gtk.IconSize.DIALOG
            )
            button = Gtk.Button.new_with_label(_('Activate'))
            button.get_style_context().add_class('suggested-action')
            button.connect('clicked', self._on_enable_update_check_button_clicked)
            self._ui.update_actions_box.add(button)

        if isinstance(row, GajimUpdateRow):
            self._ui.update_text_label.set_text(row.get_subject_text())

            button = Gtk.Button.new_with_label(_('Download'))
            button.get_style_context().add_class('suggested-action')
            button.connect('clicked', self._on_download_update_clicked)
            self._ui.update_actions_box.add(button)

        if isinstance(row, GajimPluginUpdateRow):
            self._ui.update_text_label.set_text(row.get_subject_text())

            checkbox = Gtk.CheckButton.new_with_label(_('Update plugins automatically'))
            checkbox.set_active(True)
            checkbox.set_name('auto_update_plugins')

            update_button = Gtk.Button.new_with_label(_('Update'))
            update_button.get_style_context().add_class('suggested-action')
            update_button.connect('clicked', self._on_update_plugins_clicked)

            show_button = Gtk.Button.new_with_label(_('Show Plugins'))
            show_button.connect('clicked', self._on_open_plugins)

            button_box = Gtk.Box(spacing=12)
            button_box.add(update_button)
            button_box.add(show_button)

            action_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=18,
                halign=Gtk.Align.CENTER,
            )
            action_box.add(checkbox)
            action_box.add(button_box)

            self._ui.update_actions_box.add(action_box)

        if isinstance(row, GajimPluginUpdateFinishedRow):
            self._ui.update_text_label.set_text(row.get_subject_text())
            icon_name = 'feather-check-symbolic'

            show_button = Gtk.Button.new_with_label(_('Show Plugins'))
            show_button.connect('clicked', self._on_open_plugins)
            self._ui.update_actions_box.add(show_button)

        self._ui.update_image.set_from_icon_name(icon_name, Gtk.IconSize.DIALOG)
        self._ui.update_actions_box.show_all()

    def _on_enable_update_check_button_clicked(self, _button: Gtk.Button) -> None:
        assert self._row is not None
        app.app.check_for_gajim_updates()
        self._row.destroy()

    def _on_download_update_clicked(self, _button: Gtk.Button) -> None:
        assert isinstance(self._row, GajimUpdateRow)
        if sys.platform == 'win32':
            open_uri(self._row.new_setup_url)
        else:
            open_uri('https://gajim.org/download/')
        self._row.destroy()

    def _on_update_plugins_clicked(self, _button: Gtk.Button) -> None:
        assert isinstance(self._row, GajimPluginUpdateRow)
        for child in self._ui.update_actions_box.get_children():
            if child.get_name() == 'auto_update_plugins':
                assert isinstance(child, Gtk.CheckButton)
                if child.get_active():
                    app.settings.set('plugins_auto_update', True)

        app.plugin_repository.download_plugins(self._row.plugin_manifests)
        self._row.destroy()

    def _on_open_plugins(self, _button: Gtk.Button) -> None:
        assert self._row is not None
        app.app.activate_action('plugins', None)
        self._row.destroy()


class SubscriptionPage(BaseActivityPage):
    def __init__(self) -> None:
        BaseActivityPage.__init__(self)

        self.add(self._ui.subscription_page)
        self._row = None

    def update_content(self, row: ActivityListRow) -> None:
        self._row = row

        for child in self._ui.subscription_actions_box.get_children():
            child.destroy()

        assert isinstance(row, SubscribeRow | UnsubscribedRow)
        self._ui.subscription_title_label.set_text(row.get_title_text())
        self._ui.subscription_text_label.set_text(row.get_subject_text())

        event = row.get_event()

        client = app.get_client(event.account)
        contact = client.get_module('Contacts').get_contact(event.jid)
        assert isinstance(contact, BareContact)

        self._ui.subscription_image.set_from_surface(
            contact.get_avatar(
                AvatarSize.ACTIVITY_PAGE, self.get_scale_factor(), add_show=False
            )
        )

        if isinstance(row, SubscribeRow):
            assert isinstance(event, events.SubscribePresenceReceived)

            jid = JID.from_string(event.jid)

            accept_param = structs.SubscriptionAcceptParam(
                account=event.account, jid=jid, nickname=event.user_nick
            )
            accept_button = Gtk.Button(
                label=_('Accept'),
                action_name=f'app.{event.account}-subscription-accept',
                action_target=accept_param.to_variant(),
            )
            accept_button.get_style_context().add_class('suggested-action')
            self._ui.subscription_actions_box.add(accept_button)

            deny_param = structs.AccountJidParam(account=event.account, jid=jid)
            deny_button = Gtk.Button(
                label=_('Deny'),
                action_name=f'app.{event.account}-subscription-deny',
                action_target=deny_param.to_variant(),
            )
            self._ui.subscription_actions_box.add(deny_button)

            menu_image = Gtk.Image.new_from_icon_name(
                'view-more-symbolic', Gtk.IconSize.MENU
            )
            menu_button = Gtk.MenuButton()
            menu_button.add(menu_image)
            subscription_menu = get_subscription_menu(event.account, jid)
            menu_button.set_menu_model(subscription_menu)
            self._ui.subscription_actions_box.add(menu_button)

        if isinstance(row, UnsubscribedRow):
            assert isinstance(event, events.UnsubscribedPresenceReceived)

            remove_button = Gtk.Button(
                label=_('Remove Contact'),
                action_name=f'win.{event.account}-remove-contact',
                action_target=GLib.Variant('s', str(event.jid)),
            )
            remove_button.get_style_context().add_class('suggested-action')
            self._ui.subscription_actions_box.add(remove_button)

            dismiss_button = Gtk.Button(
                label=_('Dismiss'),
            )
            dismiss_button.connect('clicked', self._on_dismiss_clicked)
            self._ui.subscription_actions_box.add(dismiss_button)

        self._ui.subscription_actions_box.show_all()

    def _on_dismiss_clicked(self, _button: Gtk.Button) -> None:
        assert isinstance(self._row, UnsubscribedRow)
        self._row.destroy()


class InvitationPage(BaseActivityPage):
    def __init__(self) -> None:
        BaseActivityPage.__init__(self)

        self.add(self._ui.muc_invitation_page)
        self._row = None

    def update_content(self, row: ActivityListRow) -> None:
        self._row = row

        for child in self._ui.invitation_actions_box.get_children():
            child.destroy()

        if isinstance(row, MucInvitationReceivedRow):
            event = row.get_event()
            invitation_widget = GroupChatInvitation(event.account, event)

            # We don't need to connect to 'accepted', since the muc joined signal
            # will remove the MucInvitationReceivedRow
            invitation_widget.connect('declined', self._on_invitation_widget_declined)
            self._ui.invitation_actions_box.add(invitation_widget)

        if isinstance(row, MucInvitationDeclinedRow):
            self._ui.invitation_title_label.set_text(row.get_title_text())
            self._ui.invitation_text_label.set_text(row.get_subject_text())

            event = row.get_event()
            client = app.get_client(event.account)
            contact = client.get_module('Contacts').get_contact(event.from_.bare)
            assert not isinstance(contact, ResourceContact)

            surface = contact.get_avatar(
                AvatarSize.ACCOUNT_PAGE, self.get_scale_factor()
            )
            self._ui.invitation_image.set_from_surface(surface)
            self._ui.invitation_declined_box.show()

        self._ui.invitation_actions_box.show_all()

    def _on_invitation_widget_declined(self, _widget: GroupChatInvitation) -> None:
        assert isinstance(self._row, MucInvitationReceivedRow)
        self._row.destroy()
