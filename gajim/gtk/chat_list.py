import logging

from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.const import KindConstant
from gajim.common.i18n import _
from gajim.common.helpers import get_groupchat_name
from gajim.common.helpers import get_group_chat_nick
from gajim.common.helpers import get_uf_relative_time

log = logging.getLogger('gajim.gtk.chatlist')


class ChatList(Gtk.ListBox):
    def __init__(self, workspace_id):
        Gtk.ListBox.__init__(self)

        self._chats = {}
        self._current_filter_text = ''
        self._workspace_id = workspace_id

        self.get_style_context().add_class('chatlist')
        self.connect('destroy', self._on_destroy)

        self.show_all()

        self.set_filter_func(self._filter_func)

        self._timer_id = GLib.timeout_add_seconds(60, self._update_timer)

    def _on_destroy(self):
        GLib.source_remove(self._timer_id)

    def _update_timer(self):
        self.update_time()
        return True

    def _filter_func(self, row):
        if not self._current_filter_text:
            return True
        return self._current_filter_text in row.jid

    def set_filter_text(self, text):
        self._current_filter_text = text
        self.invalidate_filter()

    def get_chat_type(self, account, jid):
        row = self._chats.get((account, jid))
        return row.type

    def add_chat(self, account, jid, type_):
        if self._chats.get((account, jid)) is not None:
            # Chat is already in the List
            return

        row = ChatRow(self._workspace_id, account, jid, type_)
        self._chats[(account, jid)] = row
        self.add(row)

    def select_chat(self, account, jid):
        row = self._chats[(account, jid)]
        self.select_row(row)

    def remove_chat(self, account, jid):
        row = self._chats.pop((account, jid))
        self.remove(row)
        row.destroy()

    def get_active_chat(self):
        row = self.get_selected_row()
        if row is None:
            return None

        return (row.account, row.jid)

    def contains_chat(self, account, jid):
        return self._chats.get((account, jid)) is not None

    def get_open_chats(self):
        open_chats = []
        for key, value in self._chats.items():
            open_chats.append(key + (value.type,))
        return open_chats

    def update_time(self):
        for _, row in self._chats.items():
            row.update_time()

    def update(self, event):
        row = self._chats.get((event.account, event.jid))
        row.add_unread()
        row.set_last_message_text('Me', event.msgtxt)


class ChatRow(Gtk.ListBoxRow):
    def __init__(self, workspace_id, account, jid, type_):
        Gtk.ListBoxRow.__init__(self)

        self.account = account
        self.jid = jid
        self.workspace_id = workspace_id
        self.type = type_

        self._timestamp = None
        self._unread_count = 0

        self.get_style_context().add_class('chatlist-row')

        self.connect('state-flags-changed', self._on_state_flags_changed)

        account_bar = Gtk.Box()
        account_bar.set_size_request(6, -1)
        account_bar.set_no_show_all(True)
        account_class = app.css_config.get_dynamic_class(account)
        account_bar.get_style_context().add_class(account_class)
        account_bar.get_style_context().add_class(
            'account-identifier-bar')
        if len(app.get_enabled_accounts_with_labels()) > 1:
            account_bar.show()

        contact = app.contacts.get_contact(account, jid)

        scale = self.get_scale_factor()
        if contact:
            if contact.is_groupchat:
                avatar = app.contacts.get_avatar(account,
                                                jid,
                                                AvatarSize.ROSTER,
                                                scale)
                con = app.connections[account]
                name = get_groupchat_name(con, jid)
            else:
                avatar = app.contacts.get_avatar(account,
                                                 contact.jid,
                                                 AvatarSize.ROSTER,
                                                 scale,
                                                 contact.show)
                name = contact.get_shown_name()
        else:
            avatar = app.contacts.get_avatar(account,
                                             jid,
                                             AvatarSize.ROSTER,
                                             scale)
            name = jid

        avatar_image = Gtk.Image.new_from_surface(avatar)
        chat_name_label = Gtk.Label()
        chat_name_label.set_halign(Gtk.Align.START)
        chat_name_label.set_xalign(0)
        chat_name_label.set_ellipsize(Pango.EllipsizeMode.END)
        chat_name_label.set_text(name)

        self._last_message_label = Gtk.Label()
        self._last_message_label.set_halign(Gtk.Align.START)
        self._last_message_label.set_xalign(0)
        self._last_message_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._last_message_label.get_style_context().add_class('small-label')

        self._timestamp_label = Gtk.Label()
        self._timestamp_label.set_halign(Gtk.Align.END)
        self._timestamp_label.set_valign(Gtk.Align.END)
        self._timestamp_label.get_style_context().add_class('small-label')
        self._timestamp_label.get_style_context().add_class('dim-label')

        # Get last chat message from archive
        line = app.storage.archive.get_last_conversation_line(account, jid)
        last_message_box = Gtk.Box(spacing=3)
        if line is not None and line.message is not None:
            one_line = ' '.join(line.message.splitlines())

            self._last_message_label.set_text(one_line)
            self._nick_label = Gtk.Label()
            self._nick_label.set_halign(Gtk.Align.START)
            self._nick_label.get_style_context().add_class('small-label')
            self._nick_label.get_style_context().add_class('dim-label')
            if line.kind in (KindConstant.CHAT_MSG_SENT,
                             KindConstant.SINGLE_MSG_SENT):
                self._nick_label.set_text(_('Me:'))
                last_message_box.add(self._nick_label)
            if line.kind == KindConstant.GC_MSG:
                our_nick = get_group_chat_nick(account, jid)
                if line.contact_name == our_nick:
                    self._nick_label.set_text(_('Me:'))
                else:
                    self._nick_label.set_text(_('%(muc_nick)s: ') % {
                        'muc_nick': line.contact_name})
                last_message_box.add(self._nick_label)

            # TODO: file transfers have to be displayed differently

            self._timestamp = line.time
            uf_timestamp = get_uf_relative_time(line.time)
            self._timestamp_label.set_text(uf_timestamp)

        last_message_box.add(self._last_message_label)

        self._unread_label = Gtk.Label()
        self._unread_label.set_no_show_all(True)
        self._unread_label.set_halign(Gtk.Align.END)
        self._unread_label.get_style_context().add_class('unread-counter')

        close_button = Gtk.Button.new_from_icon_name(
            'window-close-symbolic', Gtk.IconSize.BUTTON)
        close_button.set_valign(Gtk.Align.CENTER)
        close_button.set_tooltip_text(_('Close'))
        close_button.get_style_context().add_class('revealer-close-button')
        close_button.get_style_context().add_class('flat')
        close_button.connect('clicked', self._on_close_button_clicked)
        self._revealer = Gtk.Revealer()
        self._revealer.set_transition_type(
            Gtk.RevealerTransitionType.CROSSFADE)
        self._revealer.set_halign(Gtk.Align.END)
        self._revealer.add(close_button)

        meta_box = Gtk.Box(spacing=6)
        meta_box.pack_start(chat_name_label, False, True, 0)
        meta_box.pack_end(self._unread_label, False, True, 0)
        meta_box.pack_end(self._timestamp_label, False, True, 0)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        text_box.add(meta_box)
        text_box.add(last_message_box)

        main_box = Gtk.Box(spacing=12)
        main_box.pack_start(account_bar, False, True, 0)
        main_box.pack_start(avatar_image, False, True, 0)
        main_box.pack_start(text_box, True, True, 0)

        overlay = Gtk.Overlay()
        overlay.add(main_box)
        overlay.add_overlay(self._revealer)

        self.add(overlay)
        self.show_all()

    def _on_state_flags_changed(self, _listboxrow, *args):
        state = self.get_state_flags()
        if (state & Gtk.StateFlags.PRELIGHT) != 0:
            self._revealer.set_reveal_child(True)
        else:
            self._revealer.set_reveal_child(False)

    def _on_close_button_clicked(self, _button):
        app.window.remove_chat(self.workspace_id, self.account, self.jid)

    def update_time(self):
        if self._timestamp is not None:
            uf_timestamp = get_uf_relative_time(self._timestamp)
            self._timestamp_label.set_text(uf_timestamp)

    def add_unread(self):
        self._unread_count += 1
        self._unread_label.set_text(str(self._unread_count))
        self._unread_label.show()

    def set_last_message_text(self, nickname, text):
        self._last_message_label.set_text(text)
        self._nick_label.set_text(nickname)
