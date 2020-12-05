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

from typing import List  # pylint: disable=unused-import

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk

from gajim import vcard
from gajim.common import app
from gajim.common import helpers
from gajim.common.i18n import _
from gajim.common.structs import OutgoingMessage

from gajim.conversation_textview import ConversationTextview

from .dialogs import ErrorDialog
from .util import get_builder
from .util import get_icon_name
from .util import get_completion_liststore
from .util import move_window
from .util import resize_window

if app.is_installed('GSPELL'):
    from gi.repository import Gspell  # pylint: disable=ungrouped-imports


class SingleMessageWindow(Gtk.ApplicationWindow):
    """
    SingleMessageWindow can send or show a received singled message depending on
    action argument which can be 'send' or 'receive'
    """
    def __init__(self, account, to='', action='', from_whom='', subject='',
                 message='', resource='', session=None):
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_title(_('Send Single Message'))
        self.set_name('SendSingleMessageWindow')
        self.account = account
        self._action = action

        self._subject = subject
        self._message = message
        self._to = to
        self._from_whom = from_whom
        self._resource = resource
        self._session = session

        self._ui = get_builder('single_message_window.ui')
        self._message_tv_buffer = self._ui.message_textview.get_buffer()
        self._conversation_textview = ConversationTextview(
            account, used_in_history_window=True)
        self._conversation_textview.tv.show()
        self._conversation_textview.tv.set_left_margin(6)
        self._conversation_textview.tv.set_right_margin(6)
        self._conversation_textview.tv.set_top_margin(6)
        self._conversation_textview.tv.set_bottom_margin(6)
        self._ui.conversation_scrolledwindow.add(
            self._conversation_textview.tv)

        self._message_tv_buffer.connect('changed', self._update_char_counter)
        if isinstance(to, list):
            jid = ', '.join([i[0].jid for i in to])
            self._ui.to_entry.set_text(jid)
        else:
            self._ui.to_entry.set_text(to)

        if (app.settings.get('use_speller') and
                app.is_installed('GSPELL') and
                action == 'send'):
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

        self._prepare_widgets_for(self._action)

        # set_text(None) raises TypeError exception
        if self._subject is None:
            self._subject = _('(No subject)')
        self._ui.subject_entry.set_text(self._subject)
        self._ui.subject_from_entry_label.set_text(self._subject)

        if to == '':
            liststore = get_completion_liststore(self._ui.to_entry)
            self._completion_dict = helpers.get_contact_dict_for_account(
                account)
            keys = sorted(self._completion_dict.keys())
            for jid in keys:
                contact = self._completion_dict[jid]
                status_icon = get_icon_name(contact.show)
                liststore.append((status_icon, jid))
        else:
            self._completion_dict = {}

        self.add(self._ui.box)

        self.connect('delete-event', self._on_delete)
        self.connect('destroy', self._on_destroy)
        self.connect('key-press-event', self._on_key_press_event)

        self._ui.to_entry.connect('changed', self._on_to_entry_changed)
        self._ui.connect_signals(self)

        # get window position and size from config
        resize_window(self,
                      app.settings.get('single-msg-width'),
                      app.settings.get('single-msg-height'))
        move_window(self,
                    app.settings.get('single-msg-x-position'),
                    app.settings.get('single-msg-y-position'))

        self.show_all()

    def _set_cursor_to_end(self):
        end_iter = self._message_tv_buffer.get_end_iter()
        self._message_tv_buffer.place_cursor(end_iter)

    def _save_position(self):
        # save the window size and position
        x_pos, y_pos = self.get_position()
        app.settings.set('single-msg-x-position', x_pos)
        app.settings.set('single-msg-y-position', y_pos)
        width, height = self.get_size()
        app.settings.set('single-msg-width', width)
        app.settings.set('single-msg-height', height)

    def _on_to_entry_changed(self, _widget):
        entry = self._ui.to_entry.get_text()
        is_empty = bool(not entry == '' and not ',' in entry)
        self._ui.show_contact_info_button.set_sensitive(is_empty)

    def _prepare_widgets_for(self, action):
        if len(app.connections) > 1:
            if action == 'send':
                title = _('Single Message using account %s') % self.account
            else:
                title = _('Single Message in account %s') % self.account
        else:
            title = _('Single Message')

        if action == 'send': # prepare UI for Sending
            title = _('Send %s') % title
            self._ui.send_button.show()
            self._ui.send_and_close_button.show()
            self._ui.reply_button.hide()
            self._ui.close_button.hide()

            self._ui.send_grid.show()
            self._ui.received_grid.hide()

            if self._message: # we come from a reply?
                self._ui.show_contact_info_button.set_sensitive(True)
                self._ui.message_textview.grab_focus()
                self._message_tv_buffer.set_text(self._message)
                GLib.idle_add(self._set_cursor_to_end)
            else: # we write a new message (not from reply)
                if self._to: # do we already have jid?
                    self._ui.subject_entry.grab_focus()

        elif action == 'receive': # prepare UI for Receiving
            title = _('Received %s') % title
            self._ui.reply_button.show()
            self._ui.close_button.show()
            self._ui.send_button.hide()
            self._ui.send_and_close_button.hide()
            self._ui.reply_button.grab_focus()

            self._ui.received_grid.show()
            self._ui.send_grid.hide()

            if self._message:
                self._conversation_textview.print_real_text(self._message)
            fjid = self._from_whom
            if self._resource:
                fjid += '/' + self._resource
            self._ui.from_entry_label.set_text(fjid)

        self.set_title(title)

    def _update_char_counter(self, _widget):
        characters_no = self._message_tv_buffer.get_char_count()
        self._ui.count_chars_label.set_text(
            _('Characters typed: %s') % str(characters_no))

    def _send_single_message(self):
        if not app.account_is_available(self.account):
            # if offline or connecting
            ErrorDialog(_('Connection not available'),
                        _('Please make sure you are connected with "%s".') %
                        self.account)
            return True
        if isinstance(self._to, list):
            sender_list = []
            for i in self._to:
                if i[0].resource:
                    sender_list.append(i[0].jid + '/' + i[0].resource)
                else:
                    sender_list.append(i[0].jid)
        else:
            sender_list = [j.strip() for j
                           in self._ui.to_entry.get_text().split(',')]

        subject = self._ui.subject_entry.get_text()
        begin, end = self._message_tv_buffer.get_bounds()
        message = self._message_tv_buffer.get_text(begin, end, True)

        recipient_list = []

        for to_whom_jid in sender_list:
            if to_whom_jid in self._completion_dict:
                to_whom_jid = self._completion_dict[to_whom_jid].jid
            try:
                to_whom_jid = helpers.parse_jid(to_whom_jid)
            except helpers.InvalidFormat:
                ErrorDialog(
                    _('Invalid XMPP Address'),
                    _('It is not possible to send a message to %s, this '
                      'XMPP Address is not valid.') % to_whom_jid)
                return True

            if '/announce/' in to_whom_jid:
                con = app.connections[self.account]
                con.get_module('Announce').set_announce(
                    to_whom_jid, subject, message)
                continue

            recipient_list.append(to_whom_jid)

        message = OutgoingMessage(account=self.account,
                                  contact=None,
                                  message=message,
                                  type_='normal',
                                  subject=subject)
        con = app.connections[self.account]
        con.send_messages(recipient_list, message)

        self._ui.subject_entry.set_text('') # we sent ok, clear the subject
        self._message_tv_buffer.set_text('') # we sent ok, clear the textview
        return False

    def _on_destroy(self, _widget):
        contact = app.contacts.get_contact_with_highest_priority(
            self.account, self._from_whom)
        if not contact:
            # Groupchat is maybe already destroyed
            return
        controls = app.interface.minimized_controls[self.account]
        events = app.events.get_nb_roster_events(self.account,
                                                 self._from_whom,
                                                 types=['chat', 'normal'])
        if (contact.is_groupchat and
                self._from_whom not in controls and
                self._action == 'receive' and
                events == 0):
            app.interface.roster.remove_groupchat(self._from_whom, self.account)

    def _on_delete(self, *args):
        self._save_position()

    def _on_contact_info_clicked(self, _widget):
        """
        Ask for vCard
        """
        entry = self._ui.to_entry.get_text().strip()

        keys = sorted(self._completion_dict.keys())
        for key in keys:
            contact = self._completion_dict[key]
            if entry in key:
                entry = contact.jid
                break

        if entry in app.interface.instances[self.account]['infos']:
            app.interface.instances[self.account]['infos'][entry].\
                window.present()
        else:
            contact = app.contacts.create_contact(jid=entry,
                                                  account=self.account)
            app.interface.instances[self.account]['infos'][entry] = \
                     vcard.VcardWindow(contact, self.account)
            # Remove xmpp page
            app.interface.instances[self.account]['infos'][entry].xml.\
                     get_object('information_notebook').remove_page(0)

    def _on_close_clicked(self, _widget):
        self._save_position()
        self.destroy()

    def _on_send_clicked(self, _widget):
        self._send_single_message()

    def _on_reply_clicked(self, _widget):
        # we create a new blank window to send and we preset RE: and to jid
        self._subject = _('RE: %s') % self._subject
        self._message = _('%s wrote:\n') % self._from_whom + self._message
        # add > at the beginning of each line
        self._message = self._message.replace('\n', '\n> ') + '\n\n'
        self.destroy()
        SingleMessageWindow(self.account,
                            to=self._from_whom,
                            action='send',
                            from_whom=self._from_whom,
                            subject=self._subject,
                            message=self._message,
                            session=self._session)

    def _on_send_and_close_clicked(self, _widget):
        if self._send_single_message():
            return
        self._save_position()
        self.destroy()

    def _on_key_press_event(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape: # ESCAPE
            self._save_position()
            self.destroy()
