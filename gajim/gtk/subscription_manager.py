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
from gajim.common.i18n import _

from gajim.gui_menu_builder import get_subscription_manager_menu

from .add_contact import AddNewContactWindow


class SubscriptionManager(Gtk.ScrolledWindow):
    def __init__(self, account):
        Gtk.ScrolledWindow.__init__(self)
        self._account = account
        self._client = app.get_client(account)

        self.set_hexpand(True)
        self.set_size_request(400, 200)

        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self._listbox.get_style_context().add_class('subscription-listbox')
        self._set_placeholder()

        self.add(self._listbox)
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

    def _set_placeholder(self):
        label = Gtk.Label(label=_('No pending requests.'))
        label.set_valign(Gtk.Align.START)
        label.get_style_context().add_class('dim-label')
        label.show()
        self._listbox.set_placeholder(label)

    def _on_subscription_accept(self, _action, param):
        jid = param.get_string()
        row = self._get_request_row(jid)
        self._client.get_module('Presence').subscribed(jid)
        contact = self._client.get_module('Contacts').get_contact(jid)
        if not contact.is_in_roster:
            AddNewContactWindow(self._account, jid, row.user_nick)
        self._listbox.remove(row)

    def _on_subscription_block(self, _action, param):
        jid = param.get_string()
        app.events.remove_events(self._account, jid)
        self._deny_request(jid)
        self._client.get_module('Blocking').block([jid])
        row = self._get_request_row(jid)
        self._listbox.remove(row)

    def _on_subscription_report(self, _action, param):
        jid = param.get_string()
        app.events.remove_events(self._account, jid)
        self._deny_request(jid)
        self._client.get_module('Blocking').block([jid], report='spam')
        row = self._get_request_row(jid)
        self._listbox.remove(row)

    def _on_subscription_deny(self, _action, param):
        jid = param.get_string()
        self._deny_request(jid)
        row = self._get_request_row(jid)
        self._listbox.remove(row)

    def _deny_request(self, jid):
        self._client.get_module('Presence').unsubscribed(jid)

    def _get_request_row(self, jid):
        for child in self._listbox.get_children():
            if child.jid == jid:
                return child
        return None

    def add_request(self, jid, text, user_nick=None):
        if self._get_request_row(jid) is None:
            self._listbox.add(RequestRow(self._account, jid, text, user_nick))


class RequestRow(Gtk.ListBoxRow):
    def __init__(self, account, jid, text, user_nick):
        Gtk.ListBoxRow.__init__(self)
        self._account = account
        self.jid = jid
        self.user_nick = user_nick
        self.get_style_context().add_class('padding-6')

        grid = Gtk.Grid(column_spacing=12)
        image = Gtk.Image.new_from_icon_name(
            'avatar-default-symbolic', Gtk.IconSize.DND)
        image.set_valign(Gtk.Align.CENTER)
        grid.attach(image, 1, 1, 1, 2)

        if user_nick is not None:
            escaped_nick = GLib.markup_escape_text(user_nick)
            nick_markup = f'<b>{escaped_nick}</b> ({jid})'
        else:
            nick_markup = f'<b>{jid}</b>'
        nick_label = Gtk.Label()
        nick_label.set_halign(Gtk.Align.START)
        nick_label.set_ellipsize(Pango.EllipsizeMode.END)
        nick_label.set_max_width_chars(30)
        nick_label.set_tooltip_markup(nick_markup)
        nick_label.set_markup(nick_markup)
        grid.attach(nick_label, 2, 1, 1, 1)

        message_text = GLib.markup_escape_text(text)
        text_label = Gtk.Label(label=message_text)
        text_label.set_halign(Gtk.Align.START)
        text_label.set_ellipsize(Pango.EllipsizeMode.END)
        text_label.set_max_width_chars(30)
        text_label.set_tooltip_text(message_text)
        text_label.get_style_context().add_class('dim-label')
        grid.attach(text_label, 2, 2, 1, 1)

        accept_button = Gtk.Button.new_with_label(label=_('Accept'))
        accept_button.set_valign(Gtk.Align.CENTER)
        accept_button.set_action_name(
            f'win.subscription-accept-{self._account}')
        accept_button.set_action_target_value(GLib.Variant('s', str(self.jid)))
        grid.attach(accept_button, 3, 1, 1, 2)

        more_image = Gtk.Image.new_from_icon_name(
            'view-more-symbolic', Gtk.IconSize.MENU)
        more_button = Gtk.MenuButton()
        more_button.set_valign(Gtk.Align.CENTER)
        more_button.add(more_image)
        subscription_menu = get_subscription_manager_menu(
            self._account, self.jid)
        more_button.set_menu_model(subscription_menu)
        grid.attach(more_button, 4, 1, 1, 2)

        self.add(grid)
        self.show_all()
