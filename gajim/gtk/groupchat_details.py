# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.i18n import _
from gajim.common.modules.contacts import GroupchatContact

from gajim.gtk.builder import get_builder
from gajim.gtk.contact_name_widget import ContactNameWidget
from gajim.gtk.groupchat_affiliation import GroupchatAffiliation
from gajim.gtk.groupchat_config import GroupchatConfig
from gajim.gtk.groupchat_info import GroupChatInfoScrolled
from gajim.gtk.groupchat_manage import GroupchatManage
from gajim.gtk.groupchat_outcasts import GroupchatOutcasts
from gajim.gtk.groupchat_settings import GroupChatSettings
from gajim.gtk.omemo_trust_manager import OMEMOTrustManager
from gajim.gtk.sidebar_switcher import SideBarSwitcher
from gajim.gtk.structs import RemoveHistoryActionParams


class GroupchatDetails(Gtk.ApplicationWindow):
    def __init__(self,
                 contact: GroupchatContact,
                 page: str | None = None
                 ) -> None:
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_resizable(True)
        self.set_default_size(-1, 600)
        self.set_title(_('Group Chat Details'))

        self.account = contact.account
        self._client = app.get_client(contact.account)

        self._contact = contact
        self._contact.connect('avatar-update', self._on_avatar_update)
        self._contact.connect('disco-info-update', self._on_disco_info_update)

        self._ui = get_builder('groupchat_details.ui')
        self._ui.connect_signals(self)

        self._switcher = SideBarSwitcher(width=250)
        self._switcher.set_stack(self._ui.main_stack, rows_visible=False)
        self._ui.main_grid.attach(self._switcher, 0, 0, 1, 1)
        self._ui.main_stack.connect('notify::visible-child-name',
                                    self._on_stack_child_changed)
        self.add(self._ui.main_grid)

        self._groupchat_manage: GroupchatManage | None = None

        self._add_groupchat_info()
        self._add_groupchat_settings()
        self._add_groupchat_encryption()

        if self._client.state.is_available and self._contact.is_joined:
            self._add_groupchat_manage()
            self._add_affiliations()
            self._add_outcasts()
            self._add_configuration()

        self._load_avatar()

        if page is not None:
            self._switcher.set_row(page)

        self.connect('key-press-event', self._on_key_press)
        self.connect('destroy', self._on_destroy)

        self.show_all()

    def _on_disco_info_update(self,
                              _contact: GroupchatContact,
                              _signal_name: str
                              ) -> None:

        self._groupchat_info.set_info_from_contact(self._contact)

    def _on_stack_child_changed(self,
                                _widget: Gtk.Stack,
                                _pspec: GObject.ParamSpec) -> None:

        name = self._ui.main_stack.get_visible_child_name()
        self._ui.header_revealer.set_reveal_child(name != 'information')

    def _on_edit_name_clicked(self, widget: Gtk.Button) -> None:
        self._switcher.set_row('information')
        self._groupchat_info.enable_edit_mode()

    def _load_avatar(self) -> None:
        scale = self.get_scale_factor()
        surface = self._contact.get_avatar(AvatarSize.VCARD_HEADER, scale)
        self._ui.header_image.set_from_surface(surface)

    def _on_avatar_update(self,
                          _contact: GroupchatContact,
                          _signal_name: str
                          ) -> None:
        self._load_avatar()
        assert self._groupchat_manage
        self._groupchat_manage.update_avatar()

    def _add_groupchat_manage(self) -> None:
        self._groupchat_manage = GroupchatManage(self.account,
                                                 self._contact)
        self._ui.manage_box.add(self._groupchat_manage)
        self._switcher.set_row_visible('manage', True)

    def _add_groupchat_info(self) -> None:
        self._groupchat_info = GroupChatInfoScrolled(
            self._contact.account, width=600, edit_mode=True)
        self._groupchat_info.connect('name-updated', self._on_contact_name_updated)
        self._groupchat_info.set_halign(Gtk.Align.FILL)
        self._groupchat_info.set_info_from_contact(self._contact)
        self._groupchat_info.set_subject(self._contact.subject)
        self._ui.info_box.add(self._groupchat_info)
        self._switcher.set_row_visible('information', True)

    def _add_groupchat_settings(self) -> None:
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        main_box.get_style_context().add_class('padding-18')

        settings_box = GroupChatSettings(self.account, self._contact.jid)
        main_box.add(settings_box)

        remove_history_button = Gtk.Button(label=_('Remove History…'))
        remove_history_button.set_halign(Gtk.Align.START)
        remove_history_button.get_style_context().add_class(
            'destructive-action')
        params = RemoveHistoryActionParams(
            account=self.account, jid=self._contact.jid)
        remove_history_button.set_action_name('app.remove-history')
        remove_history_button.set_action_target_value(
            params.to_variant())
        main_box.add(remove_history_button)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_vexpand(True)
        scrolled_window.set_policy(Gtk.PolicyType.NEVER,
                                   Gtk.PolicyType.AUTOMATIC)
        scrolled_window.add(main_box)

        self._ui.settings_box.add(scrolled_window)
        self._switcher.set_row_visible('settings', True)

    def _add_groupchat_encryption(self) -> None:
        if (self._contact.is_groupchat and
                self._contact.muc_context == 'public'):
            # OMEMO is not available for public group chats
            self._switcher.set_row_visible('encryption-omemo', False)
            return

        self._ui.encryption_box.add(
            OMEMOTrustManager(self._contact.account, self._contact))
        self._switcher.set_row_visible('encryption-omemo', True)

    def _add_affiliations(self) -> None:
        affiliations = GroupchatAffiliation(self._client, self._contact)
        self._ui.affiliation_box.add(affiliations)
        self._switcher.set_row_visible('affiliations', True)

    def _add_outcasts(self) -> None:
        affiliations = GroupchatOutcasts(self._client, self._contact)
        self._ui.outcasts_box.add(affiliations)
        self._switcher.set_row_visible('outcasts', True)

    def _add_configuration(self) -> None:
        config = GroupchatConfig(self._client, self._contact)
        self._ui.configuration_box.add(config)
        self._switcher.set_row_visible('config', True)

    def _on_contact_name_updated(self, _widget: ContactNameWidget, name: str) -> None:
        self._ui.contact_name_header_label.set_text(name)

    def _on_key_press(self,
                      _widget: GroupchatDetails,
                      event: Gdk.EventKey) -> None:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _on_destroy(self, _widget: GroupchatDetails) -> None:
        app.check_finalize(self)
