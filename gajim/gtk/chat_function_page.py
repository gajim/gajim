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

from typing import Optional

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango

from nbxmpp.protocol import InvalidJid
from nbxmpp.protocol import JID
from nbxmpp.protocol import validate_resourcepart

from gajim.common import app
from gajim.common.client import Client
from gajim.common.i18n import _
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.types import ChatContactT

from .dataform import DataFormWidget
from .groupchat_inviter import GroupChatInviter


class ChatFunctionPage(Gtk.Box):

    __gsignals__ = {
        'finish': (GObject.SignalFlags.RUN_LAST, None, (bool,)),
        'message': (GObject.SignalFlags.RUN_LAST, None, (str,)),
    }

    def __init__(self) -> None:
        Gtk.Box.__init__(self,
                         orientation=Gtk.Orientation.VERTICAL,
                         spacing=18)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)
        self.get_style_context().add_class('padding-18')

        self._client: Optional[Client] = None
        self._contact: Optional[ChatContactT] = None
        self._mode: Optional[str] = None

        self._widget: Optional[Gtk.Widget] = None

        self._heading = Gtk.Label()
        self._heading.set_max_width_chars(30)
        self._heading.set_ellipsize(Pango.EllipsizeMode.END)
        self._heading.get_style_context().add_class('large-header')
        self.add(self._heading)

        self._content_box = Gtk.Box()
        self._content_box.set_halign(Gtk.Align.CENTER)
        self.add(self._content_box)

        cancel_button = Gtk.Button(label=_('Cancel'))
        cancel_button.connect('clicked', self._on_cancel_clicked)

        self._forget_button = Gtk.Button(label=_('Forget Group Chat'))
        self._forget_button.set_no_show_all(True)
        self._forget_button.get_style_context().add_class(
            'destructive-action')
        self._forget_button.connect('clicked', self._on_forget_clicked)

        self._confirm_button = Gtk.Button()
        self._confirm_button.set_can_default(True)
        self._confirm_button.connect('clicked', self._on_confirm_clicked)

        button_box = Gtk.Box(spacing=18)
        button_box.pack_start(cancel_button, False, True, 0)
        button_box.pack_end(self._forget_button, False, True, 0)
        button_box.pack_end(self._confirm_button, False, True, 0)

        self.add(button_box)

    def process_escape(self) -> None:
        close_control = self._mode in (
            'join-failed',
            'creation-failed',
            'config-failed',
            'captcha-error')
        self.emit('finish', close_control)

    def _clear(self) -> None:
        for child in self._content_box.get_children():
            child.destroy()

    def set_mode(self,
                 contact: ChatContactT,
                 mode: str,
                 data: Optional[str] = None
                 ) -> None:
        self._clear()
        self._confirm_button.get_style_context().remove_class(
            'destructive-action')
        self._confirm_button.get_style_context().remove_class(
            'suggested-action')
        self._confirm_button.set_sensitive(False)
        self._confirm_button.grab_default()

        self._forget_button.hide()

        self._contact = contact
        self._heading.set_text(self._contact.name)
        self._client = app.get_client(contact.account)
        self._mode = mode
        self._data = data

        if self._widget is not None:
            self._widget.destroy()

        if mode == 'invite':
            self._confirm_button.set_label(_('Invite'))
            self._confirm_button.get_style_context().add_class(
                'suggested-action')
            self._widget = GroupChatInviter(str(contact.jid))
            self._widget.set_size_request(-1, 500)
            self._widget.connect('listbox-changed', self._on_ready)
            self._widget.load_contacts()

        elif mode == 'change-nickname':
            self._confirm_button.set_label(_('Change'))
            self._confirm_button.get_style_context().add_class(
                'suggested-action')
            self._widget = InputWidget(self._contact, mode)
            self._widget.connect('changed', self._on_ready)

        elif mode == 'kick':
            self._confirm_button.set_label(_('Kick'))
            self._confirm_button.set_sensitive(True)
            self._confirm_button.get_style_context().add_class(
                'destructive-action')
            self._widget = InputWidget(self._contact, mode, data)

        elif mode == 'ban':
            self._confirm_button.set_label(_('Ban'))
            self._confirm_button.set_sensitive(True)
            self._confirm_button.get_style_context().add_class(
                'destructive-action')
            self._widget = InputWidget(self._contact, mode, data)

        elif mode == 'password-request':
            self._confirm_button.set_label(_('Join'))
            self._confirm_button.get_style_context().add_class(
                'suggested-action')
            self._widget = InputWidget(self._contact, mode)
            self._widget.connect('changed', self._on_ready)

        elif mode == 'captcha-request':
            self._confirm_button.set_label(_('Join'))
            self._confirm_button.get_style_context().add_class(
                'suggested-action')
            muc_data = self._client.get_module('MUC').get_muc_data(
                self._contact.jid)
            form = muc_data.captcha_form
            options = {'no-scrolling': True,
                       'entry-activates-default': True}
            self._widget = DataFormWidget(form, options=options)
            self._widget.set_valign(Gtk.Align.START)
            self._widget.show_all()
            self._widget.connect('is-valid', self._on_ready)

        elif mode == 'captcha-error':
            self._confirm_button.set_label(_('Try Again'))
            self._confirm_button.set_sensitive(True)
            self._confirm_button.get_style_context().add_class(
                'suggested-action')
            self._widget = ErrorWidget(error_text=data)

        elif mode in ('join-failed', 'creation-failed', 'config-failed'):
            self._confirm_button.set_label(_('Try Again'))
            self._confirm_button.set_sensitive(True)
            self._confirm_button.get_style_context().add_class(
                'suggested-action')
            if mode == 'join-failed':
                is_bookmark = self._client.get_module('Bookmarks').is_bookmark(
                    self._contact.jid)
                self._forget_button.set_visible(is_bookmark)
            self._widget = ErrorWidget(error_mode=mode, error_text=data)

        assert self._widget is not None
        self._content_box.add(self._widget)
        if isinstance(self._widget, InputWidget):
            self._widget.focus()
        elif isinstance(self._widget, DataFormWidget):
            self._widget.focus_first_entry()

    def _on_ready(self,
                  _widget: Gtk.Widget,
                  state: bool
                  ) -> None:
        self._confirm_button.set_sensitive(state)

    def _on_confirm_clicked(self, _button: Gtk.Button) -> None:
        if self._mode == 'invite':
            assert isinstance(self._widget, GroupChatInviter)
            invitees = self._widget.get_invitees()
            for jid in invitees:
                self._invite(JID.from_string(jid))

        elif self._mode == 'change-nickname':
            assert isinstance(self._widget, InputWidget)
            nickname = self._widget.get_text()
            assert self._client is not None
            assert self._contact is not None
            self._client.get_module('MUC').change_nick(
                self._contact.jid, nickname)

        elif self._mode == 'kick':
            assert isinstance(self._widget, InputWidget)
            reason = self._widget.get_text()
            assert self._client is not None
            assert self._contact is not None
            self._client.get_module('MUC').set_role(
                self._contact.jid, self._data, 'none', reason)

        elif self._mode == 'ban':
            assert isinstance(self._widget, InputWidget)
            reason = self._widget.get_text()
            assert self._client is not None
            assert self._contact is not None
            self._client.get_module('MUC').set_affiliation(
                self._contact.jid,
                {self._data: {'affiliation': 'outcast', 'reason': reason}})

        elif self._mode == 'password-request':
            assert isinstance(self._widget, InputWidget)
            password = self._widget.get_text()
            assert self._client is not None
            assert self._contact is not None
            self._client.get_module('MUC').set_password(
                self._contact.jid, password)
            self._client.get_module('MUC').join(self._contact.jid)

        elif self._mode == 'captcha-request':
            assert isinstance(self._widget, DataFormWidget)
            form_node = self._widget.get_submit_form()
            assert self._client is not None
            assert self._contact is not None
            self._client.get_module('MUC').send_captcha(
                self._contact.jid, form_node)

        elif self._mode in ('join-failed', 'captcha-error'):
            assert self._client is not None
            assert self._contact is not None
            self._client.get_module('MUC').join(self._contact.jid)

        self.emit('finish', False)

    def _on_cancel_clicked(self, _button: Gtk.Button) -> None:
        assert self._client is not None
        assert self._contact is not None

        if self._mode == 'captcha-request':
            self._client.get_module('MUC').cancel_captcha(
                self._contact.jid)
            self.emit('finish', True)
            return

        if self._mode == 'password-request':
            self._client.get_module('MUC').cancel_password_request(
                self._contact.jid)
            self.emit('finish', True)
            return

        if self._mode in (
                'join-failed',
                'creation-failed',
                'config-failed',
                'captcha-error'):
            self.emit('finish', True)
            return

        self.emit('finish', False)

    def _on_forget_clicked(self, _button: Gtk.Button) -> None:
        assert self._client is not None
        assert self._contact is not None
        self._client.get_module('Bookmarks').remove(self._contact.jid)
        self.emit('finish', True)

    def _invite(self, invited_jid: JID) -> None:
        assert self._contact is not None
        client = app.get_client(self._contact.account)
        client.get_module('MUC').invite(
            self._contact.jid, invited_jid)
        invited_contact = client.get_module('Contacts').get_contact(
            invited_jid)
        self.emit(
            'message',
            _('%s has been invited to this group chat') % invited_contact.name)


class InputWidget(Gtk.Box):

    __gsignals__ = {
        'changed': (GObject.SignalFlags.RUN_LAST, None, (bool,)),
    }

    def __init__(self,
                 contact: ChatContactT,
                 mode: str,
                 data: Optional[str] = None
                 ) -> None:
        Gtk.Box.__init__(self,
                         orientation=Gtk.Orientation.VERTICAL,
                         spacing=12)
        self._contact = contact
        self._mode = mode

        heading_label = Gtk.Label()
        heading_label.set_xalign(0)
        heading_label.get_style_context().add_class('bold16')
        self.add(heading_label)

        sub_label = Gtk.Label()
        sub_label.set_xalign(0)
        sub_label.get_style_context().add_class('dim-label')
        self.add(sub_label)

        self._entry = Gtk.Entry()
        self._entry.set_activates_default(True)
        self._entry.set_size_request(300, -1)
        self._entry.connect('changed', self._on_entry_changed)
        self.add(self._entry)

        if mode == 'change-nickname':
            heading_label.set_text(_('Change Nickname'))
            sub_label.set_text(_('Enter your new nickname'))
            assert isinstance(self._contact, GroupchatContact)
            self._entry.set_text(self._contact.nickname or '')

        elif mode == 'kick':
            heading_label.set_text(_('Kick %s') % data)
            sub_label.set_text(_('Reason (optional)'))

        elif mode == 'ban':
            heading_label.set_text(_('Ban %s') % data)
            sub_label.set_text(_('Reason (optional)'))

        elif mode == 'password-request':
            heading_label.set_text(_('Password Required'))
            sub_label.set_text(_('Enter a password to join this chat'))
            self._entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
            self._entry.set_visibility(False)

        self.connect('destroy', self._on_destroy)
        self.show_all()

    def _on_destroy(self, _widget: InputWidget) -> None:
        app.check_finalize(self)

    def _on_entry_changed(self, entry: Gtk.Entry) -> None:
        text = entry.get_text()

        if self._mode == 'change-nickname':
            assert isinstance(self._contact, GroupchatContact)
            if not text or text == self._contact.nickname:
                self.emit('changed', False)
                return
            try:
                validate_resourcepart(text)
            except InvalidJid:
                self.emit('changed', False)
                return

        self.emit('changed', bool(text))

    def focus(self) -> None:
        self._entry.grab_focus()

    def get_text(self) -> str:
        return self._entry.get_text()


class ErrorWidget(Gtk.Box):
    def __init__(self,
                 error_mode: Optional[str] = None,
                 error_text: Optional[str] = None
                 ) -> None:
        Gtk.Box.__init__(self,
                         orientation=Gtk.Orientation.VERTICAL,
                         spacing=12)
        image = Gtk.Image.new_from_icon_name(
            'dialog-error-symbolic', Gtk.IconSize.DIALOG)
        image.get_style_context().add_class('error-color')

        heading = Gtk.Label()
        heading.get_style_context().add_class('bold16')
        heading_text = _('An Error Occurred')
        if error_mode == 'join-failed':
            heading_text = _('Failed to Join Group Chat')
        elif error_mode == 'creation-failed':
            heading_text = _('Failed to Create Group Chat')
        elif error_mode == 'config-failed':
            heading_text = _('Failed to Configure Group Chat')
        heading.set_text(heading_text)

        label = Gtk.Label()
        label.set_max_width_chars(40)
        if error_text is not None:
            label.set_text(error_text)

        self.add(image)
        self.add(heading)
        self.add(label)
        self.show_all()
