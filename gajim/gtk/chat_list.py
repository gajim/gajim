import logging
from datetime import datetime

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.const import KindConstant
from gajim.common.i18n import _

from .util import convert_rgba_to_hex
from .util import text_to_color

log = logging.getLogger('gajim.gtk.chatlist')


class ChatList(Gtk.ListBox):
    def __init__(self, ui, chat_stack):
        Gtk.ListBox.__init__(self)

        self._ui = ui
        self._chat_stack = chat_stack
        self._chats = {}
        self._current_filter_text = ''
        self.set_size_request(250, -1)

        self.show_all()

        self.set_filter_func(self._filter_func)
        self.connect('row-selected', self._on_row_selected)

    def _filter_func(self, row):
        if not self._current_filter_text:
            return True
        return self._current_filter_text in row.jid

    def set_filter_text(self, text):
        self._current_filter_text = text
        self.invalidate_filter()

    def add_chat(self, account, jid):
        for _row_account, row_jid in self.get_open_chats():
            if row_jid == jid:
                self.select_chat(account, jid)
                return

        row = ChatRow(account, jid)
        self._chats[(account, jid)] = row
        self.add(row)

    def select_chat(self, account, jid):
        row = self._chats[(account, jid)]
        self.select_row(row)

    def remove_chat(self, account, jid):
        row = self._chats.pop((account, jid))
        self.remove(row)
        row.destroy()

    def _on_row_selected(self, _listbox, row):
        if row is None:
            self._chat_stack.clear()
            return
        self._chat_stack.show_chat(row.account, row.jid)

    def get_open_chats(self):
        return list(self._chats.keys())


class ChatRow(Gtk.ListBoxRow):
    def __init__(self, account, jid):
        Gtk.ListBoxRow.__init__(self)

        self.account = account
        self.jid = jid
        self._unread_count = 0

        self.get_style_context().add_class('chatlist-row')

        self.connect('state-flags-changed', self._on_state_flags_changed)

        contact = app.contacts.get_contact(account, jid)

        if contact:
            avatar = app.contacts.get_avatar(account,
                                             contact.jid,
                                             AvatarSize.ROSTER,
                                             self.get_scale_factor(),
                                             contact.show)
            name = contact.get_shown_name()
        else:
            avatar = app.contacts.get_avatar(account,
                                             jid,
                                             AvatarSize.ROSTER,
                                             self.get_scale_factor())
            name = jid

        avatar_image = Gtk.Image.new_from_surface(avatar)
        rgba = Gdk.RGBA(*text_to_color(jid))
        name_color = convert_rgba_to_hex(rgba)
        chat_name_label = Gtk.Label()
        chat_name_label.set_halign(Gtk.Align.START)
        chat_name_label.set_xalign(0)
        chat_name_label.set_max_width_chars(18)
        chat_name_label.set_ellipsize(Pango.EllipsizeMode.END)
        chat_name_label.set_markup(
            f'<span foreground="{name_color}">{name}</span>')

        last_message_label = Gtk.Label()
        last_message_label.set_halign(Gtk.Align.START)
        last_message_label.set_xalign(0)
        last_message_label.set_max_width_chars(20)
        last_message_label.set_ellipsize(Pango.EllipsizeMode.END)
        last_message_label.get_style_context().add_class('small-label')

        timestamp_label = Gtk.Label()
        timestamp_label.set_halign(Gtk.Align.END)
        timestamp_label.set_valign(Gtk.Align.END)
        timestamp_label.get_style_context().add_class('small-label')
        timestamp_label.get_style_context().add_class('dim-label')

        # Get last chat message from archive
        line = app.storage.archive.get_last_conversation_line(account, jid)
        last_message_box = Gtk.Box(spacing=3)
        if line is not None and line.message is not None:
            last_message_label.set_text(line.message)
            nick_label = Gtk.Label(label=_('Me:'))
            nick_label.set_halign(Gtk.Align.START)
            nick_label.get_style_context().add_class('small-label')
            nick_label.get_style_context().add_class('dim-label')
            if line.kind in (KindConstant.CHAT_MSG_SENT,
                             KindConstant.SINGLE_MSG_SENT):
                last_message_box.add(nick_label)
            # TODO: MUC nick
            # TODO: file transfers have to be displayed differently

            # TODO: Calculate user friendly timestamp for yesterday, etc.
            date_time = datetime.fromtimestamp(line.time)
            timestamp = date_time.strftime('%H:%M')
            timestamp_label.set_text(timestamp)
        last_message_box.add(last_message_label)

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
        meta_box.pack_end(timestamp_label, False, True, 0)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        text_box.add(meta_box)
        text_box.add(last_message_box)

        main_box = Gtk.Box(spacing=12)
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
        self.get_parent().remove_chat(self.account, self.jid)

    def set_unread(self, count):
        log.info('Set unread count: %s (%s)', self.jid, count)
        self._unread_count = count
        if not count:
            self._unread_label.hide()
        else:
            self._unread_label.set_text(str(count))
            self._unread_label.show()