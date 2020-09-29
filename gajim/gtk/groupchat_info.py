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

import time

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk

from nbxmpp.namespaces import Namespace

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.i18n import Q_
from gajim.common.helpers import open_uri
from gajim.common.helpers import get_groupchat_name
from gajim.common.const import RFC5646_LANGUAGE_TAGS
from gajim.common.const import AvatarSize

from gajim.gtk.util import get_builder
from gajim.gtk.util import make_href_markup


MUC_FEATURES = {
    'muc_open': (
        'feather-globe-symbolic',
        Q_('?Group chat feature:Open'),
        _('Anyone can join this group chat')),
    'muc_membersonly': (
        'feather-user-check-symbolic',
        Q_('?Group chat feature:Members Only'),
        _('This group chat is restricted '
          'to members only')),
    'muc_nonanonymous': (
        'feather-shield-off-symbolic',
        Q_('?Group chat feature:Not Anonymous'),
        _('All other group chat participants '
          'can see your XMPP address')),
    'muc_semianonymous': (
        'feather-shield-symbolic',
        Q_('?Group chat feature:Semi-Anonymous'),
        _('Only moderators can see your XMPP address')),
    'muc_moderated': (
        'feather-mic-off-symbolic',
        Q_('?Group chat feature:Moderated'),
        _('Participants entering this group chat need '
          'to request permission to send messages')),
    'muc_unmoderated': (
        'feather-mic-symbolic',
        Q_('?Group chat feature:Not Moderated'),
        _('Participants entering this group chat are '
          'allowed to send messages')),
    'muc_public': (
        'feather-eye-symbolic',
        Q_('?Group chat feature:Public'),
        _('Group chat can be found via search')),
    'muc_hidden': (
        'feather-eye-off-symbolic',
        Q_('?Group chat feature:Hidden'),
        _('This group chat can not be found via search')),
    'muc_passwordprotected': (
        'feather-lock-symbolic',
        Q_('?Group chat feature:Password Required'),
        _('This group chat '
          'does require a password upon entry')),
    'muc_unsecured': (
        'feather-unlock-symbolic',
        Q_('?Group chat feature:No Password Required'),
        _('This group chat does not require '
          'a password upon entry')),
    'muc_persistent': (
        'feather-hard-drive-symbolic',
        Q_('?Group chat feature:Persistent'),
        _('This group chat persists '
          'even if there are no participants')),
    'muc_temporary': (
        'feather-clock-symbolic',
        Q_('?Group chat feature:Temporary'),
        _('This group chat will be destroyed '
          'once the last participant left')),
    'mam': (
        'feather-server-symbolic',
        Q_('?Group chat feature:Archiving'),
        _('Messages are archived on the server')),
}


class GroupChatInfoScrolled(Gtk.ScrolledWindow):
    def __init__(self, account=None, options=None):
        Gtk.ScrolledWindow.__init__(self)
        if options is None:
            options = {}

        self._minimal = options.get('minimal', False)

        self.set_size_request(options.get('width', 400), -1)
        self.set_halign(Gtk.Align.CENTER)

        if self._minimal:
            self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)
        else:
            self.set_vexpand(True)
            self.set_min_content_height(400)
            self.set_policy(Gtk.PolicyType.NEVER,
                            Gtk.PolicyType.AUTOMATIC)

        self._account = account
        self._info = None

        self._ui = get_builder('groupchat_info_scrolled.ui')
        self.add(self._ui.info_grid)
        self._ui.connect_signals(self)
        self.show_all()

    def get_account(self):
        return self._account

    def set_account(self, account):
        self._account = account

    def get_jid(self):
        return self._info.jid

    def set_author(self, author, epoch_timestamp=None):
        has_author = bool(author)
        if has_author and epoch_timestamp is not None:
            time_ = time.strftime('%c', time.localtime(epoch_timestamp))
            author = f'{author} - {time_}'

        self._ui.author.set_text(author or '')
        self._ui.author.set_visible(has_author)
        self._ui.author_label.set_visible(has_author)

    def set_subject(self, subject):
        has_subject = bool(subject)
        subject = GLib.markup_escape_text(subject or '')
        self._ui.subject.set_markup(make_href_markup(subject))
        self._ui.subject.set_visible(has_subject)
        self._ui.subject_label.set_visible(has_subject)

    def set_from_disco_info(self, info):
        self._info = info
        # Set name
        if self._account is None:
            name = info.muc_name
        else:
            con = app.connections[self._account]
            name = get_groupchat_name(con, info.jid)
        self._ui.name.set_text(name)
        self._ui.name.set_visible(True)

        # Set avatar
        surface = app.interface.avatar_storage.get_muc_surface(
            self._account,
            str(info.jid),
            AvatarSize.GROUP_INFO,
            self.get_scale_factor())
        self._ui.avatar_image.set_from_surface(surface)

        # Set description
        has_desc = bool(info.muc_description)
        self._ui.description.set_text(info.muc_description or '')
        self._ui.description.set_visible(has_desc)
        self._ui.description_label.set_visible(has_desc)

        # Set address
        self._ui.address.set_text(str(info.jid))

        if self._minimal:
            return

        # Set subject
        self.set_subject(info.muc_subject)

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
                self._ui.contact_box.add(self._get_contact_button(contact))

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

    def _add_features(self, features):
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

    def _on_copy_address(self, _button):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(f'xmpp:{self._info.jid}?join', -1)

    @staticmethod
    def _on_activate_log_link(button):
        open_uri(button.get_uri())
        return Gdk.EVENT_STOP

    def _on_activate_contact_link(self, button):
        open_uri(f'xmpp:{button.get_uri()}?message', account=self._account)
        return Gdk.EVENT_STOP

    @staticmethod
    def _on_activate_subject_link(_label, uri):
        # We have to use this, because the default GTK handler
        # is not cross-platform compatible
        open_uri(uri)
        return Gdk.EVENT_STOP

    @staticmethod
    def _get_feature_icon(icon, tooltip):
        image = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU)
        image.set_valign(Gtk.Align.CENTER)
        image.set_halign(Gtk.Align.END)
        image.set_tooltip_text(tooltip)
        return image

    @staticmethod
    def _get_feature_label(text):
        label = Gtk.Label(label=text, use_markup=True)
        label.set_halign(Gtk.Align.START)
        label.set_valign(Gtk.Align.START)
        return label

    def _get_contact_button(self, contact):
        button = Gtk.LinkButton.new(contact)
        button.set_halign(Gtk.Align.START)
        button.get_style_context().add_class('link-button')
        button.connect('activate-link', self._on_activate_contact_link)
        button.show()
        return button
