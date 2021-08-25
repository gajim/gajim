# Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
# Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
#                         Nikos Kouremenos <kourem AT gmail.com>
#                         Travis Shirk <travis AT pobox.com>
# Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
#                    Julien Pivotto <roidelapluie AT gmail.com>
# Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
#                         Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
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

import os
import sys
import time
import uuid
import tempfile

from nbxmpp.const import Chatstate

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gio

from gajim.common import app
from gajim.common import helpers
from gajim.common import ged
from gajim.common import i18n
from gajim.common.events import ChatMsgEvent
from gajim.common.events import GroupChatMsgEvent
from gajim.common.events import PrivateChatMsgEvent
from gajim.common.i18n import _
from gajim.common.nec import EventHelper
from gajim.common.helpers import AdditionalDataDict
from gajim.common.const import KindConstant
from gajim.common.structs import OutgoingMessage
from gajim.common.connection_handlers_events import NotificationEvent

from gajim import gtkgui_helpers

from gajim.gui.conversation.view import ConversationView
from gajim.gui.conversation.scrolled import ScrolledView
from gajim.gui.conversation.jump_to_end_button import JumpToEndButton
from gajim.gui.dialogs import DialogButton
from gajim.gui.dialogs import ConfirmationDialog
from gajim.gui.dialogs import PastePreviewDialog
from gajim.gui.message_input import MessageInputTextView
from gajim.gui.util import get_hardware_key_codes
from gajim.gui.util import get_builder
from gajim.gui.util import get_show_in_systray
from gajim.gui.util import AccountBadge
from gajim.gui.const import ControlType  # pylint: disable=unused-import
from gajim.gui.emoji_chooser import emoji_chooser

from gajim.command_system.implementation.middleware import ChatCommandProcessor
from gajim.command_system.implementation.middleware import CommandTools

# The members of these modules are not referenced directly anywhere in this
# module, but still they need to be kept around. Importing them automatically
# registers the contained CommandContainers with the command system, thereby
# populating the list of available commands.
# pylint: disable=unused-import
from gajim.command_system.implementation import standard
from gajim.command_system.implementation import execute
# pylint: enable=unused-import

if app.is_installed('GSPELL'):
    from gi.repository import Gspell  # pylint: disable=ungrouped-imports

# This is needed so copying text from the conversation textview
# works with different language layouts. Pressing the key c on a russian
# layout yields another keyval than with the english layout.
# So we match hardware keycodes instead of keyvals.
# Multiple hardware keycodes can trigger a keyval like Gdk.KEY_c.
KEYCODES_KEY_C = get_hardware_key_codes(Gdk.KEY_c)

if sys.platform == 'darwin':
    COPY_MODIFIER = Gdk.ModifierType.META_MASK
    COPY_MODIFIER_KEYS = (Gdk.KEY_Meta_L, Gdk.KEY_Meta_R)
else:
    COPY_MODIFIER = Gdk.ModifierType.CONTROL_MASK
    COPY_MODIFIER_KEYS = (Gdk.KEY_Control_L, Gdk.KEY_Control_R)


################################################################################
class BaseControl(ChatCommandProcessor, CommandTools, EventHelper):
    """
    A base class containing a banner, ConversationView, MessageInputTextView
    """

    _type = None  # type: ControlType

    def __init__(self, widget_name, account, jid):
        EventHelper.__init__(self)
        # Undo needs this variable to know if space has been pressed.
        # Initialize it to True so empty textview is saved in undo list
        self.space_pressed = True

        self.handlers = {}

        self.account = account

        self._client = app.get_client(account)

        groupchat = self._type != ControlType.CHAT
        self.contact = self._client.get_module('Contacts').get_contact(
            jid, groupchat=groupchat)
        self._connect_contact_signals()

        # control_id is a unique id for the control,
        # its used as action name for actions that belong to a control
        self.control_id = str(uuid.uuid4())
        self.session = None

        app.last_message_time[self.account][self.contact.jid] = 0

        self.xml = get_builder('%s.ui' % widget_name)
        self.xml.connect_signals(self)
        self.widget = self.xml.get_object('%s_hbox' % widget_name)

        self._account_badge = AccountBadge(self.account)
        self.xml.account_badge_box.add(self._account_badge)
        show = len(app.settings.get_active_accounts()) > 1
        self.xml.account_badge_box.set_visible(show)

        # Drag and drop
        self.xml.overlay.add_overlay(self.xml.drop_area)
        self.xml.drop_area.hide()
        self.xml.overlay.connect(
            'drag-data-received', self._on_drag_data_received)
        self.xml.overlay.connect('drag-motion', self._on_drag_motion)
        self.xml.overlay.connect('drag-leave', self._on_drag_leave)

        self.TARGET_TYPE_URI_LIST = 80
        uri_entry = Gtk.TargetEntry.new(
            'text/uri-list',
            Gtk.TargetFlags.OTHER_APP,
            self.TARGET_TYPE_URI_LIST)
        dst_targets = Gtk.TargetList.new([uri_entry])
        dst_targets.add_text_targets(0)
        self._dnd_list = [uri_entry,
                          Gtk.TargetEntry.new(
                              'MY_TREE_MODEL_ROW',
                              Gtk.TargetFlags.SAME_APP,
                              0)]

        self.xml.overlay.drag_dest_set(
            Gtk.DestDefaults.ALL,
            self._dnd_list,
            Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        self.xml.overlay.drag_dest_set_target_list(dst_targets)

        # Create ConversationView and connect signals
        self.conversation_view = ConversationView(self.account, self.contact)
        self.conversation_view.connect('quote', self.on_quote)

        id_ = self.conversation_view.connect(
            'key-press-event', self._on_conversation_view_key_press)
        self.handlers[id_] = self.conversation_view

        self._scrolled_view = ScrolledView()
        self._scrolled_view.add(self.conversation_view)
        self._scrolled_view.set_focus_vadjustment(Gtk.Adjustment())

        self.xml.conv_view_overlay.add(self._scrolled_view)

        self._jump_to_end_button = JumpToEndButton()
        self._jump_to_end_button.connect('clicked', self._on_jump_to_end)
        self.xml.conv_view_overlay.add_overlay(self._jump_to_end_button)

        self._scrolled_view.connect('autoscroll-changed',
                                    self._on_autoscroll_changed)
        self._scrolled_view.connect('request-history',
                                    self.fetch_n_lines_history, 20)

        self.msg_textview = MessageInputTextView()
        self.msg_textview.connect('paste-clipboard',
                                  self._on_message_textview_paste_event)
        self.msg_textview.connect('key-press-event',
                                  self._on_message_textview_key_press_event)
        self.msg_textview.connect('populate-popup',
                                  self.on_msg_textview_populate_popup)
        self.msg_textview.get_buffer().connect(
            'changed', self._on_message_tv_buffer_changed)

        # Send message button
        self.xml.send_message_button.set_action_name(
            'win.send-message-%s' % self.control_id)
        self.xml.send_message_button.set_visible(
            app.settings.get('show_send_message_button'))
        app.settings.bind_signal(
            'show_send_message_button',
            self.xml.send_message_button,
            'set_visible')

        self.msg_scrolledwindow = ScrolledWindow()
        self.msg_scrolledwindow.set_margin_start(3)
        self.msg_scrolledwindow.set_margin_end(3)
        self.msg_scrolledwindow.get_style_context().add_class(
            'message-input-border')
        self.msg_scrolledwindow.add(self.msg_textview)

        self.xml.hbox.pack_start(self.msg_scrolledwindow, True, True, 0)

        # the following vars are used to keep history of user's messages
        self.sent_history = []
        self.sent_history_pos = 0
        self.received_history = []
        self.received_history_pos = 0
        self.orig_msg = None

        # For XEP-0333
        self.last_msg_id = None

        self.correcting = False
        self.last_sent_msg = None

        self.set_emoticon_popover()

        # Attach speller
        self.set_speller()

        # For XEP-0172
        self.user_nick = None

        self.command_hits = []
        self.last_key_tabs = False

        self.sendmessage = True

        self._client.get_module('Chatstate').set_active(self.contact)

        # TODO
        # id_ = app.window.connect('motion-notify-event',
        #                          self._on_window_motion_notify)
        # self.handlers[id_] = app.window

        self.encryption = self.get_encryption_state()
        self.conversation_view.encryption_enabled = self.encryption is not None

        # PluginSystem: adding GUI extension point for BaseControl
        # instance object (also subclasses, eg. ChatControl or GroupchatControl)
        app.plugin_manager.gui_extension_point('chat_control_base', self)

        # pylint: disable=line-too-long
        self.register_events([
            ('ping-sent', ged.GUI1, self._nec_ping),
            ('ping-reply', ged.GUI1, self._nec_ping),
            ('ping-error', ged.GUI1, self._nec_ping),
            ('sec-catalog-received', ged.GUI1, self._sec_labels_received),
            ('style-changed', ged.GUI1, self._style_changed),
        ])
        # pylint: enable=line-too-long

        # This is basically a very nasty hack to surpass the inability
        # to properly use the super, because of the old code.
        CommandTools.__init__(self)

    def _connect_contact_signals(self):
        raise NotImplementedError

    def _get_action(self, name):
        return app.window.lookup_action(name + self.control_id)

    def process_event(self, event):
        method_name = event.name.replace('-', '_')
        method_name = f'_on_{method_name}'
        getattr(self, method_name)(event)

    def _on_conversation_view_key_press(self, _listbox, event):
        if event.get_state() & Gdk.ModifierType.SHIFT_MASK:
            if event.keyval in (Gdk.KEY_Page_Down, Gdk.KEY_Page_Up):
                return Gdk.EVENT_PROPAGATE

        if event.keyval in COPY_MODIFIER_KEYS:
            # Don’t route modifier keys for copy action to the Message Input
            # otherwise pressing CTRL/META + c (the next event after that)
            # will not reach the textview (because the Message Input would get
            # focused).
            return Gdk.EVENT_PROPAGATE

        # if event.get_state() & COPY_MODIFIER:
        # TODO
        #     # Don’t reroute the event if it is META + c and the
        #     # textview has a selection
        #     if event.hardware_keycode in KEYCODES_KEY_C:
        #         if textview.get_buffer().props.has_selection:
        #             return Gdk.EVENT_PROPAGATE

        if not self.msg_textview.get_sensitive():
            # If the input textview is not sensitive it can’t get the focus.
            # In that case propagate_key_event() would send the event again
            # to the conversation textview. This would mean a recursion.
            return Gdk.EVENT_PROPAGATE

        # Focus the Message Input and resend the event
        self.msg_textview.grab_focus()
        self.msg_textview.get_toplevel().propagate_key_event(event)
        return Gdk.EVENT_STOP

    @property
    def type(self):
        return self._type

    @property
    def is_chat(self):
        return self._type.is_chat

    @property
    def is_privatechat(self):
        return self._type.is_privatechat

    @property
    def is_groupchat(self):
        return self._type.is_groupchat

    def minimizable(self):
        """
        Called to check if control can be minimized

        Derived classes MAY implement this.
        """
        return False

    def safe_shutdown(self):
        """
        Called to check if control can be closed without losing data.
        returns True if control can be closed safely else False

        Derived classes MAY implement this.
        """
        return True

    def allow_shutdown(self, method, on_response_yes, on_response_no,
                    on_response_minimize):
        """
        Called to check is a control is allowed to shutdown.
        If a control is not in a suitable shutdown state this method
        should call on_response_no, else on_response_yes or
        on_response_minimize

        Derived classes MAY implement this.
        """
        on_response_yes(self)

    def focus(self):
        raise NotImplementedError

    def draw_banner(self):
        """
        Draw the fat line at the top of the window
        that houses the icon, jid, etc

        Derived types MAY implement this.
        """
        self.draw_banner_text()

    def update_toolbar(self):
        """
        update state of buttons in toolbar
        """
        self._update_toolbar()
        app.plugin_manager.gui_extension_point(
            'chat_control_base_update_toolbar', self)

    def draw_banner_text(self):
        """
        Derived types SHOULD implement this
        """

    def update_ui(self):
        """
        Derived types SHOULD implement this
        """
        self.draw_banner()

    def repaint_themed_widgets(self):
        """
        Derived types MAY implement this
        """
        self.draw_banner()

    def _update_toolbar(self):
        """
        Derived types MAY implement this
        """

    def get_tab_label(self, chatstate):
        """
        Return a suitable tab label string. Returns a tuple such as: (label_str,
        color) either of which can be None if chatstate is given that means we
        have HE SENT US a chatstate and we want it displayed

        Derivded classes MUST implement this.
        """
        # Return a markup'd label and optional Gtk.Color in a tuple like:
        # return (label_str, None)

    def get_tab_image(self):
        # Return a suitable tab image for display.
        return None

    def prepare_context_menu(self, hide_buttonbar_items=False):
        """
        Derived classes SHOULD implement this
        """
        return None

    def set_session(self, session):
        oldsession = None
        if hasattr(self, 'session'):
            oldsession = self.session

        if oldsession and session == oldsession:
            return

        self.session = session

        if session:
            session.control = self

        if session and oldsession:
            oldsession.control = None

    def remove_session(self, session):
        if session != self.session:
            return
        self.session.control = None
        self.session = None

    def _nec_ping(self, obj):
        raise NotImplementedError

    def setup_seclabel(self):
        self.xml.label_selector.hide()
        self.xml.label_selector.set_no_show_all(True)
        lb = Gtk.ListStore(str)
        self.xml.label_selector.set_model(lb)
        cell = Gtk.CellRendererText()
        cell.set_property('xpad', 5)  # padding for status text
        self.xml.label_selector.pack_start(cell, True)
        # text to show is in in first column of liststore
        self.xml.label_selector.add_attribute(cell, 'text', 0)
        jid = self.contact.jid.bare
        if self._client.get_module('SecLabels').supported:
            self._client.get_module('SecLabels').request_catalog(jid)

    def _sec_labels_received(self, event):
        if event.account != self.account:
            return

        jid = self.contact.jid.bare

        if event.jid != jid:
            return
        model = self.xml.label_selector.get_model()
        model.clear()

        sel = 0
        labellist = event.catalog.get_label_names()
        default = event.catalog.default
        for index, label in enumerate(labellist):
            model.append([label])
            if label == default:
                sel = index

        self.xml.label_selector.set_active(sel)
        self.xml.label_selector.set_no_show_all(False)
        self.xml.label_selector.show_all()

    def delegate_action(self, action):
        if action == 'clear-chat':
            self.conversation_view.clear()
            self._scrolled_view.reset()
            return Gdk.EVENT_STOP

        if action == 'delete-line':
            self.clear(self.msg_textview)
            return Gdk.EVENT_STOP

        if action == 'show-emoji-chooser':
            if sys.platform in ('win32', 'darwin'):
                self.xml.emoticons_button.get_popover().show()
                return Gdk.EVENT_STOP
            self.msg_textview.emit('insert-emoji')
            return Gdk.EVENT_STOP

        return Gdk.EVENT_PROPAGATE

    def add_actions(self):
        action = Gio.SimpleAction.new_stateful(
            'set-encryption-%s' % self.control_id,
            GLib.VariantType.new('s'),
            GLib.Variant('s', self.encryption or 'disabled'))
        action.connect('change-state', self.change_encryption)
        app.window.add_action(action)

        actions = {
            'send-message-%s': self._on_send_message,
            'send-file-%s': self._on_send_file,
            'send-file-httpupload-%s': self._on_send_file,
            'send-file-jingle-%s': self._on_send_file,
        }

        for name, func in actions.items():
            action = Gio.SimpleAction.new(name % self.control_id, None)
            action.connect('activate', func)
            action.set_enabled(False)
            app.window.add_action(action)

    def remove_actions(self):
        actions = [
            'send-message-',
            'set-encryption-',
            'send-file-',
            'send-file-httpupload-',
            'send-file-jingle-',
        ]

        for action in actions:
            app.window.remove_action(f'{action}{self.control_id}')

    def change_encryption(self, action, param):
        encryption = param.get_string()
        if encryption == 'disabled':
            encryption = None

        if self.encryption == encryption:
            return

        if encryption:
            plugin = app.plugin_manager.encryption_plugins[encryption]
            if not plugin.activate_encryption(self):
                return

        action.set_state(param)
        self.set_encryption_state(encryption)
        self.set_encryption_menu_icon()
        self.set_lock_image()

    def set_lock_image(self):
        encryption_state = {'visible': self.encryption is not None,
                            'enc_type': self.encryption,
                            'authenticated': False}

        if self.encryption:
            app.plugin_manager.extension_point(
                'encryption_state' + self.encryption, self, encryption_state)

        visible, enc_type, authenticated = encryption_state.values()

        if authenticated:
            authenticated_string = _('and authenticated')
            self.xml.lock_image.set_from_icon_name(
                'security-high-symbolic', Gtk.IconSize.MENU)
        else:
            authenticated_string = _('and NOT authenticated')
            self.xml.lock_image.set_from_icon_name(
                'security-low-symbolic', Gtk.IconSize.MENU)

        tooltip = _('%(type)s encryption is active %(authenticated)s.') % {
            'type': enc_type, 'authenticated': authenticated_string}

        self.xml.authentication_button.set_tooltip_text(tooltip)
        self.xml.authentication_button.set_visible(visible)
        self.xml.lock_image.set_sensitive(visible)

    def _on_authentication_button_clicked(self, _button):
        app.plugin_manager.extension_point(
            'encryption_dialog' + self.encryption, self)

    def set_encryption_state(self, encryption):
        self.encryption = encryption
        self.conversation_view.encryption_enabled = encryption is not None
        self.contact.settings.set('encryption', self.encryption or '')

    def get_encryption_state(self):
        state = self.contact.settings.get('encryption')
        if not state:
            return None
        if state not in app.plugin_manager.encryption_plugins:
            self.set_encryption_state(None)
            return None
        return state

    def set_encryption_menu_icon(self):
        image = self.xml.encryption_menu.get_image()
        if image is None:
            image = Gtk.Image()
            self.xml.encryption_menu.set_image(image)
        if not self.encryption:
            image.set_from_icon_name('channel-insecure-symbolic',
                                     Gtk.IconSize.MENU)
        else:
            image.set_from_icon_name('channel-secure-symbolic',
                                     Gtk.IconSize.MENU)

    def set_speller(self):
        if not app.is_installed('GSPELL') or not app.settings.get('use_speller'):
            return

        gspell_lang = self.get_speller_language()
        spell_checker = Gspell.Checker.new(gspell_lang)
        spell_buffer = Gspell.TextBuffer.get_from_gtk_text_buffer(
            self.msg_textview.get_buffer())
        spell_buffer.set_spell_checker(spell_checker)
        spell_view = Gspell.TextView.get_from_gtk_text_view(self.msg_textview)
        spell_view.set_inline_spell_checking(False)
        spell_view.set_enable_language_menu(True)

        spell_checker.connect('notify::language', self.on_language_changed)

    def get_speller_language(self):
        lang = self.contact.settings.get('speller_language')
        if not lang:
            # use the default one
            lang = app.settings.get('speller_language')
            if not lang:
                lang = i18n.LANG
        gspell_lang = Gspell.language_lookup(lang)
        if gspell_lang is None:
            gspell_lang = Gspell.language_get_default()
        return gspell_lang

    def on_language_changed(self, checker, _param):
        gspell_lang = checker.get_language()
        self.contact.settings.set('speller_language', gspell_lang.get_code())

    def on_banner_label_populate_popup(self, _label, menu):
        """
        Override the default context menu and add our own menuitems
        """
        item = Gtk.SeparatorMenuItem.new()
        menu.prepend(item)

        menu2 = self.prepare_context_menu()  # pylint: disable=assignment-from-none
        i = 0
        for item in menu2:
            menu2.remove(item)
            menu.prepend(item)
            menu.reorder_child(item, i)
            i += 1
        menu.show_all()

    def shutdown(self):
        # remove_gui_extension_point() is called on shutdown, but also when
        # a plugin is getting disabled. Plugins don’t know the difference.
        # Plugins might want to remove their widgets on
        # remove_gui_extension_point(), so delete the objects only afterwards.
        app.plugin_manager.remove_gui_extension_point('chat_control_base', self)
        app.plugin_manager.remove_gui_extension_point(
            'chat_control_base_update_toolbar', self)

        self._client.disconnect_all_from_obj(self)

        for i in list(self.handlers.keys()):
            if self.handlers[i].handler_is_connected(i):
                self.handlers[i].disconnect(i)
        self.handlers.clear()

        self.conversation_view.destroy()
        self._scrolled_view.destroy()

        del self.conversation_view
        del self._scrolled_view
        del self.msg_textview
        del self.msg_scrolledwindow

        self.widget.destroy()
        del self.widget

        del self.xml

        self.unregister_events()

    def on_msg_textview_populate_popup(self, _textview, menu):
        """
        Override the default context menu and we prepend an option to switch
        languages
        """
        item = Gtk.MenuItem.new_with_mnemonic(_('_Undo'))
        menu.prepend(item)
        id_ = item.connect('activate', self.msg_textview.undo)
        self.handlers[id_] = item

        item = Gtk.SeparatorMenuItem.new()
        menu.prepend(item)

        item = Gtk.MenuItem.new_with_mnemonic(_('_Clear'))
        menu.prepend(item)
        id_ = item.connect('activate', self.msg_textview.clear)
        self.handlers[id_] = item

        paste_item = Gtk.MenuItem.new_with_label(_('Paste as quote'))
        id_ = paste_item.connect('activate', self.paste_clipboard_as_quote)
        self.handlers[id_] = paste_item
        menu.append(paste_item)

        menu.show_all()

    def insert_as_quote(self, text: str) -> None:
        text = '> ' + text.replace('\n', '\n> ') + '\n'
        message_buffer = self.msg_textview.get_buffer()
        message_buffer.insert_at_cursor(text)
        self.msg_textview.grab_focus()

    def paste_clipboard_as_quote(self, _item: Gtk.MenuItem) -> None:
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        text = clipboard.wait_for_text()
        if text is None:
            return
        self.insert_as_quote(text)

    def on_quote(self, _widget, text):
        self.insert_as_quote(text)

    # moved from ChatControl
    def _on_banner_eventbox_button_press_event(self, _widget, event):
        """
        If right-clicked, show popup
        """
        if event.button == 3:  # right click
            self.parent_win.popup_menu(event)

    def _on_message_textview_paste_event(self, _texview):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        image = clipboard.wait_for_image()
        if image is not None:
            if not app.settings.get('confirm_paste_image'):
                self._paste_event_confirmed(True, image)
                return
            PastePreviewDialog(
                _('Paste Image'),
                _('You are trying to paste an image'),
                _('Are you sure you want to paste your '
                  'clipboard\'s image into the chat window?'),
                _('_Do not ask me again'),
                image,
                [DialogButton.make('Cancel'),
                 DialogButton.make('Accept',
                                   text=_('_Paste'),
                                   callback=self._paste_event_confirmed,
                                   args=[image])]).show()

    def _paste_event_confirmed(self, is_checked, image):
        if is_checked:
            app.settings.set('confirm_paste_image', False)

        dir_ = tempfile.gettempdir()
        path = os.path.join(dir_, '%s.png' % str(uuid.uuid4()))
        image.savev(path, 'png', [], [])

        self._start_filetransfer(path)

    def _get_pref_ft_method(self):
        ft_pref = app.settings.get_account_setting(self.account,
                                                   'filetransfer_preference')
        httpupload = app.window.lookup_action(
            'send-file-httpupload-%s' % self.control_id)
        jingle = app.window.lookup_action(
            'send-file-jingle-%s' % self.control_id)

        if self._type.is_groupchat:
            if httpupload.get_enabled():
                return 'httpupload'
            return None

        if httpupload.get_enabled() and jingle.get_enabled():
            return ft_pref

        if httpupload.get_enabled():
            return 'httpupload'

        if jingle.get_enabled():
            return 'jingle'
        return None

    def _start_filetransfer(self, path):
        method = self._get_pref_ft_method()
        if method is None:
            return

        if method == 'httpupload':
            app.interface.send_httpupload(self, path)

        else:
            ft = app.interface.instances['file_transfers']
            ft.send_file(self.account, self.contact, path)

    def _on_message_textview_key_press_event(self, textview, event):
        if event.keyval == Gdk.KEY_space:
            self.space_pressed = True

        elif (self.space_pressed or self.msg_textview.undo_pressed) and \
        event.keyval not in (Gdk.KEY_Control_L, Gdk.KEY_Control_R) and \
        not (event.keyval == Gdk.KEY_z and event.get_state() & Gdk.ModifierType.CONTROL_MASK):
            # If the space key has been pressed and now it hasn't,
            # we save the buffer into the undo list. But be careful we're not
            # pressing Control again (as in ctrl+z)
            _buffer = textview.get_buffer()
            start_iter, end_iter = _buffer.get_bounds()
            self.msg_textview.save_undo(_buffer.get_text(start_iter,
                                                         end_iter,
                                                         True))
            self.space_pressed = False

        # Ctrl [+ Shift] + Tab are not forwarded to notebook. We handle it here
        if self._type.is_groupchat:
            if event.keyval not in (Gdk.KEY_ISO_Left_Tab, Gdk.KEY_Tab):
                self.last_key_tabs = False

        if event.get_state() & Gdk.ModifierType.SHIFT_MASK:
            if event.get_state() & Gdk.ModifierType.CONTROL_MASK and \
                            event.keyval == Gdk.KEY_ISO_Left_Tab:
                self.parent_win.move_to_next_unread_tab(False)
                return True

            if event.keyval in (Gdk.KEY_Page_Down, Gdk.KEY_Page_Up):
                self.conversation_view.event(event)
                return True

        if event.get_state() & Gdk.ModifierType.CONTROL_MASK:
            if event.keyval == Gdk.KEY_Tab:
                self.parent_win.move_to_next_unread_tab(True)
                return True

        message_buffer = self.msg_textview.get_buffer()
        event_state = event.get_state()
        if event.keyval == Gdk.KEY_Tab:
            start, end = message_buffer.get_bounds()
            position = message_buffer.get_insert()
            end = message_buffer.get_iter_at_mark(position)
            text = message_buffer.get_text(start, end, False)
            split = text.split()
            if (text.startswith(self.COMMAND_PREFIX) and
                    not text.startswith(self.COMMAND_PREFIX * 2) and
                    len(split) == 1):
                text = split[0]
                bare = text.lstrip(self.COMMAND_PREFIX)
                if len(text) == 1:
                    self.command_hits = []
                    for command in self.list_commands():
                        for name in command.names:
                            self.command_hits.append(name)
                else:
                    if (self.last_key_tabs and self.command_hits and
                            self.command_hits[0].startswith(bare)):
                        self.command_hits.append(self.command_hits.pop(0))
                    else:
                        self.command_hits = []
                        for command in self.list_commands():
                            for name in command.names:
                                if name.startswith(bare):
                                    self.command_hits.append(name)

                if self.command_hits:
                    message_buffer.delete(start, end)
                    message_buffer.insert_at_cursor(self.COMMAND_PREFIX + \
                        self.command_hits[0] + ' ')
                    self.last_key_tabs = True
                return True
            if not self._type.is_groupchat:
                self.last_key_tabs = False
        if event.keyval == Gdk.KEY_Up:
            if event_state & Gdk.ModifierType.CONTROL_MASK:
                if event_state & Gdk.ModifierType.SHIFT_MASK:  # Ctrl+Shift+UP
                    self.scroll_messages('up', message_buffer, 'received')
                else:  # Ctrl+UP
                    self.scroll_messages('up', message_buffer, 'sent')
                return True
        elif event.keyval == Gdk.KEY_Down:
            if event_state & Gdk.ModifierType.CONTROL_MASK:
                if event_state & Gdk.ModifierType.SHIFT_MASK:  # Ctrl+Shift+Down
                    self.scroll_messages('down', message_buffer, 'received')
                else:  # Ctrl+Down
                    self.scroll_messages('down', message_buffer, 'sent')
                return True
        elif event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):  # ENTER
            if event_state & Gdk.ModifierType.SHIFT_MASK:
                textview.insert_newline()
                return True

            if event_state & Gdk.ModifierType.CONTROL_MASK:
                if not app.settings.get('send_on_ctrl_enter'):
                    textview.insert_newline()
                    return True
            else:
                if app.settings.get('send_on_ctrl_enter'):
                    textview.insert_newline()
                    return True

            if not app.account_is_available(self.account):
                # we are not connected
                app.interface.raise_dialog('not-connected-while-sending')
                return True

            self._on_send_message()
            return True

        elif event.keyval == Gdk.KEY_z: # CTRL+z
            if event_state & Gdk.ModifierType.CONTROL_MASK:
                self.msg_textview.undo()
                return True

        return False

    def _on_autoscroll_changed(self, _widget, autoscroll):
        self._jump_to_end_button.toggle(not autoscroll)
        if not autoscroll:
            return

        # Check for unread messages and sendXEP-0333 Send <displayed> marker
        type_ = ['chat-message', 'private-chat-message']
        jid = self.contact.jid
        if self.is_groupchat:
            type_ = ['group-chat-message']
            jid = self.contact.jid.bare
        if not app.events.remove_events(self.account,
                                        jid,
                                        types=type_):
            # There were events to remove
            self._client.get_module('ChatMarkers').send_displayed_marker(
                self.contact,
                self.last_msg_id,
                self._type)
            self.last_msg_id = None

    def _on_jump_to_end(self, _button):
        self.scroll_to_end(force=True)
        self._jump_to_end_button.reset_unread_count()

    def _on_drag_data_received(self, widget, context, x, y, selection,
                               target_type, timestamp):
        """
        Derived types SHOULD implement this
        """

    def _on_drag_leave(self, *args):
        self.xml.drop_area.set_no_show_all(True)
        self.xml.drop_area.hide()

    def _on_drag_motion(self, *args):
        self.xml.drop_area.set_no_show_all(False)
        self.xml.drop_area.show_all()

    def drag_data_file_transfer(self, selection: Gtk.SelectionData) -> None:
        # we may have more than one file dropped
        uri_splitted = selection.get_uris()
        for uri in uri_splitted:
            path = helpers.get_file_path_from_dnd_dropped_uri(uri)
            if not os.path.isfile(path):  # is it a file?
                self.add_info_message(_("The following file could not be accessed and was not uploaded: ") + path)
                continue

            self._start_filetransfer(path)

    def get_seclabel(self):
        idx = self.xml.label_selector.get_active()
        if idx == -1:
            return None

        jid = self.contact.jid.bare
        catalog = self._client.get_module('SecLabels').get_catalog(jid)
        labels, label_list = catalog.labels, catalog.get_label_names()
        lname = label_list[idx]
        label = labels[lname]
        return label

    def _on_send_message(self, *args):
        self.msg_textview.replace_emojis()
        message = self.msg_textview.get_text()
        xhtml = self.msg_textview.get_xhtml()
        self.send_message(message, xhtml=xhtml)

    def send_message(self,
                     message,
                     type_='chat',
                     resource=None,
                     xhtml=None,
                     process_commands=True,
                     attention=False):
        """
        Send the given message to the active tab. Doesn't return None if error
        """
        if not message or message == '\n':
            return None

        if process_commands and self.process_as_command(message):
            return

        label = self.get_seclabel()

        if self.correcting and self.last_sent_msg:
            correct_id = self.last_sent_msg
        else:
            correct_id = None

        chatstate = self._client.get_module('Chatstate').get_active_chatstate(
            self.contact)

        message_ = OutgoingMessage(account=self.account,
                                   contact=self.contact,
                                   message=message,
                                   type_=type_,
                                   chatstate=chatstate,
                                   resource=resource,
                                   user_nick=self.user_nick,
                                   label=label,
                                   control=self,
                                   attention=attention,
                                   correct_id=correct_id,
                                   xhtml=xhtml)

        self._client.send_message(message_)

        # Record the history of sent messages
        self.save_message(message, 'sent')

        # Be sure to send user nickname only once according to JEP-0172
        self.user_nick = None

        # Clear msg input
        message_buffer = self.msg_textview.get_buffer()
        message_buffer.set_text('') # clear message buffer (and tv of course)

    def _on_window_motion_notify(self, *args):
        """
        It gets called no matter if it is the active window or not
        """
        # TODO
        return
        if self.parent_win.get_active_jid() == self.contact.jid:
            # if window is the active one, set last interaction
            self._client.get_module('Chatstate').set_mouse_activity(
                self.contact, self.msg_textview.has_text())

    def _on_message_tv_buffer_changed(self, textbuffer):
        has_text = self.msg_textview.has_text()
        app.window.lookup_action(
                'send-message-' + self.control_id).set_enabled(has_text)

        if textbuffer.get_char_count() and self.encryption:
            app.plugin_manager.extension_point(
                'typing' + self.encryption, self)

        self._client.get_module('Chatstate').set_keyboard_activity(self.contact)
        if not has_text:
            self._client.get_module('Chatstate').set_chatstate_delayed(
                self.contact, Chatstate.ACTIVE)
            return
        self._client.get_module('Chatstate').set_chatstate(
            self.contact, Chatstate.COMPOSING)

    def save_message(self, message, msg_type):
        # save the message, so user can scroll though the list with key up/down
        if msg_type == 'sent':
            history = self.sent_history
            pos = self.sent_history_pos
        else:
            history = self.received_history
            pos = self.received_history_pos
        size = len(history)
        scroll = pos != size
        # we don't want size of the buffer to grow indefinitely
        max_size = app.settings.get('key_up_lines')
        for _i in range(size - max_size + 1):
            if pos == 0:
                break
            history.pop(0)
            pos -= 1
        history.append(message)
        if not scroll or msg_type == 'sent':
            pos = len(history)
        if msg_type == 'sent':
            self.sent_history_pos = pos
            self.orig_msg = None
        else:
            self.received_history_pos = pos

    def add_info_message(self, text):
        self.conversation_view.add_info_message(text)

    def add_file_transfer(self, transfer):
        self.conversation_view.add_file_transfer(transfer)

    def add_message(self,
                    text,
                    kind,
                    name,
                    tim,
                    displaymarking=None,
                    msg_log_id=None,
                    message_id=None,
                    stanza_id=None,
                    correct_id=None,
                    additional_data=None):

        if additional_data is None:
            additional_data = AdditionalDataDict()

        if self._scrolled_view.get_lower_complete():
            self.conversation_view.add_message(
                text,
                kind,
                name,
                tim,
                display_marking=displaymarking,
                message_id=message_id,
                correct_id=correct_id,
                log_line_id=msg_log_id,
                additional_data=additional_data)

            if not self._scrolled_view.get_autoscroll():
                if kind == 'outgoing':
                    self.scroll_to_end()
                else:
                    self._jump_to_end_button.add_unread_count()
        else:
            self._jump_to_end_button.add_unread_count()

        if message_id:
            if self._type.is_groupchat:
                self.last_msg_id = stanza_id or message_id
            else:
                self.last_msg_id = message_id

        if kind == 'incoming':
            # Record the history of received messages
            self.save_message(text, 'received')

            # Issue notification
            self._notify(name, text, tim)

            # Add message event
            self._add_message_event(text, msg_log_id, message_id, stanza_id)

            # Send chat marker if we’re actively following the chat
            chat_active = app.window.is_chat_active(
                self.account, self.contact.jid)
            if chat_active and self._scrolled_view.get_autoscroll():
                self._client.get_module('ChatMarkers').send_displayed_marker(
                    self.contact,
                    self.last_msg_id,
                    self._type)

    def _notify(self, name, text, tim):
        if app.window.is_chat_active(self.account, self.contact.jid):
            if self._scrolled_view.get_autoscroll():
                return

        popup_event_type = _('New Message')
        popup_title = _('New message from %s') % name
        needs_highlight = False

        if self.is_chat:
            popup_msg_type = 'chat'
            sound_event = 'first_message_received'

        if self.is_groupchat:
            popup_msg_type = 'gc_msg'
            popup_title += f' ({self.contact.name})'
            needs_highlight = helpers.message_needs_highlight(
                text, self.contact.nickname, self._client.get_own_jid().bare)
            if needs_highlight:
                sound_event = 'muc_message_highlight'
            else:
                sound_event = 'muc_message_received'
            if not self.contact.can_notify():
                sound_event = None

        if self.is_privatechat:
            popup_msg_type = 'pm'
            popup_title += f' (private in {self.room_name})'
            sound_event = 'first_message_received'

        # Is it a history message? Don't want sound-floods when we join.
        if tim is not None and time.mktime(time.localtime()) - tim > 1:
            sound_event = None

        popup_text = ''
        if app.settings.get('notification_preview_message'):
            if text.startswith('/me') or text.startswith('/me\n'):
                popup_text = f'* {name} {text[3:]}'
            else:
                popup_text = text

        popup_enabled = False
        if app.settings.get('autopopupaway'):
            popup_enabled = True
        if self._client.status == 'online':
            popup_enabled = True
        if self.is_groupchat and not self.contact.can_notify():
            popup_enabled = False

        event = NotificationEvent(
            None,
            account=self.account,
            jid=self.contact.jid,
            popup_event_type=popup_event_type,
            popup_msg_type=popup_msg_type,
            popup_title=popup_title,
            popup_text=popup_text,
            popup_enabled=popup_enabled,
            sound_event=sound_event)
        app.nec.push_incoming_event(event)

    def _add_message_event(self, text, msg_log_id, message_id, stanza_id):
        if app.window.is_chat_active(self.account, self.contact.jid):
            if self._scrolled_view.get_autoscroll():
                return

        if self.is_groupchat:
            event_type = GroupChatMsgEvent
            event = 'gc_message_received'
        else:
            if self.is_chat:
                event_type = ChatMsgEvent
            else:
                event_type = PrivateChatMsgEvent
            event = 'message_received'
        show_in_systray = get_show_in_systray(
            event_type.type_, self.account, self.contact.jid)

        event = event_type(text,
                           '',
                           self,
                           msg_log_id,
                           message_id=message_id,
                           stanza_id=stanza_id,
                           show_in_systray=show_in_systray)
        app.events.add_event(self.account, str(self.contact.jid), event)

    def toggle_emoticons(self):
        """
        Hide show emoticons_button
        """
        if app.settings.get('emoticons_theme'):
            self.xml.emoticons_button.set_no_show_all(False)
            self.xml.emoticons_button.show()
        else:
            self.xml.emoticons_button.set_no_show_all(True)
            self.xml.emoticons_button.hide()

    def set_emoticon_popover(self):
        if not app.settings.get('emoticons_theme'):
            return

        if sys.platform in ('win32', 'darwin'):
            emoji_chooser.text_widget = self.msg_textview
            self.xml.emoticons_button.set_popover(emoji_chooser)
            return

        self.xml.emoticons_button.set_sensitive(True)
        self.xml.emoticons_button.connect('clicked',
                                          self._on_emoticon_button_clicked)

    def _on_emoticon_button_clicked(self, _widget):
        # Present GTK emoji chooser (not cross platform compatible)
        self.msg_textview.emit('insert-emoji')
        self.xml.emoticons_button.set_property('active', False)

    def on_color_menuitem_activate(self, _widget):
        color_dialog = Gtk.ColorChooserDialog(None, app.window)
        color_dialog.set_use_alpha(False)
        color_dialog.connect('response', self.msg_textview.color_set)
        color_dialog.show_all()

    def on_font_menuitem_activate(self, _widget):
        font_dialog = Gtk.FontChooserDialog(None, app.window)
        start, finish = self.msg_textview.get_active_iters()
        font_dialog.connect('response', self.msg_textview.font_set, start, finish)
        font_dialog.show_all()

    def on_formatting_menuitem_activate(self, widget):
        tag = widget.get_name()
        self.msg_textview.set_tag(tag)

    def on_clear_formatting_menuitem_activate(self, _widget):
        self.msg_textview.clear_tags()

    def _style_changed(self, *args):
        self.update_tags()

    def update_tags(self):
        self.conversation_view.update_text_tags()

    @staticmethod
    def clear(tv):
        buffer_ = tv.get_buffer()
        start, end = buffer_.get_bounds()
        buffer_.delete(start, end)

    def _on_send_file(self, action, _param):
        name = action.get_name()
        if 'httpupload' in name:
            app.interface.send_httpupload(self)
            return

        if 'jingle' in name:
            self._on_send_file_jingle()
            return

        method = self._get_pref_ft_method()
        if method is None:
            return

        if method == 'httpupload':
            app.interface.send_httpupload(self)
        else:
            self._on_send_file_jingle()

    def _on_send_file_jingle(self, gc_contact=None):
        """
        gc_contact can be set when we are in a groupchat control
        """
        def _on_ok(_contact):
            app.interface.instances['file_transfers'].show_file_send_request(
                self.account, _contact)

        if self._type.is_privatechat:
            gc_contact = self.gc_contact

        if not gc_contact:
            _on_ok(self.contact)
            return

        # gc or pm
        gc_control = app.interface.msg_win_mgr.get_gc_control(
            gc_contact.room_jid, self.account)
        self_contact = app.contacts.get_gc_contact(self.account,
                                                   gc_control.room_jid,
                                                   gc_control.nick)
        if (gc_control.is_anonymous and
                gc_contact.affiliation.value not in ['admin', 'owner'] and
                self_contact.affiliation.value in ['admin', 'owner']):
            contact = app.contacts.get_contact(self.account, gc_contact.jid)
            if not contact or contact.sub not in ('both', 'to'):

                ConfirmationDialog(
                    _('Privacy'),
                    _('Warning'),
                    _('If you send a file to <b>%s</b>, your real XMPP '
                      'address will be revealed.') % gc_contact.name,
                    [DialogButton.make('Cancel'),
                     DialogButton.make(
                         'OK',
                         text=_('_Continue'),
                         callback=lambda: _on_ok(gc_contact))]).show()
                return
        _on_ok(gc_contact)

    def set_control_active(self, state):
        if state:
            self.set_emoticon_popover()
            jid = self.contact.jid
            if self.conversation_view.autoscroll:
                # we are at the end
                type_ = ['chat-message']
                if self.is_groupchat:
                    type_ = ['group-chat-message']
                if self.is_privatechat:
                    type_ = ['private-chat-message']
                if not app.events.remove_events(self.account,
                                                self.contact.jid,
                                                types=type_):
                    # There were events to remove
                    self.redraw_after_event_removed(jid)
                    # XEP-0333 Send <displayed> marker
                    self._client.get_module('ChatMarkers').send_displayed_marker(
                        self.contact,
                        self.last_msg_id,
                        self._type)
                    self.last_msg_id = None
            # send chatstate inactive to the one we're leaving
            # and active to the one we visit
            if self.msg_textview.has_text():
                self._client.get_module('Chatstate').set_chatstate(
                    self.contact, Chatstate.PAUSED)
            else:
                self._client.get_module('Chatstate').set_chatstate(
                    self.contact, Chatstate.ACTIVE)
        else:
            self._client.get_module('Chatstate').set_chatstate(
                self.contact, Chatstate.INACTIVE)

    def scroll_to_end(self, force=False):
        # Clear view and reload conversation
        self.conversation_view.clear()
        self._scrolled_view.reset()
        self.conversation_view.scroll_to_end(force)

    def scroll_to_message(self, log_line_id, timestamp):
        row = self.conversation_view.get_row_by_log_line_id(log_line_id)
        if row is None:
            # Clear view and reload conversation around timestamp
            self.conversation_view.lock()
            self.conversation_view.clear()
            self._scrolled_view.reset()
            before, at_after = app.storage.archive.get_conversation_around(
                self.account, self.contact.jid, timestamp)
            self.add_messages(before)
            self.add_messages(at_after)

        GLib.idle_add(
            self.conversation_view.scroll_to_message_and_highlight,
            log_line_id)
        GLib.idle_add(self.conversation_view.unlock)

    def fetch_n_lines_history(self, _scrolled, before, n_lines):
        if self.conversation_view.locked:
            return

        self.conversation_view.lock()
        if before:
            row = self.conversation_view.get_first_message_row()
        else:
            row = self.conversation_view.get_last_message_row()
        if row is None:
            timestamp = time.time()
        else:
            timestamp = row.db_timestamp

        if self.is_groupchat:
            messages = app.storage.archive.get_conversation_muc_before_after(
                self.account,
                self.contact.jid,
                before,
                timestamp,
                n_lines)
        else:
            messages = app.storage.archive.get_conversation_before_after(
                self.account,
                self.contact.jid,
                before,
                timestamp,
                n_lines)

        if not messages:
            self._scrolled_view.set_history_complete(before, True)
            self.conversation_view.unlock()
            return

        self.add_messages(messages)

        if len(messages) < n_lines:
            self._scrolled_view.set_history_complete(before, True)

        if self._scrolled_view.get_autoscroll():
            if self.conversation_view.reduce_message_count(before):
                self._scrolled_view.set_history_complete(before, False)

        self.conversation_view.unlock()

    def add_messages(self, messages):
        for msg in messages:
            if not msg or not msg.message:
                continue

            contact_name = msg.contact_name
            if msg.kind in (
                    KindConstant.SINGLE_MSG_RECV, KindConstant.CHAT_MSG_RECV):
                kind = 'incoming'
                contact_name = self.contact.name
            elif msg.kind == KindConstant.GC_MSG:
                kind = 'incoming'
            elif msg.kind in (
                    KindConstant.SINGLE_MSG_SENT, KindConstant.CHAT_MSG_SENT):
                kind = 'outgoing'
                contact_name = self.get_our_nick()
            else:
                raise ValueError('no kind attribute')

            self.conversation_view.add_message(
                msg.message,
                kind,
                contact_name,
                msg.time,
                additional_data=msg.additional_data,
                message_id=msg.message_id,
                log_line_id=msg.log_line_id,
                marker=msg.marker,
                error=msg.error)

    def has_focus(self):
        if app.window.get_property('has-toplevel-focus'):
            if self == app.window.get_active_control():
                return True
        return False

    def scroll_messages(self, direction, msg_buf, msg_type):
        if msg_type == 'sent':
            history = self.sent_history
            pos = self.sent_history_pos
            self.received_history_pos = len(self.received_history)
        else:
            history = self.received_history
            pos = self.received_history_pos
            self.sent_history_pos = len(self.sent_history)
        size = len(history)
        if self.orig_msg is None:
            # user was typing something and then went into history, so save
            # whatever is already typed
            start_iter = msg_buf.get_start_iter()
            end_iter = msg_buf.get_end_iter()
            self.orig_msg = msg_buf.get_text(start_iter, end_iter, False)
        if pos == size and size > 0 and direction == 'up' and \
        msg_type == 'sent' and not self.correcting and (not \
        history[pos - 1].startswith('/') or history[pos - 1].startswith('/me')):
            self.correcting = True
            gtkgui_helpers.add_css_class(
                self.msg_textview, 'gajim-msg-correcting')
            message = history[pos - 1]
            msg_buf.set_text(message)
            return
        if self.correcting:
            # We were previously correcting
            gtkgui_helpers.remove_css_class(
                self.msg_textview, 'gajim-msg-correcting')
        self.correcting = False
        pos += -1 if direction == 'up' else +1
        if pos == -1:
            return
        if pos >= size:
            pos = size
            message = self.orig_msg
            self.orig_msg = None
        else:
            message = history[pos]
        if msg_type == 'sent':
            self.sent_history_pos = pos
        else:
            self.received_history_pos = pos
            if self.orig_msg is not None:
                message = '> %s\n' % message.replace('\n', '\n> ')
        msg_buf.set_text(message)

    def update_account_badge(self):
        show = len(app.settings.get_active_accounts()) > 1
        self.xml.account_badge_box.set_visible(show)


class ScrolledWindow(Gtk.ScrolledWindow):
    def __init__(self, *args, **kwargs):
        Gtk.ScrolledWindow.__init__(self, *args, **kwargs)

        self.set_overlay_scrolling(False)
        self.set_max_content_height(100)
        self.set_propagate_natural_height(True)
        self.get_style_context().add_class('scrolled-no-border')
        self.get_style_context().add_class('no-scroll-indicator')
        self.get_style_context().add_class('scrollbar-style')
        self.get_style_context().add_class('one-line-scrollbar')
        self.set_shadow_type(Gtk.ShadowType.IN)
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
