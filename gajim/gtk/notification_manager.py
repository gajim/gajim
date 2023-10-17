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
from gajim.common.helpers import get_groupchat_name
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant

from gajim.gtk.menus import get_subscription_menu
from gajim.gtk.util import open_window

NotificationActionListT = list[
    tuple[str,
          Callable[[Gio.SimpleAction, GLib.Variant], Any],
          str | None]]


class NotificationManager(Gtk.ListBox):
    def __init__(self, account: str) -> None:
        Gtk.ListBox.__init__(self)
        self._account = account
        self._client = app.get_client(account)
        self._client.connect_signal(
            'state-changed', self._on_client_state_changed)

        self.set_selection_mode(Gtk.SelectionMode.NONE)
        self.set_halign(Gtk.Align.CENTER)
        self.get_style_context().add_class('notification-listbox')

        label = Gtk.Label(label=_('No Notifications'))
        label.set_valign(Gtk.Align.START)
        label.get_style_context().add_class('dim-label')
        label.show()
        self.set_placeholder(label)

        self.show_all()

        self._add_actions()
        self.connect('destroy', self._on_destroy)

    def _on_destroy(self, *args: Any) -> None:
        self._remove_actions()

    def _on_client_state_changed(self,
                                 _client: types.Client,
                                 _signal_name: str,
                                 _state: SimpleClientState
                                 ) -> None:
        self.update_actions()

    def _add_actions(self) -> None:
        actions: NotificationActionListT = [
            ('subscription-accept', self._on_subscription_accept, 'as'),
            ('subscription-deny', self._on_subscription_deny, 's'),
            ('subscription-deny-all', self._on_subscription_deny_all, None),
            ('subscription-block', self._on_subscription_block, 's'),
            ('subscription-report', self._on_subscription_report, 's'),
        ]
        for action in actions:
            action_name, func, typ = action
            if typ is not None:
                typ = GLib.VariantType.new(typ)
            act = Gio.SimpleAction.new(
                f'{action_name}-{self._account}', typ)
            act.connect('activate', func)
            app.window.add_action(act)

    def update_actions(self) -> None:
        online = app.account_is_connected(self._account)
        blocking_support = self._client.get_module('Blocking').supported

        sub_accept = app.window.get_action(
            f'subscription-accept-{self._account}')
        sub_accept.set_enabled(online)

        sub_deny = app.window.get_action(
            f'subscription-deny-{self._account}')
        sub_deny.set_enabled(online)

        sub_deny_all = app.window.get_action(
            f'subscription-deny-all-{self._account}')
        sub_deny_all.set_enabled(online)

        sub_block = app.window.get_action(
            f'subscription-block-{self._account}')
        sub_block.set_enabled(online and blocking_support)

        sub_report = app.window.get_action(
            f'subscription-report-{self._account}')
        sub_report.set_enabled(online and blocking_support)

    def _remove_actions(self) -> None:
        actions = [
            'subscription-accept',
            'subscription-deny',
            'subscription-deny-all',
            'subscription-block',
            'subscription-report',
        ]
        for action in actions:
            app.window.remove_action(f'{action}-{self._account}')

    def update_unread_count(self):
        count = len(self.get_children())
        app.window.update_account_unread_count(self._account, count)

    def _on_row_destroy(self, _widget: Gtk.Widget) -> None:
        self.update_unread_count()

    def _on_subscription_accept(self,
                                _action: Gio.SimpleAction,
                                param: GLib.Variant
                                ) -> None:
        jid, nickname = param.get_strv()
        row = self._get_notification_row(jid)
        self._client.get_module('Presence').subscribed(jid)
        jid = JID.from_string(jid)
        contact = self._client.get_module('Contacts').get_contact(jid)
        assert isinstance(contact, BareContact)
        if not contact.is_in_roster:
            open_window('AddContact', account=self._account,
                        jid=jid, nick=nickname or contact.name)
        if row is not None:
            row.destroy()

    def _on_subscription_block(self,
                               _action: Gio.SimpleAction,
                               param: GLib.Variant
                               ) -> None:
        jid = param.get_string()
        self._deny_request(jid)
        self._client.get_module('Blocking').block([jid])
        row = self._get_notification_row(jid)
        if row is not None:
            row.destroy()

    def _on_subscription_report(self,
                                _action: Gio.SimpleAction,
                                param: GLib.Variant
                                ) -> None:
        jid = param.get_string()
        self._deny_request(jid)
        self._client.get_module('Blocking').block([jid], report='spam')
        row = self._get_notification_row(jid)
        if row is not None:
            row.destroy()

    def _on_subscription_deny(self,
                              _action: Gio.SimpleAction,
                              param: GLib.Variant
                              ) -> None:
        jid = param.get_string()
        self._deny_request(jid)
        row = self._get_notification_row(jid)
        if row is not None:
            row.destroy()

    def _on_subscription_deny_all(self,
                                  _action: Gio.SimpleAction,
                                  _param: GLib.Variant
                                  ) -> None:

        for row in cast(list[NotificationRow], self.get_children()):
            if row.type != 'subscribe':
                continue
            self._deny_request(row.jid)
            row.destroy()

    def _deny_request(self, jid: str) -> None:
        self._client.get_module('Presence').unsubscribed(jid)

    def _get_notification_row(self, jid: str) -> NotificationRow | None:
        rows = cast(list[NotificationRow], self.get_children())
        for row in rows:
            if row.jid == jid:
                return row
        return None

    def add_subscription_request(self,
                                 event: SubscribePresenceReceived
                                 ) -> None:
        row = self._get_notification_row(event.jid)
        if row is None:
            new_row = SubscriptionRequestRow(
                self._account,
                event.jid,
                event.status,
                event.user_nick)
            new_row.connect('destroy', self._on_row_destroy)
            self.add(new_row)

            nick = event.user_nick
            if not nick:
                contact = self._client.get_module('Contacts').get_contact(
                    event.jid)
                assert isinstance(contact, BareContact)
                nick = contact.name
            text = _('%s asks you to share your status') % nick

            app.ged.raise_event(
                Notification(account=self._account,
                             jid=event.jid,
                             type='subscription-request',
                             title=_('Subscription Request'),
                             text=text))
            self.update_unread_count()
        elif row.type == 'unsubscribed':
            row.destroy()

    def add_unsubscribed(self,
                         event: UnsubscribedPresenceReceived
                         ) -> None:
        row = self._get_notification_row(event.jid)
        if row is None:
            new_row = UnsubscribedRow(self._account, event.jid)
            new_row.connect('destroy', self._on_row_destroy)
            self.add(new_row)
            self.update_unread_count()

            contact = self._client.get_module('Contacts').get_contact(
                event.jid)
            assert isinstance(contact, BareContact)
            text = _('%s stopped sharing their status') % contact.name

            app.ged.raise_event(
                Notification(account=self._account,
                             jid=event.jid,
                             type='unsubscribed',
                             title=_('Contact Unsubscribed'),
                             text=text))
        elif row.type == 'subscribe':
            row.destroy()

    def add_invitation_received(self, event: MucInvitation) -> None:
        row = self._get_notification_row(str(event.muc))
        if row is not None:
            return

        new_row = InvitationReceivedRow(self._account, event)
        new_row.connect('destroy', self._on_row_destroy)
        self.add(new_row)
        self.update_unread_count()

        jid = event.from_.bare
        client = app.get_client(event.account)
        muc_contact = client.get_module('Contacts').get_contact(event.muc)
        assert isinstance(muc_contact, GroupchatContact)
        if (muc_contact.muc_context == 'private' and
                not event.muc.bare_match(event.from_)):
            contact = self._client.get_module('Contacts').get_contact(jid)
            assert isinstance(contact, BareContact)
            text = _('%(contact)s invited you to %(chat)s') % {
                'contact': contact.name,
                'chat': event.info.muc_name}
        else:
            text = _('You have been invited to %s') % event.info.muc_name

        app.ged.raise_event(
            Notification(account=self._account,
                         jid=jid,
                         type='group-chat-invitation',
                         title=_('Group Chat Invitation'),
                         text=text))

    def add_invitation_declined(self, event: MucDecline) -> None:
        row = self._get_notification_row(str(event.muc))
        if row is not None:
            return

        new_row = InvitationDeclinedRow(self._account, event)
        new_row.connect('destroy', self._on_row_destroy)
        self.add(new_row)
        self.update_unread_count()


class NotificationRow(Gtk.ListBoxRow):
    def __init__(self, account: str, jid: str) -> None:
        Gtk.ListBoxRow.__init__(self)
        self._account = account
        self._client = app.get_client(account)
        self.jid = jid
        self.type = ''

        self.grid = Gtk.Grid(column_spacing=12)
        self.add(self.grid)

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
        contact = self._client.get_module('Contacts').get_contact(jid)
        assert isinstance(
            contact, BareContact | GroupchatContact | GroupchatParticipant)
        if isinstance(contact, GroupchatContact):
            surface = contact.get_avatar(
                AvatarSize.ROSTER, self.get_scale_factor())
        else:
            surface = contact.get_avatar(
                AvatarSize.ROSTER, self.get_scale_factor(), add_show=False)
        image = Gtk.Image.new_from_surface(surface)
        image.set_valign(Gtk.Align.CENTER)
        return image


class SubscriptionRequestRow(NotificationRow):
    def __init__(self,
                 account: str,
                 jid: str,
                 text: str,
                 user_nick: str | None = None
                 ) -> None:
        NotificationRow.__init__(self, account, jid)
        self.type = 'subscribe'

        image = self._generate_avatar_image(jid)
        self.grid.attach(image, 1, 1, 1, 2)

        if user_nick is not None:
            escaped_nick = GLib.markup_escape_text(user_nick)
            nick_markup = f'<b>{escaped_nick}</b> ({jid})'
        else:
            nick_markup = f'<b>{jid}</b>'

        nick_label = self._generate_label()
        nick_label.set_tooltip_markup(nick_markup)
        nick_label.set_markup(nick_markup)
        self.grid.attach(nick_label, 2, 1, 1, 1)

        message_text = GLib.markup_escape_text(text)
        text_label = self._generate_label()
        text_label.set_text(message_text)
        text_label.set_tooltip_text(message_text)
        text_label.get_style_context().add_class('dim-label')
        self.grid.attach(text_label, 2, 2, 1, 1)

        accept_button = Gtk.Button.new_with_label(label=_('Accept'))
        accept_button.set_valign(Gtk.Align.CENTER)
        accept_button.set_action_name(
            f'win.subscription-accept-{self._account}')
        accept_button.set_action_target_value(GLib.Variant.new_strv([
            self.jid,
            user_nick or ''
        ]))
        self.grid.attach(accept_button, 3, 1, 1, 2)

        more_image = Gtk.Image.new_from_icon_name(
            'view-more-symbolic', Gtk.IconSize.MENU)
        more_button = Gtk.MenuButton()
        more_button.set_valign(Gtk.Align.CENTER)
        more_button.add(more_image)
        subscription_menu = get_subscription_menu(
            self._account, JID.from_string(self.jid))
        more_button.set_menu_model(subscription_menu)
        self.grid.attach(more_button, 4, 1, 1, 2)

        self.show_all()


class UnsubscribedRow(NotificationRow):
    def __init__(self, account: str, jid: str) -> None:
        NotificationRow.__init__(self, account, jid)
        self.type = 'unsubscribed'

        image = self._generate_avatar_image(jid)
        self.grid.attach(image, 1, 1, 1, 2)

        contact = self._client.get_module('Contacts').get_contact(jid)
        assert isinstance(contact, BareContact)
        nick_markup = f'<b>{contact.name}</b>'
        nick_label = self._generate_label()
        nick_label.set_tooltip_markup(nick_markup)
        nick_label.set_markup(nick_markup)
        self.grid.attach(nick_label, 2, 1, 1, 1)

        message_text = _('Stopped sharing their status with you')
        text_label = self._generate_label()
        text_label.set_text(message_text)
        text_label.set_tooltip_text(message_text)
        text_label.get_style_context().add_class('dim-label')
        self.grid.attach(text_label, 2, 2, 1, 1)

        remove_button = Gtk.Button.new_with_label(label=_('Remove'))
        remove_button.set_valign(Gtk.Align.CENTER)
        remove_button.set_tooltip_text(_('Remove from contact list'))
        remove_button.set_action_name(
            f'win.{self._account}-remove-contact')
        remove_button.set_action_target_value(GLib.Variant('s', str(self.jid)))
        self.grid.attach(remove_button, 3, 1, 1, 2)

        dismiss_button = Gtk.Button.new_from_icon_name(
            'window-close-symbolic', Gtk.IconSize.BUTTON)
        dismiss_button.set_valign(Gtk.Align.CENTER)
        dismiss_button.set_tooltip_text(_('Remove Notification'))
        dismiss_button.connect('clicked', self._on_dismiss)
        self.grid.attach(dismiss_button, 4, 1, 1, 2)

        self.show_all()

    def _on_dismiss(self, _button: Gtk.Button) -> None:
        self.destroy()


class InvitationReceivedRow(NotificationRow):
    def __init__(self, account: str, event: MucInvitation) -> None:
        NotificationRow.__init__(self, account, str(event.muc))
        self.type = 'invitation-received'

        self._event = event

        jid = event.from_.bare
        image = self._generate_avatar_image(jid)
        self.grid.attach(image, 1, 1, 1, 2)

        title_label = self._generate_label()
        title_label.set_text(_('Group Chat Invitation Received'))
        title_label.get_style_context().add_class('bold')
        self.grid.attach(title_label, 2, 1, 1, 1)

        client = app.get_client(event.account)
        muc_contact = client.get_module('Contacts').get_contact(event.muc)
        assert isinstance(muc_contact, GroupchatContact)
        if (muc_contact.muc_context == 'private' and
                not event.muc.bare_match(event.from_)):
            contact = self._client.get_module('Contacts').get_contact(jid)
            assert isinstance(contact, BareContact)
            invitation_text = _('%(contact)s invited you to %(chat)s') % {
                'contact': contact.name,
                'chat': event.info.muc_name}
        else:
            invitation_text = _('You have been invited '
                                'to %s') % event.info.muc_name
        text_label = self._generate_label()
        text_label.set_text(invitation_text)
        text_label.set_tooltip_text(invitation_text)
        text_label.get_style_context().add_class('dim-label')
        self.grid.attach(text_label, 2, 2, 1, 1)

        show_button = Gtk.Button.new_with_label(label=_('Show'))
        show_button.set_valign(Gtk.Align.CENTER)
        show_button.set_halign(Gtk.Align.END)
        show_button.set_tooltip_text(_('Show Invitation'))
        show_button.connect('clicked', self._on_show_invitation)
        self.grid.attach(show_button, 3, 1, 1, 2)

        decline_button = Gtk.Button.new_with_label(label=_('Decline'))
        decline_button.set_valign(Gtk.Align.CENTER)
        decline_button.set_tooltip_text(_('Decline Invitation'))
        decline_button.connect('clicked', self._on_decline_invitation)
        self.grid.attach(decline_button, 4, 1, 1, 2)

        self.show_all()

    def _on_show_invitation(self, _button: Gtk.Button) -> None:
        open_window('GroupChatInvitation',
                    account=self._account,
                    event=self._event)
        self.destroy()

    def _on_decline_invitation(self, _button: Gtk.Button) -> None:
        self._client.get_module('MUC').decline(
            self.jid, self._event.from_)
        self.destroy()


class InvitationDeclinedRow(NotificationRow):
    def __init__(self, account: str, event: MucDecline) -> None:
        NotificationRow.__init__(self, account, str(event.muc))
        self.type = 'invitation-declined'

        jid = event.from_.bare

        image = self._generate_avatar_image(jid)
        self.grid.attach(image, 1, 1, 1, 2)

        title_label = self._generate_label()
        title_label.set_text(_('Group Chat Invitation Declined'))
        title_label.get_style_context().add_class('bold')
        self.grid.attach(title_label, 2, 1, 1, 1)

        contact = self._client.get_module('Contacts').get_contact(jid)
        assert isinstance(contact, BareContact)
        muc_name = get_groupchat_name(self._client, event.muc)
        invitation_text = _('%(contact)s declined your invitation '
                            'to %(chat)s') % {
                                'contact': contact.name,
                                'chat': muc_name}
        text_label = self._generate_label()
        text_label.set_text(invitation_text)
        text_label.set_tooltip_text(invitation_text)
        text_label.get_style_context().add_class('dim-label')
        self.grid.attach(text_label, 2, 2, 1, 1)

        dismiss_button = Gtk.Button.new_from_icon_name(
            'window-close-symbolic', Gtk.IconSize.BUTTON)
        dismiss_button.set_valign(Gtk.Align.CENTER)
        dismiss_button.set_halign(Gtk.Align.END)
        dismiss_button.set_tooltip_text(_('Remove Notification'))
        dismiss_button.connect('clicked', self._on_dismiss)
        self.grid.attach(dismiss_button, 3, 1, 1, 2)

        self.show_all()

    def _on_dismiss(self, _button: Gtk.Button) -> None:
        self.destroy()
