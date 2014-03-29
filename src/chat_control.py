# -*- coding:utf-8 -*-
## src/chat_control.py
##
## Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
## Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
##                         Nikos Kouremenos <kourem AT gmail.com>
##                         Travis Shirk <travis AT pobox.com>
## Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
##                    Julien Pivotto <roidelapluie AT gmail.com>
## Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
##                         Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

import os
import time
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Pango
from gi.repository import GObject
from gi.repository import GLib
import gtkgui_helpers
import gui_menu_builder
import message_control
import dialogs
import history_window
import notify
import re

from common import gajim
from common import helpers
from common import exceptions
from common import ged
from common import i18n
from message_control import MessageControl
from conversation_textview import ConversationTextview
from message_textview import MessageTextView
from common.stanza_session import EncryptedStanzaSession, ArchivingStanzaSession
from common.contacts import GC_Contact
from common.logger import constants
from common.pep import MOODS, ACTIVITIES
from nbxmpp.protocol import NS_XHTML, NS_XHTML_IM, NS_FILE, NS_MUC
from nbxmpp.protocol import NS_RECEIPTS, NS_ESESSION
from nbxmpp.protocol import NS_JINGLE_RTP_AUDIO, NS_JINGLE_RTP_VIDEO
from nbxmpp.protocol import NS_JINGLE_ICE_UDP, NS_JINGLE_FILE_TRANSFER
from nbxmpp.protocol import NS_CHATSTATES
from common.connection_handlers_events import MessageOutgoingEvent
from common.exceptions import GajimGeneralException

from command_system.implementation.middleware import ChatCommandProcessor
from command_system.implementation.middleware import CommandTools
from command_system.implementation.hosts import ChatCommands

# Here we load the module with the standard commands, so they are being detected
# and dispatched.
from command_system.implementation.standard import StandardChatCommands
from command_system.implementation.execute import Execute, Show

try:
    import gtkspell
    HAS_GTK_SPELL = True
except ImportError:
    HAS_GTK_SPELL = False

from common import dbus_support
if dbus_support.supported:
    import dbus
    import remote_control

################################################################################
class ChatControlBase(MessageControl, ChatCommandProcessor, CommandTools):
    """
    A base class containing a banner, ConversationTextview, MessageTextView
    """

    keymap = Gdk.Keymap.get_default()
    try:
        keycode_c = keymap.get_entries_for_keyval(Gdk.KEY_c)[1][0].keycode
    except TypeError:
        keycode_c = 54
    try:
        keycode_ins = keymap.get_entries_for_keyval(Gdk.KEY_Insert)[1][0].keycode
    except TypeError:
        keycode_ins = 118

    def make_href(self, match):
        url_color = gajim.config.get('urlmsgcolor')
        url = match.group()
        if not '://' in url:
            url = 'http://' + url
        return '<a href="%s"><span color="%s">%s</span></a>' % (url,
                url_color, match.group())

    def get_font_attrs(self):
        """
        Get pango font attributes for banner from theme settings
        """
        theme = gajim.config.get('roster_theme')
        bannerfont = gajim.config.get_per('themes', theme, 'bannerfont')
        bannerfontattrs = gajim.config.get_per('themes', theme, 'bannerfontattrs')

        if bannerfont:
            font = Pango.FontDescription(bannerfont)
        else:
            font = Pango.FontDescription('Normal')
        if bannerfontattrs:
            # B attribute is set by default
            if 'B' in bannerfontattrs:
                font.set_weight(Pango.Weight.HEAVY)
            if 'I' in bannerfontattrs:
                font.set_style(Pango.Style.ITALIC)

        font_attrs = 'font_desc="%s"' % font.to_string()

        # in case there is no font specified we use x-large font size
        if font.get_size() == 0:
            font_attrs = '%s size="x-large"' % font_attrs
        font.set_weight(Pango.Weight.NORMAL)
        font_attrs_small = 'font_desc="%s" size="small"' % font.to_string()
        return (font_attrs, font_attrs_small)

    def get_nb_unread(self):
        jid = self.contact.jid
        if self.resource:
            jid += '/' + self.resource
        type_ = self.type_id
        return len(gajim.events.get_events(self.account, jid, ['printed_' + type_,
                type_]))

    def draw_banner(self):
        """
        Draw the fat line at the top of the window that houses the icon, jid, etc

        Derived types MAY implement this.
        """
        self.draw_banner_text()
        self._update_banner_state_image()
        gajim.plugin_manager.gui_extension_point('chat_control_base_draw_banner',
            self)

    def update_toolbar(self):
        """
        update state of buttons in toolbar
        """
        self._update_toolbar()
        gajim.plugin_manager.gui_extension_point(
            'chat_control_base_update_toolbar', self)

    def draw_banner_text(self):
        """
        Derived types SHOULD implement this
        """
        pass

    def update_ui(self):
        """
        Derived types SHOULD implement this
        """
        self.draw_banner()

    def repaint_themed_widgets(self):
        """
        Derived types MAY implement this
        """
        self._paint_banner()
        self.draw_banner()

    def _update_banner_state_image(self):
        """
        Derived types MAY implement this
        """
        pass

    def _update_toolbar(self):
        """
        Derived types MAY implement this
        """
        pass

    def _nec_our_status(self, obj):
        if self.account != obj.conn.name:
            return
        if obj.show == 'offline' or (obj.show == 'invisible' and \
        obj.conn.is_zeroconf):
            self.got_disconnected()
        else:
            # Other code rejoins all GCs, so we don't do it here
            if not self.type_id == message_control.TYPE_GC:
                self.got_connected()
        if self.parent_win:
            self.parent_win.redraw_tab(self)

    def _nec_ping_sent(self, obj):
        if self.contact != obj.contact:
            return
        self.print_conversation(_('Ping?'), 'status')

    def _nec_ping_reply(self, obj):
        if self.contact != obj.contact:
            return
        self.print_conversation(_('Pong! (%s s.)') % obj.seconds, 'status')

    def _nec_ping_error(self, obj):
        if self.contact != obj.contact:
            return
        self.print_conversation(_('Error.'), 'status')

    def handle_message_textview_mykey_press(self, widget, event_keyval,
    event_keymod):
        """
        Derives types SHOULD implement this, rather than connection to the even
        itself
        """
        event = Gdk.Event(Gdk.EventType.KEY_PRESS)
        event.keyval = event_keyval
        event.state = event_keymod
        event.time = 0

        _buffer = widget.get_buffer()
        start, end = _buffer.get_bounds()

        if event.keyval -- Gdk.KEY_Tab:
            position = _buffer.get_insert()
            end = _buffer.get_iter_at_mark(position)

            text = _buffer.get_text(start, end, False)

            splitted = text.split()

            if (text.startswith(self.COMMAND_PREFIX) and not
                    text.startswith(self.COMMAND_PREFIX * 2) and len(splitted) == 1):

                text = splitted[0]
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
                    _buffer.delete(start, end)
                    _buffer.insert_at_cursor(self.COMMAND_PREFIX + self.command_hits[0] + ' ')
                    self.last_key_tabs = True

                return True

            self.last_key_tabs = False

    def status_url_clicked(self, widget, url):
        helpers.launch_browser_mailer('url', url)

    def setup_seclabel(self, combo):
        self.seclabel_combo = combo
        self.seclabel_combo.hide()
        self.seclabel_combo.set_no_show_all(True)
        lb = Gtk.ListStore(str)
        self.seclabel_combo.set_model(lb)
        cell = Gtk.CellRendererText()
        cell.set_property('xpad', 5)  # padding for status text
        self.seclabel_combo.pack_start(cell, True)
        # text to show is in in first column of liststore
        self.seclabel_combo.add_attribute(cell, 'text', 0)
        if gajim.connections[self.account].seclabel_supported:
            gajim.connections[self.account].seclabel_catalogue(self.contact.jid, self.on_seclabels_ready)

    def on_seclabels_ready(self):
        lb = self.seclabel_combo.get_model()
        lb.clear()
        i = 0
        sel = 0
        catalogue = gajim.connections[self.account].seclabel_catalogues[
            self.contact.jid]
        for label in catalogue[2]:
            lb.append([label])
            if label == catalogue[3]:
                sel = i
            i += 1
        self.seclabel_combo.set_active(sel)
        self.seclabel_combo.set_no_show_all(False)
        self.seclabel_combo.show_all()

    def __init__(self, type_id, parent_win, widget_name, contact, acct,
    resource=None):
        # Undo needs this variable to know if space has been pressed.
        # Initialize it to True so empty textview is saved in undo list
        self.space_pressed = True

        if resource is None:
            # We very likely got a contact with a random resource.
            # This is bad, we need the highest for caps etc.
            c = gajim.contacts.get_contact_with_highest_priority(acct,
                contact.jid)
            if c and not isinstance(c, GC_Contact):
                contact = c

        MessageControl.__init__(self, type_id, parent_win, widget_name,
            contact, acct, resource=resource)

        widget = self.xml.get_object('history_button')
        # set document-open-recent icon for history button
        if gtkgui_helpers.gtk_icon_theme.has_icon('document-open-recent'):
            img = self.xml.get_object('history_image')
            img.set_from_icon_name('document-open-recent', Gtk.IconSize.MENU)

        id_ = widget.connect('clicked', self._on_history_menuitem_activate)
        self.handlers[id_] = widget

        # when/if we do XHTML we will put formatting buttons back
        widget = self.xml.get_object('emoticons_button')
        widget.set_sensitive(False)
        id_ = widget.connect('clicked', self.on_emoticons_button_clicked)
        self.handlers[id_] = widget

        # Create banner and connect signals
        widget = self.xml.get_object('banner_eventbox')
        id_ = widget.connect('button-press-event',
            self._on_banner_eventbox_button_press_event)
        self.handlers[id_] = widget

        self.urlfinder = re.compile(
            r"(www\.(?!\.)|[a-z][a-z0-9+.-]*://)[^\s<>'\"]+[^!,\.\s<>\)'\"\]]")

        self.banner_status_label = self.xml.get_object('banner_label')
        id_ = self.banner_status_label.connect('populate_popup',
            self.on_banner_label_populate_popup)
        self.handlers[id_] = self.banner_status_label

        # Init DND
        self.TARGET_TYPE_URI_LIST = 80
        self.dnd_list = [Gtk.TargetEntry.new('text/uri-list', 0,
            self.TARGET_TYPE_URI_LIST), Gtk.TargetEntry.new('MY_TREE_MODEL_ROW',
            Gtk.TargetFlags.SAME_APP, 0)]
        id_ = self.widget.connect('drag_data_received',
            self._on_drag_data_received)
        self.handlers[id_] = self.widget
        self.widget.drag_dest_set(Gtk.DestDefaults.MOTION |
            Gtk.DestDefaults.HIGHLIGHT | Gtk.DestDefaults.DROP,
            self.dnd_list, Gdk.DragAction.COPY)

        # Create textviews and connect signals
        self.conv_textview = ConversationTextview(self.account)
        id_ = self.conv_textview.connect('quote', self.on_quote)
        self.handlers[id_] = self.conv_textview.tv
        id_ = self.conv_textview.tv.connect('key_press_event',
            self._conv_textview_key_press_event)
        self.handlers[id_] = self.conv_textview.tv
        # FIXME: DND on non editable TextView, find a better way
        self.drag_entered = False
        id_ = self.conv_textview.tv.connect('drag_data_received',
            self._on_drag_data_received)
        self.handlers[id_] = self.conv_textview.tv
        id_ = self.conv_textview.tv.connect('drag_motion', self._on_drag_motion)
        self.handlers[id_] = self.conv_textview.tv
        id_ = self.conv_textview.tv.connect('drag_leave', self._on_drag_leave)
        self.handlers[id_] = self.conv_textview.tv
        self.conv_textview.tv.drag_dest_set(Gtk.DestDefaults.MOTION |
            Gtk.DestDefaults.HIGHLIGHT | Gtk.DestDefaults.DROP,
            self.dnd_list, Gdk.DragAction.COPY)

        self.conv_scrolledwindow = self.xml.get_object(
            'conversation_scrolledwindow')
        self.conv_scrolledwindow.add(self.conv_textview.tv)
        widget = self.conv_scrolledwindow.get_vadjustment()
        id_ = widget.connect('value-changed',
            self.on_conversation_vadjustment_value_changed)
        self.handlers[id_] = widget
        id_ = widget.connect('changed',
            self.on_conversation_vadjustment_changed)
        self.handlers[id_] = widget
        self.scroll_to_end_id = None
        self.was_at_the_end = True
        self.correcting = False
        self.last_sent_msg = None
        self.last_sent_txt = None
        self.last_received_txt = {} # one per name
        self.last_received_id = {} # one per name

        # add MessageTextView to UI and connect signals
        self.msg_scrolledwindow = self.xml.get_object('message_scrolledwindow')
        self.msg_textview = MessageTextView()
        id_ = self.msg_textview.connect('mykeypress',
            self._on_message_textview_mykeypress_event)
        self.handlers[id_] = self.msg_textview
        self.msg_scrolledwindow.add(self.msg_textview)
        id_ = self.msg_textview.connect('key_press_event',
            self._on_message_textview_key_press_event)
        self.handlers[id_] = self.msg_textview
        id_ = self.msg_textview.connect('configure-event',
            self.on_configure_event)
        self.handlers[id_] = self.msg_textview
        id_ = self.msg_textview.connect('populate_popup',
            self.on_msg_textview_populate_popup)
        self.handlers[id_] = self.msg_textview
        # Setup DND
        id_ = self.msg_textview.connect('drag_data_received',
            self._on_drag_data_received)
        self.handlers[id_] = self.msg_textview
        self.msg_textview.drag_dest_set(Gtk.DestDefaults.MOTION |
            Gtk.DestDefaults.HIGHLIGHT, self.dnd_list, Gdk.DragAction.COPY)

        self.update_font()

        # Hook up send button
        widget = self.xml.get_object('send_button')
        id_ = widget.connect('clicked', self._on_send_button_clicked)
        widget.set_sensitive(False)
        self.handlers[id_] = widget

        widget = self.xml.get_object('formattings_button')
        id_ = widget.connect('clicked', self.on_formattings_button_clicked)
        self.handlers[id_] = widget

        # the following vars are used to keep history of user's messages
        self.sent_history = []
        self.sent_history_pos = 0
        self.received_history = []
        self.received_history_pos = 0
        self.orig_msg = None

        # Emoticons menu
        # set image no matter if user wants at this time emoticons or not
        # (so toggle works ok)
        img = self.xml.get_object('emoticons_button_image')
        img.set_from_file(os.path.join(gajim.DATA_DIR, 'emoticons', 'static',
            'smile.png'))
        self.toggle_emoticons()

        # Attach speller
        if gajim.config.get('use_speller') and HAS_GTK_SPELL:
            self.set_speller()
        self.conv_textview.tv.show()
        self._paint_banner()

        # For XEP-0172
        self.user_nick = None

        self.smooth = True

        self.command_hits = []
        self.last_key_tabs = False

        # PluginSystem: adding GUI extension point for ChatControlBase
        # instance object (also subclasses, eg. ChatControl or GroupchatControl)
        gajim.plugin_manager.gui_extension_point('chat_control_base', self)

        gajim.ged.register_event_handler('our-show', ged.GUI1,
            self._nec_our_status)
        gajim.ged.register_event_handler('ping-sent', ged.GUI1,
            self._nec_ping_sent)
        gajim.ged.register_event_handler('ping-reply', ged.GUI1,
            self._nec_ping_reply)
        gajim.ged.register_event_handler('ping-error', ged.GUI1,
            self._nec_ping_error)

        # This is bascially a very nasty hack to surpass the inability
        # to properly use the super, because of the old code.
        CommandTools.__init__(self)

    def set_speller(self):
        # now set the one the user selected
        per_type = 'contacts'
        if self.type_id == message_control.TYPE_GC:
            per_type = 'rooms'
        lang = gajim.config.get_per(per_type, self.contact.jid,
                'speller_language')
        if not lang:
            # use the default one
            lang = gajim.config.get('speller_language')
            if not lang:
                lang = gajim.LANG
        if lang:
            try:
                gtkspell.Spell(self.msg_textview, lang)
                self.msg_textview.lang = lang
            except (GObject.GError, RuntimeError, TypeError, OSError):
                dialogs.AspellDictError(lang)

    def on_banner_label_populate_popup(self, label, menu):
        """
        Override the default context menu and add our own menutiems
        """
        item = Gtk.SeparatorMenuItem.new()
        menu.prepend(item)

        menu2 = self.prepare_context_menu()
        i = 0
        for item in menu2:
            menu2.remove(item)
            menu.prepend(item)
            menu.reorder_child(item, i)
            i += 1
        menu.show_all()

    def shutdown(self):
        super(ChatControlBase, self).shutdown()
        # PluginSystem: removing GUI extension points connected with ChatControlBase
        # instance object
        gajim.plugin_manager.remove_gui_extension_point('chat_control_base',
            self)
        gajim.plugin_manager.remove_gui_extension_point(
            'chat_control_base_draw_banner', self)
        gajim.plugin_manager.remove_gui_extension_point('print_special_text',
            self)
        gajim.ged.remove_event_handler('our-show', ged.GUI1,
            self._nec_our_status)

    def on_msg_textview_populate_popup(self, textview, menu):
        """
        Override the default context menu and we prepend an option to switch
        languages
        """
        def _on_select_dictionary(widget, lang):
            per_type = 'contacts'
            if self.type_id == message_control.TYPE_GC:
                per_type = 'rooms'
            if not gajim.config.get_per(per_type, self.contact.jid):
                gajim.config.add_per(per_type, self.contact.jid)
            gajim.config.set_per(per_type, self.contact.jid, 'speller_language',
                    lang)
            spell = gtkspell.get_from_text_view(self.msg_textview)
            self.msg_textview.lang = lang
            spell.set_language(lang)
            widget.set_active(True)

        item = Gtk.ImageMenuItem.new_from_stock(Gtk.STOCK_UNDO, None)
        menu.prepend(item)
        id_ = item.connect('activate', self.msg_textview.undo)
        self.handlers[id_] = item

        item = Gtk.SeparatorMenuItem.new()
        menu.prepend(item)

        item = Gtk.ImageMenuItem.new_from_stock(Gtk.STOCK_CLEAR, None)
        menu.prepend(item)
        id_ = item.connect('activate', self.msg_textview.clear)
        self.handlers[id_] = item

        menu.show_all()

    def on_quote(self, widget, text):
        text = '>' + text.replace('\n', '\n>') + '\n'
        message_buffer = self.msg_textview.get_buffer()
        message_buffer.insert_at_cursor(text)

    # moved from ChatControl
    def _on_banner_eventbox_button_press_event(self, widget, event):
        """
        If right-clicked, show popup
        """
        if event.button == 3:  # right click
            self.parent_win.popup_menu(event)

    def _on_send_button_clicked(self, widget):
        """
        When send button is pressed: send the current message
        """
        message_buffer = self.msg_textview.get_buffer()
        start_iter = message_buffer.get_start_iter()
        end_iter = message_buffer.get_end_iter()
        message = message_buffer.get_text(start_iter, end_iter, False)
        xhtml = self.msg_textview.get_xhtml()

        # send the message
        self.send_message(message, xhtml=xhtml)

    def _paint_banner(self):
        """
        Repaint banner with theme color
        """
        theme = gajim.config.get('roster_theme')
        bgcolor = gajim.config.get_per('themes', theme, 'bannerbgcolor')
        textcolor = gajim.config.get_per('themes', theme, 'bannertextcolor')
        # the backgrounds are colored by using an eventbox by
        # setting the bg color of the eventbox and the fg of the name_label
        banner_eventbox = self.xml.get_object('banner_eventbox')
        banner_name_label = self.xml.get_object('banner_name_label')
        self.disconnect_style_event(banner_name_label)
        self.disconnect_style_event(self.banner_status_label)
        if bgcolor:
            color = Gdk.RGBA()
            Gdk.RGBA.parse(color, bgcolor)
            banner_eventbox.override_background_color(Gtk.StateType.NORMAL,
                color)
            default_bg = False
        else:
            default_bg = True
        if textcolor:
            color = Gdk.RGBA()
            Gdk.RGBA.parse(color, textcolor)
            banner_name_label.override_color(Gtk.StateType.NORMAL,
                color)
            self.banner_status_label.override_color(
                Gtk.StateType.NORMAL, color)
            default_fg = False
        else:
            default_fg = True
        if default_bg or default_fg:
            self._on_style_set_event(banner_name_label, None, default_fg,
                    default_bg)
            if self.banner_status_label.get_realized():
                # Widget is realized
                self._on_style_set_event(self.banner_status_label, None, default_fg,
                        default_bg)

    def disconnect_style_event(self, widget):
        # Try to find the event_id
        for id_ in self.handlers.keys():
            if self.handlers[id_] == widget:
                widget.disconnect(id_)
                del self.handlers[id_]
                break

    def connect_style_event(self, widget, set_fg=False, set_bg=False):
        self.disconnect_style_event(widget)
        id_ = widget.connect('style-set', self._on_style_set_event, set_fg,
            set_bg)
        self.handlers[id_] = widget

    def _on_style_set_event(self, widget, style, *opts):
        """
        Set style of widget from style class *.Frame.Eventbox
                opts[0] == True -> set fg color
                opts[1] == True -> set bg color
        """
        banner_eventbox = self.xml.get_object('banner_eventbox')
        self.disconnect_style_event(widget)
        context = widget.get_style_context()
        if opts[1]:
            bg_color = context.get_background_color(Gtk.StateFlags.SELECTED)
            banner_eventbox.override_background_color(Gtk.StateType.NORMAL, bg_color)
        if opts[0]:
            fg_color = context.get_color(Gtk.StateFlags.SELECTED)
            widget.override_color(Gtk.StateType.NORMAL, fg_color)
        self.connect_style_event(widget, opts[0], opts[1])

    def _conv_textview_key_press_event(self, widget, event):
        # translate any layout to latin_layout
        valid, entries = self.keymap.get_entries_for_keyval(event.keyval)
        keycode = entries[0].keycode
        if (event.get_state() & Gdk.ModifierType.CONTROL_MASK and keycode in (
        self.keycode_c, self.keycode_ins)) or (
        event.get_state() & Gdk.ModifierType.SHIFT_MASK and \
        event.keyval in (Gdk.KEY_Page_Down, Gdk.KEY_Page_Up)):
            return False
        self.parent_win.notebook.event(event)
        return True

    def show_emoticons_menu(self):
        if not gajim.config.get('emoticons_theme'):
            return
        gajim.interface.emoticon_menuitem_clicked = self.append_emoticon
        gajim.interface.emoticons_menu.popup(None, None, None, None, 1, 0)

    def _on_message_textview_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_space:
            self.space_pressed = True

        elif (self.space_pressed or self.msg_textview.undo_pressed) and \
        event.keyval not in (Gdk.KEY_Control_L, Gdk.KEY_Control_R) and \
        not (event.keyval == Gdk.KEY_z and event.get_state() & Gdk.ModifierType.CONTROL_MASK):
            # If the space key has been pressed and now it hasnt,
            # we save the buffer into the undo list. But be carefull we're not
            # pressiong Control again (as in ctrl+z)
            _buffer = widget.get_buffer()
            start_iter, end_iter = _buffer.get_bounds()
            self.msg_textview.save_undo(_buffer.get_text(start_iter, end_iter, True))
            self.space_pressed = False

        # Ctrl [+ Shift] + Tab are not forwarded to notebook. We handle it here
        if self.widget_name == 'groupchat_control':
            if event.keyval not in (Gdk.KEY_ISO_Left_Tab, Gdk.KEY_Tab):
                self.last_key_tabs = False
        if event.get_state() & Gdk.ModifierType.SHIFT_MASK:
            # CTRL + SHIFT + TAB
            if event.get_state() & Gdk.ModifierType.CONTROL_MASK and \
                            event.keyval == Gdk.KEY_ISO_Left_Tab:
                self.parent_win.move_to_next_unread_tab(False)
                return True
            # SHIFT + PAGE_[UP|DOWN]: send to conv_textview
            elif event.keyval == Gdk.KEY_Page_Down or \
                            event.keyval == Gdk.KEY_Page_Up:
                self.conv_textview.tv.event(event)
                return True
        elif event.get_state() & Gdk.ModifierType.CONTROL_MASK:
            if event.keyval == Gdk.KEY_Tab:  # CTRL + TAB
                self.parent_win.move_to_next_unread_tab(True)
                return True
################################################################################
        # temporary solution instead Gtk.binding_entry_add_signal
        message_buffer = self.msg_textview.get_buffer()
        event_state = event.get_state()
        if event.keyval == Gdk.KEY_Up:
            if event_state & Gdk.ModifierType.CONTROL_MASK:
                if event_state & Gdk.ModifierType.SHIFT_MASK: # Ctrl+Shift+UP
                    self.scroll_messages('up', message_buffer, 'received')
                else:  # Ctrl+UP
                    self.scroll_messages('up', message_buffer, 'sent')
            return True
        elif event.keyval == Gdk.KEY_Down:
            if event_state & Gdk.ModifierType.CONTROL_MASK:
                if event_state & Gdk.ModifierType.SHIFT_MASK: # Ctrl+Shift+Down
                    self.scroll_messages('down', message_buffer, 'received')
                else:  # Ctrl+Down
                    self.scroll_messages('down', message_buffer, 'sent')
            return True

        elif event.keyval == Gdk.KEY_Return or \
        event.keyval == Gdk.KEY_KP_Enter:  # ENTER
            message_textview = widget
            message_buffer = message_textview.get_buffer()
            start_iter, end_iter = message_buffer.get_bounds()
            message = message_buffer.get_text(start_iter, end_iter, False)
            xhtml = self.msg_textview.get_xhtml()

            if gajim.config.get('send_on_ctrl_enter'):
                if event_state & Gdk.ModifierType.CONTROL_MASK:  # CTRL + ENTER
                    send_message = True
                else:
                    end_iter = message_buffer.get_end_iter()
                    message_buffer.insert_at_cursor('\n')
                    send_message = False

            else: # send on Enter, do newline on Ctrl Enter
                if event_state & Gdk.ModifierType.CONTROL_MASK:  # Ctrl + ENTER
                    end_iter = message_buffer.get_end_iter()
                    message_buffer.insert_at_cursor('\n')
                    send_message = False
                else: # ENTER
                    send_message = True

            if gajim.connections[self.account].connected < 2 and send_message:
                # we are not connected
                dialogs.ErrorDialog(_('A connection is not available'),
                        _('Your message can not be sent until you are connected.'))
                send_message = False

            if send_message:
                self.send_message(message, xhtml=xhtml) # send the message
            return True
        elif event.keyval == Gdk.KEY_z: # CTRL+z
            if event_state & Gdk.ModifierType.CONTROL_MASK:
                self.msg_textview.undo()
                return True
################################################################################
        return False

    def _on_message_textview_mykeypress_event(self, widget, event_keyval,
    event_keymod):
        """
        When a key is pressed: if enter is pressed without the shift key, message
        (if not empty) is sent and printed in the conversation
        """
        # NOTE: handles mykeypress which is custom signal connected to this
        # CB in new_tab(). for this singal see message_textview.py
        message_textview = widget
        message_buffer = message_textview.get_buffer()
        start_iter, end_iter = message_buffer.get_bounds()
        message = message_buffer.get_text(start_iter, end_iter, False)
        xhtml = self.msg_textview.get_xhtml()

        # construct event instance from binding
        event = Gdk.Event(Gdk.EventType.KEY_PRESS)  # it's always a key-press here
        event.keyval = event_keyval
        event.state = event_keymod
        event.time = 0  # assign current time

        if event.keyval == Gdk.KEY_Up:
            if event.get_state() == Gdk.ModifierType.CONTROL_MASK:  # Ctrl+UP
                self.scroll_messages('up', message_buffer, 'sent')
            # Ctrl+Shift+UP
            elif event.get_state() == (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK):
                self.scroll_messages('up', message_buffer, 'received')
        elif event.keyval == Gdk.KEY_Down:
            if event.get_state() == Gdk.ModifierType.CONTROL_MASK:  # Ctrl+Down
                self.scroll_messages('down', message_buffer, 'sent')
            # Ctrl+Shift+Down
            elif event.get_state() == (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK):
                self.scroll_messages('down', message_buffer, 'received')
        elif event.keyval == Gdk.KEY_Return or \
                event.keyval == Gdk.KEY_KP_Enter:  # ENTER
            # NOTE: SHIFT + ENTER is not needed to be emulated as it is not
            # binding at all (textview's default action is newline)

            if gajim.config.get('send_on_ctrl_enter'):
                # here, we emulate GTK default action on ENTER (add new line)
                # normally I would add in keypress but it gets way to complex
                # to get instant result on changing this advanced setting
                if event.get_state() == 0:  # no ctrl, no shift just ENTER add newline
                    end_iter = message_buffer.get_end_iter()
                    message_buffer.insert_at_cursor('\n')
                    send_message = False
                elif event.get_state() & Gdk.ModifierType.CONTROL_MASK:  # CTRL + ENTER
                    send_message = True
            else: # send on Enter, do newline on Ctrl Enter
                if event.get_state() & Gdk.ModifierType.CONTROL_MASK:  # Ctrl + ENTER
                    end_iter = message_buffer.get_end_iter()
                    message_buffer.insert_at_cursor('\n')
                    send_message = False
                else: # ENTER
                    send_message = True

            if gajim.connections[self.account].connected < 2 and send_message:
                # we are not connected
                dialogs.ErrorDialog(_('A connection is not available'),
                    _('Your message can not be sent until you are connected.'),
                    transient_for=self.parent_win.window)
                send_message = False

            if send_message:
                self.send_message(message, xhtml=xhtml) # send the message
        elif event.keyval == Gdk.KEY_z: # CTRL+z
            if event.get_state() & Gdk.ModifierType.CONTROL_MASK:
                self.msg_textview.undo()
        else:
            # Give the control itself a chance to process
            self.handle_message_textview_mykey_press(widget, event_keyval,
                    event_keymod)

    def _on_drag_data_received(self, widget, context, x, y, selection,
                    target_type, timestamp):
        """
        Derived types SHOULD implement this
        """
        pass

    def _on_drag_leave(self, widget, context, time):
        # FIXME: DND on non editable TextView, find a better way
        self.drag_entered = False
        self.conv_textview.tv.set_editable(False)

    def _on_drag_motion(self, widget, context, x, y, time):
        # FIXME: DND on non editable TextView, find a better way
        if not self.drag_entered:
            # We drag new data over the TextView, make it editable to catch dnd
            self.drag_entered_conv = True
            self.conv_textview.tv.set_editable(True)

    def get_seclabel(self):
        label = None
        if self.seclabel_combo is not None:
            idx = self.seclabel_combo.get_active()
            if idx != -1:
                cat = gajim.connections[self.account].seclabel_catalogues[self.contact.jid]
                lname = cat[2][idx]
                label = cat[1][lname]
        return label

    def send_message(self, message, keyID='', type_='chat', chatstate=None,
    msg_id=None, resource=None, xhtml=None, callback=None, callback_args=[],
    process_commands=True, attention=False):
        """
        Send the given message to the active tab. Doesn't return None if error
        """
        if not message or message == '\n':
            return None

        if process_commands and self.process_as_command(message):
            return

        label = self.get_seclabel()

        def _cb(msg, cb, *cb_args):
            self.last_sent_msg = msg
            self.last_sent_txt = cb_args[0]
            if cb:
                cb(msg, *cb_args)

        if self.correcting and self.last_sent_msg:
            correction_msg = self.last_sent_msg
        else:
            correction_msg = None

        gajim.nec.push_outgoing_event(MessageOutgoingEvent(None,
            account=self.account, jid=self.contact.jid, message=message,
            keyID=keyID, type_=type_, chatstate=chatstate, msg_id=msg_id,
            resource=resource, user_nick=self.user_nick, xhtml=xhtml,
            label=label, callback=_cb, callback_args=[callback] + callback_args,
            control=self, attention=attention, correction_msg=correction_msg))

        # Record the history of sent messages
        self.save_message(message, 'sent')

        # Be sure to send user nickname only once according to JEP-0172
        self.user_nick = None

        # Clear msg input
        message_buffer = self.msg_textview.get_buffer()
        message_buffer.set_text('') # clear message buffer (and tv of course)

    def save_message(self, message, msg_type):
        # save the message, so user can scroll though the list with key up/down
        if msg_type == 'sent':
            history = self.sent_history
            pos = self.sent_history_pos
        else:
            history = self.received_history
            pos = self.received_history_pos
        size = len(history)
        scroll = False if pos == size else True # are we scrolling?
        # we don't want size of the buffer to grow indefinately
        max_size = gajim.config.get('key_up_lines')
        for i in range(size - max_size + 1):
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

    def print_conversation_line(self, text, kind, name, tim,
    other_tags_for_name=[], other_tags_for_time=[], other_tags_for_text=[],
    count_as_new=True, subject=None, old_kind=None, xhtml=None, simple=False,
    xep0184_id=None, graphics=True, displaymarking=None, msg_id=None,
    correct_id=None):
        """
        Print 'chat' type messages
        correct_id = (message_id, correct_id)
        """
        jid = self.contact.jid
        full_jid = self.get_full_jid()
        textview = self.conv_textview
        end = False
        if self.was_at_the_end or kind == 'outgoing':
            end = True
        old_txt = ''
        if name in self.last_received_txt:
            old_txt = self.last_received_txt[name]
        if correct_id and correct_id[1] and \
        name in self.conv_textview.last_received_message_marks and \
        correct_id[1] == self.last_received_id[name]:
            self.conv_textview.correct_last_received_message(text, xhtml,
                name, old_txt)
        else:
            textview.print_conversation_line(text, jid, kind, name, tim,
                other_tags_for_name, other_tags_for_time, other_tags_for_text,
                subject, old_kind, xhtml, simple=simple, graphics=graphics,
                displaymarking=displaymarking)

        if xep0184_id is not None:
            textview.show_xep0184_warning(xep0184_id)

        if not count_as_new:
            return
        if kind in ('incoming', 'outgoing'):
            self.last_received_txt[name] = text
            if correct_id:
                self.last_received_id[name] = correct_id[0]
        if kind == 'incoming':
            if not self.type_id == message_control.TYPE_GC or \
            gajim.config.get('notify_on_all_muc_messages') or \
            'marked' in other_tags_for_text:
                # it's a normal message, or a muc message with want to be
                # notified about if quitting just after
                # other_tags_for_text == ['marked'] --> highlighted gc message
                gajim.last_message_time[self.account][full_jid] = time.time()

        if kind in ('incoming', 'incoming_queue'):
            # Record the history of received messages
            self.save_message(text, 'received')

        if kind in ('incoming', 'incoming_queue', 'error'):
            gc_message = False
            if self.type_id == message_control.TYPE_GC:
                gc_message = True

            if ((self.parent_win and (not self.parent_win.get_active_control() or \
            self != self.parent_win.get_active_control() or \
            not self.parent_win.is_active() or not end)) or \
            (gc_message and \
            jid in gajim.interface.minimized_controls[self.account])) and \
            kind in ('incoming', 'incoming_queue', 'error'):
                # we want to have save this message in events list
                # other_tags_for_text == ['marked'] --> highlighted gc message
                if gc_message:
                    if 'marked' in other_tags_for_text:
                        type_ = 'printed_marked_gc_msg'
                    else:
                        type_ = 'printed_gc_msg'
                    event = 'gc_message_received'
                else:
                    type_ = 'printed_' + self.type_id
                    event = 'message_received'
                show_in_roster = notify.get_show_in_roster(event,
                    self.account, self.contact, self.session)
                show_in_systray = notify.get_show_in_systray(event,
                    self.account, self.contact, type_)

                event = gajim.events.create_event(type_, (text, subject, self,
                    msg_id), show_in_roster=show_in_roster,
                    show_in_systray=show_in_systray)
                gajim.events.add_event(self.account, full_jid, event)
                # We need to redraw contact if we show in roster
                if show_in_roster:
                    gajim.interface.roster.draw_contact(self.contact.jid,
                        self.account)

        if not self.parent_win:
            return

        if (not self.parent_win.get_active_control() or \
        self != self.parent_win.get_active_control() or \
        not self.parent_win.is_active() or not end) and \
        kind in ('incoming', 'incoming_queue', 'error'):
            self.parent_win.redraw_tab(self)
            if not self.parent_win.is_active():
                self.parent_win.show_title(True, self) # Enabled Urgent hint
            else:
                self.parent_win.show_title(False, self) # Disabled Urgent hint

    def toggle_emoticons(self):
        """
        Hide show emoticons_button and make sure emoticons_menu is always there
        when needed
        """
        emoticons_button = self.xml.get_object('emoticons_button')
        if gajim.config.get('emoticons_theme'):
            emoticons_button.show()
            emoticons_button.set_no_show_all(False)
        else:
            emoticons_button.hide()
            emoticons_button.set_no_show_all(True)

    def append_emoticon(self, str_):
        buffer_ = self.msg_textview.get_buffer()
        if buffer_.get_char_count():
            buffer_.insert_at_cursor(' %s ' % str_)
        else: # we are the beginning of buffer
            buffer_.insert_at_cursor('%s ' % str_)
        self.msg_textview.grab_focus()

    def on_emoticons_button_clicked(self, widget):
        """
        Popup emoticons menu
        """
        gajim.interface.emoticon_menuitem_clicked = self.append_emoticon
        gajim.interface.popup_emoticons_under_button(widget, self.parent_win)

    def on_formattings_button_clicked(self, widget):
        """
        Popup formattings menu
        """
        menu = Gtk.Menu()

        menuitems = ((_('Bold'), 'bold'),
        (_('Italic'), 'italic'),
        (_('Underline'), 'underline'),
        (_('Strike'), 'strike'))

        active_tags = self.msg_textview.get_active_tags()

        for menuitem in menuitems:
            item = Gtk.CheckMenuItem(menuitem[0])
            if menuitem[1] in active_tags:
                item.set_active(True)
            else:
                item.set_active(False)
            item.connect('activate', self.msg_textview.set_tag,
                    menuitem[1])
            menu.append(item)

        item = Gtk.SeparatorMenuItem.new() # separator
        menu.append(item)

        item = Gtk.ImageMenuItem(_('Color'))
        icon = Gtk.Image.new_from_stock(Gtk.STOCK_SELECT_COLOR, Gtk.IconSize.MENU)
        item.set_image(icon)
        item.connect('activate', self.on_color_menuitem_activale)
        menu.append(item)

        item = Gtk.ImageMenuItem(_('Font'))
        icon = Gtk.Image.new_from_stock(Gtk.STOCK_SELECT_FONT, Gtk.IconSize.MENU)
        item.set_image(icon)
        item.connect('activate', self.on_font_menuitem_activale)
        menu.append(item)

        item = Gtk.SeparatorMenuItem.new() # separator
        menu.append(item)

        item = Gtk.ImageMenuItem(_('Clear formating'))
        icon = Gtk.Image.new_from_stock(Gtk.STOCK_CLEAR, Gtk.IconSize.MENU)
        item.set_image(icon)
        item.connect('activate', self.msg_textview.clear_tags)
        menu.append(item)

        menu.show_all()
        menu.attach_to_widget(widget, None)
        gtkgui_helpers.popup_emoticons_under_button(menu, widget,
                self.parent_win)

    def on_color_menuitem_activale(self, widget):
        color_dialog = Gtk.ColorChooserDialog(None, self.parent_win.window)
        color_dialog.set_use_alpha(False)
        color_dialog.connect('response', self.msg_textview.color_set)
        color_dialog.show_all()

    def on_font_menuitem_activale(self, widget):
        font_dialog = Gtk.FontChooserDialog(None, self.parent_win.window)
        start, finish = self.msg_textview.get_active_iters()
        font_dialog.connect('response', self.msg_textview.font_set, start, finish)
        font_dialog.show_all()

    def on_actions_button_clicked(self, widget):
        """
        Popup action menu
        """
        menu = self.prepare_context_menu(hide_buttonbar_items=True)
        menu.show_all()
        menu.attach_to_widget(widget, None)
        gtkgui_helpers.popup_emoticons_under_button(menu, widget,
                self.parent_win)

    def update_font(self):
        font = Pango.FontDescription(gajim.config.get('conversation_font'))
        self.conv_textview.tv.override_font(font)
        self.msg_textview.override_font(font)

    def update_tags(self):
        self.conv_textview.update_tags()

    def clear(self, tv):
        buffer_ = tv.get_buffer()
        start, end = buffer_.get_bounds()
        buffer_.delete(start, end)

    def _on_history_menuitem_activate(self, widget=None, jid=None):
        """
        When history menuitem is pressed: call history window
        """
        if not jid:
            jid = self.contact.jid

        if 'logs' in gajim.interface.instances:
            gajim.interface.instances['logs'].window.present()
            gajim.interface.instances['logs'].open_history(jid, self.account)
        else:
            gajim.interface.instances['logs'] = \
                    history_window.HistoryWindow(jid, self.account)

    def _on_send_file(self, gc_contact=None):
        """
        gc_contact can be set when we are in a groupchat control
        """
        def _on_ok(c):
            gajim.interface.instances['file_transfers'].show_file_send_request(
                    self.account, c)
        if self.TYPE_ID == message_control.TYPE_PM:
            gc_contact = self.gc_contact
        if gc_contact:
            # gc or pm
            gc_control = gajim.interface.msg_win_mgr.get_gc_control(
                    gc_contact.room_jid, self.account)
            self_contact = gajim.contacts.get_gc_contact(self.account,
                    gc_control.room_jid, gc_control.nick)
            if gc_control.is_anonymous and gc_contact.affiliation not in ['admin',
            'owner'] and self_contact.affiliation in ['admin', 'owner']:
                contact = gajim.contacts.get_contact(self.account, gc_contact.jid)
                if not contact or contact.sub not in ('both', 'to'):
                    prim_text = _('Really send file?')
                    sec_text = _('If you send a file to %s, he/she will know your '
                            'real Jabber ID.') % gc_contact.name
                    dialog = dialogs.NonModalConfirmationDialog(prim_text,
                        sec_text, on_response_ok=(_on_ok, gc_contact))
                    dialog.popup()
                    return
            _on_ok(gc_contact)
            return
        _on_ok(self.contact)

    def on_minimize_menuitem_toggled(self, widget):
        """
        When a grouchat is minimized, unparent the tab, put it in roster etc
        """
        old_value = False
        minimized_gc = gajim.config.get_per('accounts', self.account,
                'minimized_gc').split()
        if self.contact.jid in minimized_gc:
            old_value = True
        minimize = widget.get_active()
        if minimize and not self.contact.jid in minimized_gc:
            minimized_gc.append(self.contact.jid)
        if not minimize and self.contact.jid in minimized_gc:
            minimized_gc.remove(self.contact.jid)
        if old_value != minimize:
            gajim.config.set_per('accounts', self.account, 'minimized_gc',
                    ' '.join(minimized_gc))

    def set_control_active(self, state):
        if state:
            jid = self.contact.jid
            if self.was_at_the_end:
                # we are at the end
                type_ = ['printed_' + self.type_id]
                if self.type_id == message_control.TYPE_GC:
                    type_ = ['printed_gc_msg', 'printed_marked_gc_msg']
                if not gajim.events.remove_events(self.account, self.get_full_jid(),
                types=type_):
                    # There were events to remove
                    self.redraw_after_event_removed(jid)

    def bring_scroll_to_end(self, textview, diff_y=0):
        """
        Scroll to the end of textview if end is not visible
        """
        if self.scroll_to_end_id:
            # a scroll is already planned
            return
        buffer_ = textview.get_buffer()
        end_iter = buffer_.get_end_iter()
        end_rect = textview.get_iter_location(end_iter)
        visible_rect = textview.get_visible_rect()
        # scroll only if expected end is not visible
        if end_rect.y >= (visible_rect.y + visible_rect.height + diff_y):
            self.scroll_to_end_id = GLib.idle_add(self.scroll_to_end_iter,
                    textview)

    def scroll_to_end_iter(self, textview):
        buffer_ = textview.get_buffer()
        end_iter = buffer_.get_end_iter()
        textview.scroll_to_iter(end_iter, 0, False, 1, 1)
        self.scroll_to_end_id = None
        return False

    def on_configure_event(self, msg_textview, event):
        """
        When message_textview changes its size: if the new height will enlarge
        the window, enable the scrollbar automatic policy.  Also enable scrollbar
        automatic policy for horizontal scrollbar if message we have in
        message_textview is too big
        """
        if msg_textview.get_window() is None:
            return

        min_height = self.conv_scrolledwindow.get_property('height-request')
        conversation_height = self.conv_textview.tv.get_window().get_size()[1]
        message_height = msg_textview.get_window().get_size()[1]
        message_width = msg_textview.get_window().get_size()[0]
        # new tab is not exposed yet
        if conversation_height < 2:
            return

        if conversation_height < min_height:
            min_height = conversation_height

        # we don't want to always resize in height the message_textview
        # so we have minimum on conversation_textview's scrolled window
        # but we also want to avoid window resizing so if we reach that
        # minimum for conversation_textview and maximum for message_textview
        # we set to automatic the scrollbar policy
        diff_y = message_height - event.height
        if diff_y != 0:
            if conversation_height + diff_y < min_height:
                if message_height + conversation_height - min_height > min_height:
                    policy = self.msg_scrolledwindow.get_property(
                            'vscrollbar-policy')
                    if policy != Gtk.PolicyType.AUTOMATIC:
                        self.msg_scrolledwindow.set_property('vscrollbar-policy',
                                Gtk.PolicyType.AUTOMATIC)
                        self.msg_scrolledwindow.set_property('height-request',
                                message_height + conversation_height - min_height)
            else:
                self.msg_scrolledwindow.set_property('vscrollbar-policy',
                        Gtk.PolicyType.NEVER)
                self.msg_scrolledwindow.set_property('height-request', -1)

        self.smooth = True # reinit the flag
        # enable scrollbar automatic policy for horizontal scrollbar
        # if message we have in message_textview is too big
        if event.width > message_width:
            self.msg_scrolledwindow.set_property('hscrollbar-policy',
                    Gtk.PolicyType.AUTOMATIC)
        else:
            self.msg_scrolledwindow.set_property('hscrollbar-policy',
                    Gtk.PolicyType.NEVER)

        return True

    def on_conversation_vadjustment_changed(self, adjustment):
        # used to stay at the end of the textview when we shrink conversation
        # textview.
        if self.was_at_the_end:
            if self.conv_textview.at_the_end():
                # we are at the end
                self.conv_textview.bring_scroll_to_end(-18)
            else:
                self.conv_textview.bring_scroll_to_end(-18, use_smooth=False)
        self.was_at_the_end = (adjustment.get_upper() - adjustment.get_value()\
            - adjustment.get_page_size()) < 18

    def on_conversation_vadjustment_value_changed(self, adjustment):
        # stop automatic scroll when we manually scroll
        if not self.conv_textview.auto_scrolling:
            self.conv_textview.stop_scrolling()
        self.was_at_the_end = (adjustment.get_upper() - adjustment.get_value() \
            - adjustment.get_page_size()) < 18
        if self.resource:
            jid = self.contact.get_full_jid()
        else:
            jid = self.contact.jid
        types_list = []
        type_ = self.type_id
        if type_ == message_control.TYPE_GC:
            type_ = 'gc_msg'
            types_list = ['printed_' + type_, type_, 'printed_marked_gc_msg']
        else: # Not a GC
            types_list = ['printed_' + type_, type_]

        if not len(gajim.events.get_events(self.account, jid, types_list)):
            return
        if not self.parent_win:
            return
        if self.conv_textview.at_the_end() and \
        self.parent_win.get_active_control() == self and \
        self.parent_win.window.is_active():
            # we are at the end
            if self.type_id == message_control.TYPE_GC:
                if not gajim.events.remove_events(self.account, jid,
                types=types_list):
                    self.redraw_after_event_removed(jid)
            elif self.session and self.session.remove_events(types_list):
                # There were events to remove
                self.redraw_after_event_removed(jid)

    def redraw_after_event_removed(self, jid):
        """
        We just removed a 'printed_*' event, redraw contact in roster or
        gc_roster and titles in roster and msg_win
        """
        self.parent_win.redraw_tab(self)
        self.parent_win.show_title()
        # TODO : get the contact and check notify.get_show_in_roster()
        if self.type_id == message_control.TYPE_PM:
            room_jid, nick = gajim.get_room_and_nick_from_fjid(jid)
            groupchat_control = gajim.interface.msg_win_mgr.get_gc_control(
                    room_jid, self.account)
            if room_jid in gajim.interface.minimized_controls[self.account]:
                groupchat_control = \
                        gajim.interface.minimized_controls[self.account][room_jid]
            contact = gajim.contacts.get_contact_with_highest_priority(
                self.account, room_jid)
            if contact:
                gajim.interface.roster.draw_contact(room_jid, self.account)
            if groupchat_control:
                groupchat_control.draw_contact(nick)
                if groupchat_control.parent_win:
                    groupchat_control.parent_win.redraw_tab(groupchat_control)
        else:
            gajim.interface.roster.draw_contact(jid, self.account)
            gajim.interface.roster.show_title()

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
            context = self.msg_textview.get_style_context()
            state = Gtk.StateFlags.NORMAL
            self.old_message_tv_color = context.get_background_color(state)
            color = Gdk.RGBA()
            Gdk.RGBA.parse(color, 'PaleGoldenrod')
            self.msg_textview.override_background_color(Gtk.StateType.NORMAL,
                color)
            message = history[pos - 1]
            msg_buf.set_text(message)
            return
        if self.correcting:
            # We were previously correcting
            self.msg_textview.override_background_color(Gtk.StateType.NORMAL,
                self.old_message_tv_color)
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

    def lighten_color(self, color):
        p = 0.4
        mask = 0
        color.red = int((color.red * p) + (mask * (1 - p)))
        color.green = int((color.green * p) + (mask * (1 - p)))
        color.blue = int((color.blue * p) + (mask * (1 - p)))
        return color

    def widget_set_visible(self, widget, state):
        """
        Show or hide a widget
        """
        # make the last message visible, when changing to "full view"
        if not state:
            GLib.idle_add(self.conv_textview.scroll_to_end_iter)

        widget.set_no_show_all(state)
        if state:
            widget.hide()
        else:
            widget.show_all()

    def chat_buttons_set_visible(self, state):
        """
        Toggle chat buttons
        """
        MessageControl.chat_buttons_set_visible(self, state)
        self.widget_set_visible(self.xml.get_object('actions_hbox'), state)

    def got_connected(self):
        self.msg_textview.set_sensitive(True)
        self.msg_textview.set_editable(True)
        self.update_toolbar()

    def got_disconnected(self):
        self.msg_textview.set_sensitive(False)
        self.msg_textview.set_editable(False)
        self.conv_textview.tv.grab_focus()

        self.no_autonegotiation = False
        self.update_toolbar()


################################################################################
class ChatControl(ChatControlBase):
    """
    A control for standard 1-1 chat
    """
    (
            JINGLE_STATE_NULL,
            JINGLE_STATE_CONNECTING,
            JINGLE_STATE_CONNECTION_RECEIVED,
            JINGLE_STATE_CONNECTED,
            JINGLE_STATE_ERROR
    ) = range(5)

    TYPE_ID = message_control.TYPE_CHAT
    old_msg_kind = None # last kind of the printed message

    # Set a command host to bound to. Every command given through a chat will be
    # processed with this command host.
    COMMAND_HOST = ChatCommands

    def __init__(self, parent_win, contact, acct, session, resource=None):
        ChatControlBase.__init__(self, self.TYPE_ID, parent_win,
            'chat_control', contact, acct, resource)

        self.gpg_is_active = False
        self.last_recv_message_id = None
        self.last_recv_message_marks = None
        # for muc use:
        # widget = self.xml.get_object('muc_window_actions_button')
        self.actions_button = self.xml.get_object('message_window_actions_button')
        id_ = self.actions_button.connect('clicked',
            self.on_actions_button_clicked)
        self.handlers[id_] = self.actions_button

        self._formattings_button = self.xml.get_object('formattings_button')

        self._add_to_roster_button = self.xml.get_object(
            'add_to_roster_button')
        id_ = self._add_to_roster_button.connect('clicked',
            self._on_add_to_roster_menuitem_activate)
        self.handlers[id_] = self._add_to_roster_button

        self._audio_button = self.xml.get_object('audio_togglebutton')
        id_ = self._audio_button.connect('toggled', self.on_audio_button_toggled)
        self.handlers[id_] = self._audio_button
        # add a special img
        gtkgui_helpers.add_image_to_button(self._audio_button,
            'gajim-mic_inactive')

        self._video_button = self.xml.get_object('video_togglebutton')
        id_ = self._video_button.connect('toggled', self.on_video_button_toggled)
        self.handlers[id_] = self._video_button
        # add a special img
        gtkgui_helpers.add_image_to_button(self._video_button,
            'gajim-cam_inactive')

        self._send_file_button = self.xml.get_object('send_file_button')
        # add a special img for send file button
        pixbuf = gtkgui_helpers.get_icon_pixmap('document-send', quiet=True)
        img = Gtk.Image.new_from_pixbuf(pixbuf)
        self._send_file_button.set_image(img)
        id_ = self._send_file_button.connect('clicked',
            self._on_send_file_menuitem_activate)
        self.handlers[id_] = self._send_file_button

        self._convert_to_gc_button = self.xml.get_object(
            'convert_to_gc_button')
        id_ = self._convert_to_gc_button.connect('clicked',
            self._on_convert_to_gc_menuitem_activate)
        self.handlers[id_] = self._convert_to_gc_button

        self._contact_information_button = self.xml.get_object(
            'contact_information_button')
        id_ = self._contact_information_button.connect('clicked',
            self._on_contact_information_menuitem_activate)
        self.handlers[id_] = self._contact_information_button

        compact_view = gajim.config.get('compact_view')
        self.chat_buttons_set_visible(compact_view)
        self.widget_set_visible(self.xml.get_object('banner_eventbox'),
            gajim.config.get('hide_chat_banner'))

        self.authentication_button = self.xml.get_object(
            'authentication_button')
        id_ = self.authentication_button.connect('clicked',
            self._on_authentication_button_clicked)
        self.handlers[id_] = self.authentication_button

        # Add lock image to show chat encryption
        self.lock_image = self.xml.get_object('lock_image')

        # Convert to GC icon
        img = self.xml.get_object('convert_to_gc_button_image')
        img.set_from_pixbuf(gtkgui_helpers.load_icon(
                'muc_active').get_pixbuf())

        self._audio_banner_image = self.xml.get_object('audio_banner_image')
        self._video_banner_image = self.xml.get_object('video_banner_image')
        self.audio_sid = None
        self.audio_state = self.JINGLE_STATE_NULL
        self.audio_available = False
        self.video_sid = None
        self.video_state = self.JINGLE_STATE_NULL
        self.video_available = False

        self.update_toolbar()

        self._pep_images = {}
        self._pep_images['mood'] = self.xml.get_object('mood_image')
        self._pep_images['activity'] = self.xml.get_object('activity_image')
        self._pep_images['tune'] = self.xml.get_object('tune_image')
        self._pep_images['location'] = self.xml.get_object('location_image')
        self.update_all_pep_types()

        # keep timeout id and window obj for possible big avatar
        # it is on enter-notify and leave-notify so no need to be
        # per jid
        self.show_bigger_avatar_timeout_id = None
        self.bigger_avatar_window = None
        self.show_avatar()

        # chatstate timers and state
        self.reset_kbd_mouse_timeout_vars()
        self._schedule_activity_timers()

        # Hook up signals
        id_ = self.parent_win.window.connect('motion-notify-event',
            self._on_window_motion_notify)
        self.handlers[id_] = self.parent_win.window
        message_tv_buffer = self.msg_textview.get_buffer()
        id_ = message_tv_buffer.connect('changed',
            self._on_message_tv_buffer_changed)
        self.handlers[id_] = message_tv_buffer

        widget = self.xml.get_object('avatar_eventbox')
        widget.set_property('height-request', gajim.config.get(
            'chat_avatar_height'))
        id_ = widget.connect('enter-notify-event',
            self.on_avatar_eventbox_enter_notify_event)
        self.handlers[id_] = widget

        id_ = widget.connect('leave-notify-event',
            self.on_avatar_eventbox_leave_notify_event)
        self.handlers[id_] = widget

        id_ = widget.connect('button-press-event',
            self.on_avatar_eventbox_button_press_event)
        self.handlers[id_] = widget

        widget = self.xml.get_object('location_eventbox')
        id_ = widget.connect('button-release-event',
            self.on_location_eventbox_button_release_event)
        self.handlers[id_] = widget
        id_ = widget.connect('enter-notify-event',
            self.on_location_eventbox_enter_notify_event)
        self.handlers[id_] = widget
        id_ = widget.connect('leave-notify-event',
            self.on_location_eventbox_leave_notify_event)
        self.handlers[id_] = widget

        for key in ('1', '2', '3', '4', '5', '6', '7', '8', '9', '*', '0', '#'):
            widget = self.xml.get_object(key + '_button')
            id_ = widget.connect('pressed', self.on_num_button_pressed, key)
            self.handlers[id_] = widget
            id_ = widget.connect('released', self.on_num_button_released)
            self.handlers[id_] = widget

        self.dtmf_window = self.xml.get_object('dtmf_window')
        self.dtmf_window.get_child().set_direction(Gtk.TextDirection.LTR)
        id_ = self.dtmf_window.connect('focus-out-event',
            self.on_dtmf_window_focus_out_event)
        self.handlers[id_] = self.dtmf_window

        widget = self.xml.get_object('dtmf_button')
        id_ = widget.connect('clicked', self.on_dtmf_button_clicked)
        self.handlers[id_] = widget

        widget = self.xml.get_object('mic_hscale')
        id_ = widget.connect('value_changed', self.on_mic_hscale_value_changed)
        self.handlers[id_] = widget

        widget = self.xml.get_object('sound_hscale')
        id_ = widget.connect('value_changed', self.on_sound_hscale_value_changed)
        self.handlers[id_] = widget

        self.info_bar = Gtk.InfoBar()
        content_area = self.info_bar.get_content_area()
        self.info_bar_label = Gtk.Label()
        self.info_bar_label.set_use_markup(True)
        self.info_bar_label.set_alignment(0, 0)
        content_area.add(self.info_bar_label)
        self.info_bar.set_no_show_all(True)
        widget = self.xml.get_object('vbox2')
        widget.pack_start(self.info_bar, False, True, 5)
        widget.reorder_child(self.info_bar, 1)

        # List of waiting infobar messages
        self.info_bar_queue = []

        self.subscribe_events()

        if not session:
            # Don't use previous session if we want to a specific resource
            # and it's not the same
            if not resource:
                resource = contact.resource
            session = gajim.connections[self.account].find_controlless_session(
                self.contact.jid, resource)

        self.setup_seclabel(self.xml.get_object('label_selector'))
        if session:
            session.control = self
            self.session = session

            if session.enable_encryption:
                self.print_esession_details()

        # Enable encryption if needed
        self.no_autonegotiation = False
        e2e_is_active = self.session and self.session.enable_encryption
        gpg_pref = gajim.config.get_per('contacts', contact.jid, 'gpg_enabled')

        # try GPG first
        if not e2e_is_active and gpg_pref and \
        gajim.config.get_per('accounts', self.account, 'keyid') and \
        gajim.connections[self.account].USE_GPG:
            self.gpg_is_active = True
            gajim.encrypted_chats[self.account].append(contact.jid)
            msg = _('OpenPGP encryption enabled')
            ChatControlBase.print_conversation_line(self, msg, 'status', '',
                None)

            if self.session:
                self.session.loggable = gajim.config.get_per('accounts',
                    self.account, 'log_encrypted_sessions')
            # GPG is always authenticated as we use GPG's WoT
            self._show_lock_image(self.gpg_is_active, 'OpenPGP',
                self.gpg_is_active, self.session and self.session.is_loggable(),
                True)

        self.update_ui()
        # restore previous conversation
        self.restore_conversation()
        self.msg_textview.grab_focus()

        gajim.ged.register_event_handler('pep-received', ged.GUI1,
            self._nec_pep_received)
        gajim.ged.register_event_handler('vcard-received', ged.GUI1,
            self._nec_vcard_received)
        gajim.ged.register_event_handler('failed-decrypt', ged.GUI1,
            self._nec_failed_decrypt)
        gajim.ged.register_event_handler('chatstate-received', ged.GUI1,
            self._nec_chatstate_received)
        gajim.ged.register_event_handler('caps-received', ged.GUI1,
            self._nec_caps_received)

        # PluginSystem: adding GUI extension point for this ChatControl
        # instance object
        gajim.plugin_manager.gui_extension_point('chat_control', self)

    def subscribe_events(self):
        """
        Register listeners to the events class
        """
        gajim.events.event_added_subscribe(self.on_event_added)
        gajim.events.event_removed_subscribe(self.on_event_removed)

    def unsubscribe_events(self):
        """
        Unregister listeners to the events class
        """
        gajim.events.event_added_unsubscribe(self.on_event_added)
        gajim.events.event_removed_unsubscribe(self.on_event_removed)

    def _update_toolbar(self):
        if (gajim.connections[self.account].connected > 1 and not \
        self.TYPE_ID == 'pm') or (self.contact.show != 'offline' and \
        self.TYPE_ID == 'pm'):
            emoticons_button = self.xml.get_object('emoticons_button')
            emoticons_button.set_sensitive(True)
            send_button = self.xml.get_object('send_button')
            send_button.set_sensitive(True)
        # Formatting
        if self.contact.supports(NS_XHTML_IM) and not self.gpg_is_active:
            self._formattings_button.set_sensitive(True)
            self._formattings_button.set_tooltip_text(_(
                'Show a list of formattings'))
        else:
            self._formattings_button.set_sensitive(False)
            if self.contact.supports(NS_XHTML_IM):
                self._formattings_button.set_tooltip_text(_('Formattings are '
                    'not available when GPG is active'))
            else:
                self._formattings_button.set_tooltip_text(_('This contact does '
                    'not support HTML'))

        # Add to roster
        if not isinstance(self.contact, GC_Contact) \
        and _('Not in Roster') in self.contact.groups and \
        gajim.connections[self.account].roster_supported:
            self._add_to_roster_button.show()
        else:
            self._add_to_roster_button.hide()

        # Jingle detection
        if self.contact.supports(NS_JINGLE_ICE_UDP) and \
        gajim.HAVE_FARSTREAM and self.contact.resource:
            self.audio_available = self.contact.supports(NS_JINGLE_RTP_AUDIO)
            self.video_available = self.contact.supports(NS_JINGLE_RTP_VIDEO)
        else:
            if self.video_available or self.audio_available:
                self.stop_jingle()
            self.video_available = False
            self.audio_available = False

        # Audio buttons
        self._audio_button.set_sensitive(self.audio_available)

        # Video buttons
        self._video_button.set_sensitive(self.video_available)

        # change tooltip text for audio and video buttons if farstream is
        # not installed
        audio_tooltip_text = _('Toggle audio session') + '\n'
        video_tooltip_text = _('Toggle video session') + '\n'
        if not gajim.HAVE_FARSTREAM:
            ext_text = _('Feature not available, see Help->Features')
            self._audio_button.set_tooltip_text(audio_tooltip_text + ext_text)
            self._video_button.set_tooltip_text(video_tooltip_text + ext_text)
        elif not self.audio_available :
            ext_text =_('Feature not supported by remote client')
            self._audio_button.set_tooltip_text(audio_tooltip_text + ext_text)
            self._video_button.set_tooltip_text(video_tooltip_text + ext_text)
        else:
            self._audio_button.set_tooltip_text(audio_tooltip_text[:-1])
            self._video_button.set_tooltip_text(video_tooltip_text[:-1])

        # Send file
        if ((self.contact.supports(NS_FILE) or \
        self.contact.supports(NS_JINGLE_FILE_TRANSFER)) and \
        (self.type_id == 'chat' or self.gc_contact.resource)) and \
        self.contact.show != 'offline':
            self._send_file_button.set_sensitive(True)
            self._send_file_button.set_tooltip_text(_('Send files'))
        else:
            self._send_file_button.set_sensitive(False)
            if not (self.contact.supports(NS_FILE) or self.contact.supports(
            NS_JINGLE_FILE_TRANSFER)):
                self._send_file_button.set_tooltip_text(_(
                    "This contact does not support file transfer."))
            else:
                self._send_file_button.set_tooltip_text(
                    _("You need to know the real JID of the contact to send "
                    "him or her a file."))

        # Convert to GC
        if gajim.config.get_per('accounts', self.account, 'is_zeroconf'):
            self._convert_to_gc_button.set_no_show_all(True)
            self._convert_to_gc_button.hide()
        else:
            if self.contact.supports(NS_MUC):
                self._convert_to_gc_button.set_sensitive(True)
            else:
                self._convert_to_gc_button.set_sensitive(False)

        # Information
        if gajim.account_is_disconnected(self.account):
            self._contact_information_button.set_sensitive(False)
        else:
            self._contact_information_button.set_sensitive(True)


    def update_all_pep_types(self):
        for pep_type in self._pep_images:
            self.update_pep(pep_type)

    def update_pep(self, pep_type):
        if isinstance(self.contact, GC_Contact):
            return
        if pep_type not in self._pep_images:
            return
        pep = self.contact.pep
        img = self._pep_images[pep_type]
        if pep_type in pep:
            img.set_from_pixbuf(gtkgui_helpers.get_pep_as_pixbuf(pep[pep_type]))
            img.set_tooltip_markup(pep[pep_type].asMarkupText())
            img.show()
        else:
            img.hide()

    def _nec_pep_received(self, obj):
        if obj.conn.name != self.account:
            return
        if obj.jid != self.contact.jid:
            return

        if obj.pep_type == 'nickname':
            self.update_ui()
            self.parent_win.redraw_tab(self)
            self.parent_win.show_title()
        else:
            self.update_pep(obj.pep_type)

    def _update_jingle(self, jingle_type):
        if jingle_type not in ('audio', 'video'):
            return
        banner_image = getattr(self, '_' + jingle_type + '_banner_image')
        state = getattr(self, jingle_type + '_state')
        if state == self.JINGLE_STATE_NULL:
            banner_image.hide()
        else:
            banner_image.show()
        if state == self.JINGLE_STATE_CONNECTING:
            banner_image.set_from_stock(
                    Gtk.STOCK_CONVERT, 1)
        elif state == self.JINGLE_STATE_CONNECTION_RECEIVED:
            banner_image.set_from_stock(
                    Gtk.STOCK_NETWORK, 1)
        elif state == self.JINGLE_STATE_CONNECTED:
            banner_image.set_from_stock(
                    Gtk.STOCK_CONNECT, 1)
        elif state == self.JINGLE_STATE_ERROR:
            banner_image.set_from_stock(
                    Gtk.STOCK_DIALOG_WARNING, 1)
        self.update_toolbar()

    def update_audio(self):
        self._update_jingle('audio')
        hbox = self.xml.get_object('audio_buttons_hbox')
        if self.audio_state == self.JINGLE_STATE_CONNECTED:
            # Set volume from config
            input_vol = gajim.config.get('audio_input_volume')
            output_vol = gajim.config.get('audio_output_volume')
            input_vol = max(min(input_vol, 100), 0)
            output_vol = max(min(output_vol, 100), 0)
            self.xml.get_object('mic_hscale').set_value(input_vol)
            self.xml.get_object('sound_hscale').set_value(output_vol)
            # Show vbox
            hbox.set_no_show_all(False)
            hbox.show_all()
        elif not self.audio_sid:
            hbox.set_no_show_all(True)
            hbox.hide()

    def update_video(self):
        self._update_jingle('video')

    def change_resource(self, resource):
        old_full_jid = self.get_full_jid()
        self.resource = resource
        new_full_jid = self.get_full_jid()
        # update gajim.last_message_time
        if old_full_jid in gajim.last_message_time[self.account]:
            gajim.last_message_time[self.account][new_full_jid] = \
                    gajim.last_message_time[self.account][old_full_jid]
        # update events
        gajim.events.change_jid(self.account, old_full_jid, new_full_jid)
        # update MessageWindow._controls
        self.parent_win.change_jid(self.account, old_full_jid, new_full_jid)

    def stop_jingle(self, sid=None, reason=None):
        if self.audio_sid and sid in (self.audio_sid, None):
            self.close_jingle_content('audio')
        if self.video_sid and sid in (self.video_sid, None):
            self.close_jingle_content('video')

    def _set_jingle_state(self, jingle_type, state, sid=None, reason=None):
        if jingle_type not in ('audio', 'video'):
            return
        if state in ('connecting', 'connected', 'stop', 'error') and reason:
            str = _('%(type)s state : %(state)s, reason: %(reason)s') % {
                    'type': jingle_type.capitalize(), 'state': state, 'reason': reason}
            self.print_conversation(str, 'info')

        states = {'connecting': self.JINGLE_STATE_CONNECTING,
                'connection_received': self.JINGLE_STATE_CONNECTION_RECEIVED,
                'connected': self.JINGLE_STATE_CONNECTED,
                'stop': self.JINGLE_STATE_NULL,
                'error': self.JINGLE_STATE_ERROR}

        jingle_state = states[state]
        if getattr(self, jingle_type + '_state') == jingle_state or state == 'error':
            return

        if state == 'stop' and getattr(self, jingle_type + '_sid') not in (None, sid):
            return

        setattr(self, jingle_type + '_state', jingle_state)

        if jingle_state == self.JINGLE_STATE_NULL:
            setattr(self, jingle_type + '_sid', None)
        if state in ('connection_received', 'connecting'):
            setattr(self, jingle_type + '_sid', sid)

        getattr(self, '_' + jingle_type + '_button').set_active(jingle_state != self.JINGLE_STATE_NULL)

        getattr(self, 'update_' + jingle_type)()

    def set_audio_state(self, state, sid=None, reason=None):
        self._set_jingle_state('audio', state, sid=sid, reason=reason)

    def set_video_state(self, state, sid=None, reason=None):
        self._set_jingle_state('video', state, sid=sid, reason=reason)

    def _get_audio_content(self):
        session = gajim.connections[self.account].get_jingle_session(
                self.contact.get_full_jid(), self.audio_sid)
        return session.get_content('audio')

    def on_num_button_pressed(self, widget, num):
        self._get_audio_content()._start_dtmf(num)

    def on_num_button_released(self, released):
        self._get_audio_content()._stop_dtmf()

    def on_dtmf_button_clicked(self, widget):
        self.dtmf_window.show_all()

    def on_dtmf_window_focus_out_event(self, widget, event):
        self.dtmf_window.hide()

    def on_mic_hscale_value_changed(self, widget, value):
        self._get_audio_content().set_mic_volume(value / 100)
        # Save volume to config
        gajim.config.set('audio_input_volume', value)

    def on_sound_hscale_value_changed(self, widget, value):
        self._get_audio_content().set_out_volume(value / 100)
        # Save volume to config
        gajim.config.set('audio_output_volume', value)

    def on_avatar_eventbox_enter_notify_event(self, widget, event):
        """
        Enter the eventbox area so we under conditions add a timeout to show a
        bigger avatar after 0.5 sec
        """
        jid = self.contact.jid
        avatar_pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(jid)
        if avatar_pixbuf in ('ask', None):
            return
        avatar_w = avatar_pixbuf.get_width()
        avatar_h = avatar_pixbuf.get_height()

        scaled_buf = self.xml.get_object('avatar_image').get_pixbuf()
        scaled_buf_w = scaled_buf.get_width()
        scaled_buf_h = scaled_buf.get_height()

        # do we have something bigger to show?
        if avatar_w > scaled_buf_w or avatar_h > scaled_buf_h:
            # wait for 0.5 sec in case we leave earlier
            if self.show_bigger_avatar_timeout_id is not None:
                GLib.source_remove(self.show_bigger_avatar_timeout_id)
            self.show_bigger_avatar_timeout_id = GLib.timeout_add(500,
                    self.show_bigger_avatar, widget)

    def on_avatar_eventbox_leave_notify_event(self, widget, event):
        """
        Left the eventbox area that holds the avatar img
        """
        # did we add a timeout? if yes remove it
        if self.show_bigger_avatar_timeout_id is not None:
            GLib.source_remove(self.show_bigger_avatar_timeout_id)
            self.show_bigger_avatar_timeout_id = None

    def on_avatar_eventbox_button_press_event(self, widget, event):
        """
        If right-clicked, show popup
        """
        if event.button == 3: # right click
            menu = Gtk.Menu()
            menuitem = Gtk.ImageMenuItem.new_from_stock(Gtk.STOCK_SAVE_AS, None)
            id_ = menuitem.connect('activate',
                gtkgui_helpers.on_avatar_save_as_menuitem_activate,
                self.contact.jid, self.contact.get_shown_name())
            self.handlers[id_] = menuitem
            menu.append(menuitem)
            menu.show_all()
            menu.connect('selection-done', lambda w: w.destroy())
            # show the menu
            menu.show_all()
            menu.attach_to_widget(widget, None)
            menu.popup(None, None, None, None, event.button, event.time)
        return True

    def on_location_eventbox_button_release_event(self, widget, event):
        if 'location' in self.contact.pep:
            location = self.contact.pep['location']._pep_specific_data
            if ('lat' in location) and ('lon' in location):
                uri = 'http://www.openstreetmap.org/?' + \
                        'mlat=%(lat)s&mlon=%(lon)s&zoom=16' % {'lat': location['lat'],
                        'lon': location['lon']}
                helpers.launch_browser_mailer('url', uri)

    def on_location_eventbox_leave_notify_event(self, widget, event):
        """
        Just moved the mouse so show the cursor
        """
        cursor = Gdk.Cursor.new(Gdk.CursorType.LEFT_PTR)
        self.parent_win.window.get_window().set_cursor(cursor)

    def on_location_eventbox_enter_notify_event(self, widget, event):
        cursor = Gdk.Cursor.new(Gdk.CursorType.HAND2)
        self.parent_win.window.get_window().set_cursor(cursor)

    def _on_window_motion_notify(self, widget, event):
        """
        It gets called no matter if it is the active window or not
        """
        if self.parent_win.get_active_jid() == self.contact.jid:
            # if window is the active one, change vars assisting chatstate
            self.mouse_over_in_last_5_secs = True
            self.mouse_over_in_last_30_secs = True

    def _schedule_activity_timers(self):
        self.possible_paused_timeout_id = GLib.timeout_add_seconds(5,
                self.check_for_possible_paused_chatstate, None)
        self.possible_inactive_timeout_id = GLib.timeout_add_seconds(30,
                self.check_for_possible_inactive_chatstate, None)

    def update_ui(self):
        # The name banner is drawn here
        ChatControlBase.update_ui(self)
        self.update_toolbar()

    def _update_banner_state_image(self):
        contact = gajim.contacts.get_contact_with_highest_priority(self.account,
                self.contact.jid)
        if not contact or self.resource:
            # For transient contacts
            contact = self.contact
        show = contact.show
        jid = contact.jid

        # Set banner image
        img_32 = gajim.interface.roster.get_appropriate_state_images(jid,
                size='32', icon_name=show)
        img_16 = gajim.interface.roster.get_appropriate_state_images(jid,
                icon_name=show)
        if show in img_32 and img_32[show].get_pixbuf():
            # we have 32x32! use it!
            banner_image = img_32[show]
            use_size_32 = True
        else:
            banner_image = img_16[show]
            use_size_32 = False

        banner_status_img = self.xml.get_object('banner_status_image')
        if banner_image.get_storage_type() == Gtk.ImageType.ANIMATION:
            banner_status_img.set_from_animation(banner_image.get_animation())
        else:
            pix = banner_image.get_pixbuf()
            if pix is not None:
                if use_size_32:
                    banner_status_img.set_from_pixbuf(pix)
                else: # we need to scale 16x16 to 32x32
                    scaled_pix = pix.scale_simple(32, 32,
                                                    GdkPixbuf.InterpType.BILINEAR)
                    banner_status_img.set_from_pixbuf(scaled_pix)

    def draw_banner_text(self):
        """
        Draw the text in the fat line at the top of the window that houses the
        name, jid
        """
        contact = self.contact
        jid = contact.jid

        banner_name_label = self.xml.get_object('banner_name_label')

        name = contact.get_shown_name()
        if self.resource:
            name += '/' + self.resource
        if self.TYPE_ID == message_control.TYPE_PM:
            name = i18n.direction_mark +  _(
                '%(nickname)s from group chat %(room_name)s') % \
                {'nickname': name, 'room_name': self.room_name}
        name = i18n.direction_mark + GLib.markup_escape_text(name)

        # We know our contacts nick, but if another contact has the same nick
        # in another account we need to also display the account.
        # except if we are talking to two different resources of the same contact
        acct_info = ''
        for account in gajim.contacts.get_accounts():
            if account == self.account:
                continue
            if acct_info: # We already found a contact with same nick
                break
            for jid in gajim.contacts.get_jid_list(account):
                other_contact_ = \
                    gajim.contacts.get_first_contact_from_jid(account, jid)
                if other_contact_.get_shown_name() == \
                self.contact.get_shown_name():
                    acct_info = i18n.direction_mark + ' (%s)' % \
                        GLib.markup_escape_text(self.account)
                    break

        status = contact.status
        if status is not None:
            banner_name_label.set_ellipsize(Pango.EllipsizeMode.END)
            self.banner_status_label.set_ellipsize(Pango.EllipsizeMode.END)
            status_reduced = helpers.reduce_chars_newlines(status, max_lines=1)
        else:
            status_reduced = ''
        status_escaped = GLib.markup_escape_text(status_reduced)

        font_attrs, font_attrs_small = self.get_font_attrs()
        st = gajim.config.get('displayed_chat_state_notifications')
        cs = contact.chatstate
        if cs and st in ('composing_only', 'all'):
            if contact.show == 'offline':
                chatstate = ''
            elif st == 'all' or cs == 'composing':
                chatstate = helpers.get_uf_chatstate(cs)
            else:
                chatstate = ''

            label_text = '<span %s>%s</span><span %s>%s %s</span>' \
                % (font_attrs,  name, font_attrs_small, acct_info, chatstate)
            if acct_info:
                acct_info = i18n.direction_mark + ' ' + acct_info
            label_tooltip = '%s%s %s' % (name, acct_info, chatstate)
        else:
            # weight="heavy" size="x-large"
            label_text = '<span %s>%s</span><span %s>%s</span>' % \
                    (font_attrs, name, font_attrs_small, acct_info)
            if acct_info:
                acct_info = i18n.direction_mark + ' ' + acct_info
            label_tooltip = '%s%s' % (name, acct_info)

        if status_escaped:
            status_text = self.urlfinder.sub(self.make_href, status_escaped)
            status_text = '<span %s>%s</span>' % (font_attrs_small, status_text)
            self.banner_status_label.set_tooltip_text(status)
            self.banner_status_label.set_no_show_all(False)
            self.banner_status_label.show()
        else:
            status_text = ''
            self.banner_status_label.hide()
            self.banner_status_label.set_no_show_all(True)

        self.banner_status_label.set_markup(status_text)
        # setup the label that holds name and jid
        banner_name_label.set_markup(label_text)
        banner_name_label.set_tooltip_text(label_tooltip)

    def close_jingle_content(self, jingle_type):
        sid = getattr(self, jingle_type + '_sid')
        if not sid:
            return
        setattr(self, jingle_type + '_sid', None)
        setattr(self, jingle_type + '_state', self.JINGLE_STATE_NULL)
        session = gajim.connections[self.account].get_jingle_session(
                self.contact.get_full_jid(), sid)
        if session:
            content = session.get_content(jingle_type)
            if content:
                session.remove_content(content.creator, content.name)
        getattr(self, '_' + jingle_type + '_button').set_active(False)
        getattr(self, 'update_' + jingle_type)()

    def on_jingle_button_toggled(self, widget, jingle_type):
        img_name = 'gajim-%s_%s' % ({'audio': 'mic', 'video': 'cam'}[jingle_type],
                        {True: 'active', False: 'inactive'}[widget.get_active()])
        path_to_img = gtkgui_helpers.get_icon_path(img_name)

        if widget.get_active():
            if getattr(self, jingle_type + '_state') == \
            self.JINGLE_STATE_NULL:
                if jingle_type == 'video':
                    video_hbox = self.xml.get_object('video_hbox')
                    video_hbox.set_no_show_all(False)
                    if gajim.config.get('video_see_self'):
                        fixed = self.xml.get_object('outgoing_fixed')
                        fixed.set_no_show_all(False)
                        video_hbox.show_all()
                        if os.name == 'nt':
                            out_xid = self.xml.get_object(
                                'outgoing_drawingarea').get_window().handle
                        else:
                            out_xid = self.xml.get_object(
                                'outgoing_drawingarea').get_window().xid
                    else:
                        out_xid = None
                    video_hbox.show_all()
                    in_xid = self.xml.get_object('incoming_drawingarea').get_window().xid
                    sid = gajim.connections[self.account].start_video(
                        self.contact.get_full_jid(), in_xid, out_xid)
                else:
                    sid = getattr(gajim.connections[self.account],
                        'start_' + jingle_type)(self.contact.get_full_jid())
                getattr(self, 'set_' + jingle_type + '_state')('connecting', sid)
        else:
            video_hbox = self.xml.get_object('video_hbox')
            video_hbox.set_no_show_all(True)
            video_hbox.hide()
            fixed = self.xml.get_object('outgoing_fixed')
            fixed.set_no_show_all(True)
            self.close_jingle_content(jingle_type)

        img = getattr(self, '_' + jingle_type + '_button').get_property('image')
        img.set_from_file(path_to_img)

    def on_audio_button_toggled(self, widget):
        self.on_jingle_button_toggled(widget, 'audio')

    def on_video_button_toggled(self, widget):
        self.on_jingle_button_toggled(widget, 'video')

    def _toggle_gpg(self):
        if not self.gpg_is_active and not self.contact.keyID:
            dialogs.ErrorDialog(_('No OpenPGP key assigned'),
                _('No OpenPGP key is assigned to this contact. So you cannot '
                'encrypt messages with OpenPGP.'))
            return
        ec = gajim.encrypted_chats[self.account]
        if self.gpg_is_active:
            # Disable encryption
            ec.remove(self.contact.jid)
            self.gpg_is_active = False
            loggable = False
            msg = _('OpenPGP encryption disabled')
            ChatControlBase.print_conversation_line(self, msg, 'status', '',
                None)
            if self.session:
                self.session.loggable = True

        else:
            # Enable encryption
            ec.append(self.contact.jid)
            self.gpg_is_active = True
            msg = _('OpenPGP encryption enabled')
            ChatControlBase.print_conversation_line(self, msg, 'status', '',
                None)

            loggable = gajim.config.get_per('accounts', self.account,
                'log_encrypted_sessions')

            if self.session:
                self.session.loggable = loggable

                loggable = self.session.is_loggable()
            else:
                loggable = loggable and gajim.config.should_log(self.account,
                        self.contact.jid)

            if loggable:
                msg = _('Session WILL be logged')
            else:
                msg = _('Session WILL NOT be logged')

            ChatControlBase.print_conversation_line(self, msg,
                    'status', '', None)

        gajim.config.set_per('contacts', self.contact.jid,
                'gpg_enabled', self.gpg_is_active)

        self._show_lock_image(self.gpg_is_active, 'OpenPGP',
                self.gpg_is_active, loggable, True)

    def _show_lock_image(self, visible, enc_type='', enc_enabled=False,
                    chat_logged=False, authenticated=False):
        """
        Set lock icon visibility and create tooltip
        """
        #encryption %s active
        status_string = enc_enabled and _('is') or _('is NOT')
        #chat session %s be logged
        logged_string = chat_logged and _('will') or _('will NOT')

        if authenticated:
            #About encrypted chat session
            authenticated_string = _('and authenticated')
            img_path = gtkgui_helpers.get_icon_path('security-high')
        else:
            #About encrypted chat session
            authenticated_string = _('and NOT authenticated')
            img_path = gtkgui_helpers.get_icon_path('security-low')
        self.lock_image.set_from_file(img_path)

        #status will become 'is' or 'is not', authentificaed will become
        #'and authentificated' or 'and not authentificated', logged will become
        #'will' or 'will not'
        tooltip = _('%(type)s encryption %(status)s active %(authenticated)s.\n'
                'Your chat session %(logged)s be logged.') % {'type': enc_type,
                'status': status_string, 'authenticated': authenticated_string,
                'logged': logged_string}

        self.authentication_button.set_tooltip_text(tooltip)
        self.widget_set_visible(self.authentication_button, not visible)
        self.lock_image.set_sensitive(enc_enabled)

    def _on_authentication_button_clicked(self, widget):
        if self.gpg_is_active:
            dialogs.GPGInfoWindow(self, self.parent_win.window)
        elif self.session and self.session.enable_encryption:
            dialogs.ESessionInfoWindow(self.session, self.parent_win.window)

    def send_message(self, message, keyID='', chatstate=None, xhtml=None,
    process_commands=True, attention=False):
        """
        Send a message to contact
        """
        message = helpers.remove_invalid_xml_chars(message)
        if message in ('', None, '\n'):
            return None

        # refresh timers
        self.reset_kbd_mouse_timeout_vars()

        contact = self.contact

        encrypted = bool(self.session) and self.session.enable_encryption

        keyID = ''
        if self.gpg_is_active:
            keyID = contact.keyID
            encrypted = True
            if not keyID:
                keyID = 'UNKNOWN'

        chatstates_on = gajim.config.get('outgoing_chat_state_notifications') != \
                'disabled'
        chatstate_to_send = None
        if chatstates_on and contact is not None:
            if contact.supports(NS_CHATSTATES):
                # send active chatstate on every message (as XEP says)
                chatstate_to_send = 'active'
                contact.our_chatstate = 'active'

                GLib.source_remove(self.possible_paused_timeout_id)
                GLib.source_remove(self.possible_inactive_timeout_id)
                self._schedule_activity_timers()

        def _on_sent(msg_stanza, message, encrypted, xhtml, label, old_txt):
            id_ = msg_stanza.getID()
            if self.contact.supports(NS_RECEIPTS) and gajim.config.get_per(
            'accounts', self.account, 'request_receipt'):
                xep0184_id = id_
            else:
                xep0184_id = None
            if label:
                displaymarking = label.getTag('displaymarking')
            else:
                displaymarking = None
            if self.correcting and \
            self.conv_textview.last_sent_message_marks[0]:
                self.conv_textview.correct_last_sent_message(message, xhtml,
                    self.get_our_nick(), old_txt)
                self.correcting = False
                self.msg_textview.override_background_color(
                    Gtk.StateType.NORMAL, self.old_message_tv_color)
                return
            self.print_conversation(message, self.contact.jid,
                encrypted=encrypted, xep0184_id=xep0184_id, xhtml=xhtml,
                displaymarking=displaymarking)

        ChatControlBase.send_message(self, message, keyID, type_='chat',
            chatstate=chatstate_to_send, xhtml=xhtml, callback=_on_sent,
            callback_args=[message, encrypted, xhtml, self.get_seclabel(),
            self.last_sent_txt], process_commands=process_commands,
            attention=attention)

    def check_for_possible_paused_chatstate(self, arg):
        """
        Did we move mouse of that window or write something in message textview
        in the last 5 seconds? If yes - we go active for mouse, composing for
        kbd.  If not - we go paused if we were previously composing
        """
        contact = self.contact
        jid = contact.jid
        current_state = contact.our_chatstate
        if current_state is False: # jid doesn't support chatstates
            return False # stop looping

        message_buffer = self.msg_textview.get_buffer()
        if self.kbd_activity_in_last_5_secs and message_buffer.get_char_count():
            # Only composing if the keyboard activity was in text entry
            self.send_chatstate('composing')
        elif self.mouse_over_in_last_5_secs and current_state == 'inactive' and\
        jid == self.parent_win.get_active_jid():
            self.send_chatstate('active')
        else:
            if current_state == 'composing':
                self.send_chatstate('paused') # pause composing

        # assume no activity and let the motion-notify or 'insert-text' make them
        # True refresh 30 seconds vars too or else it's 30 - 5 = 25 seconds!
        self.reset_kbd_mouse_timeout_vars()
        return True # loop forever

    def check_for_possible_inactive_chatstate(self, arg):
        """
        Did we move mouse over that window or wrote something in message textview
        in the last 30 seconds? if yes - we go active. If no - we go inactive
        """
        contact = self.contact

        current_state = contact.our_chatstate
        if current_state is False: # jid doesn't support chatstates
            return False # stop looping

        if self.mouse_over_in_last_5_secs or self.kbd_activity_in_last_5_secs:
            return True # loop forever

        if not self.mouse_over_in_last_30_secs or \
        self.kbd_activity_in_last_30_secs:
            self.send_chatstate('inactive', contact)

        # assume no activity and let the motion-notify or 'insert-text' make them
        # True refresh 30 seconds too or else it's 30 - 5 = 25 seconds!
        self.reset_kbd_mouse_timeout_vars()
        return True # loop forever

    def reset_kbd_mouse_timeout_vars(self):
        self.kbd_activity_in_last_5_secs = False
        self.mouse_over_in_last_5_secs = False
        self.mouse_over_in_last_30_secs = False
        self.kbd_activity_in_last_30_secs = False

    def on_cancel_session_negotiation(self):
        msg = _('Session negotiation cancelled')
        ChatControlBase.print_conversation_line(self, msg, 'status', '', None)

    def print_archiving_session_details(self):
        """
        Print esession settings to textview
        """
        archiving = bool(self.session) and isinstance(self.session,
                ArchivingStanzaSession) and self.session.archiving
        if archiving:
            msg = _('This session WILL be archived on server')
        else:
            msg = _('This session WILL NOT be archived on server')
        ChatControlBase.print_conversation_line(self, msg, 'status', '', None)

    def print_esession_details(self):
        """
        Print esession settings to textview
        """
        e2e_is_active = bool(self.session) and self.session.enable_encryption
        if e2e_is_active:
            msg = _('This session is encrypted')

            if self.session.is_loggable():
                msg += _(' and WILL be logged')
            else:
                msg += _(' and WILL NOT be logged')

            ChatControlBase.print_conversation_line(self, msg, 'status', '', None)

            if not self.session.verified_identity:
                ChatControlBase.print_conversation_line(self, _("Remote contact's identity not verified. Click the shield button for more details."), 'status', '', None)
        else:
            msg = _('E2E encryption disabled')
            ChatControlBase.print_conversation_line(self, msg, 'status', '', None)

        self._show_lock_image(e2e_is_active, 'E2E', e2e_is_active, self.session and \
                        self.session.is_loggable(), self.session and self.session.verified_identity)

    def print_session_details(self, old_session=None):
        if isinstance(self.session, EncryptedStanzaSession) or \
        (old_session and isinstance(old_session, EncryptedStanzaSession)):
            self.print_esession_details()
        elif isinstance(self.session, ArchivingStanzaSession):
            self.print_archiving_session_details()

    def get_our_nick(self):
        return gajim.nicks[self.account]

    def print_conversation(self, text, frm='', tim=None, encrypted=False,
    subject=None, xhtml=None, simple=False, xep0184_id=None,
    displaymarking=None, msg_id=None, correct_id=None):
        """
        Print a line in the conversation

        If frm is set to status: it's a status message.
        if frm is set to error: it's an error message. The difference between
                status and error is mainly that with error, msg count as a new message
                (in systray and in control).
        If frm is set to info: it's a information message.
        If frm is set to print_queue: it is incomming from queue.
        If frm is set to another value: it's an outgoing message.
        If frm is not set: it's an incomming message.
        """
        contact = self.contact

        if frm == 'status':
            if not gajim.config.get('print_status_in_chats'):
                return
            kind = 'status'
            name = ''
        elif frm == 'error':
            kind = 'error'
            name = ''
        elif frm == 'info':
            kind = 'info'
            name = ''
        else:
            if self.session and self.session.enable_encryption:
                # ESessions
                if not encrypted:
                    msg = _('The following message was NOT encrypted')
                    ChatControlBase.print_conversation_line(self, msg, 'status',
                        '',  tim)
            else:
                # GPG encryption
                if encrypted and not self.gpg_is_active:
                    msg = _('The following message was encrypted')
                    ChatControlBase.print_conversation_line(self, msg, 'status',
                        '', tim)
                    # turn on OpenPGP if this was in fact a XEP-0027 encrypted
                    # message
                    if encrypted == 'xep27':
                        self._toggle_gpg()
                elif not encrypted and self.gpg_is_active:
                    msg = _('The following message was NOT encrypted')
                    ChatControlBase.print_conversation_line(self, msg, 'status',
                        '', tim)
            if not frm:
                kind = 'incoming'
                name = contact.get_shown_name()
            elif frm == 'print_queue': # incoming message, but do not update time
                kind = 'incoming_queue'
                name = contact.get_shown_name()
            else:
                kind = 'outgoing'
                name = self.get_our_nick()
                if not xhtml and not (encrypted and self.gpg_is_active) and \
                gajim.config.get('rst_formatting_outgoing_messages'):
                    from common.rst_xhtml_generator import create_xhtml
                    xhtml = create_xhtml(text)
                    if xhtml:
                        xhtml = '<body xmlns="%s">%s</body>' % (NS_XHTML, xhtml)
        ChatControlBase.print_conversation_line(self, text, kind, name, tim,
            subject=subject, old_kind=self.old_msg_kind, xhtml=xhtml,
            simple=simple, xep0184_id=xep0184_id, displaymarking=displaymarking,
            msg_id=msg_id, correct_id=correct_id)
        if text.startswith('/me ') or text.startswith('/me\n'):
            self.old_msg_kind = None
        else:
            self.old_msg_kind = kind

    def get_tab_label(self, chatstate):
        unread = ''
        if self.resource:
            jid = self.contact.get_full_jid()
        else:
            jid = self.contact.jid
        num_unread = len(gajim.events.get_events(self.account, jid,
                ['printed_' + self.type_id, self.type_id]))
        if num_unread == 1 and not gajim.config.get('show_unread_tab_icon'):
            unread = '*'
        elif num_unread > 1:
            unread = '[' + str(num_unread) + ']'

        # Draw tab label using chatstate
        theme = gajim.config.get('roster_theme')
        color_s = None
        if not chatstate:
            chatstate = self.contact.chatstate
        if chatstate is not None:
            if chatstate == 'composing':
                color_s = gajim.config.get_per('themes', theme,
                    'state_composing_color')
            elif chatstate == 'inactive':
                color_s = gajim.config.get_per('themes', theme,
                    'state_inactive_color')
            elif chatstate == 'gone':
                color_s = gajim.config.get_per('themes', theme,
                    'state_gone_color')
            elif chatstate == 'paused':
                color_s = gajim.config.get_per('themes', theme,
                    'state_paused_color')

        context = self.parent_win.notebook.get_style_context()
        if color_s:
            # We set the color for when it's the current tab or not
            color = Gdk.RGBA()
            ok = Gdk.RGBA.parse(color, color_s)
            if not ok:
                del color
                color = context.get_color(Gtk.StateFlags.ACTIVE)
            # In inactive tab color to be lighter against the darker inactive
            # background
            if chatstate in ('inactive', 'gone') and\
            self.parent_win.get_active_control() != self:
                color = self.lighten_color(color)
        else: # active or not chatstate, get color from gtk
            color = context.get_color(Gtk.StateFlags.ACTIVE)

        name = self.contact.get_shown_name()
        if self.resource:
            name += '/' + self.resource
        label_str = GLib.markup_escape_text(name)
        if num_unread: # if unread, text in the label becomes bold
            label_str = '<b>' + unread + label_str + '</b>'
        return (label_str, color)

    def get_tab_image(self, count_unread=True):
        if self.resource:
            jid = self.contact.get_full_jid()
        else:
            jid = self.contact.jid
        if count_unread:
            num_unread = len(gajim.events.get_events(self.account, jid,
                    ['printed_' + self.type_id, self.type_id]))
        else:
            num_unread = 0
        # Set tab image (always 16x16); unread messages show the 'event' image
        tab_img = None

        if num_unread and gajim.config.get('show_unread_tab_icon'):
            img_16 = gajim.interface.roster.get_appropriate_state_images(
                    self.contact.jid, icon_name='event')
            tab_img = img_16['event']
        else:
            contact = gajim.contacts.get_contact_with_highest_priority(
                    self.account, self.contact.jid)
            if not contact or self.resource:
                # For transient contacts
                contact = self.contact
            img_16 = gajim.interface.roster.get_appropriate_state_images(
                    self.contact.jid, icon_name=contact.show)
            tab_img = img_16[contact.show]

        return tab_img

    def prepare_context_menu(self, hide_buttonbar_items=False):
        """
        Set compact view menuitem active state sets active and sensitivity state
        for toggle_gpg_menuitem sets sensitivity for history_menuitem (False for
        tranasports) and file_transfer_menuitem and hide()/show() for
        add_to_roster_menuitem
        """
        if gajim.jid_is_transport(self.contact.jid):
            menu = gui_menu_builder.get_transport_menu(self.contact,
                self.account)
        else:
            menu = gui_menu_builder.get_contact_menu(self.contact, self.account,
                use_multiple_contacts=False, show_start_chat=False,
                show_encryption=True, control=self,
                show_buttonbar_items=not hide_buttonbar_items)
        return menu

    def send_chatstate(self, state, contact=None):
        """
        Send OUR chatstate as STANDLONE chat state message (eg. no body)
        to contact only if new chatstate is different from the previous one
        if jid is not specified, send to active tab
        """
        # JEP 85 does not allow resending the same chatstate
        # this function checks for that and just returns so it's safe to call it
        # with same state.

        # This functions also checks for violation in state transitions
        # and raises RuntimeException with appropriate message
        # more on that http://xmpp.org/extensions/xep-0085.html#statechart

        # do not send nothing if we have chat state notifications disabled
        # that means we won't reply to the <active/> from other peer
        # so we do not broadcast jep85 capabalities
        chatstate_setting = gajim.config.get('outgoing_chat_state_notifications')
        if chatstate_setting == 'disabled':
            return
        elif chatstate_setting == 'composing_only' and state != 'active' and\
                state != 'composing':
            return

        if contact is None:
            contact = self.parent_win.get_active_contact()
            if contact is None:
                # contact was from pm in MUC, and left the room so contact is None
                # so we cannot send chatstate anymore
                return

        # Don't send chatstates to offline contacts
        if contact.show == 'offline':
            return

        if not contact.supports(NS_CHATSTATES):
            return

        # if the new state we wanna send (state) equals
        # the current state (contact.our_chatstate) then return
        if contact.our_chatstate == state:
            return

        # if wel're inactive prevent composing (XEP violation)
        if contact.our_chatstate == 'inactive' and state == 'composing':
            # go active before
            gajim.nec.push_outgoing_event(MessageOutgoingEvent(None,
                account=self.account, jid=self.contact.jid, chatstate='active',
                control=self))
            contact.our_chatstate = 'active'
            self.reset_kbd_mouse_timeout_vars()

        gajim.nec.push_outgoing_event(MessageOutgoingEvent(None,
            account=self.account, jid=self.contact.jid, chatstate=state,
            msg_id=contact.msg_id, control=self))

        contact.our_chatstate = state
        if state == 'active':
            self.reset_kbd_mouse_timeout_vars()

    def shutdown(self):
        # PluginSystem: removing GUI extension points connected with ChatControl
        # instance object
        gajim.plugin_manager.remove_gui_extension_point('chat_control', self)

        gajim.ged.remove_event_handler('pep-received', ged.GUI1,
            self._nec_pep_received)
        gajim.ged.remove_event_handler('vcard-received', ged.GUI1,
            self._nec_vcard_received)
        gajim.ged.remove_event_handler('failed-decrypt', ged.GUI1,
            self._nec_failed_decrypt)
        gajim.ged.remove_event_handler('chatstate-received', ged.GUI1,
            self._nec_chatstate_received)
        gajim.ged.remove_event_handler('caps-received', ged.GUI1,
            self._nec_caps_received)

        self.unsubscribe_events()

        # Send 'gone' chatstate
        self.send_chatstate('gone', self.contact)
        self.contact.chatstate = None
        self.contact.our_chatstate = None

        for jingle_type in ('audio', 'video'):
            self.close_jingle_content(jingle_type)

        # disconnect self from session
        if self.session:
            self.session.control = None

        # Disconnect timer callbacks
        GLib.source_remove(self.possible_paused_timeout_id)
        GLib.source_remove(self.possible_inactive_timeout_id)
        # Remove bigger avatar window
        if self.bigger_avatar_window:
            self.bigger_avatar_window.destroy()
        # Clean events
        gajim.events.remove_events(self.account, self.get_full_jid(),
                types=['printed_' + self.type_id, self.type_id])
        # Remove contact instance if contact has been removed
        key = (self.contact.jid, self.account)
        roster = gajim.interface.roster
        if key in roster.contacts_to_be_removed.keys() and \
        not roster.contact_has_pending_roster_events(self.contact,
        self.account):
            backend = roster.contacts_to_be_removed[key]['backend']
            del roster.contacts_to_be_removed[key]
            roster.remove_contact(self.contact.jid, self.account, force=True,
                backend=backend)
        # remove all register handlers on widgets, created by self.xml
        # to prevent circular references among objects
        for i in list(self.handlers.keys()):
            if self.handlers[i].handler_is_connected(i):
                self.handlers[i].disconnect(i)
            del self.handlers[i]
        self.conv_textview.del_handlers()
        if gajim.config.get('use_speller') and HAS_GTK_SPELL:
            spell_obj = gtkspell.get_from_text_view(self.msg_textview)
            if spell_obj:
                spell_obj.detach()
        self.msg_textview.destroy()
        # PluginSystem: calling shutdown of super class (ChatControlBase) to let
        # it remove it's GUI extension points
        super(ChatControl, self).shutdown()

    def minimizable(self):
        return False

    def safe_shutdown(self):
        return False

    def allow_shutdown(self, method, on_yes, on_no, on_minimize):
        if time.time() - gajim.last_message_time[self.account]\
        [self.get_full_jid()] < 2:
            # 2 seconds

            def on_ok():
                on_yes(self)

            def on_cancel():
                on_no(self)

            dialogs.ConfirmationDialog(
                #%s is being replaced in the code with JID
                _('You just received a new message from "%s"') % \
                self.contact.jid,
                _('If you close this tab and you have history disabled, '\
                'this message will be lost.'), on_response_ok=on_ok,
                on_response_cancel=on_cancel,
                transient_for=self.parent_win.window)
            return
        on_yes(self)

    def _nec_chatstate_received(self, obj):
        """
        Handle incoming chatstate that jid SENT TO us
        """
        self.draw_banner_text()
        # update chatstate in tab for this chat
        self.parent_win.redraw_tab(self, self.contact.chatstate)

    def _nec_caps_received(self, obj):
        if obj.conn.name != self.account:
            return
        if self.TYPE_ID == 'chat' and obj.jid != self.contact.jid:
            return
        if self.TYPE_ID == 'pm' and obj.fjid != self.contact.jid:
            return
        self.update_ui()

    def set_control_active(self, state):
        ChatControlBase.set_control_active(self, state)
        # send chatstate inactive to the one we're leaving
        # and active to the one we visit
        if state:
            message_buffer = self.msg_textview.get_buffer()
            if message_buffer.get_char_count():
                self.send_chatstate('paused', self.contact)
            else:
                self.send_chatstate('active', self.contact)
            self.reset_kbd_mouse_timeout_vars()
            GLib.source_remove(self.possible_paused_timeout_id)
            GLib.source_remove(self.possible_inactive_timeout_id)
            self._schedule_activity_timers()
        else:
            self.send_chatstate('inactive', self.contact)
        # Hide bigger avatar window
        if self.bigger_avatar_window:
            self.bigger_avatar_window.destroy()
            self.bigger_avatar_window = None
            # Re-show the small avatar
            self.show_avatar()

    def show_avatar(self):
        if not gajim.config.get('show_avatar_in_chat'):
            return

        jid_with_resource = self.contact.get_full_jid()
        pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(jid_with_resource)
        if pixbuf == 'ask':
            # we don't have the vcard
            if self.TYPE_ID == message_control.TYPE_PM:
                if self.gc_contact.jid:
                    # We know the real jid of this contact
                    real_jid = self.gc_contact.jid
                    if self.gc_contact.resource:
                        real_jid += '/' + self.gc_contact.resource
                else:
                    real_jid = jid_with_resource
                gajim.connections[self.account].request_vcard(real_jid,
                        jid_with_resource)
            else:
                gajim.connections[self.account].request_vcard(jid_with_resource)
            return
        elif pixbuf:
            scaled_pixbuf = gtkgui_helpers.get_scaled_pixbuf(pixbuf, 'chat')
        else:
            scaled_pixbuf = None

        image = self.xml.get_object('avatar_image')
        image.set_from_pixbuf(scaled_pixbuf)
        image.show_all()

    def _nec_vcard_received(self, obj):
        if obj.conn.name != self.account:
            return
        j = gajim.get_jid_without_resource(self.contact.jid)
        if obj.jid != j:
            return
        self.show_avatar()

    def _on_drag_data_received(self, widget, context, x, y, selection,
            target_type, timestamp):
        if not selection.data:
            return
        if self.TYPE_ID == message_control.TYPE_PM:
            c = self.gc_contact
        else:
            c = self.contact
        if target_type == self.TARGET_TYPE_URI_LIST:
            if not c.resource: # If no resource is known, we can't send a file
                return
            uri = selection.data.strip()
            uri_splitted = uri.split() # we may have more than one file dropped
            for uri in uri_splitted:
                path = helpers.get_file_path_from_dnd_dropped_uri(uri)
                if os.path.isfile(path): # is it file?
                    ft = gajim.interface.instances['file_transfers']
                    ft.send_file(self.account, c, path)
            return

        # chat2muc
        treeview = gajim.interface.roster.tree
        model = treeview.get_model()
        data = selection.data
        path = treeview.get_selection().get_selected_rows()[1][0]
        iter_ = model.get_iter(path)
        type_ = model[iter_][2]
        if type_ != 'contact': # source is not a contact
            return
        dropped_jid = data

        dropped_transport = gajim.get_transport_name_from_jid(dropped_jid)
        c_transport = gajim.get_transport_name_from_jid(c.jid)
        if dropped_transport or c_transport:
            return # transport contacts cannot be invited

        dialogs.TransformChatToMUC(self.account, [c.jid], [dropped_jid])

    def _on_message_tv_buffer_changed(self, textbuffer):
        self.kbd_activity_in_last_5_secs = True
        self.kbd_activity_in_last_30_secs = True
        if textbuffer.get_char_count():
            self.send_chatstate('composing', self.contact)

            e2e_is_active = self.session and \
                    self.session.enable_encryption
            e2e_pref = gajim.config.get_per('accounts', self.account,
                    'enable_esessions') and gajim.config.get_per('accounts',
                    self.account, 'autonegotiate_esessions') and gajim.config.get_per(
                    'contacts', self.contact.jid, 'autonegotiate_esessions')
            want_e2e = not e2e_is_active and not self.gpg_is_active \
                    and e2e_pref

            if want_e2e and not self.no_autonegotiation \
            and gajim.HAVE_PYCRYPTO and self.contact.supports(NS_ESESSION):
                self.begin_e2e_negotiation()
            elif (not self.session or not self.session.status) and \
            gajim.connections[self.account].archiving_supported:
                self.begin_archiving_negotiation()
        else:
            self.send_chatstate('active', self.contact)

    def restore_conversation(self):
        jid = self.contact.jid
        # don't restore lines if it's a transport
        if gajim.jid_is_transport(jid):
            return

        # How many lines to restore and when to time them out
        restore_how_many = gajim.config.get('restore_lines')
        if restore_how_many <= 0:
            return
        timeout = gajim.config.get('restore_timeout') # in minutes

        # number of messages that are in queue and are already logged, we want
        # to avoid duplication
        pending_how_many = len(gajim.events.get_events(self.account, jid,
                ['chat', 'pm']))
        if self.resource:
            pending_how_many += len(gajim.events.get_events(self.account,
                    self.contact.get_full_jid(), ['chat', 'pm']))

        try:
            rows = gajim.logger.get_last_conversation_lines(jid, restore_how_many,
                    pending_how_many, timeout, self.account)
        except exceptions.DatabaseMalformed:
            import common.logger
            dialogs.ErrorDialog(_('Database Error'),
                _('The database file (%s) cannot be read. Try to repair it or '
                'remove it (all history will be lost).') % common.logger.LOG_DB_PATH)
            rows = []
        local_old_kind = None
        self.conv_textview.just_cleared = True
        for row in rows: # row[0] time, row[1] has kind, row[2] the message
            if not row[2]: # message is empty, we don't print it
                continue
            if row[1] in (constants.KIND_CHAT_MSG_SENT,
                            constants.KIND_SINGLE_MSG_SENT):
                kind = 'outgoing'
                name = self.get_our_nick()
            elif row[1] in (constants.KIND_SINGLE_MSG_RECV,
                            constants.KIND_CHAT_MSG_RECV):
                kind = 'incoming'
                name = self.contact.get_shown_name()
            elif row[1] == constants.KIND_ERROR:
                kind = 'status'
                name = self.contact.get_shown_name()

            tim = time.localtime(float(row[0]))

            if gajim.config.get('restored_messages_small'):
                small_attr = ['small']
            else:
                small_attr = []
            xhtml = None
            if row[2].startswith('<body '):
                xhtml = row[2]
            ChatControlBase.print_conversation_line(self, row[2], kind, name,
                tim, small_attr, small_attr + ['restored_message'],
                small_attr + ['restored_message'], False,
                old_kind=local_old_kind, xhtml=xhtml)
            if row[2].startswith('/me ') or row[2].startswith('/me\n'):
                local_old_kind = None
            else:
                local_old_kind = kind
        if len(rows):
            self.conv_textview.print_empty_line()

    def read_queue(self):
        """
        Read queue and print messages containted in it
        """
        jid = self.contact.jid
        jid_with_resource = jid
        if self.resource:
            jid_with_resource += '/' + self.resource
        events = gajim.events.get_events(self.account, jid_with_resource)

        # list of message ids which should be marked as read
        message_ids = []
        for event in events:
            if event.type_ != self.type_id:
                continue
            data = event.parameters
            kind = data[2]
            if kind == 'error':
                kind = 'info'
            else:
                kind = 'print_queue'
            if data[11]:
                kind = 'out'
            dm = data[10]
            self.print_conversation(data[0], kind, tim=data[3],
                encrypted=data[4], subject=data[1], xhtml=data[7],
                displaymarking=dm)
            if len(data) > 6 and isinstance(data[6], int):
                message_ids.append(data[6])

            if len(data) > 8 and not self.session:
                self.set_session(data[8])
        if message_ids:
            gajim.logger.set_read_messages(message_ids)
        gajim.events.remove_events(self.account, jid_with_resource,
                types=[self.type_id])

        typ = 'chat' # Is it a normal chat or a pm ?

        # reset to status image in gc if it is a pm
        # Is it a pm ?
        room_jid, nick = gajim.get_room_and_nick_from_fjid(jid)
        control = gajim.interface.msg_win_mgr.get_gc_control(room_jid,
                self.account)
        if control and control.type_id == message_control.TYPE_GC:
            control.update_ui()
            control.parent_win.show_title()
            typ = 'pm'

        self.redraw_after_event_removed(jid)
        if (self.contact.show in ('offline', 'error')):
            show_offline = gajim.config.get('showoffline')
            show_transports = gajim.config.get('show_transports_group')
            if (not show_transports and gajim.jid_is_transport(jid)) or \
            (not show_offline and typ == 'chat' and \
            len(gajim.contacts.get_contacts(self.account, jid)) < 2):
                gajim.interface.roster.remove_to_be_removed(self.contact.jid,
                        self.account)
            elif typ == 'pm':
                control.remove_contact(nick)

    def show_bigger_avatar(self, small_avatar):
        """
        Resize the avatar, if needed, so it has at max half the screen size and
        shows it
        """
        #if not small_avatar.window:
            ### Tab has been closed since we hovered the avatar
            #return
        avatar_pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(
                self.contact.jid)
        if avatar_pixbuf in ('ask', None):
            return
        # Hide the small avatar
        # this code hides the small avatar when we show a bigger one in case
        # the avatar has a transparency hole in the middle
        # so when we show the big one we avoid seeing the small one behind.
        # It's why I set it transparent.
        image = self.xml.get_object('avatar_image')
        pixbuf = image.get_pixbuf()
        pixbuf.fill(0xffffff00) # RGBA
        image.set_from_pixbuf(pixbuf)
        #image.queue_draw()

        screen_w = Gdk.Screen.width()
        screen_h = Gdk.Screen.height()
        avatar_w = avatar_pixbuf.get_width()
        avatar_h = avatar_pixbuf.get_height()
        half_scr_w = screen_w / 2
        half_scr_h = screen_h / 2
        if avatar_w > half_scr_w:
            avatar_w = half_scr_w
        if avatar_h > half_scr_h:
            avatar_h = half_scr_h
        # we should make the cursor visible
        # gtk+ doesn't make use of the motion notify on gtkwindow by default
        # so this line adds that

        alloc = small_avatar.get_allocation()
        # make the bigger avatar window show up centered
        small_avatar_x, small_avatar_y = alloc.x, alloc.y
        translated_coordinates = small_avatar.translate_coordinates(
            gajim.interface.roster.window, 0, 0)
        if translated_coordinates:
            small_avatar_x, small_avatar_y = translated_coordinates
        roster_x, roster_y  = self.parent_win.window.get_window().get_origin()[1:]
        center_x = roster_x + small_avatar_x + (alloc.width / 2)
        center_y = roster_y + small_avatar_y + (alloc.height / 2)
        pos_x, pos_y = center_x - (avatar_w / 2), center_y - (avatar_h / 2)

        dialogs.BigAvatarWindow(avatar_pixbuf, pos_x, pos_y, avatar_w,
            avatar_h, self.show_avatar)

    def _on_send_file_menuitem_activate(self, widget):
        self._on_send_file()

    def _on_add_to_roster_menuitem_activate(self, widget):
        dialogs.AddNewContactWindow(self.account, self.contact.jid)

    def _on_contact_information_menuitem_activate(self, widget):
        gajim.interface.roster.on_info(widget, self.contact, self.account)

    def _on_toggle_gpg_menuitem_activate(self, widget):
        self._toggle_gpg()

    def _on_convert_to_gc_menuitem_activate(self, widget):
        """
        User wants to invite some friends to chat
        """
        dialogs.TransformChatToMUC(self.account, [self.contact.jid])

    def _on_toggle_e2e_menuitem_activate(self, widget):
        if self.session and self.session.enable_encryption:
            # e2e was enabled, disable it
            jid = str(self.session.jid)
            thread_id = self.session.thread_id

            self.session.terminate_e2e()

            gajim.connections[self.account].delete_session(jid, thread_id)

            # presumably the user had a good reason to shut it off, so
            # disable autonegotiation too
            self.no_autonegotiation = True
        else:
            self.begin_e2e_negotiation()

    def begin_negotiation(self):
        self.no_autonegotiation = True

        if not self.session:
            fjid = self.contact.get_full_jid()
            new_sess = gajim.connections[self.account].make_new_session(fjid, type_=self.type_id)
            self.set_session(new_sess)

    def begin_e2e_negotiation(self):
        self.begin_negotiation()
        self.session.negotiate_e2e(False)

    def begin_archiving_negotiation(self):
        self.begin_negotiation()
        self.session.negotiate_archiving()

    def _nec_failed_decrypt(self, obj):
        if obj.session != self.session:
            return

        details = _('Unable to decrypt message from %s\nIt may have been '
            'tampered with.') % obj.fjid
        self.print_conversation_line(details, 'status', '', obj.timestamp)

        # terminate the session
        thread_id = self.session.thread_id
        self.session.terminate_e2e()
        obj.conn.delete_session(obj.fjid, thread_id)

        # restart the session
        self.begin_e2e_negotiation()

        # Stop emission so it doesn't go to gui_interface
        return True

    def got_connected(self):
        ChatControlBase.got_connected(self)
        # Refreshing contact
        contact = gajim.contacts.get_contact_with_highest_priority(
                self.account, self.contact.jid)
        if isinstance(contact, GC_Contact):
            contact = contact.as_contact()
        if contact:
            self.contact = contact
        self.draw_banner()
        emoticons_button = self.xml.get_object('emoticons_button')
        emoticons_button.set_sensitive(True)
        send_button = self.xml.get_object('send_button')
        send_button.set_sensitive(True)

    def got_disconnected(self):
        # Emoticons button
        emoticons_button = self.xml.get_object('emoticons_button')
        emoticons_button.set_sensitive(False)
        send_button = self.xml.get_object('send_button')
        send_button.set_sensitive(False)
        # Add to roster
        self._add_to_roster_button.hide()
        # Audio button
        self._audio_button.set_sensitive(False)
        # Video button
        self._video_button.set_sensitive(False)
        # Send file button
        self._send_file_button.set_tooltip_text('')
        self._send_file_button.set_sensitive(False)
        # Convert to GC button
        self._convert_to_gc_button.set_sensitive(False)

        ChatControlBase.got_disconnected(self)

    def update_status_display(self, name, uf_show, status):
        """
        Print the contact's status and update the status/GPG image
        """
        self.update_ui()
        self.parent_win.redraw_tab(self)

        self.print_conversation(_('%(name)s is now %(status)s') % {'name': name,
                'status': uf_show}, 'status')

        if status:
            self.print_conversation(' (', 'status', simple=True)
            self.print_conversation('%s' % (status), 'status', simple=True)
            self.print_conversation(')', 'status', simple=True)

    def _info_bar_show_message(self):
        if self.info_bar.get_visible():
            # A message is already shown
            return
        if not self.info_bar_queue:
            return
        markup, buttons, args, type_ = self.info_bar_queue[0]
        self.info_bar_label.set_markup(markup)

        # Remove old buttons
        area = self.info_bar.get_action_area()
        for b in area.get_children():
            area.remove(b)

        # Add new buttons
        for button in buttons:
            self.info_bar.add_action_widget(button, 0)

        self.info_bar.set_message_type(type_)
        self.info_bar.set_no_show_all(False)
        self.info_bar.show_all()

    def _add_info_bar_message(self, markup, buttons, args,
    type_=Gtk.MessageType.INFO):
        self.info_bar_queue.append((markup, buttons, args, type_))
        self._info_bar_show_message()

    def _get_file_props_event(self, file_props, type_):
        evs = gajim.events.get_events(self.account, self.contact.jid, [type_])
        for ev in evs:
            if ev.parameters == file_props:
                return ev
        return None

    def _on_accept_file_request(self, widget, file_props):
        gajim.interface.instances['file_transfers'].on_file_request_accepted(
            self.account, self.contact, file_props)
        ev = self._get_file_props_event(file_props, 'file-request')
        if ev:
            gajim.events.remove_events(self.account, self.contact.jid, event=ev)

    def _on_cancel_file_request(self, widget, file_props):
        gajim.connections[self.account].send_file_rejection(file_props)
        ev = self._get_file_props_event(file_props, 'file-request')
        if ev:
            gajim.events.remove_events(self.account, self.contact.jid, event=ev)

    def _got_file_request(self, file_props):
        """
        Show an InfoBar on top of control
        """
        markup = '<b>%s:</b> %s' % (_('File transfer'), file_props.name)
        if file_props.desc:
            markup += ' (%s)' % file_props.desc
        markup += '\n%s: %s' % (_('Size'), helpers.convert_bytes(
            file_props.size))
        b1 = Gtk.Button(_('_Accept'))
        b1.connect('clicked', self._on_accept_file_request, file_props)
        b2 = Gtk.Button(stock=Gtk.STOCK_CANCEL)
        b2.connect('clicked', self._on_cancel_file_request, file_props)
        self._add_info_bar_message(markup, [b1, b2], file_props,
            Gtk.MessageType.QUESTION)

    def _on_open_ft_folder(self, widget, file_props):
        path = os.path.split(file_props.file_name)[0]
        if os.path.exists(path) and os.path.isdir(path):
            helpers.launch_file_manager(path)
        ev = self._get_file_props_event(file_props, 'file-completed')
        if ev:
            gajim.events.remove_events(self.account, self.contact.jid, event=ev)

    def _on_ok(self, widget, file_props, type_):
        ev = self._get_file_props_event(file_props, type_)
        if ev:
            gajim.events.remove_events(self.account, self.contact.jid, event=ev)

    def _got_file_completed(self, file_props):
        markup = '<b>%s:</b> %s' % (_('File transfer completed'),
            file_props.name)
        if file_props.desc:
            markup += ' (%s)' % file_props.desc
        b1 = Gtk.Button(_('_Open Containing Folder'))
        b1.connect('clicked', self._on_open_ft_folder, file_props)
        b2 = Gtk.Button(stock=Gtk.STOCK_OK)
        b2.connect('clicked', self._on_ok, file_props, 'file-completed')
        self._add_info_bar_message(markup, [b1, b2], file_props)

    def _got_file_error(self, file_props, type_, pri_txt, sec_txt):
        markup = '<b>%s:</b> %s' % (pri_txt, sec_txt)
        b = Gtk.Button(stock=Gtk.STOCK_OK)
        b.connect('clicked', self._on_ok, file_props, type_)
        self._add_info_bar_message(markup, [b], file_props, Gtk.MessageType.ERROR)

    def _on_accept_gc_invitation(self, widget, event):
        room_jid = event.parameters[0]
        password = event.parameters[2]
        is_continued = event.parameters[3]
        try:
            if is_continued:
                gajim.interface.join_gc_room(self.account, room_jid,
                    gajim.nicks[self.account], password, is_continued=True)
            else:
                dialogs.JoinGroupchatWindow(self.account, room_jid)
        except GajimGeneralException:
            pass
        gajim.events.remove_events(self.account, self.contact.jid, event=event)

    def _on_cancel_gc_invitation(self, widget, event):
        gajim.events.remove_events(self.account, self.contact.jid, event=event)

    def _get_gc_invitation(self, event):
        room_jid = event.parameters[0]
        comment = event.parameters[1]
        markup = '<b>%s:</b> %s' % (_('Groupchat Invitation'), room_jid)
        if comment:
            markup += ' (%s)' % comment
        b1 = Gtk.Button(_('_Join'))
        b1.connect('clicked', self._on_accept_gc_invitation, event)
        b2 = Gtk.Button(stock=Gtk.STOCK_CANCEL)
        b2.connect('clicked', self._on_cancel_gc_invitation, event)
        self._add_info_bar_message(markup, [b1, b2], event.parameters,
            Gtk.MessageType.QUESTION)

    def on_event_added(self, event):
        if event.account != self.account:
            return
        if event.jid != self.contact.jid:
            return
        if event.type_ == 'file-request':
            self._got_file_request(event.parameters)
        elif event.type_ == 'file-completed':
            self._got_file_completed(event.parameters)
        elif event.type_ in ('file-error', 'file-stopped'):
            msg_err = ''
            if event.parameters.error == -1:
                msg_err = _('Remote contact stopped transfer')
            elif event.parameters.error == -6:
                msg_err = _('Error opening file')
            self._got_file_error(event.parameters, event.type_,
                _('File transfer stopped'), msg_err)
        elif event.type_ in ('file-request-error', 'file-send-error'):
            self._got_file_error(event.parameters, event.type_,
                _('File transfer cancelled'),
                _('Connection with peer cannot be established.'))
        elif event.type_ == 'gc-invitation':
            self._get_gc_invitation(event)

    def on_event_removed(self, event_list):
        """
        Called when one or more events are removed from the event list
        """
        for ev in event_list:
            if ev.account != self.account:
                continue
            if ev.jid != self.contact.jid:
                continue
            if ev.type_ not in ('file-request', 'file-completed', 'file-error',
            'file-stopped', 'file-request-error', 'file-send-error',
            'gc-invitation'):
                continue
            i = 0
            removed = False
            for ib_msg in self.info_bar_queue:
                if ev.type_ == 'gc-invitation':
                    if ev.parameters[0] == ib_msg[2][0]:
                        self.info_bar_queue.remove(ib_msg)
                        removed = True
                else: # file-*
                    if ib_msg[2] == ev.parameters:
                        self.info_bar_queue.remove(ib_msg)
                        removed = True
                if removed:
                    if i == 0:
                        # We are removing the one currently displayed
                        self.info_bar.set_no_show_all(True)
                        self.info_bar.hide()
                        # show next one?
                        GLib.idle_add(self._info_bar_show_message)
                    break
                i += 1
