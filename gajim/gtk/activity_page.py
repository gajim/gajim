# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import sys

from gi.repository import GLib
from gi.repository import Gtk
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import ResourceContact
from gajim.common.util.uri import open_uri

from gajim.gtk import structs
from gajim.gtk.activity_list import ActivityListItemT
from gajim.gtk.activity_list import GajimPluginUpdate
from gajim.gtk.activity_list import GajimPluginUpdateFinished
from gajim.gtk.activity_list import GajimUpdate
from gajim.gtk.activity_list import GajimUpdatePermission
from gajim.gtk.activity_list import MucInvitation
from gajim.gtk.activity_list import MucInvitationDeclined
from gajim.gtk.activity_list import Subscribe
from gajim.gtk.activity_list import Unsubscribed
from gajim.gtk.builder import get_builder
from gajim.gtk.groupchat_invitation import GroupChatInvitation
from gajim.gtk.menus import get_subscription_menu
from gajim.gtk.util.classes import SignalManager


class ActivityPage(Gtk.Stack):
    def __init__(self) -> None:
        Gtk.Stack.__init__(self, hexpand=True)
        self.add_css_class("activity-page")
        self.add_named(DefaultPage(), "default")

        self._pages = {
            GajimUpdate: GajimUpdatePage,
            GajimPluginUpdate: GajimPluginUpdatePage,
            GajimUpdatePermission: GajimUpdatePermissionPage,
            GajimPluginUpdateFinished: GajimPluginUpdateFinishedPage,
            Subscribe: SubscribePage,
            Unsubscribed: UnsubscribedPage,
            MucInvitation: InvitationPage,
            MucInvitationDeclined: InvitationDeclinedPage,
        }

    def show_default_page(self) -> None:
        self.set_visible_child_name("default")

    def process_row_activated(self, item: ActivityListItemT) -> None:
        child = self.get_child_by_name("activity")
        if child is not None:
            self.remove(child)

        page = self._pages[type(item)](item)  # pyright: ignore

        self.add_named(page, "activity")
        self.set_visible_child_name("activity")


class BaseActivityPage(Gtk.Box, SignalManager):
    def __init__(self) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=6)
        SignalManager.__init__(self)
        self._ui = None

    def do_unroot(self) -> None:
        self._disconnect_all()
        Gtk.Box.do_unroot(self)
        del self._ui
        app.check_finalize(self)


class DefaultPage(BaseActivityPage):
    def __init__(self) -> None:
        BaseActivityPage.__init__(self)
        self._ui = get_builder("activity_default.ui")
        self.append(self._ui.default_page)


class GajimUpdatePermissionPage(BaseActivityPage):
    def __init__(self, item: GajimUpdatePermission) -> None:
        BaseActivityPage.__init__(self)
        self._ui = get_builder("activity_gajim_update.ui")

        self._ui.update_permission_box.set_visible(True)
        self._ui.update_permission_title_label.set_text(item.title)
        self._ui.update_permission_enable_button.set_sensitive(
            item.state.get("state") != "completed"
        )
        self._connect(
            self._ui.update_permission_enable_button,
            "clicked",
            self._on_enable_update_clicked,
            item,
        )
        self.append(self._ui.gajim_update_page)

    def _on_enable_update_clicked(
        self, _button: Gtk.Button, item: GajimUpdatePermission
    ) -> None:
        app.settings.set("check_for_update", True)
        app.app.check_for_gajim_updates()
        item.state["state"] = "completed"
        self._ui.update_permission_enable_button.set_sensitive(False)


class GajimUpdatePage(BaseActivityPage):
    def __init__(self, item: GajimUpdate) -> None:
        BaseActivityPage.__init__(self)
        self._ui = get_builder("activity_gajim_update.ui")

        self._ui.update_gajim_box.set_visible(True)
        self._ui.update_gajim_title_label.set_text(item.title)
        self._ui.update_gajim_text_label.set_text(item.subject)
        self._connect(
            self._ui.update_gajim_button,
            "clicked",
            self._on_download_update_clicked,
            item,
        )
        self.append(self._ui.gajim_update_page)

    def _on_download_update_clicked(
        self, _button: Gtk.Button, item: GajimUpdate
    ) -> None:
        if sys.platform == "win32":
            event = item.get_event()
            open_uri(event.setup_url)
        else:
            open_uri("https://gajim.org/download/")


class GajimPluginUpdatePage(BaseActivityPage):
    def __init__(self, item: GajimPluginUpdate) -> None:
        BaseActivityPage.__init__(self)
        self._ui = get_builder("activity_gajim_update.ui")

        self._ui.update_plugins_box.set_visible(True)
        self._ui.update_plugins_title_label.set_text(item.title)
        self._ui.update_plugins_text_label.set_text(item.subject)
        self._connect(
            self._ui.update_plugins_show_button,
            "clicked",
            self._on_open_plugins,
            item,
        )

        self._ui.update_plugins_button.set_sensitive(
            item.state.get("state") != "completed"
        )
        self._connect(
            self._ui.update_plugins_button,
            "clicked",
            self._on_update_plugins_clicked,
            item,
        )
        self.append(self._ui.gajim_update_page)

    def _on_update_plugins_clicked(
        self, _button: Gtk.Button, item: GajimPluginUpdate
    ) -> None:
        app.settings.set(
            "plugins_auto_update",
            self._ui.update_plugins_automatically_checkbox.get_active(),
        )

        event = item.get_event()
        app.plugin_repository.download_plugins(event.manifests)

        item.state["state"] = "completed"
        self._ui.update_plugins_button.set_sensitive(False)

    def _on_open_plugins(self, _button: Gtk.Button, item: GajimPluginUpdate) -> None:
        app.app.activate_action("plugins", None)


class GajimPluginUpdateFinishedPage(BaseActivityPage):
    def __init__(self, item: GajimPluginUpdateFinished) -> None:
        BaseActivityPage.__init__(self)
        self._ui = get_builder("activity_gajim_update.ui")

        self._ui.update_plugins_success_box.set_visible(True)
        self._ui.update_plugins_success_title_label.set_text(item.title)
        self._ui.update_plugins_success_text_label.set_text(item.subject)
        self._connect(
            self._ui.update_plugins_success_button,
            "clicked",
            self._on_open_plugins,
            item,
        )
        self.append(self._ui.gajim_update_page)

    def _on_open_plugins(
        self, _button: Gtk.Button, item: GajimPluginUpdateFinished
    ) -> None:
        app.app.activate_action("plugins", None)


class SubscribePage(BaseActivityPage):
    def __init__(self, item: Subscribe) -> None:
        BaseActivityPage.__init__(self)
        self._ui = get_builder("activity_subscription.ui")

        self._ui.subscription_title_label.set_text(item.title)
        self._ui.subscription_text_label.set_text(item.subject)

        event = item.get_event()

        client = app.get_client(event.account)
        contact = client.get_module("Contacts").get_contact(event.jid)
        assert isinstance(contact, BareContact)

        self._ui.subscription_image.set_from_paintable(
            contact.get_avatar(
                AvatarSize.ACTIVITY_PAGE, self.get_scale_factor(), add_show=False
            )
        )

        self._ui.subscribe_box.set_sensitive(item.state.get("state") != "completed")
        self._ui.subscribe_box.set_visible(True)

        jid = JID.from_string(event.jid)

        deny_param = structs.AccountJidParam(account=event.account, jid=jid)
        self._ui.subscribe_deny_button.set_action_target_value(deny_param.to_variant())
        self._ui.subscribe_deny_button.set_action_name(
            f"app.{event.account}-subscription-deny"
        )
        self._connect(self._ui.subscribe_deny_button, "clicked", self._on_click, item)

        accept_param = structs.SubscriptionAcceptParam(
            account=event.account, jid=jid, nickname=event.user_nick
        )
        self._ui.subscribe_accept_button.set_action_target_value(
            accept_param.to_variant()
        )
        self._ui.subscribe_accept_button.set_action_name(
            f"app.{event.account}-subscription-accept"
        )
        self._connect(self._ui.subscribe_deny_button, "clicked", self._on_click, item)

        self._ui.subscribe_menu_button.set_menu_model(
            get_subscription_menu(event.account, jid)
        )

        self.append(self._ui.subscription_page)

    def _on_click(self, button: Gtk.Button, item: Subscribe) -> None:
        item.state["state"] = "completed"
        self._ui.subscribe_box.set_sensitive(False)


class UnsubscribedPage(BaseActivityPage):
    def __init__(self, item: Unsubscribed) -> None:
        BaseActivityPage.__init__(self)
        self._ui = get_builder("activity_subscription.ui")

        self._ui.subscription_title_label.set_text(item.title)
        self._ui.subscription_text_label.set_text(item.subject)

        event = item.get_event()

        client = app.get_client(event.account)
        contact = client.get_module("Contacts").get_contact(event.jid)
        assert isinstance(contact, BareContact)

        self._ui.subscription_image.set_from_paintable(
            contact.get_avatar(
                AvatarSize.ACTIVITY_PAGE, self.get_scale_factor(), add_show=False
            )
        )

        self._ui.unsubscribed_box.set_sensitive(item.state.get("state") != "completed")
        self._ui.unsubscribed_box.set_visible(True)
        self._ui.unsubscribed_remove_button.set_action_target_value(
            GLib.Variant("as", [event.account, str(event.jid)])
        )
        self._ui.unsubscribed_remove_button.set_action_name(
            f"app.{event.account}-remove-contact"
        )
        self._connect(
            self._ui.unsubscribed_remove_button, "clicked", self._on_clicked, item
        )

        self.append(self._ui.subscription_page)

    def _on_clicked(self, _button: Gtk.Button, item: Unsubscribed) -> None:
        item.state["state"] = "completed"
        self._ui.unsubscribed_box.set_sensitive(False)


class InvitationPage(BaseActivityPage):
    def __init__(self, item: MucInvitation) -> None:
        BaseActivityPage.__init__(self)
        self._ui = get_builder("activity_muc_invitation.ui")

        self._ui.muc_invitation_box.set_visible(True)
        event = item.get_event()
        invitation_widget = GroupChatInvitation(event.account, event)

        if item.state.get("state") == "completed":
            invitation_widget.disable_buttons()
        else:
            self._connect(invitation_widget, "declined", self._on_clicked, item)
            self._connect(invitation_widget, "accepted", self._on_clicked, item)

        self._ui.muc_invitation_box.append(invitation_widget)
        self.append(self._ui.muc_invitation_page)

    def _on_clicked(
        self, invitation_widget: GroupChatInvitation, item: MucInvitation
    ) -> None:
        item.state["state"] = "completed"
        invitation_widget.disable_buttons()


class InvitationDeclinedPage(BaseActivityPage):
    def __init__(self, item: MucInvitationDeclined) -> None:
        BaseActivityPage.__init__(self)
        self._ui = get_builder("activity_muc_invitation.ui")

        self._ui.muc_invitation_declined_box.set_visible(True)
        self._ui.invitation_title_label.set_text(item.title)
        self._ui.invitation_text_label.set_text(item.subject)

        event = item.get_event()
        client = app.get_client(event.account)
        contact = client.get_module("Contacts").get_contact(event.from_.bare)
        assert not isinstance(contact, ResourceContact)

        texture = contact.get_avatar(AvatarSize.ACCOUNT_PAGE, self.get_scale_factor())
        self._ui.invitation_image.set_from_paintable(texture)
        self.append(self._ui.muc_invitation_page)
