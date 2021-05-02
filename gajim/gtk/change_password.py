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
from nbxmpp.errors import ChangePasswordStanzaError

from gajim.common import app
from gajim.common.i18n import _
from gajim.common import passwords
from gajim.common.helpers import to_user_string

from .assistant import Assistant
from .assistant import Page
from .dataform import DataFormWidget

log = logging.getLogger('gajim.gui.change_password')


class ChangePassword(Assistant):
    def __init__(self, account):
        Assistant.__init__(self)

        self.account = account
        self._con = app.connections.get(account)
        self._destroyed = False

        self.add_button('apply', _('Change'), 'suggested-action',
                        complete=True)
        self.add_button('close', _('Close'))
        self.add_button('back', _('Back'))

        self.add_pages({'password': EnterPassword(),
                        'next_stage': NextStage()})

        progress = self.add_default_page('progress')
        progress.set_title(_('Changing Password...'))
        progress.set_text(_('Trying to change password...'))

        success = self.add_default_page('success')
        success.set_title(_('Password Changed'))
        success.set_heading(_('Password Changed'))
        success.set_text(_('Your password has successfully been changed.'))

        error = self.add_default_page('error')
        error.set_title(_('Password Change Failed'))
        error.set_heading(_('Password Change Failed'))
        error.set_text(
            _('An error occurred while trying to change your password.'))

        self.set_button_visible_func(self._visible_func)

        self.connect('button-clicked', self._on_button_clicked)
        self.connect('page-changed', self._on_page_changed)
        self.connect('destroy', self._on_destroy)

        self.show_all()

    @staticmethod
    def _visible_func(_assistant, page_name):
        if page_name in ('password', 'next_stage'):
            return ['apply']

        if page_name == 'progress':
            return None

        if page_name == 'error':
            return ['back']

        if page_name == 'success':
            return ['close']
        raise ValueError('page %s unknown' % page_name)

    def _on_button_clicked(self, _assistant, button_name):
        page = self.get_current_page()
        if button_name == 'apply':
            self.show_page('progress', Gtk.StackTransitionType.SLIDE_LEFT)
            self._on_apply(next_stage=page == 'next_stage')

        elif button_name == 'back':
            self.show_page('password', Gtk.StackTransitionType.SLIDE_RIGHT)

        elif button_name == 'close':
            self.destroy()

    def _on_page_changed(self, _assistant, page_name):
        if page_name in ('password', 'next_stage'):
            self.set_default_button('apply')

        elif page_name == 'success':
            password = self.get_page('password').get_password()
            passwords.save_password(self.account, password)
            self.set_default_button('close')

        elif page_name == 'error':
            self.set_default_button('back')

    def _on_apply(self, next_stage=False):
        if next_stage:
            form = self.get_page('next_stage').get_submit_form()
            self._con.get_module('Register').change_password_with_form(
                form, callback=self._on_change_password)
        else:
            password = self.get_page('password').get_password()
            self._con.get_module('Register').change_password(
                password, callback=self._on_change_password)

    def _on_change_password(self, task):
        try:
            task.finish()
        except ChangePasswordStanzaError as error:
            self.get_page('next_stage').set_form(error.get_form())
            self.show_page('next_stage', Gtk.StackTransitionType.SLIDE_LEFT)

        except StanzaError as error:
            error_text = to_user_string(error)
            self.get_page('error').set_text(error_text)
            self.show_page('error', Gtk.StackTransitionType.SLIDE_LEFT)

        else:
            self.show_page('success')

    def _on_destroy(self, *args):
        self._destroyed = True


class EnterPassword(Page):
    def __init__(self):
        Page.__init__(self)
        self.complete = False
        self.title = _('Change Password')

        heading = Gtk.Label(label=_('Change Password'))
        heading.get_style_context().add_class('large-header')
        heading.set_max_width_chars(30)
        heading.set_line_wrap(True)
        heading.set_halign(Gtk.Align.CENTER)
        heading.set_justify(Gtk.Justification.CENTER)

        label = Gtk.Label(label=_('Please enter your new password.'))
        label.set_max_width_chars(50)
        label.set_line_wrap(True)
        label.set_halign(Gtk.Align.CENTER)
        label.set_justify(Gtk.Justification.CENTER)
        label.set_margin_bottom(12)

        self._password1_entry = Gtk.Entry()
        self._password1_entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self._password1_entry.set_visibility(False)
        self._password1_entry.set_invisible_char('•')
        self._password1_entry.set_valign(Gtk.Align.END)
        self._password1_entry.set_placeholder_text(
            _('Enter new password...'))
        self._password1_entry.connect('changed', self._on_changed)
        self._password2_entry = Gtk.Entry()
        self._password2_entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self._password2_entry.set_visibility(False)
        self._password2_entry.set_invisible_char('•')
        self._password2_entry.set_activates_default(True)
        self._password2_entry.set_valign(Gtk.Align.START)
        self._password2_entry.set_placeholder_text(
            _('Confirm new password...'))
        self._password2_entry.connect('changed', self._on_changed)

        self.pack_start(heading, False, True, 0)
        self.pack_start(label, False, True, 0)
        self.pack_start(self._password1_entry, True, True, 0)
        self.pack_start(self._password2_entry, True, True, 0)
        self._show_icon(False)
        self.show_all()

    def _show_icon(self, show):
        if show:
            self._password2_entry.set_icon_from_icon_name(
                Gtk.EntryIconPosition.SECONDARY, 'dialog-warning-symbolic')
            self._password2_entry.set_icon_tooltip_text(
                Gtk.EntryIconPosition.SECONDARY, _('Passwords do not match'))
        else:
            self._password2_entry.set_icon_from_icon_name(
                Gtk.EntryIconPosition.SECONDARY, None)

    def _on_changed(self, _entry):
        password1 = self._password1_entry.get_text()
        if not password1:
            self._show_icon(True)
            self._set_complete(False)
            return

        password2 = self._password2_entry.get_text()
        if password1 != password2:
            self._show_icon(True)
            self._set_complete(False)
            return
        self._show_icon(False)
        self._set_complete(True)

    def _set_complete(self, state):
        self.complete = state
        self.update_page_complete()

    def get_password(self):
        return self._password1_entry.get_text()


class NextStage(Page):
    def __init__(self):
        Page.__init__(self)
        self.set_valign(Gtk.Align.FILL)
        self.complete = False
        self.title = _('Change Password')
        self._current_form = None

        self.show_all()

    def _on_is_valid(self, _widget, is_valid):
        self.complete = is_valid
        self.update_page_complete()

    def set_form(self, form):
        if self._current_form is not None:
            self.remove(self._current_form)
            self._current_form.destroy()
        self._current_form = DataFormWidget(form)
        self._current_form.connect('is-valid', self._on_is_valid)
        self._current_form.validate()
        self.pack_start(self._current_form, True, True, 0)
        self._current_form.show_all()

    def get_submit_form(self):
        return self._current_form.get_submit_form()
