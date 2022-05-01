#
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

from typing import cast
from typing import Any
from typing import Optional
from typing import Union

import logging

from gi.repository import Gio
from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import GLib

import cairo

from nbxmpp.errors import StanzaError
from nbxmpp.namespaces import Namespace
from nbxmpp.modules.vcard4 import VCard
from nbxmpp.modules.user_avatar import Avatar
from nbxmpp.task import Task

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.i18n import _
from gajim.common.i18n import Q_

from gajim.gui.avatar import clip_circle
from gajim.gui.avatar_selector import AvatarSelector
from gajim.gui.dialogs import ErrorDialog
from gajim.gui.filechoosers import AvatarChooserDialog
from gajim.gui.builder import get_builder
from gajim.gui.vcard_grid import VCardGrid
from gajim.gui.util import scroll_to_end

log = logging.getLogger('gajim.gui.profile')

MENU_DICT = {
    'fn': Q_('?profile:Full Name'),
    'bday': _('Birthday'),
    'gender': Q_('?profile:Gender'),
    'adr': Q_('?profile:Address'),
    'email': _('Email'),
    'impp': Q_('?profile:IM Address'),
    'tel': _('Phone No.'),
    'org': Q_('?profile:Organisation'),
    'title': Q_('?profile:Title'),
    'role': Q_('?profile:Role'),
    'url': _('URL'),
    'key': Q_('?profile:Public Encryption Key'),
    'note': Q_('?profile:Note'),
}


class ProfileWindow(Gtk.ApplicationWindow):
    def __init__(self, account: str) -> None:
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_resizable(True)
        self.set_default_size(700, 600)
        self.set_name('ProfileWindow')
        self.set_title(_('Profile'))

        self.account = account
        self._jid = app.get_jid_from_account(account)

        self._client = app.get_client(self.account)
        self._contact = self._client.get_module('Contacts').get_contact(
            self._jid)

        self._ui = get_builder('profile.ui')

        menu = Gio.Menu()
        for action, label in MENU_DICT.items():
            menu.append(label, 'win.add-' + action.lower())

        self._ui.add_entry_button.set_menu_model(menu)
        self._add_actions()

        self._avatar_selector: Optional[AvatarSelector] = None
        self._current_avatar: Optional[cairo.Surface] = None
        self._current_vcard: Optional[VCard] = None
        self._avatar_nick_public: Optional[bool] = None

        # False  - no change to avatar
        # None   - we want to delete the avatar
        # Avatar - upload new avatar
        self._new_avatar: Union[None, bool, Avatar] = False

        self._ui.nickname_entry.set_text(app.nicks[account])

        self._vcard_grid = VCardGrid(self.account)
        self._ui.profile_box.add(self._vcard_grid)

        self.add(self._ui.profile_stack)
        self.show_all()

        self._load_avatar()

        client = app.get_client(account)
        client.get_module('VCard4').request_vcard(
            callback=self._on_vcard_received)

        client.get_module('PubSub').get_access_model(
            Namespace.VCARD4_PUBSUB,
            callback=self._on_access_model_received,
            user_data=Namespace.VCARD4_PUBSUB)

        client.get_module('PubSub').get_access_model(
            Namespace.AVATAR_METADATA,
            callback=self._on_access_model_received,
            user_data=Namespace.AVATAR_METADATA)

        client.get_module('PubSub').get_access_model(
            Namespace.AVATAR_DATA,
            callback=self._on_access_model_received,
            user_data=Namespace.AVATAR_DATA)

        client.get_module('PubSub').get_access_model(
            Namespace.NICK,
            callback=self._on_access_model_received,
            user_data=Namespace.NICK)

        self._ui.connect_signals(self)
        self.connect('key-press-event', self._on_key_press)

        self.connect('destroy', self._on_destroy)

    def _on_destroy(self, *args: Any) -> None:
        self._avatar_selector = None
        self._ui.privacy_popover.destroy()
        app.check_finalize(self)

    def _on_access_model_received(self, task: Task) -> None:
        namespace = task.get_user_data()

        try:
            result = task.finish()
        except StanzaError as error:
            log.warning('Unable to get access model for %s: %s',
                        namespace, error)
            return

        access_model = result == 'open'

        if namespace == Namespace.VCARD4_PUBSUB:
            self._set_vcard_access_switch(access_model)
        else:
            if self._avatar_nick_public is None:
                self._avatar_nick_public = access_model
            else:
                self._avatar_nick_public = (self._avatar_nick_public or
                                            access_model)
            assert self._avatar_nick_public is not None
            self._set_avatar_nick_access_switch(self._avatar_nick_public)

    def _on_vcard_received(self, task: Task):
        try:
            self._current_vcard = cast(VCard, task.finish())
        except StanzaError as error:
            log.info('Error loading VCard: %s', error)
            self._current_vcard = VCard()

        if self._current_vcard is None:
            self._current_vcard = VCard()

        self._load_avatar()
        self._vcard_grid.set_vcard(self._current_vcard.copy())
        self._ui.profile_stack.set_visible_child_name('profile')
        self._ui.spinner.stop()

    def _load_avatar(self) -> None:
        scale = self.get_scale_factor()
        self._current_avatar = self._contact.get_avatar(AvatarSize.VCARD,
                                                        scale,
                                                        add_show=False)
        self._ui.avatar_image.set_from_surface(self._current_avatar)
        self._ui.avatar_image.show()

    def _on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> None:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _add_actions(self) -> None:
        for action in MENU_DICT:
            action_name = 'add-' + action.lower()
            act = Gio.SimpleAction.new(action_name, None)
            act.connect('activate', self._on_action)
            self.add_action(act)

    def _on_action(self,
                   action: Gio.SimpleAction,
                   _param: Optional[GLib.Variant]
                   ) -> None:
        name = action.get_name()
        key = name.split('-')[1]
        self._vcard_grid.add_new_property(key)
        GLib.idle_add(scroll_to_end, self._ui.scrolled)

    def _on_edit_clicked(self, *args: Any) -> None:
        self._vcard_grid.set_editable(True)
        self._ui.edit_button.hide()
        self._ui.add_entry_button.set_no_show_all(False)
        self._ui.add_entry_button.show_all()
        self._ui.cancel_button.show()
        self._ui.save_button.show()
        self._ui.remove_avatar_button.show()
        self._ui.edit_avatar_button.show()
        self._ui.nickname_entry.set_sensitive(True)
        self._ui.privacy_button.show()

    def _on_cancel_clicked(self, _button: Gtk.Button) -> None:
        self._vcard_grid.set_editable(False)
        self._ui.edit_button.show()
        self._ui.add_entry_button.hide()
        self._ui.cancel_button.hide()
        self._ui.save_button.hide()
        self._ui.remove_avatar_button.hide()
        self._ui.edit_avatar_button.hide()
        self._ui.privacy_button.hide()
        self._ui.nickname_entry.set_sensitive(False)
        self._ui.avatar_image.set_from_surface(self._current_avatar)
        self._ui.nickname_entry.set_text(app.nicks[self.account])
        self._vcard_grid.set_vcard(self._current_vcard.copy())
        self._new_avatar = False

    def _on_save_clicked(self, _button: Gtk.Button) -> None:
        self._ui.spinner.start()
        self._ui.profile_stack.set_visible_child_name('spinner')
        self._ui.add_entry_button.hide()
        self._ui.cancel_button.hide()
        self._ui.save_button.hide()
        self._ui.edit_button.show()
        self._ui.remove_avatar_button.hide()
        self._ui.edit_avatar_button.hide()
        self._ui.privacy_button.hide()
        self._ui.nickname_entry.set_sensitive(False)

        self._vcard_grid.validate()
        self._vcard_grid.sort()

        vcard = self._vcard_grid.get_vcard()
        self._current_vcard = vcard.copy()

        client = app.get_client(self.account)
        client.get_module('VCard4').set_vcard(
            self._current_vcard,
            public=self._ui.vcard_access.get_active(),
            callback=self._on_save_finished)

        public = self._ui.avatar_nick_access.get_active()

        if self._new_avatar is False:
            if self._avatar_nick_public != public:
                client.get_module('UserAvatar').set_access_model(public)

        else:
            # Only update avatar if it changed
            client.get_module('UserAvatar').set_avatar(
                self._new_avatar,
                public=public,
                callback=self._on_set_avatar)

        nick = GLib.markup_escape_text(self._ui.nickname_entry.get_text())
        client.get_module('UserNickname').set_nickname(nick, public=public)

        if not nick:
            nick = app.settings.get_account_setting(
                self.account, 'name')
        app.nicks[self.account] = nick

    def _on_set_avatar(self, task: Task) -> None:
        try:
            task.finish()
        except StanzaError as error:
            if self._new_avatar is None:
                # Trying to remove the avatar but the node does not exist
                if error.condition == 'item-not-found':
                    return

            title = _('Error while uploading avatar')
            text = error.get_text()

            if (error.condition == 'not-acceptable' and
                    error.app_condition == 'payload-too-big'):
                text = _('Avatar file size too big')

            ErrorDialog(title, text)

            self._ui.avatar_image.set_from_surface(self._current_avatar)
            self._new_avatar = False
            return

    def _on_remove_avatar(self, _button: Gtk.Button) -> None:
        scale = self.get_scale_factor()
        surface = self._contact.get_avatar(AvatarSize.VCARD,
                                           scale,
                                           add_show=False,
                                           default=True)

        self._ui.avatar_image.set_from_surface(surface)
        self._ui.remove_avatar_button.hide()
        self._new_avatar = None

    def _on_edit_avatar(self, button: Gtk.Button) -> None:
        def _on_file_selected(path: str) -> None:
            if self._avatar_selector is None:
                self._avatar_selector = AvatarSelector()
                self._ui.avatar_selector_box.add(self._avatar_selector)

            self._avatar_selector.prepare_crop_area(path)
            self._ui.avatar_update_button.set_sensitive(
                self._avatar_selector.get_prepared())
            self._ui.profile_stack.set_visible_child_name('avatar_selector')

        AvatarChooserDialog(_on_file_selected,
                            transient_for=button.get_toplevel())

    def _on_cancel_update_avatar(self, _button: Gtk.Button) -> None:
        self._ui.profile_stack.set_visible_child_name('profile')

    def _on_update_avatar(self, _button: Gtk.Button) -> None:
        assert self._avatar_selector
        success, data, width, height = self._avatar_selector.get_avatar_bytes()
        if not success:
            self._ui.profile_stack.set_visible_child_name('profile')
            ErrorDialog(_('Error while processing image'),
                        _('Failed to generate avatar.'))
            return

        assert data
        assert height
        assert width
        sha = app.app.avatar_storage.save_avatar(data)
        if sha is None:
            self._ui.profile_stack.set_visible_child_name('profile')
            ErrorDialog(_('Error while processing image'),
                        _('Failed to generate avatar.'))
            return

        self._new_avatar = Avatar()
        self._new_avatar.add_image_source(data, 'image/png', height, width)

        scale = self.get_scale_factor()
        surface = app.app.avatar_storage.surface_from_filename(
            sha, AvatarSize.VCARD, scale)
        if surface is None:
            return

        self._ui.avatar_image.set_from_surface(clip_circle(surface))
        self._ui.remove_avatar_button.show()
        self._ui.profile_stack.set_visible_child_name('profile')

    def _set_vcard_access_switch(self, state: bool) -> None:
        self._ui.vcard_access.set_active(state)
        self._ui.vcard_access_label.set_text(
            _('Everyone') if state else _('Contacts'))

    def _set_avatar_nick_access_switch(self, state: bool) -> None:
        self._ui.avatar_nick_access.set_active(state)
        self._ui.avatar_nick_access_label.set_text(
            _('Everyone') if state else _('Contacts'))

    def _access_switch_toggled(self, *args: Any) -> None:
        state = self._ui.vcard_access.get_active()
        self._set_vcard_access_switch(state)

        state = self._ui.avatar_nick_access.get_active()
        self._set_avatar_nick_access_switch(state)

    def _on_save_finished(self, task: Task) -> None:
        try:
            task.finish()
        except StanzaError as err:
            log.error('Could not publish VCard: %s', err)
            # TODO Handle error
            return

        self._vcard_grid.set_editable(False)
        self._ui.profile_stack.set_visible_child_name('profile')
        self._ui.spinner.stop()
