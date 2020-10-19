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

import logging

from gi.repository import Gtk

from nbxmpp.errors import StanzaError

from gajim.common import app
from gajim.common import ged
from gajim.common.i18n import _
from gajim.common.helpers import to_user_string
from gajim.common.helpers import event_filter

from gajim.gtk.assistant import Assistant
from gajim.gtk.assistant import Page

log = logging.getLogger('gajim.gtk.remove_account')


class RemoveAccount(Assistant):
    def __init__(self, account):
        Assistant.__init__(self)

        self.account = account
        self._con = app.connections.get(account)
        self._destroyed = False
        self._account_removed = False

        self.add_button('remove', _('Remove'), 'destructive-action')
        self.add_button('close', _('Close'))
        self.add_button('back', _('Back'))

        self.add_pages({'remove_choice': RemoveChoice(account)})

        progress = self.add_default_page('progress')
        progress.set_title(_('Removing Account...'))
        progress.set_text(_('Trying to remove account...'))

        success = self.add_default_page('success')
        success.set_title(_('Account Removed'))
        success.set_heading(_('Account Removed'))
        success.set_text(
            _('Your account has has been removed successfully.'))

        error = self.add_default_page('error')
        error.set_title(_('Account Removal Failed'))
        error.set_heading(_('Account Removal Failed'))

        self.set_button_visible_func(self._visible_func)

        self.connect('button-clicked', self._on_button_clicked)
        self.connect('page-changed', self._on_page_changed)
        self.connect('destroy', self._on_destroy)

        self.register_events([
            ('account-connected', ged.GUI1, self._on_account_connected),
            ('account-disconnected', ged.GUI1, self._on_account_disconnected),
        ])

        self._set_remove_from_server_checkbox()

        self.show_all()

    @event_filter(['account'])
    def _on_account_connected(self, event):
        self._con = app.connections.get(self.account)
        self._set_remove_from_server_checkbox()

    @event_filter(['account'])
    def _on_account_disconnected(self, event):
        self._set_remove_from_server_checkbox()

        if self._account_removed:
            self.show_page('success')
            app.interface.remove_account(self.account)

    def _set_remove_from_server_checkbox(self):
        enabled = self._con is not None and self._con.state.is_available
        self.get_page('remove_choice').set_remove_from_server(enabled)

    @staticmethod
    def _visible_func(_assistant, page_name):
        if page_name == 'remove_choice':
            return ['remove']

        if page_name == 'progress':
            return None

        if page_name == 'error':
            return ['back']

        if page_name == 'success':
            return ['close']
        raise ValueError('page %s unknown' % page_name)

    def _on_button_clicked(self, _assistant, button_name):
        page = self.get_current_page()
        if button_name == 'remove':
            if page == 'remove_choice':
                self.show_page('progress', Gtk.StackTransitionType.SLIDE_LEFT)
                self._on_remove()
            return

        if button_name == 'back':
            if page == 'error':
                self.show_page('remove_choice',
                               Gtk.StackTransitionType.SLIDE_RIGHT)
            return

        if button_name == 'close':
            self.destroy()

    def _on_page_changed(self, _assistant, page_name):
        if page_name == 'remove_choice':
            self.set_default_button('remove')

        elif page_name == 'success':
            self.set_default_button('close')

        elif page_name == 'error':
            self.set_default_button('back')

    def _on_remove(self, *args):
        if self.get_page('remove_choice').remove_from_server:
            self._con.set_remove_account(True)
            self._con.get_module('Register').unregister(
                callback=self._on_remove_response)
            return

        if self._con is None or self._con.state.is_disconnected:
            app.interface.remove_account(self.account)
            self.show_page('success')
            return

        self._con.disconnect(gracefully=True, reconnect=False)
        self._account_removed = True

    def _on_remove_response(self, task):
        try:
            task.finish()
        except StanzaError as error:
            self._con.set_remove_account(False)

            error_text = to_user_string(error)
            self.get_page('error').set_text(error_text)
            self.show_page('error')
            return

        self._account_removed = True

    def _on_destroy(self, *args):
        self._destroyed = True


class RemoveChoice(Page):
    def __init__(self, account):
        Page.__init__(self)
        self.title = _('Remove Account')

        heading = Gtk.Label(label=_('Remove Account'))
        heading.get_style_context().add_class('large-header')
        heading.set_max_width_chars(30)
        heading.set_line_wrap(True)
        heading.set_halign(Gtk.Align.CENTER)
        heading.set_justify(Gtk.Justification.CENTER)

        label = Gtk.Label(label=_('This will remove your account from Gajim.'))
        label.set_max_width_chars(50)
        label.set_line_wrap(True)
        label.set_halign(Gtk.Align.CENTER)
        label.set_justify(Gtk.Justification.CENTER)

        service = app.settings.get_account_setting(account, 'hostname')
        check_label = Gtk.Label()
        check_label.set_markup(
            _('Do you want to unregister your account on <b>%s</b> as '
              'well?') % service)
        check_label.set_max_width_chars(50)
        check_label.set_line_wrap(True)
        check_label.set_halign(Gtk.Align.CENTER)
        check_label.set_justify(Gtk.Justification.CENTER)
        check_label.set_margin_top(40)

        self._server = Gtk.CheckButton.new_with_mnemonic(
            _('_Unregister account from service'))
        self._server.set_halign(Gtk.Align.CENTER)

        self.pack_start(heading, False, True, 0)
        self.pack_start(label, False, True, 0)
        self.pack_start(check_label, False, True, 0)
        self.pack_start(self._server, False, True, 0)
        self.show_all()

    @property
    def remove_from_server(self):
        return self._server.get_active()

    def set_remove_from_server(self, enabled):
        self._server.set_sensitive(enabled)
        if enabled:
            self._server.set_tooltip_text('')
        else:
            self._server.set_active(False)
            self._server.set_tooltip_text(_('Account has to be connected'))
