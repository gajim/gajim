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

from gajim.common import app
from gajim.common.modules import dataforms
from gajim.common import helpers
from gajim.common.connection_handlers_events import MessageOutgoingEvent
from gajim.gtk.dialogs import ErrorDialog
from gajim.gtk.dialogs import AspellDictError
from gajim.gtk.util import get_builder
from gajim.gtk.util import get_iconset_name_for
from gajim.gtk.util import get_completion_liststore
from gajim.gtk.util import move_window
from gajim.gtk.util import resize_window
from gajim.dataforms_widget import DataFormWidget
from gajim.conversation_textview import ConversationTextview


if app.is_installed('GSPELL'):
    from gi.repository import Gspell


class SingleMessageWindow:
    """
    SingleMessageWindow can send or show a received singled message depending on
    action argument which can be 'send' or 'receive'
    """
    # Keep a reference on windows so garbage collector don't restroy them
    instances = []  # type: List[SingleMessageWindow]
    def __init__(self, account, to='', action='', from_whom='', subject='',
            message='', resource='', session=None, form_node=None):
        self.instances.append(self)
        self.account = account
        self.action = action

        self.subject = subject
        self.message = message
        self.to = to
        self.from_whom = from_whom
        self.resource = resource
        self.session = session

        self.xml = get_builder('single_message_window.ui')
        self.window = self.xml.get_object('single_message_window')
        self.count_chars_label = self.xml.get_object('count_chars_label')
        self.from_label = self.xml.get_object('from_label')
        self.from_entry = self.xml.get_object('from_entry')
        self.to_label = self.xml.get_object('to_label')
        self.to_entry = self.xml.get_object('to_entry')
        self.subject_entry = self.xml.get_object('subject_entry')
        self.message_scrolledwindow = self.xml.get_object(
                'message_scrolledwindow')
        self.message_textview = self.xml.get_object('message_textview')
        self.message_tv_buffer = self.message_textview.get_buffer()
        self.conversation_scrolledwindow = self.xml.get_object(
                'conversation_scrolledwindow')
        self.conversation_textview = ConversationTextview(
            account, used_in_history_window=True)
        self.conversation_textview.tv.show()
        self.conversation_tv_buffer = self.conversation_textview.tv.get_buffer()
        self.xml.get_object('conversation_scrolledwindow').add(
                self.conversation_textview.tv)

        self.form_widget = None
        parent_box = self.xml.get_object('conversation_scrolledwindow').\
                           get_parent()
        if form_node:
            dataform = dataforms.extend_form(node=form_node)
            dataform.type_ = 'submit'
            self.form_widget = DataFormWidget(dataform)
            self.form_widget.show_all()
            parent_box.add(self.form_widget)
            parent_box.child_set_property(self.form_widget, 'position',
                parent_box.child_get_property(self.xml.get_object(
                'conversation_scrolledwindow'), 'position'))
            self.action = 'form'

        self.send_button = self.xml.get_object('send_button')
        self.reply_button = self.xml.get_object('reply_button')
        self.send_and_close_button = self.xml.get_object('send_and_close_button')
        self.cancel_button = self.xml.get_object('cancel_button')
        self.close_button = self.xml.get_object('close_button')
        self.message_tv_buffer.connect('changed', self.update_char_counter)
        if isinstance(to, list):
            jid = ', '.join([i[0].get_full_jid() for i in to])
            self.to_entry.set_text(jid)
            self.to_entry.set_sensitive(False)
        else:
            self.to_entry.set_text(to)

        if app.config.get('use_speller') and app.is_installed('GSPELL') and action == 'send':
            lang = app.config.get('speller_language')
            gspell_lang = Gspell.language_lookup(lang)
            if gspell_lang is None:
                AspellDictError(lang)
            else:
                spell_buffer = Gspell.TextBuffer.get_from_gtk_text_buffer(
                    self.message_textview.get_buffer())
                spell_buffer.set_spell_checker(Gspell.Checker.new(gspell_lang))
                spell_view = Gspell.TextView.get_from_gtk_text_view(
                    self.message_textview)
                spell_view.set_inline_spell_checking(True)
                spell_view.set_enable_language_menu(True)

        self.prepare_widgets_for(self.action)

        # set_text(None) raises TypeError exception
        if self.subject is None:
            self.subject = ''
        self.subject_entry.set_text(self.subject)


        if to == '':
            liststore = get_completion_liststore(self.to_entry)
            self.completion_dict = helpers.get_contact_dict_for_account(account)
            keys = sorted(self.completion_dict.keys())
            for jid in keys:
                contact = self.completion_dict[jid]
                status_icon = get_iconset_name_for(contact.show)
                liststore.append((status_icon, jid))
        else:
            self.completion_dict = {}
        self.xml.connect_signals(self)

        # get window position and size from config
        resize_window(self.window,
            app.config.get('single-msg-width'),
            app.config.get('single-msg-height'))
        move_window(self.window,
            app.config.get('single-msg-x-position'),
            app.config.get('single-msg-y-position'))

        self.window.show_all()

    def on_single_message_window_destroy(self, widget):
        self.instances.remove(self)
        c = app.contacts.get_contact_with_highest_priority(self.account,
                self.from_whom)
        if not c:
            # Groupchat is maybe already destroyed
            return
        if c.is_groupchat() and self.from_whom not in \
        app.interface.minimized_controls[self.account] and self.action == \
        'receive' and app.events.get_nb_roster_events(self.account,
        self.from_whom, types=['chat', 'normal']) == 0:
            app.interface.roster.remove_groupchat(self.from_whom, self.account)

    def set_cursor_to_end(self):
        end_iter = self.message_tv_buffer.get_end_iter()
        self.message_tv_buffer.place_cursor(end_iter)

    def save_pos(self):
        # save the window size and position
        x, y = self.window.get_position()
        app.config.set('single-msg-x-position', x)
        app.config.set('single-msg-y-position', y)
        width, height = self.window.get_size()
        app.config.set('single-msg-width', width)
        app.config.set('single-msg-height', height)

    def on_single_message_window_delete_event(self, window, ev):
        self.save_pos()

    def prepare_widgets_for(self, action):
        if len(app.connections) > 1:
            if action == 'send':
                title = _('Single Message using account %s') % self.account
            else:
                title = _('Single Message in account %s') % self.account
        else:
            title = _('Single Message')

        if action == 'send': # prepare UI for Sending
            title = _('Send %s') % title
            self.send_button.show()
            self.send_and_close_button.show()
            self.to_label.show()
            self.to_entry.show()
            self.reply_button.hide()
            self.from_label.hide()
            self.from_entry.hide()
            self.conversation_scrolledwindow.hide()
            self.message_scrolledwindow.show()

            if self.message: # we come from a reply?
                self.message_textview.grab_focus()
                self.cancel_button.hide()
                self.close_button.show()
                self.message_tv_buffer.set_text(self.message)
                GLib.idle_add(self.set_cursor_to_end)
            else: # we write a new message (not from reply)
                self.close_button.hide()
                if self.to: # do we already have jid?
                    self.subject_entry.grab_focus()

        elif action == 'receive': # prepare UI for Receiving
            title = _('Received %s') % title
            self.reply_button.show()
            self.from_label.show()
            self.from_entry.show()
            self.send_button.hide()
            self.send_and_close_button.hide()
            self.to_label.hide()
            self.to_entry.hide()
            self.conversation_scrolledwindow.show()
            self.message_scrolledwindow.hide()

            if self.message:
                self.conversation_textview.print_real_text(self.message)
            fjid = self.from_whom
            if self.resource:
                fjid += '/' + self.resource # Full jid of sender (with resource)
            self.from_entry.set_text(fjid)
            self.from_entry.set_property('editable', False)
            self.subject_entry.set_property('editable', False)
            self.reply_button.grab_focus()
            self.cancel_button.hide()
            self.close_button.show()
        elif action == 'form': # prepare UI for Receiving
            title = _('Form %s') % title
            self.send_button.show()
            self.send_and_close_button.show()
            self.to_label.show()
            self.to_entry.show()
            self.reply_button.hide()
            self.from_label.hide()
            self.from_entry.hide()
            self.conversation_scrolledwindow.hide()
            self.message_scrolledwindow.hide()

        self.window.set_title(title)

    def on_cancel_button_clicked(self, widget):
        self.save_pos()
        self.window.destroy()

    def on_close_button_clicked(self, widget):
        self.save_pos()
        self.window.destroy()

    def update_char_counter(self, widget):
        characters_no = self.message_tv_buffer.get_char_count()
        self.count_chars_label.set_text(str(characters_no))

    def send_single_message(self):
        if app.connections[self.account].connected <= 1:
            # if offline or connecting
            ErrorDialog(_('Connection not available'),
                _('Please make sure you are connected with "%s".') % self.account)
            return True
        if isinstance(self.to, list):
            sender_list = []
            for i in self.to:
                if i[0].resource:
                    sender_list.append(i[0].jid + '/' + i[0].resource)
                else:
                    sender_list.append(i[0].jid)
        else:
            sender_list = [j.strip() for j in self.to_entry.get_text().split(
                ',')]

        subject = self.subject_entry.get_text()
        begin, end = self.message_tv_buffer.get_bounds()
        message = self.message_tv_buffer.get_text(begin, end, True)

        if self.form_widget:
            form_node = self.form_widget.data_form
        else:
            form_node = None

        recipient_list = []

        for to_whom_jid in sender_list:
            if to_whom_jid in self.completion_dict:
                to_whom_jid = self.completion_dict[to_whom_jid].jid
            try:
                to_whom_jid = helpers.parse_jid(to_whom_jid)
            except helpers.InvalidFormat:
                ErrorDialog(_('Invalid JID'),
                    _('It is not possible to send a message to %s, this JID is not '
                    'valid.') % to_whom_jid)
                return True

            if '/announce/' in to_whom_jid:
                app.connections[self.account].send_motd(to_whom_jid, subject,
                    message)
                continue

            recipient_list.append(to_whom_jid)

        app.nec.push_outgoing_event(MessageOutgoingEvent(None,
            account=self.account, jid=recipient_list, message=message,
            type_='normal', subject=subject, form_node=form_node))

        self.subject_entry.set_text('') # we sent ok, clear the subject
        self.message_tv_buffer.set_text('') # we sent ok, clear the textview

    def on_send_button_clicked(self, widget):
        self.send_single_message()

    def on_reply_button_clicked(self, widget):
        # we create a new blank window to send and we preset RE: and to jid
        self.subject = _('RE: %s') % self.subject
        self.message = _('%s wrote:\n') % self.from_whom + self.message
        # add > at the begining of each line
        self.message = self.message.replace('\n', '\n> ') + '\n\n'
        self.window.destroy()
        SingleMessageWindow(self.account, to=self.from_whom, action='send',
            from_whom=self.from_whom, subject=self.subject, message=self.message,
            session=self.session)

    def on_send_and_close_button_clicked(self, widget):
        if self.send_single_message():
            return
        self.save_pos()
        self.window.destroy()

    def on_single_message_window_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Escape: # ESCAPE
            self.save_pos()
            self.window.destroy()
