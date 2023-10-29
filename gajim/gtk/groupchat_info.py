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

import logging
import time

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk
from nbxmpp import JID
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import DiscoInfo
from nbxmpp.structs import MucSubject

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.const import RFC5646_LANGUAGE_TAGS
from gajim.common.const import XmppUriQuery
from gajim.common.helpers import get_groupchat_name
from gajim.common.helpers import open_uri
from gajim.common.i18n import _
from gajim.common.i18n import p_
from gajim.common.modules.contacts import GroupchatContact

from gajim.gtk.builder import get_builder
from gajim.gtk.util import make_href_markup

log = logging.getLogger('gajim.gtk.groupchat_info')

MUC_FEATURES = {
    'muc_open': (
        'feather-globe-symbolic',
        p_('Group chat feature', 'Open'),
        _('Anyone can join this group chat')),
    'muc_membersonly': (
        'feather-user-check-symbolic',
        p_('Group chat feature', 'Members Only'),
        _('This group chat is restricted '
          'to members only')),
    'muc_nonanonymous': (
        'feather-shield-off-symbolic',
        p_('Group chat feature', 'Not Anonymous'),
        _('All other group chat participants '
          'can see your XMPP address')),
    'muc_semianonymous': (
        'feather-shield-symbolic',
        p_('Group chat feature', 'Semi-Anonymous'),
        _('Only moderators can see your XMPP address')),
    'muc_moderated': (
        'feather-mic-off-symbolic',
        p_('Group chat feature', 'Moderated'),
        _('Participants entering this group chat need '
          'to request permission to send messages')),
    'muc_unmoderated': (
        'feather-mic-symbolic',
        p_('Group chat feature', 'Not Moderated'),
        _('Participants entering this group chat are '
          'allowed to send messages')),
    'muc_public': (
        'feather-eye-symbolic',
        p_('Group chat feature', 'Public'),
        _('Group chat can be found via search')),
    'muc_hidden': (
        'feather-eye-off-symbolic',
        p_('Group chat feature', 'Hidden'),
        _('This group chat can not be found via search')),
    'muc_passwordprotected': (
        'feather-lock-symbolic',
        p_('Group chat feature', 'Password Required'),
        _('This group chat '
          'does require a password upon entry')),
    'muc_unsecured': (
        'feather-unlock-symbolic',
        p_('Group chat feature', 'No Password Required'),
        _('This group chat does not require '
          'a password upon entry')),
    'muc_persistent': (
        'feather-hard-drive-symbolic',
        p_('Group chat feature', 'Persistent'),
        _('This group chat persists '
          'even if there are no participants')),
    'muc_temporary': (
        'feather-clock-symbolic',
        p_('Group chat feature', 'Temporary'),
        _('This group chat will be destroyed '
          'once the last participant left')),
    'mam': (
        'feather-server-symbolic',
        p_('Group chat feature', 'Archiving'),
        _('Messages are archived on the server')),
}


class GroupChatInfoScrolled(Gtk.ScrolledWindow):
    def __init__(self,
                 account: str | None = None,
                 width: int = 300,
                 minimal: bool = False
                 ) -> None:
        Gtk.ScrolledWindow.__init__(self)
        self.set_size_request(width, -1)
        self.set_halign(Gtk.Align.CENTER)

        self._minimal = minimal

        if minimal:
            self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)
        else:
            self.set_vexpand(True)
            self.set_hexpand(True)
            self.set_propagate_natural_width(True)
            self.set_min_content_height(400)
            self.set_policy(Gtk.PolicyType.NEVER,
                            Gtk.PolicyType.AUTOMATIC)

        self._account = account
        self._info: DiscoInfo | None = None

        self._ui = get_builder('groupchat_info_scrolled.ui')
        self.add(self._ui.info_grid)
        self._ui.connect_signals(self)
        self.show_all()

    def get_account(self) -> str | None:
        return self._account

    def set_account(self, account: str) -> None:
        self._account = account

    def get_jid(self) -> JID | None:
        jid = self._ui.address_label.get_text()
        if not jid:
            return None

        return JID.from_string(self._ui.address_label.get_text())

    def set_subject(self, muc_subject: MucSubject | None) -> None:
        if muc_subject is None:
            return

        author = muc_subject.author
        has_author = bool(author)
        if has_author and muc_subject.timestamp is not None:
            time_ = time.strftime('%c', time.localtime(muc_subject.timestamp))
            author = f'{muc_subject.author} - {time_}'

        self._ui.author.set_text(author or '')
        self._ui.author.set_visible(has_author)
        self._ui.author_label.set_visible(has_author)

        has_subject = bool(muc_subject.text)
        subject = GLib.markup_escape_text(muc_subject.text)
        self._ui.subject.set_markup(make_href_markup(subject))
        self._ui.subject.set_visible(has_subject)
        self._ui.subject_label.set_visible(has_subject)

    def set_info_from_contact(self, contact: GroupchatContact) -> None:
        disco_info = contact.get_disco()
        if disco_info is not None:
            self.set_from_disco_info(disco_info)
            return

        self._ui.address.set_text(str(contact.jid))
        self._ui.address.set_tooltip_text(str(contact.jid))
        self._ui.address_copy_button.set_sensitive(True)

    def set_from_disco_info(self, info: DiscoInfo) -> None:
        self._info = info
        # Set name
        if self._account is None:
            name = info.muc_name
        else:
            client = app.get_client(self._account)
            name = get_groupchat_name(client, info.jid)
            contact = client.get_module('Contacts').get_contact(
                info.jid, groupchat=True)
            surface = contact.get_avatar(
                AvatarSize.GROUP_INFO,
                self.get_scale_factor())
            self._ui.avatar_image.set_from_surface(surface)

        self._ui.name.set_text(name)
        self._ui.name.set_visible(True)

        # Set description
        has_desc = bool(info.muc_description)
        self._ui.description.set_text(info.muc_description or '')
        self._ui.description.set_visible(has_desc)
        self._ui.description_label.set_visible(has_desc)

        # Set address
        self._ui.address.set_text(str(info.jid))
        self._ui.address.set_tooltip_text(str(info.jid))
        self._ui.address_copy_button.set_sensitive(True)

        if self._minimal:
            return

        # Set user
        has_users = info.muc_users is not None
        self._ui.users.set_text(info.muc_users or '')
        self._ui.users.set_visible(has_users)
        self._ui.users_image.set_visible(has_users)

        # Set contacts
        self._ui.contact_box.foreach(self._ui.contact_box.remove)
        has_contacts = bool(info.muc_contacts)
        if has_contacts:
            for contact in info.muc_contacts:
                try:
                    jid = JID.from_string(contact).new_as_bare()
                except Exception as e:
                    log.debug('Bad MUC contact address %s: %s', contact, str(e))
                else:
                    self._ui.contact_box.add(self._get_contact_button(jid))

        self._ui.contact_box.set_visible(has_contacts)
        self._ui.contact_label.set_visible(has_contacts)

        # Set discussion logs
        has_log_uri = bool(info.muc_log_uri)
        self._ui.logs.set_uri(info.muc_log_uri or '')
        self._ui.logs.set_label(_('Website'))
        self._ui.logs.set_visible(has_log_uri)
        self._ui.logs_label.set_visible(has_log_uri)

        # Set room language
        has_lang = bool(info.muc_lang)
        lang = ''
        if has_lang:
            lang = RFC5646_LANGUAGE_TAGS.get(info.muc_lang, info.muc_lang)
        self._ui.lang.set_text(lang)
        self._ui.lang.set_visible(has_lang)
        self._ui.lang_image.set_visible(has_lang)

        self._add_features(info.features)

    def _add_features(self, features: list[str]) -> None:
        grid = self._ui.info_grid
        for row in range(30, 9, -1):
            # Remove everything from row 30 to 10
            # We probably will never have 30 rows and
            # there is no method to count grid rows
            grid.remove_row(row)
        features = list(features)

        if Namespace.MAM_2 in features:
            features.append('mam')

        row = 10

        for feature in MUC_FEATURES:
            if feature in features:
                icon, name, tooltip = MUC_FEATURES.get(feature,
                                                       (None, None, None))
                if icon is None:
                    continue
                grid.attach(self._get_feature_icon(icon, tooltip), 0, row, 1, 1)
                grid.attach(self._get_feature_label(name), 1, row, 1, 1)
                row += 1
        grid.show_all()

    def _on_copy_address(self, _button: Gtk.Button) -> None:
        jid = JID.from_string(self._ui.address_label.get_text())
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(jid.to_iri(XmppUriQuery.JOIN.value), -1)

    @staticmethod
    def _on_activate_log_link(button: Gtk.LinkButton) -> int:
        open_uri(button.get_uri())
        return Gdk.EVENT_STOP

    def _on_activate_contact_link(self, button: Gtk.LinkButton) -> int:
        open_uri(button.get_uri(), account=self._account)
        return Gdk.EVENT_STOP

    @staticmethod
    def _on_activate_subject_link(_label: Gtk.Label, uri: str) -> int:
        # We have to use this, because the default GTK handler
        # is not cross-platform compatible
        open_uri(uri)
        return Gdk.EVENT_STOP

    @staticmethod
    def _get_feature_icon(icon: str, tooltip: str) -> Gtk.Image:
        image = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU)
        image.set_valign(Gtk.Align.CENTER)
        image.set_halign(Gtk.Align.END)
        image.set_tooltip_text(tooltip)
        return image

    @staticmethod
    def _get_feature_label(text: str) -> Gtk.Label:
        label = Gtk.Label(label=text, use_markup=True)
        label.set_halign(Gtk.Align.START)
        label.set_valign(Gtk.Align.START)
        return label

    def _get_contact_button(self, contact: JID) -> Gtk.Button:
        button = Gtk.LinkButton(contact.to_iri(XmppUriQuery.MESSAGE.value),
                                label=str(contact))
        button.set_halign(Gtk.Align.START)
        button.get_style_context().add_class('link-button')
        button.connect('activate-link', self._on_activate_contact_link)
        button.show()
        return button
