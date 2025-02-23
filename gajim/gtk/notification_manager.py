# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast

from collections.abc import Callable

from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango
from nbxmpp import JID

from gajim.common import app
from gajim.common import types
from gajim.common.const import AvatarSize
from gajim.common.const import SimpleClientState
from gajim.common.events import MucDecline
from gajim.common.events import MucInvitation
from gajim.common.events import Notification
from gajim.common.events import SubscribePresenceReceived
from gajim.common.events import UnsubscribedPresenceReceived
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.util.muc import get_groupchat_name

from gajim.gtk.menus import get_subscription_menu
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import get_listbox_row_count
from gajim.gtk.util.misc import iterate_listbox_children
from gajim.gtk.util.window import open_window

NotificationActionListT = list[
    tuple[str, Callable[[Gio.SimpleAction, GLib.Variant], Any], str | None]
]


class NotificationManager(Gtk.ListBox, SignalManager):
    def __init__(self, account: str) -> None:
        Gtk.ListBox.__init__(self)
        SignalManager.__init__(self)

        self._account = account
        self._client = app.get_client(account)
        self._client.connect_signal("state-changed", self._on_client_state_changed)

        self.set_selection_mode(Gtk.SelectionMode.NONE)
        self.set_halign(Gtk.Align.CENTER)
        self.add_css_class("notification-listbox")

        label = Gtk.Label(label=_("No Notifications"))
        label.set_valign(Gtk.Align.START)
        label.add_css_class("dim-label")
        self.set_placeholder(label)

        self._add_actions()

    def do_unroot(self) -> None:
        self._disconnect_all()
        self._remove_actions()
        self._client.disconnect_all_from_obj(self)
        Gtk.ListBox.do_unroot(self)
        app.check_finalize(self)

    def _on_client_state_changed(
        self, _client: types.Client, _signal_name: str, _state: SimpleClientState
    ) -> None:
        self.update_actions()

    def _add_actions(self) -> None:
        actions: NotificationActionListT = [
            ("subscription-accept", self._on_subscription_accept, "as"),
            ("subscription-deny", self._on_subscription_deny, "s"),
            ("subscription-deny-all", self._on_subscription_deny_all, None),
            ("subscription-block", self._on_subscription_block, "s"),
            ("subscription-report", self._on_subscription_report, "s"),
        ]
        for action in actions:
            action_name, func, typ = action
            if typ is not None:
                typ = GLib.VariantType.new(typ)
            act = Gio.SimpleAction.new(f"{action_name}-{self._account}", typ)
            self._connect(act, "activate", func)
            app.window.add_action(act)

    def update_actions(self) -> None:
        online = app.account_is_connected(self._account)
        blocking_support = self._client.get_module("Blocking").supported

        sub_accept = app.window.get_action(f"subscription-accept-{self._account}")
        sub_accept.set_enabled(online)

        sub_deny = app.window.get_action(f"subscription-deny-{self._account}")
        sub_deny.set_enabled(online)

        sub_deny_all = app.window.get_action(f"subscription-deny-all-{self._account}")
        sub_deny_all.set_enabled(online)

        sub_block = app.window.get_action(f"subscription-block-{self._account}")
        sub_block.set_enabled(online and blocking_support)

        sub_report = app.window.get_action(f"subscription-report-{self._account}")
        sub_report.set_enabled(online and blocking_support)

    def _remove_actions(self) -> None:
        actions = [
            "subscription-accept",
            "subscription-deny",
            "subscription-deny-all",
            "subscription-block",
            "subscription-report",
        ]
        for action in actions:
            app.window.remove_action(f"{action}-{self._account}")

    def update_unread_count(self):
        count = get_listbox_row_count(self)
        app.window.update_account_unread_count(self._account, count)

    def remove_row(self, row: NotificationRow) -> None:
        self.remove(row)
        self.update_unread_count()

    def _on_subscription_accept(
        self, _action: Gio.SimpleAction, param: GLib.Variant
    ) -> None:
        jid, nickname = param.get_strv()
        row = self._get_notification_row(jid)
        self._client.get_module("Presence").subscribed(jid)
        jid = JID.from_string(jid)
        contact = self._client.get_module("Contacts").get_contact(jid)
        assert isinstance(contact, BareContact)
        if not contact.is_in_roster:
            open_window(
                "AddContact",
                account=self._account,
                jid=jid,
                nick=nickname or contact.name,
            )
        if row is not None:
            self.remove(row)
            self.update_unread_count()

    def _on_subscription_block(
        self, _action: Gio.SimpleAction, param: GLib.Variant
    ) -> None:
        jid = param.get_string()
        self._deny_request(jid)
        self._client.get_module("Blocking").block([jid])
        row = self._get_notification_row(jid)
        if row is not None:
            self.remove(row)
            self.update_unread_count()

    def _on_subscription_report(
        self, _action: Gio.SimpleAction, param: GLib.Variant
    ) -> None:
        jid = param.get_string()
        self._deny_request(jid)
        self._client.get_module("Blocking").block([jid], report="spam")
        row = self._get_notification_row(jid)
        if row is not None:
            self.remove(row)
            self.update_unread_count()

    def _on_subscription_deny(
        self, _action: Gio.SimpleAction, param: GLib.Variant
    ) -> None:
        jid = param.get_string()
        self._deny_request(jid)
        row = self._get_notification_row(jid)
        if row is not None:
            self.remove(row)
            self.update_unread_count()

    def _on_subscription_deny_all(
        self, _action: Gio.SimpleAction, _param: GLib.Variant
    ) -> None:

        for row in cast(list[NotificationRow], iterate_listbox_children(self)):
            if row.type != "subscribe":
                continue
            self._deny_request(row.jid)
            self.remove(row)
        self.update_unread_count()

    def _deny_request(self, jid: str) -> None:
        self._client.get_module("Presence").unsubscribed(jid)

    def _get_notification_row(self, jid: str) -> NotificationRow | None:
        rows = cast(list[NotificationRow], iterate_listbox_children(self))
        for row in rows:
            if row.jid == jid:
                return row
        return None

    def add_subscription_request(self, event: SubscribePresenceReceived) -> None:
        row = self._get_notification_row(event.jid)
        if row is None:
            new_row = SubscriptionRequestRow(
                self._account, event.jid, event.status, event.user_nick
            )
            self.append(new_row)

            nick = event.user_nick
            if not nick:
                contact = self._client.get_module("Contacts").get_contact(event.jid)
                assert isinstance(contact, BareContact)
                nick = contact.name
            text = _("%s asks you to share your status") % nick

            app.ged.raise_event(
                Notification(
                    account=self._account,
                    jid=event.jid,
                    type="subscription-request",
                    title=_("Subscription Request"),
                    text=text,
                )
            )
        elif row.type == "unsubscribed":
            self.remove(row)

        self.update_unread_count()

    def add_unsubscribed(self, event: UnsubscribedPresenceReceived) -> None:
        row = self._get_notification_row(event.jid)
        if row is None:
            new_row = UnsubscribedRow(self._account, event.jid)
            self.append(new_row)
            self.update_unread_count()

            contact = self._client.get_module("Contacts").get_contact(event.jid)
            assert isinstance(contact, BareContact)
            text = _("%s stopped sharing their status") % contact.name

            app.ged.raise_event(
                Notification(
                    account=self._account,
                    jid=event.jid,
                    type="unsubscribed",
                    title=_("Contact Unsubscribed"),
                    text=text,
                )
            )
        elif row.type == "subscribe":
            self.remove(row)

        self.update_unread_count()

    def add_invitation_received(self, event: MucInvitation) -> None:
        row = self._get_notification_row(str(event.muc))
        if row is not None:
            return

        jid = event.from_.bare
        client = app.get_client(event.account)
        muc_contact = client.get_module("Contacts").get_contact(event.muc)
        assert isinstance(muc_contact, GroupchatContact)

        new_row = InvitationReceivedRow(self._account, event, muc_contact)
        self.append(new_row)
        self.update_unread_count()

        if muc_contact.muc_context == "private" and not event.muc.bare_match(
            event.from_
        ):
            contact = self._client.get_module("Contacts").get_contact(jid)
            assert isinstance(contact, BareContact)
            text = _("%(contact)s invited you to %(chat)s") % {
                "contact": contact.name,
                "chat": event.info.muc_name,
            }
        else:
            text = _("You have been invited to %s") % event.info.muc_name

        app.ged.raise_event(
            Notification(
                account=self._account,
                jid=jid,
                type="group-chat-invitation",
                title=_("Group Chat Invitation"),
                text=text,
            )
        )

    def add_invitation_declined(self, event: MucDecline) -> None:
        row = self._get_notification_row(str(event.muc))
        if row is not None:
            return

        new_row = InvitationDeclinedRow(self._account, event)
        self.append(new_row)
        self.update_unread_count()


class NotificationRow(Gtk.ListBoxRow, SignalManager):
    def __init__(self, account: str, jid: str) -> None:
        Gtk.ListBoxRow.__init__(self)
        SignalManager.__init__(self)

        self._account = account
        self._client = app.get_client(account)
        self.jid = jid
        self.type = ""

        self.grid = Gtk.Grid(column_spacing=12)
        self.set_child(self.grid)

    def do_unroot(self) -> None:
        self._disconnect_all()
        Gtk.ListBoxRow.do_unroot(self)
        app.check_finalize(self)

    @staticmethod
    def _generate_label() -> Gtk.Label:
        label = Gtk.Label()
        label.set_halign(Gtk.Align.START)
        label.set_hexpand(True)
        label.set_xalign(0)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_max_width_chars(30)
        return label

    def _generate_avatar_image(self, jid: str | JID) -> Gtk.Image:
        contact = self._client.get_module("Contacts").get_contact(jid)
        assert isinstance(
            contact, BareContact | GroupchatContact | GroupchatParticipant
        )
        if isinstance(contact, GroupchatContact):
            texture = contact.get_avatar(AvatarSize.ROSTER, self.get_scale_factor())
        else:
            texture = contact.get_avatar(
                AvatarSize.ROSTER, self.get_scale_factor(), add_show=False
            )
        image = Gtk.Image.new_from_paintable(texture)
        image.set_valign(Gtk.Align.CENTER)
        image.set_pixel_size(AvatarSize.ROSTER)
        return image


class SubscriptionRequestRow(NotificationRow):
    def __init__(
        self, account: str, jid: str, text: str, user_nick: str | None = None
    ) -> None:
        NotificationRow.__init__(self, account, jid)
        self.type = "subscribe"

        image = self._generate_avatar_image(jid)
        self.grid.attach(image, 1, 1, 1, 2)

        if user_nick is not None:
            escaped_nick = GLib.markup_escape_text(user_nick)
            nick_markup = f"<b>{escaped_nick}</b> ({jid})"
        else:
            nick_markup = f"<b>{jid}</b>"

        nick_label = self._generate_label()
        nick_label.set_tooltip_markup(nick_markup)
        nick_label.set_markup(nick_markup)
        self.grid.attach(nick_label, 2, 1, 1, 1)

        message_text = GLib.markup_escape_text(text)
        text_label = self._generate_label()
        text_label.set_text(message_text)
        text_label.set_tooltip_text(message_text)
        text_label.add_css_class("dim-label")
        self.grid.attach(text_label, 2, 2, 1, 1)

        accept_button = Gtk.Button.new_with_label(label=_("Accept"))
        accept_button.set_valign(Gtk.Align.CENTER)
        accept_button.set_action_name(f"win.subscription-accept-{self._account}")
        accept_button.set_action_target_value(
            GLib.Variant.new_strv([self.jid, user_nick or ""])
        )
        self.grid.attach(accept_button, 3, 1, 1, 2)

        more_image = Gtk.Image.new_from_icon_name("view-more-symbolic")
        more_button = Gtk.MenuButton()
        more_button.set_valign(Gtk.Align.CENTER)
        more_button.set_child(more_image)
        subscription_menu = get_subscription_menu(
            self._account, JID.from_string(self.jid)
        )
        more_button.set_menu_model(subscription_menu)
        self.grid.attach(more_button, 4, 1, 1, 2)


class UnsubscribedRow(NotificationRow):
    def __init__(self, account: str, jid: str) -> None:
        NotificationRow.__init__(self, account, jid)
        self.type = "unsubscribed"

        image = self._generate_avatar_image(jid)
        self.grid.attach(image, 1, 1, 1, 2)

        contact = self._client.get_module("Contacts").get_contact(jid)
        assert isinstance(contact, BareContact)
        nick_markup = f"<b>{contact.name}</b>"
        nick_label = self._generate_label()
        nick_label.set_tooltip_markup(nick_markup)
        nick_label.set_markup(nick_markup)
        self.grid.attach(nick_label, 2, 1, 1, 1)

        message_text = _("Stopped sharing their status with you")
        text_label = self._generate_label()
        text_label.set_text(message_text)
        text_label.set_tooltip_text(message_text)
        text_label.add_css_class("dim-label")
        self.grid.attach(text_label, 2, 2, 1, 1)

        remove_button = Gtk.Button.new_with_label(label=_("Remove"))
        remove_button.set_valign(Gtk.Align.CENTER)
        remove_button.set_tooltip_text(_("Remove from contact list"))
        remove_button.set_action_name(f"win.{self._account}-remove-contact")
        remove_button.set_action_target_value(
            GLib.Variant("as", [self._account, str(self.jid)])
        )
        self.grid.attach(remove_button, 3, 1, 1, 2)

        dismiss_button = Gtk.Button.new_from_icon_name("window-close-symbolic")
        dismiss_button.set_valign(Gtk.Align.CENTER)
        dismiss_button.set_tooltip_text(_("Remove Notification"))
        self._connect(dismiss_button, "clicked", self._on_dismiss)
        self.grid.attach(dismiss_button, 4, 1, 1, 2)

    def _on_dismiss(self, _button: Gtk.Button) -> None:
        listbox = cast(NotificationManager, self.get_parent())
        listbox.remove_row(self)


class InvitationReceivedRow(NotificationRow):
    def __init__(
        self, account: str, event: MucInvitation, muc_contact: GroupchatContact
    ) -> None:
        NotificationRow.__init__(self, account, str(event.muc))
        self.type = "invitation-received"

        self._muc_contact = muc_contact
        self._muc_contact.connect("room-joined", self._on_room_joined)

        self._event = event

        jid = event.from_.bare
        image = self._generate_avatar_image(jid)
        self.grid.attach(image, 1, 1, 1, 2)

        title_label = self._generate_label()
        title_label.set_text(_("Group Chat Invitation Received"))
        title_label.add_css_class("bold")
        self.grid.attach(title_label, 2, 1, 1, 1)

        if self._muc_contact.muc_context == "private" and not event.muc.bare_match(
            event.from_
        ):
            contact = self._client.get_module("Contacts").get_contact(jid)
            assert isinstance(contact, BareContact)
            invitation_text = _("%(contact)s invited you to %(chat)s") % {
                "contact": contact.name,
                "chat": event.info.muc_name,
            }
        else:
            invitation_text = _("You have been invited to %s") % event.info.muc_name
        text_label = self._generate_label()
        text_label.set_text(invitation_text)
        text_label.set_tooltip_text(invitation_text)
        text_label.add_css_class("dim-label")
        self.grid.attach(text_label, 2, 2, 1, 1)

        show_button = Gtk.Button.new_with_label(label=_("Show"))
        show_button.set_valign(Gtk.Align.CENTER)
        show_button.set_halign(Gtk.Align.END)
        show_button.set_tooltip_text(_("Show Invitation"))
        self._connect(show_button, "clicked", self._on_show_invitation)
        self.grid.attach(show_button, 3, 1, 1, 2)

        decline_button = Gtk.Button.new_with_label(label=_("Decline"))
        decline_button.set_valign(Gtk.Align.CENTER)
        decline_button.set_tooltip_text(_("Decline Invitation"))
        self._connect(decline_button, "clicked", self._on_decline_invitation)
        self.grid.attach(decline_button, 4, 1, 1, 2)

    def do_unroot(self) -> None:
        self._muc_contact.disconnect_all_from_obj(self)
        NotificationRow.do_unroot(self)

    def _on_show_invitation(self, _button: Gtk.Button) -> None:
        open_window(
            "GroupChatInvitationDialog", account=self._account, event=self._event
        )
        listbox = cast(NotificationManager, self.get_parent())
        listbox.remove_row(self)

    def _on_decline_invitation(self, _button: Gtk.Button) -> None:
        self._client.get_module("MUC").decline(self.jid, self._event.from_)
        listbox = cast(NotificationManager, self.get_parent())
        listbox.remove_row(self)

    def _on_room_joined(self, contact: GroupchatContact, signal_name: str) -> None:
        listbox = cast(NotificationManager, self.get_parent())
        listbox.remove_row(self)


class InvitationDeclinedRow(NotificationRow):
    def __init__(self, account: str, event: MucDecline) -> None:
        NotificationRow.__init__(self, account, str(event.muc))
        self.type = "invitation-declined"

        jid = event.from_.bare

        image = self._generate_avatar_image(jid)
        self.grid.attach(image, 1, 1, 1, 2)

        title_label = self._generate_label()
        title_label.set_text(_("Group Chat Invitation Declined"))
        title_label.add_css_class("bold")
        self.grid.attach(title_label, 2, 1, 1, 1)

        contact = self._client.get_module("Contacts").get_contact(jid)
        assert isinstance(contact, BareContact)
        muc_name = get_groupchat_name(self._client, event.muc)
        invitation_text = _("%(contact)s declined your invitation to %(chat)s") % {
            "contact": contact.name,
            "chat": muc_name,
        }
        text_label = self._generate_label()
        text_label.set_text(invitation_text)
        text_label.set_tooltip_text(invitation_text)
        text_label.add_css_class("dim-label")
        self.grid.attach(text_label, 2, 2, 1, 1)

        dismiss_button = Gtk.Button.new_from_icon_name("window-close-symbolic")
        dismiss_button.set_valign(Gtk.Align.CENTER)
        dismiss_button.set_halign(Gtk.Align.END)
        dismiss_button.set_tooltip_text(_("Remove Notification"))
        self._connect(dismiss_button, "clicked", self._on_dismiss)
        self.grid.attach(dismiss_button, 3, 1, 1, 2)

    def _on_dismiss(self, _button: Gtk.Button) -> None:
        listbox = cast(NotificationManager, self.get_parent())
        listbox.remove_row(self)
