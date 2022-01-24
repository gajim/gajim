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

from typing import Any
from typing import Optional

from gi.repository import Gdk
from gi.repository import Gtk

from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common.helpers import get_contact_dict_for_account
from gajim.common.helpers import validate_jid
from gajim.common.i18n import _
from gajim.common.structs import OutgoingMessage

from .dialogs import ErrorDialog
from .builder import get_builder
from .util import get_completion_liststore
from .util import get_icon_name

if app.is_installed('GSPELL'):
    from gi.repository import Gspell  # pylint: disable=ungrouped-imports


class SingleMessageWindow(Gtk.ApplicationWindow):
    def __init__(self,
                 account: str,
                 recipients: Optional[str] = None
                 ) -> None:
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_size_request(500, -1)
        self.set_name('SingleMessageWindow')

        self.account = account
        self._client = app.get_client(account)
        self._recipients = recipients
        self._completion_dict = {}

        if len(app.connections) > 1:
            title = _('Single Message (%s)') % self.account
        else:
            title = _('Single Message')
        self.set_title(title)

        self._ui = get_builder('single_message_window.ui')
        self._message_buffer = self._ui.message_textview.get_buffer()
        self._message_buffer.connect('changed', self._update_char_counter)

        if recipients is not None:
            self._ui.recipients_entry.set_text(recipients)

        if (app.settings.get('use_speller') and
                app.is_installed('GSPELL')):
            lang = app.settings.get('speller_language')
            gspell_lang = Gspell.language_lookup(lang)
            if gspell_lang is None:
                gspell_lang = Gspell.language_get_default()
            spell_buffer = Gspell.TextBuffer.get_from_gtk_text_buffer(
                self._ui.message_textview.get_buffer())
            spell_buffer.set_spell_checker(Gspell.Checker.new(gspell_lang))
            spell_view = Gspell.TextView.get_from_gtk_text_view(
                self._ui.message_textview)
            spell_view.set_inline_spell_checking(True)
            spell_view.set_enable_language_menu(True)

        liststore = get_completion_liststore(self._ui.recipients_entry)
        self._completion_dict = get_contact_dict_for_account(account)
        for jid, contact in self._completion_dict.items():
            icon_name = get_icon_name(contact.show.value)
            liststore.append((icon_name, jid))

        self.add(self._ui.box)

        if self._recipients is not None:
            self._ui.message_textview.grab_focus()

        self.connect('key-press-event', self._on_key_press)
        self._ui.connect_signals(self)

        self.show_all()

    def _on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> None:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _on_changed(self, *args: Any) -> None:
        recipients = self._ui.recipients_entry.get_text()
        begin, end = self._message_buffer.get_bounds()
        message = self._message_buffer.get_text(begin, end, True)
        self._ui.send_button.set_sensitive(bool(recipients and message))

    def _update_char_counter(self, _widget: Gtk.TextView) -> None:
        characters_no = self._message_buffer.get_char_count()
        self._ui.count_chars_label.set_text(
            _('Characters typed: %s') % str(characters_no))
        self._on_changed()

    def _on_send_clicked(self, _widget: Gtk.Button) -> None:
        if not app.account_is_available(self.account):
            ErrorDialog(_('Not Connected'),
                        _('Please make sure you are connected with "%s".') %
                        self.account)
            return

        jids = self._ui.recipients_entry.get_text()
        subject = self._ui.subject_entry.get_text()
        begin, end = self._message_buffer.get_bounds()
        message = self._message_buffer.get_text(begin, end, True)

        recipient_list: list[JID] = []
        for jid in jids.split(','):
            try:
                jid = validate_jid(jid.strip())
            except ValueError as err:
                ErrorDialog(
                    _('Cannot Send Message'),
                    _('XMPP Address "%(jid)s" is invalid.\n%(error)s') % {
                        'jid': jid, 'error': err})
                return

            if '/announce/' in str(jid):
                self._client.get_module('Announce').set_announce(
                    jid, subject, message)
                continue

            recipient_list.append(jid)

        message = OutgoingMessage(account=self.account,
                                  contact=None,
                                  message=message,
                                  type_='normal',
                                  subject=subject)
        self._client.send_messages(recipient_list, message)
        self.destroy()
