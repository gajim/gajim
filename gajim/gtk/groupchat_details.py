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

from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import Gtk

from nbxmpp.const import Affiliation
from nbxmpp.structs import MucSubject

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.i18n import _
from gajim.common.modules.contacts import GroupchatContact
from gajim.gtk.groupchat_affiliation import GroupchatAffiliation
from gajim.gtk.groupchat_outcasts import GroupchatOutcasts

from .builder import get_builder
from .groupchat_info import GroupChatInfoScrolled
from .groupchat_settings import GroupChatSettings
from .sidebar_switcher import SideBarSwitcher


class GroupchatDetails(Gtk.ApplicationWindow):
    def __init__(self,
                 contact: GroupchatContact,
                 subject: str,
                 page: Optional[str] = None
                 ) -> None:
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_resizable(True)
        self.set_default_size(-1, 600)
        self.set_title(_('Groupchat Details'))

        self.account = contact.account
        self._client = app.get_client(contact.account)
        self._subject_text = subject
        self._contact = contact
        self._contact.connect(
            'room-subject', self._on_room_subject)

        self._ui = get_builder('groupchat_details.ui')
        self._ui.connect_signals(self)

        self._switcher = SideBarSwitcher()
        self._switcher.set_stack(self._ui.main_stack)
        self._ui.main_grid.attach(self._switcher, 0, 0, 1, 1)
        self._ui.main_stack.connect('notify::visible-child-name',
                                    self._on_stack_child_changed)
        self.add(self._ui.main_grid)

        self._add_groupchat_info()
        self._add_groupchat_settings()
        self._add_affiliations()
        self._add_outcasts()

        self._prepare_subject()
        self._load_avatar()
        self._ui.name_entry.set_text(contact.name)

        if page is not None:
            self._switcher.set_row(page)

        self.connect('key-press-event', self._on_key_press)
        self.connect('destroy', self._on_destroy)

        self.show_all()

    @property
    def disco_info(self):
        return app.storage.cache.get_last_disco_info(self._contact.jid)

    def _on_stack_child_changed(self,
                                _widget: Gtk.Stack,
                                _pspec: GObject.ParamSpec) -> None:

        name = self._ui.main_stack.get_visible_child_name()
        self._ui.header_revealer.set_reveal_child(name != 'information')

    def _on_edit_name_toggled(self, widget: Gtk.ToggleButton) -> None:
        active = widget.get_active()
        self._ui.name_entry.set_sensitive(active)
        if active:
            self._ui.name_entry.grab_focus()

        name = self._ui.name_entry.get_text()
        self._client.get_module('Bookmarks').modify(
            self._contact.jid, name=name)

    def _load_avatar(self) -> None:
        scale = self.get_scale_factor()
        surface = self._contact.get_avatar(AvatarSize.VCARD_HEADER, scale)
        self._ui.header_image.set_from_surface(surface)

    def _prepare_subject(self) -> None:
        self._ui.subject_textview.get_buffer().set_text(self._subject_text)

        joined = self._contact.is_joined
        change_allowed = self._is_subject_change_allowed()
        self._ui.subject_textview.set_sensitive(joined and change_allowed)

    def _is_subject_change_allowed(self) -> bool:
        contact = self._contact.get_self()
        if contact is None:
            return False

        if contact.affiliation in (Affiliation.OWNER, Affiliation.ADMIN):
            return True

        if self.disco_info is None:
            return False
        return self.disco_info.muc_subjectmod or False

    def _on_subject_text_changed(self, buffer_: Gtk.TextBuffer) -> None:
        text = buffer_.get_text(buffer_.get_start_iter(),
                                buffer_.get_end_iter(),
                                False)
        self._ui.subject_change_button.set_sensitive(
            text != self._subject_text)

    def _on_subject_change_clicked(self, _button: Gtk.Button) -> None:
        buffer_ = self._ui.subject_textview.get_buffer()
        subject = buffer_.get_text(buffer_.get_start_iter(),
                                   buffer_.get_end_iter(),
                                   False)
        self._client.get_module('MUC').set_subject(self._contact.jid, subject)

    def _on_room_subject(self,
                         _contact: GroupchatContact,
                         _signal_name: str,
                         subject: Optional[MucSubject]
                         ) -> None:
        if subject is None:
            return

        self._subject_text = subject.text
        self._ui.subject_textview.get_buffer().set_text(subject.text)

    def _add_groupchat_info(self) -> None:
        groupchat_info = GroupChatInfoScrolled(self._contact.account, width=600)
        groupchat_info.set_halign(Gtk.Align.FILL)
        disco_info = self._contact.get_disco()
        assert disco_info is not None
        groupchat_info.set_from_disco_info(disco_info)
        groupchat_info.set_subject(self._contact.subject)
        self._ui.info_box.add(groupchat_info)

    def _add_groupchat_settings(self) -> None:
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_vexpand(True)
        scrolled_window.set_policy(Gtk.PolicyType.NEVER,
                                   Gtk.PolicyType.AUTOMATIC)

        settings_box = GroupChatSettings(self.account, self._contact.jid)
        scrolled_window.add(settings_box)
        self._ui.settings_box.add(scrolled_window)

    def _add_affiliations(self) -> None:
        affiliations = GroupchatAffiliation(self._client, self._contact)
        self._ui.affiliation_box.add(affiliations)

    def _add_outcasts(self) -> None:
        affiliations = GroupchatOutcasts(self._client, self._contact)
        self._ui.outcasts_box.add(affiliations)

    def _on_key_press(self,
                      _widget: GroupchatDetails,
                      event: Gdk.EventKey) -> None:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _on_destroy(self, _widget: GroupchatDetails) -> None:
        app.check_finalize(self)
