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

from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.i18n import _
from gajim.common.helpers import allow_showing_notification
from gajim.common.helpers import get_groupchat_name
from gajim.common.helpers import get_muc_context

from gajim.gui_menu_builder import get_subscription_menu

from .util import open_window


class NotificationManager(Gtk.ListBox):
    def __init__(self, account):
        Gtk.ListBox.__init__(self)
        self._account = account
        self._client = app.get_client(account)

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

    def _on_destroy(self, *args):
        self._remove_actions()

    def _add_actions(self):
        actions = [
            ('subscription-accept', self._on_subscription_accept),
            ('subscription-deny', self._on_subscription_deny),
            ('subscription-block', self._on_subscription_block),
            ('subscription-report', self._on_subscription_report),
        ]
        for action in actions:
            action_name, func = action
            act = Gio.SimpleAction.new(
                f'{action_name}-{self._account}', GLib.VariantType.new('s'))
            act.connect('activate', func)
            app.window.add_action(act)

    def update_actions(self):
        online = app.account_is_connected(self._account)
        blocking_support = self._client.get_module('Blocking').supported

        app.window.lookup_action(
            f'subscription-accept-{self._account}').set_enabled(online)
        app.window.lookup_action(
            f'subscription-deny-{self._account}').set_enabled(online)
        app.window.lookup_action(
            f'subscription-block-{self._account}').set_enabled(
                online and blocking_support)
        app.window.lookup_action(
            f'subscription-report-{self._account}').set_enabled(
                online and blocking_support)

    def _remove_actions(self):
        actions = [
            'subscription-accept',
            'subscription-deny',
            'subscription-block',
            'subscription-report',
        ]
        for action in actions:
            app.window.remove_action(f'{action}-{self._account}')

    def _on_subscription_accept(self, _action, param):
        jid = param.get_string()
        row = self._get_notification_row(jid)
        self._client.get_module('Presence').subscribed(jid)
        contact = self._client.get_module('Contacts').get_contact(jid)
        if not contact.is_in_roster:
            open_window('AddContact', account=self._account,
                        jid=jid, nick=contact.name)
        self.remove(row)

    def _on_subscription_block(self, _action, param):
        jid = param.get_string()
        self._deny_request(jid)
        self._client.get_module('Blocking').block([jid])
        row = self._get_notification_row(jid)
        self.remove(row)

    def _on_subscription_report(self, _action, param):
        jid = param.get_string()
        self._deny_request(jid)
        self._client.get_module('Blocking').block([jid], report='spam')
        row = self._get_notification_row(jid)
        self.remove(row)

    def _on_subscription_deny(self, _action, param):
        jid = param.get_string()
        self._deny_request(jid)
        row = self._get_notification_row(jid)
        self.remove(row)

    def _deny_request(self, jid):
        self._client.get_module('Presence').unsubscribed(jid)

    def _get_notification_row(self, jid):
        for child in self.get_children():
            if child.jid == jid:
                return child
        return None

    def add_subscription_request(self, event):
        row = self._get_notification_row(event.jid)
        if row is None:
            self.add(SubscriptionRequestRow(
                self._account, event.jid, event.status, event.user_nick))

            if allow_showing_notification(self._account):
                event_type = _('Subscription Request')
                contact = self._client.get_module('Contacts').get_contact(
                    event.jid)
                text = _('%s asks you to share your status') % contact.name
                app.notification.popup(
                    event_type,
                    event.jid,
                    self._account,
                    'subscription-request',
                    'gajim-subscription_request',
                    event_type,
                    text)

        elif row.type == 'unsubscribed':
            self.remove(row)

    def add_unsubscribed(self, event):
        row = self._get_notification_row(event.jid)
        if row is None:
            self.add(UnsubscribedRow(self._account, event.jid))

            if allow_showing_notification(self._account):
                event_type = _('Contact Unsubscribed')
                contact = self._client.get_module('Contacts').get_contact(
                    event.jid)
                text = _('%s stopped sharing their status') % contact.name
                app.notification.popup(
                    event_type,
                    event.jid,
                    self._account,
                    'unsubscribed',
                    'gajim-unsubscribed',
                    event_type,
                    text)
        elif row.type == 'subscribe':
            self.remove(row)

    def add_invitation_received(self, event):
        row = self._get_notification_row(event.muc)
        if row is None:
            self.add(InvitationReceivedRow(self._account, event))

            if allow_showing_notification(self._account):
                if get_muc_context(event.muc) == 'public':
                    jid = event.from_
                else:
                    jid = event.from_.bare
                contact = self._client.get_module('Contacts').get_contact(jid)
                event_type = _('Group Chat Invitation')
                text = _('%(contact)s invited you to %(chat)s') % {
                    'contact': contact.name,
                    'chat': event.info.muc_name}
                app.notification.popup(
                    event_type,
                    str(jid),
                    self._account,
                    'gc-invitation',
                    'gajim-gc_invitation',
                    event_type,
                    text,
                    room_jid=event.muc)

    def add_invitation_declined(self, event):
        row = self._get_notification_row(event.muc)
        if row is None:
            self.add(InvitationDeclinedRow(self._account, event))


class NotificationRow(Gtk.ListBoxRow):
    def __init__(self, account, jid):
        Gtk.ListBoxRow.__init__(self)
        self._account = account
        self._client = app.get_client(account)
        self.jid = jid

        self.grid = Gtk.Grid(column_spacing=12)
        self.add(self.grid)

    @staticmethod
    def _generate_label():
        label = Gtk.Label()
        label.set_halign(Gtk.Align.START)
        label.set_hexpand(True)
        label.set_xalign(0)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_max_width_chars(30)
        return label

    def _generate_avatar_image(self, jid):
        contact = self._client.get_module('Contacts').get_contact(jid)
        surface = contact.get_avatar(
            AvatarSize.ROSTER, self.get_scale_factor(), add_show=False)
        image = Gtk.Image.new_from_surface(surface)
        image.set_valign(Gtk.Align.CENTER)
        return image


class SubscriptionRequestRow(NotificationRow):
    def __init__(self, account, jid, text, user_nick=None):
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
        accept_button.set_action_target_value(GLib.Variant('s', str(self.jid)))
        self.grid.attach(accept_button, 3, 1, 1, 2)

        more_image = Gtk.Image.new_from_icon_name(
            'view-more-symbolic', Gtk.IconSize.MENU)
        more_button = Gtk.MenuButton()
        more_button.set_valign(Gtk.Align.CENTER)
        more_button.add(more_image)
        subscription_menu = get_subscription_menu(self._account, self.jid)
        more_button.set_menu_model(subscription_menu)
        self.grid.attach(more_button, 4, 1, 1, 2)

        self.show_all()


class UnsubscribedRow(NotificationRow):
    def __init__(self, account, jid):
        NotificationRow.__init__(self, account, jid)
        self.type = 'unsubscribed'

        image = self._generate_avatar_image(jid)
        self.grid.attach(image, 1, 1, 1, 2)

        contact = self._client.get_module('Contacts').get_contact(jid)
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
        remove_button.set_tooltip_text('Remove from contact list')
        remove_button.set_action_name(
            f'win.remove-contact-{self._account}')
        remove_button.set_action_target_value(GLib.Variant('s', str(self.jid)))
        self.grid.attach(remove_button, 3, 1, 1, 2)

        dismiss_button = Gtk.Button.new_from_icon_name(
            'window-close-symbolic', Gtk.IconSize.BUTTON)
        dismiss_button.set_valign(Gtk.Align.CENTER)
        dismiss_button.set_tooltip_text(_('Remove Notification'))
        dismiss_button.connect('clicked', self._on_dismiss)
        self.grid.attach(dismiss_button, 4, 1, 1, 2)

        self.show_all()

    def _on_dismiss(self, _button):
        self.destroy()


class InvitationReceivedRow(NotificationRow):
    def __init__(self, account, event):
        NotificationRow.__init__(self, account, event.muc)
        self.type = 'invitation-received'

        self._event = event

        if get_muc_context(event.muc) == 'public':
            jid = event.from_
        else:
            jid = event.from_.bare
        image = self._generate_avatar_image(jid)
        self.grid.attach(image, 1, 1, 1, 2)

        title_label = self._generate_label()
        title_label.set_text(_('Group Chat Invitation Received'))
        title_label.get_style_context().add_class('bold')
        self.grid.attach(title_label, 2, 1, 1, 1)

        contact = self._client.get_module('Contacts').get_contact(jid)
        invitation_text = _('%(contact)s invited you to %(chat)s') % {
            'contact': contact.name,
            'chat': event.info.muc_name}
        text_label = self._generate_label()
        text_label.set_text(invitation_text)
        text_label.set_tooltip_text(invitation_text)
        text_label.get_style_context().add_class('dim-label')
        self.grid.attach(text_label, 2, 2, 1, 1)

        show_button = Gtk.Button.new_with_label(label=_('Show'))
        show_button.set_valign(Gtk.Align.CENTER)
        show_button.set_halign(Gtk.Align.END)
        show_button.set_tooltip_text('Show Invitation')
        show_button.connect('clicked', self._on_show_invitation)
        self.grid.attach(show_button, 3, 1, 1, 2)

        decline_button = Gtk.Button.new_with_label(label=_('Decline'))
        decline_button.set_valign(Gtk.Align.CENTER)
        decline_button.set_tooltip_text('Decline Invitation')
        decline_button.connect('clicked', self._on_decline_invitation)
        self.grid.attach(decline_button, 4, 1, 1, 2)

        self.show_all()

    def _on_show_invitation(self, _button):
        open_window('GroupChatInvitation',
                    account=self._account,
                    event=self._event)
        self.destroy()

    def _on_decline_invitation(self, _button):
        self._client.get_module('MUC').decline(
            self.jid, self._event.from_)
        self.destroy()


class InvitationDeclinedRow(NotificationRow):
    def __init__(self, account, event):
        NotificationRow.__init__(self, account, event.muc)
        self.type = 'invitation-declined'

        jid = event.from_.bare

        image = self._generate_avatar_image(jid)
        self.grid.attach(image, 1, 1, 1, 2)

        title_label = self._generate_label()
        title_label.set_text(_('Group Chat Invitation Declined'))
        title_label.get_style_context().add_class('bold')
        self.grid.attach(title_label, 2, 1, 1, 1)

        contact = self._client.get_module('Contacts').get_contact(jid)
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

    def _on_dismiss(self, _button):
        self.destroy()
