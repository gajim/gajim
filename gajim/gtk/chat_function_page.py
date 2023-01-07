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

from enum import Enum
from pathlib import Path

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango
from nbxmpp.protocol import InvalidJid
from nbxmpp.protocol import JID
from nbxmpp.protocol import validate_resourcepart

from gajim.common import app
from gajim.common import types
from gajim.common.const import SimpleClientState
from gajim.common.i18n import _
from gajim.common.modules.contacts import GroupchatContact

from gajim.gtk.dataform import DataFormWidget
from gajim.gtk.file_transfer_selector import FileTransferSelector
from gajim.gtk.groupchat_inviter import GroupChatInviter


class FunctionMode(Enum):
    INVITE = 'invite'
    SEND_FILE = 'send-file'
    CHANGE_NICKNAME = 'change-nickname'
    KICK = 'kick'
    BAN = 'ban'
    PASSWORD_REQUEST = 'password-request'  # noqa: S105
    CAPTCHA_REQUEST = 'captcha-request'
    CAPTCHA_ERROR = 'captcha-error'
    JOIN_FAILED = 'join-failed'
    CREATION_FAILED = 'creation-failed'
    CONFIG_FAILED = 'config-failed'


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

        self._client: Optional[types.Client] = None
        self._contact: Optional[types.ChatContactT] = None
        self._mode: Optional[FunctionMode] = None
        self._data: Optional[str] = None
        self._ready_state = True

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
            FunctionMode.CREATION_FAILED,
            FunctionMode.CONFIG_FAILED,
            FunctionMode.CAPTCHA_ERROR)
        self.emit('finish', close_control)

    def _reset(self) -> None:
        if self._client is not None:
            self._client.disconnect_all_from_obj(self)

        for child in self._content_box.get_children():
            child.destroy()

        if self._widget is not None:
            self._widget.destroy()

        self._confirm_button.get_style_context().remove_class(
            'destructive-action')
        self._confirm_button.get_style_context().remove_class(
            'suggested-action')
        self._confirm_button.set_sensitive(False)
        self._confirm_button.grab_default()

        self._forget_button.set_sensitive(True)
        self._forget_button.hide()

        self._ready_state = True

    def set_mode(self,
                 contact: types.ChatContactT,
                 mode: FunctionMode,
                 data: Optional[str] = None,
                 files: Optional[list[str]] = None
                 ) -> None:

        self._reset()

        self._contact = contact
        self._client = app.get_client(contact.account)
        self._client.connect_signal(
            'state-changed', self._on_client_state_changed)

        self._mode = mode
        self._data = data

        self._heading.set_text(self._contact.name)

        if mode == FunctionMode.INVITE:
            self._confirm_button.set_label(_('Invite'))
            self._confirm_button.get_style_context().add_class(
                'suggested-action')
            self._widget = GroupChatInviter(str(contact.jid))
            self._widget.set_size_request(-1, 500)
            self._widget.connect('listbox-changed', self._on_ready)
            self._widget.load_contacts()

        elif mode == FunctionMode.SEND_FILE:
            self._confirm_button.set_label(_('Send Files'))
            self._confirm_button.get_style_context().add_class(
                'suggested-action')
            self._widget = FileTransferSelector(self._contact, data)
            self._widget.connect('changed', self._on_ready)
            if files is not None:
                self._widget.add_files(files)

        elif mode == FunctionMode.CHANGE_NICKNAME:
            self._confirm_button.set_label(_('Change'))
            self._confirm_button.get_style_context().add_class(
                'suggested-action')
            self._widget = InputWidget(self._contact, mode)
            self._widget.connect('changed', self._on_ready)

        elif mode == FunctionMode.KICK:
            self._confirm_button.set_label(_('Kick'))
            self._confirm_button.set_sensitive(True)
            self._confirm_button.get_style_context().add_class(
                'destructive-action')
            self._widget = InputWidget(self._contact, mode, data)

        elif mode == FunctionMode.BAN:
            self._confirm_button.set_label(_('Ban'))
            self._confirm_button.set_sensitive(True)
            self._confirm_button.get_style_context().add_class(
                'destructive-action')
            self._widget = InputWidget(self._contact, mode, data)

        elif mode == FunctionMode.PASSWORD_REQUEST:
            self._confirm_button.set_label(_('Join'))
            self._confirm_button.get_style_context().add_class(
                'suggested-action')
            self._widget = InputWidget(self._contact, mode)
            self._widget.connect('changed', self._on_ready)

        elif mode == FunctionMode.CAPTCHA_REQUEST:
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

        elif mode == FunctionMode.CAPTCHA_ERROR:
            self._confirm_button.set_label(_('Try Again'))
            self._confirm_button.set_sensitive(True)
            self._confirm_button.get_style_context().add_class(
                'suggested-action')
            self._widget = ErrorWidget(error_text=data)

        elif mode in (FunctionMode.JOIN_FAILED,
                      FunctionMode.CREATION_FAILED,
                      FunctionMode.CONFIG_FAILED):
            self._confirm_button.set_label(_('Try Again'))
            self._confirm_button.set_sensitive(True)
            self._confirm_button.get_style_context().add_class(
                'suggested-action')
            if mode == FunctionMode.JOIN_FAILED:
                is_bookmark = self._client.get_module('Bookmarks').is_bookmark(
                    self._contact.jid)
                self._forget_button.set_visible(is_bookmark)
            self._widget = ErrorWidget(mode=mode, error_text=data)

        assert self._widget is not None
        self._content_box.add(self._widget)
        if isinstance(self._widget, InputWidget):
            self._widget.focus()
        elif isinstance(self._widget, DataFormWidget):
            self._widget.focus_first_entry()

    def _on_client_state_changed(self,
                                 _client: types.Client,
                                 _signal_name: str,
                                 _state: SimpleClientState
                                 ) -> None:

        self._update_button_state()

    def _on_ready(self,
                  _widget: Gtk.Widget,
                  state: bool
                  ) -> None:

        self._ready_state = state
        self._update_button_state()

    def _update_button_state(self) -> None:
        assert self._contact is not None
        if app.account_is_connected(self._contact.account):
            self._confirm_button.set_sensitive(self._ready_state)
            self._forget_button.set_sensitive(True)
            return

        self._confirm_button.set_sensitive(False)
        self._forget_button.set_sensitive(False)

    def _on_confirm_clicked(self, _button: Gtk.Button) -> None:
        assert self._client is not None
        assert self._contact is not None

        if self._mode == FunctionMode.INVITE:
            assert isinstance(self._widget, GroupChatInviter)
            invitees = self._widget.get_invitees()
            for jid in invitees:
                self._invite(JID.from_string(jid))

        elif self._mode == FunctionMode.SEND_FILE:
            assert isinstance(self._widget, FileTransferSelector)
            if self._widget.transfer_resource_required():
                return

            self._send_files(self._widget.get_catalog())

        elif self._mode == FunctionMode.CHANGE_NICKNAME:
            assert isinstance(self._widget, InputWidget)
            nickname = self._widget.get_text()
            self._client.get_module('MUC').change_nick(
                self._contact.jid, nickname)

        elif self._mode == FunctionMode.KICK:
            assert isinstance(self._widget, InputWidget)
            reason = self._widget.get_text()
            self._client.get_module('MUC').set_role(
                self._contact.jid, self._data, 'none', reason)

        elif self._mode == FunctionMode.BAN:
            assert isinstance(self._widget, InputWidget)
            reason = self._widget.get_text()
            self._client.get_module('MUC').set_affiliation(
                self._contact.jid,
                {self._data: {'affiliation': 'outcast', 'reason': reason}})

        elif self._mode == FunctionMode.PASSWORD_REQUEST:
            assert isinstance(self._widget, InputWidget)
            password = self._widget.get_text()
            self._client.get_module('MUC').set_password(
                self._contact.jid, password)
            self._client.get_module('MUC').join(self._contact.jid)

        elif self._mode == FunctionMode.CAPTCHA_REQUEST:
            assert isinstance(self._widget, DataFormWidget)
            form_node = self._widget.get_submit_form()
            self._client.get_module('MUC').send_captcha(
                self._contact.jid, form_node)

        elif self._mode in (FunctionMode.JOIN_FAILED,
                            FunctionMode.CAPTCHA_ERROR):
            self._client.get_module('MUC').join(self._contact.jid)

        self.emit('finish', False)

    def _on_cancel_clicked(self, _button: Gtk.Button) -> None:
        assert self._client is not None
        assert self._contact is not None

        connected = app.account_is_connected(self._contact.account)
        close_control = False

        if self._mode == FunctionMode.CAPTCHA_REQUEST:
            if connected:
                self._client.get_module('MUC').cancel_captcha(
                    self._contact.jid)
            close_control = True

        elif self._mode == FunctionMode.PASSWORD_REQUEST:
            if connected:
                self._client.get_module('MUC').cancel_password_request(
                    self._contact.jid)
            close_control = True

        elif self._mode in (
                FunctionMode.CREATION_FAILED,
                FunctionMode.CONFIG_FAILED,
                FunctionMode.CAPTCHA_ERROR):
            close_control = True

        self.emit('finish', close_control)

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

    def _send_files(self, catalog: list[tuple[Path, str, JID]]) -> None:
        assert self._contact is not None
        client = app.get_client(self._contact.account)

        # catalog: list[(file Path, transfer method, recipient JID)]
        for path, method, jid in catalog:
            if method == 'httpupload':
                client.get_module('HTTPUpload').send_file(
                    self._contact, path)
                continue

            # Send using Jingle
            app.interface.instances['file_transfers'].send_file(
                self._contact.account,
                self._contact,
                jid,
                str(path))


class InputWidget(Gtk.Box):

    __gsignals__ = {
        'changed': (GObject.SignalFlags.RUN_LAST, None, (bool,)),
    }

    def __init__(self,
                 contact: types.ChatContactT,
                 mode: FunctionMode,
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

        if mode == FunctionMode.CHANGE_NICKNAME:
            heading_label.set_text(_('Change Nickname'))
            sub_label.set_text(_('Enter your new nickname'))
            assert isinstance(self._contact, GroupchatContact)
            self._entry.set_text(self._contact.nickname or '')

        elif mode == FunctionMode.KICK:
            heading_label.set_text(_('Kick %s') % data)
            sub_label.set_text(_('Reason (optional)'))

        elif mode == FunctionMode.BAN:
            heading_label.set_text(_('Ban %s') % data)
            sub_label.set_text(_('Reason (optional)'))

        elif mode == FunctionMode.PASSWORD_REQUEST:
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

        if self._mode == FunctionMode.CHANGE_NICKNAME:
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
                 mode: Optional[FunctionMode] = None,
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
        if mode == FunctionMode.JOIN_FAILED:
            heading_text = _('Failed to Join Group Chat')
        elif mode == FunctionMode.CREATION_FAILED:
            heading_text = _('Failed to Create Group Chat')
        elif mode == FunctionMode.CONFIG_FAILED:
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
