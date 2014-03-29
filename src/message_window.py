# -*- coding:utf-8 -*-
## src/message_window.py
##
## Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005-2008 Travis Shirk <travis AT pobox.com>
##                         Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006 Geobert Quach <geobert AT gmail.com>
##                    Dimitur Kirov <dkirov AT gmail.com>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007 Julien Pivotto <roidelapluie AT gmail.com>
##                    Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
##                    Jonathan Schleifer <js-gajim AT webkeks.org>
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

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import GLib
import time

import common
import gtkgui_helpers
import message_control
import dialogs
from chat_control import ChatControlBase

from common import gajim

####################

class MessageWindow(object):
    """
    Class for windows which contain message like things; chats, groupchats, etc
    """

    # DND_TARGETS is the targets needed by drag_source_set and drag_dest_set
    DND_TARGETS = [('GAJIM_TAB', 0, 81)]
    hid = 0 # drag_data_received handler id
    (
            CLOSE_TAB_MIDDLE_CLICK,
            CLOSE_ESC,
            CLOSE_CLOSE_BUTTON,
            CLOSE_COMMAND,
            CLOSE_CTRL_KEY
    ) = range(5)

    def __init__(self, acct, type_, parent_window=None, parent_paned=None):
        # A dictionary of dictionaries
        # where _contacts[account][jid] == A MessageControl
        self._controls = {}

        # If None, the window is not tied to any specific account
        self.account = acct
        # If None, the window is not tied to any specific type
        self.type_ = type_
        # dict { handler id: widget}. Keeps callbacks, which
        # lead to cylcular references
        self.handlers = {}
        # Don't show warning dialogs when we want to delete the window
        self.dont_warn_on_delete = False

        self.widget_name = 'message_window'
        self.xml = gtkgui_helpers.get_gtk_builder('%s.ui' % self.widget_name)
        self.window = self.xml.get_object(self.widget_name)
        self.notebook = self.xml.get_object('notebook')
        self.parent_paned = None

        if parent_window:
            orig_window = self.window
            self.window = parent_window
            self.parent_paned = parent_paned
            self.notebook.reparent(self.parent_paned)
            self.parent_paned.pack2(self.notebook, resize=True, shrink=True)
            gajim.interface.roster.xml.get_object('show_roster_menuitem').\
                set_sensitive(True)
            orig_window.destroy()
            del orig_window

        # NOTE: we use 'connect_after' here because in
        # MessageWindowMgr._new_window we register handler that saves window
        # state when closing it, and it should be called before
        # MessageWindow._on_window_delete, which manually destroys window
        # through win.destroy() - this means no additional handlers for
        # 'delete-event' are called.
        id_ = self.window.connect_after('delete-event', self._on_window_delete)
        self.handlers[id_] = self.window
        id_ = self.window.connect('destroy', self._on_window_destroy)
        self.handlers[id_] = self.window
        id_ = self.window.connect('focus-in-event', self._on_window_focus)
        self.handlers[id_] = self.window

        keys=['<Control>f', '<Control>g', '<Control>h', '<Control>i',
                '<Control>l', '<Control>L', '<Control><Shift>n', '<Control>u',
                '<Control>b', '<Control>F4',
                '<Control>w', '<Control>Page_Up', '<Control>Page_Down', '<Alt>Right',
                '<Alt>Left', '<Alt>d', '<Alt>c', '<Alt>m', '<Alt>t', 'Escape'] + \
                ['<Alt>'+str(i) for i in list(range(10))]
        accel_group = Gtk.AccelGroup()
        for key in keys:
            keyval, mod = Gtk.accelerator_parse(key)
            accel_group.connect(keyval, mod, Gtk.AccelFlags.VISIBLE,
                self.accel_group_func)
        self.window.add_accel_group(accel_group)

        # gtk+ doesn't make use of the motion notify on gtkwindow by default
        # so this line adds that
        self.window.add_events(Gdk.EventMask.POINTER_MOTION_MASK)

        id_ = self.notebook.connect('switch-page',
            self._on_notebook_switch_page)
        self.handlers[id_] = self.notebook
        id_ = self.notebook.connect('key-press-event',
            self._on_notebook_key_press)
        self.handlers[id_] = self.notebook

        # Tab customizations
        pref_pos = gajim.config.get('tabs_position')
        if pref_pos == 'bottom':
            nb_pos = Gtk.PositionType.BOTTOM
        elif pref_pos == 'left':
            nb_pos = Gtk.PositionType.LEFT
        elif pref_pos == 'right':
            nb_pos = Gtk.PositionType.RIGHT
        else:
            nb_pos = Gtk.PositionType.TOP
        self.notebook.set_tab_pos(nb_pos)
        window_mode = gajim.interface.msg_win_mgr.mode
        if gajim.config.get('tabs_always_visible') or \
        window_mode == MessageWindowMgr.ONE_MSG_WINDOW_ALWAYS_WITH_ROSTER:
            self.notebook.set_show_tabs(True)
        else:
            self.notebook.set_show_tabs(False)
        self.notebook.set_show_border(gajim.config.get('tabs_border'))
        self.show_icon()

    def change_account_name(self, old_name, new_name):
        if old_name in self._controls:
            self._controls[new_name] = self._controls[old_name]
            del self._controls[old_name]

        for ctrl in self.controls():
            if ctrl.account == old_name:
                ctrl.account = new_name
        if self.account == old_name:
            self.account = new_name

    def change_jid(self, account, old_jid, new_jid):
        """
        Called when the full jid of the control is changed
        """
        if account not in self._controls:
            return
        if old_jid not in self._controls[account]:
            return
        if old_jid == new_jid:
            return
        self._controls[account][new_jid] = self._controls[account][old_jid]
        del self._controls[account][old_jid]

    def get_num_controls(self):
        return sum(len(d) for d in self._controls.values())

    def resize(self, width, height):
        gtkgui_helpers.resize_window(self.window, width, height)

    def _on_window_focus(self, widget, event):
        # window received focus, so if we had urgency REMOVE IT
        # NOTE: we do not have to read the message (it maybe in a bg tab)
        # to remove urgency hint so this functions does that
        gtkgui_helpers.set_unset_urgency_hint(self.window, False)

        ctrl = self.get_active_control()
        if ctrl:
            ctrl.set_control_active(True)
            # Undo "unread" state display, etc.
            if ctrl.type_id == message_control.TYPE_GC:
                self.redraw_tab(ctrl, 'active')
            else:
                # NOTE: we do not send any chatstate to preserve
                # inactive, gone, etc.
                self.redraw_tab(ctrl)

    def _on_window_delete(self, win, event):
        if self.dont_warn_on_delete:
            # Destroy the window
            return False

        # Number of controls that will be closed and for which we'll loose data:
        # chat, pm, gc that won't go in roster
        number_of_closed_control = 0
        for ctrl in self.controls():
            if not ctrl.safe_shutdown():
                number_of_closed_control += 1

        if number_of_closed_control > 1:
            def on_yes1(checked):
                if checked:
                    gajim.config.set('confirm_close_multiple_tabs', False)
                self.dont_warn_on_delete = True
                for ctrl in self.controls():
                    if ctrl.minimizable():
                        ctrl.minimize()
                win.destroy()

            if not gajim.config.get('confirm_close_multiple_tabs'):
                for ctrl in self.controls():
                    if ctrl.minimizable():
                        ctrl.minimize()
                # destroy window
                return False
            dialogs.YesNoDialog(
                _('You are going to close several tabs'),
                _('Do you really want to close them all?'),
                checktext=_('_Do not ask me again'), on_response_yes=on_yes1,
                transient_for=self.window)
            return True

        def on_yes(ctrl):
            if self.on_delete_ok == 1:
                self.dont_warn_on_delete = True
                win.destroy()
            self.on_delete_ok -= 1

        def on_no(ctrl):
            return

        def on_minimize(ctrl):
            ctrl.minimize()
            if self.on_delete_ok == 1:
                self.dont_warn_on_delete = True
                win.destroy()
            self.on_delete_ok -= 1

        # Make sure all controls are okay with being deleted
        self.on_delete_ok = self.get_nb_controls()
        for ctrl in self.controls():
            ctrl.allow_shutdown(self.CLOSE_CLOSE_BUTTON, on_yes, on_no,
                    on_minimize)
        return True # halt the delete for the moment

    def _on_window_destroy(self, win):
        for ctrl in self.controls():
            ctrl.shutdown()
        self._controls.clear()
        # Clean up handlers connected to the parent window, this is important since
        # self.window may be the RosterWindow
        for i in list(self.handlers.keys()):
            if self.handlers[i].handler_is_connected(i):
                self.handlers[i].disconnect(i)
            del self.handlers[i]
        del self.handlers

    def new_tab(self, control):
        fjid = control.get_full_jid()

        if control.account not in self._controls:
            self._controls[control.account] = {}

        self._controls[control.account][fjid] = control

        if self.get_num_controls() == 2:
            # is first conversation_textview scrolled down ?
            scrolled = False
            first_widget = self.notebook.get_nth_page(0)
            ctrl = self._widget_to_control(first_widget)
            conv_textview = ctrl.conv_textview
            if conv_textview.at_the_end():
                scrolled = True
            self.notebook.set_show_tabs(True)
            if scrolled:
                GLib.idle_add(conv_textview.scroll_to_end_iter)

        # Add notebook page and connect up to the tab's close button
        xml = gtkgui_helpers.get_gtk_builder('message_window.ui', 'chat_tab_ebox')
        tab_label_box = xml.get_object('chat_tab_ebox')
        widget = xml.get_object('tab_close_button')
        # this reduces the size of the button
#        style = Gtk.RcStyle()
#        style.xthickness = 0
#        style.ythickness = 0
#        widget.modify_style(style)

        id_ = widget.connect('clicked', self._on_close_button_clicked, control)
        control.handlers[id_] = widget

        id_ = tab_label_box.connect('button-press-event',
            self.on_tab_eventbox_button_press_event, control.widget)
        control.handlers[id_] = tab_label_box
        self.notebook.append_page(control.widget, tab_label_box)

        self.notebook.set_tab_reorderable(control.widget, True)

        self.redraw_tab(control)
        if self.parent_paned:
            self.notebook.show_all()
        else:
            self.window.show_all()
        # NOTE: we do not call set_control_active(True) since we don't know
        # whether the tab is the active one.
        self.show_title()
        GLib.timeout_add(500, control.msg_textview.grab_focus)

    def on_tab_eventbox_button_press_event(self, widget, event, child):
        if event.button == 3: # right click
            n = self.notebook.page_num(child)
            self.notebook.set_current_page(n)
            self.popup_menu(event)
        elif event.button == 2: # middle click
            ctrl = self._widget_to_control(child)
            self.remove_tab(ctrl, self.CLOSE_TAB_MIDDLE_CLICK)
        else:
            ctrl = self._widget_to_control(child)
            GLib.idle_add(ctrl.msg_textview.grab_focus)

    def _on_message_textview_mykeypress_event(self, widget, event_keyval,
            event_keymod):
        # NOTE: handles mykeypress which is custom signal; see message_textview.py

        # construct event instance from binding
        event = Gdk.Event(Gdk.EventType.KEY_PRESS) # it's always a key-press here
        event.keyval = event_keyval
        event.state = event_keymod
        event.time = 0 # assign current time

        if event.get_state() & Gdk.ModifierType.CONTROL_MASK:
            # Tab switch bindings
            if event.keyval == Gdk.KEY_Tab: # CTRL + TAB
                self.move_to_next_unread_tab(True)
            elif event.keyval == Gdk.KEY_ISO_Left_Tab: # CTRL + SHIFT + TAB
                self.move_to_next_unread_tab(False)
            elif event.keyval == Gdk.KEY_Page_Down: # CTRL + PAGE DOWN
                self.notebook.event(event)
            elif event.keyval == Gdk.KEY_Page_Up: # CTRL + PAGE UP
                self.notebook.event(event)

    def accel_group_func(self, accel_group, acceleratable, keyval, modifier):
        st = '1234567890' # alt+1 means the first tab (tab 0)
        control = self.get_active_control()
        if not control:
            # No more control in this window
            return

        # CTRL mask
        if modifier & Gdk.ModifierType.CONTROL_MASK:
            if keyval == Gdk.KEY_h: # CTRL + h
                if Gtk.Settings.get_default().get_property(
                'gtk-key-theme-name') != 'Emacs':
                    control._on_history_menuitem_activate()
                    return True
            elif control.type_id == message_control.TYPE_CHAT and \
            keyval == Gdk.KEY_f: # CTRL + f
                # CTRL + f moves cursor one char forward when user uses Emacs
                # theme
                if not Gtk.Settings.get_default().get_property(
                'gtk-key-theme-name') == 'Emacs':
                    control._on_send_file_menuitem_activate(None)
                    return True
            elif control.type_id == message_control.TYPE_CHAT and \
            keyval == Gdk.KEY_g: # CTRL + g
                control._on_convert_to_gc_menuitem_activate(None)
                return True
            elif control.type_id in (message_control.TYPE_CHAT,
            message_control.TYPE_PM) and keyval == Gdk.KEY_i: # CTRL + i
                control._on_contact_information_menuitem_activate(None)
                return True
            elif keyval == Gdk.KEY_l or keyval == Gdk.KEY_L: # CTRL + l|L
                control.conv_textview.clear()
                return True
            elif keyval == Gdk.KEY_u: # CTRL + u: emacs style clear line
                control.clear(control.msg_textview)
                return True
            elif control.type_id == message_control.TYPE_GC and \
            keyval == Gdk.KEY_b: # CTRL + b
                control._on_bookmark_room_menuitem_activate(None)
                return True
            # Tab switch bindings
            elif keyval == Gdk.KEY_F4: # CTRL + F4
                self.remove_tab(control, self.CLOSE_CTRL_KEY)
                return True
            elif keyval == Gdk.KEY_w: # CTRL + w
                # CTRL + w removes latest word before sursor when User uses emacs
                # theme
                if not Gtk.Settings.get_default().get_property(
                'gtk-key-theme-name') == 'Emacs':
                    self.remove_tab(control, self.CLOSE_CTRL_KEY)
                    return True
            elif keyval in (Gdk.KEY_Page_Up, Gdk.KEY_Page_Down):
                # CTRL + PageUp | PageDown
                # Create event and send it to notebook
                event = Gdk.Event(Gdk.EventType.KEY_PRESS)
                event.window = self.window.get_window()
                event.time = int(time.time())
                event.state = Gdk.ModifierType.CONTROL_MASK
                event.keyval = int(keyval)
                self.notebook.event(event)
                return True

            if modifier & Gdk.ModifierType.SHIFT_MASK:
                # CTRL + SHIFT
                if control.type_id == message_control.TYPE_GC and \
                keyval == Gdk.KEY_n: # CTRL + SHIFT + n
                    control._on_change_nick_menuitem_activate(None)
                    return True
        # MOD1 (ALT) mask
        elif modifier & Gdk.ModifierType.MOD1_MASK:
            # Tab switch bindings
            if keyval == Gdk.KEY_Right: # ALT + RIGHT
                new = self.notebook.get_current_page() + 1
                if new >= self.notebook.get_n_pages():
                    new = 0
                self.notebook.set_current_page(new)
                return True
            elif keyval == Gdk.KEY_Left: # ALT + LEFT
                new = self.notebook.get_current_page() - 1
                if new < 0:
                    new = self.notebook.get_n_pages() - 1
                self.notebook.set_current_page(new)
                return True
            elif chr(keyval) in st: # ALT + 1,2,3..
                self.notebook.set_current_page(st.index(chr(keyval)))
                return True
            elif keyval == Gdk.KEY_c: # ALT + C toggles chat buttons
                control.chat_buttons_set_visible(not control.hide_chat_buttons)
                return True
            elif keyval == Gdk.KEY_m: # ALT + M show emoticons menu
                control.show_emoticons_menu()
                return True
            elif keyval == Gdk.KEY_d: # ALT + D show actions menu
                if Gtk.Settings.get_default().get_property(
                'gtk-key-theme-name') != 'Emacs':
                    control.on_actions_button_clicked(control.actions_button)
                    return True
            elif control.type_id == message_control.TYPE_GC and \
            keyval == Gdk.KEY_t: # ALT + t
                control._on_change_subject_menuitem_activate(None)
                return True
        # Close tab bindings
        elif keyval == Gdk.KEY_Escape and \
        gajim.config.get('escape_key_closes'): # Escape
            self.remove_tab(control, self.CLOSE_ESC)
            return True

    def _on_close_button_clicked(self, button, control):
        """
        When close button is pressed: close a tab
        """
        self.remove_tab(control, self.CLOSE_CLOSE_BUTTON)

    def show_icon(self):
        window_mode = gajim.interface.msg_win_mgr.mode
        icon = None
        if window_mode == MessageWindowMgr.ONE_MSG_WINDOW_NEVER:
            ctrl = self.get_active_control()
            if not ctrl:
                return
            icon = ctrl.get_tab_image(count_unread=False)
        elif window_mode == MessageWindowMgr.ONE_MSG_WINDOW_ALWAYS:
            pass # keep default icon
        elif window_mode == MessageWindowMgr.ONE_MSG_WINDOW_ALWAYS_WITH_ROSTER:
            pass # keep default icon
        elif window_mode == MessageWindowMgr.ONE_MSG_WINDOW_PERACCT:
            pass # keep default icon
        elif window_mode == MessageWindowMgr.ONE_MSG_WINDOW_PERTYPE:
            if self.type_ == 'gc':
                icon = gtkgui_helpers.load_icon('muc_active')
            else:
                # chat, pm
                icon = gtkgui_helpers.load_icon('online')
        if icon:
            self.window.set_icon(icon.get_pixbuf())

    def show_title(self, urgent=True, control=None):
        """
        Redraw the window's title
        """
        if not control:
            control = self.get_active_control()
        if not control:
            # No more control in this window
            return
        unread = 0
        for ctrl in self.controls():
            if ctrl.type_id == message_control.TYPE_GC and not \
            gajim.config.get('notify_on_all_muc_messages') and not \
            ctrl.attention_flag:
                # count only pm messages
                unread += ctrl.get_nb_unread_pm()
                continue
            unread += ctrl.get_nb_unread()

        unread_str = ''
        if unread > 1:
            unread_str = '[' + str(unread) + '] '
        elif unread == 1:
            unread_str = '* '
        else:
            urgent = False

        if control.type_id == message_control.TYPE_GC:
            name = control.room_jid.split('@')[0]
            urgent = control.attention_flag
        else:
            name = control.contact.get_shown_name()
            if control.resource:
                name += '/' + control.resource

        window_mode = gajim.interface.msg_win_mgr.mode
        if window_mode == MessageWindowMgr.ONE_MSG_WINDOW_PERTYPE:
            # Show the plural form since number of tabs > 1
            if self.type_ == 'chat':
                label = _('Chats')
            elif self.type_ == 'gc':
                label = _('Group Chats')
            else:
                label = _('Private Chats')
        elif window_mode == MessageWindowMgr.ONE_MSG_WINDOW_ALWAYS_WITH_ROSTER:
            label = None
        elif self.get_num_controls() == 1:
            label = name
        else:
            label = _('Messages')

        title = 'Gajim'
        if label:
            title = '%s - %s' % (label, title)

        if window_mode == MessageWindowMgr.ONE_MSG_WINDOW_PERACCT:
            title = title + ": " + control.account

        self.window.set_title(unread_str + title)

        if urgent:
            gtkgui_helpers.set_unset_urgency_hint(self.window, unread)
        else:
            gtkgui_helpers.set_unset_urgency_hint(self.window, False)

    def set_active_tab(self, ctrl):
        ctrl_page = self.notebook.page_num(ctrl.widget)
        self.notebook.set_current_page(ctrl_page)
        self.window.present()
        GLib.idle_add(ctrl.msg_textview.grab_focus)

    def remove_tab(self, ctrl, method, reason = None, force = False):
        """
        Reason is only for gc (offline status message) if force is True, do not
        ask any confirmation
        """
        def close(ctrl):
            if reason is not None: # We are leaving gc with a status message
                ctrl.shutdown(reason)
            else: # We are leaving gc without status message or it's a chat
                ctrl.shutdown()
            # Update external state
            gajim.events.remove_events(ctrl.account, ctrl.get_full_jid,
                    types = ['printed_msg', 'chat', 'gc_msg'])

            fjid = ctrl.get_full_jid()
            jid = gajim.get_jid_without_resource(fjid)

            fctrl = self.get_control(fjid, ctrl.account)
            bctrl = self.get_control(jid, ctrl.account)
            # keep last_message_time around unless this was our last control with
            # that jid
            if not fctrl and not bctrl and \
            fjid in gajim.last_message_time[ctrl.account]:
                del gajim.last_message_time[ctrl.account][fjid]

            self.notebook.remove_page(self.notebook.page_num(ctrl.widget))

            del self._controls[ctrl.account][fjid]

            if len(self._controls[ctrl.account]) == 0:
                del self._controls[ctrl.account]

            self.check_tabs()
            self.show_title()

        def on_yes(ctrl):
            close(ctrl)

        def on_no(ctrl):
            return

        def on_minimize(ctrl):
            if method != self.CLOSE_COMMAND:
                ctrl.minimize()
                self.check_tabs()
                return
            close(ctrl)

        # Shutdown the MessageControl
        if force:
            close(ctrl)
        else:
            ctrl.allow_shutdown(method, on_yes, on_no, on_minimize)

    def check_tabs(self):
        if self.get_num_controls() == 0:
            # These are not called when the window is destroyed like this, fake it
            gajim.interface.msg_win_mgr._on_window_delete(self.window, None)
            gajim.interface.msg_win_mgr._on_window_destroy(self.window)
            # dnd clean up
            self.notebook.drag_dest_unset()
            if self.parent_paned:
                # Don't close parent window, just remove the child
                child = self.parent_paned.get_child2()
                self.parent_paned.remove(child)
                gajim.interface.roster.xml.get_object('show_roster_menuitem').\
                    set_sensitive(False)
            else:
                self.window.destroy()
            return # don't show_title, we are dead
        elif self.get_num_controls() == 1: # we are going from two tabs to one
            window_mode = gajim.interface.msg_win_mgr.mode
            show_tabs_if_one_tab = gajim.config.get('tabs_always_visible') or \
                window_mode == MessageWindowMgr.ONE_MSG_WINDOW_ALWAYS_WITH_ROSTER
            self.notebook.set_show_tabs(show_tabs_if_one_tab)

    def redraw_tab(self, ctrl, chatstate = None):
        tab = self.notebook.get_tab_label(ctrl.widget)
        if not tab:
            return
        hbox = tab.get_children()[0]
        status_img = hbox.get_children()[0]
        nick_label = hbox.get_children()[1]

        # Optionally hide close button
        close_button = hbox.get_children()[2]
        if gajim.config.get('tabs_close_button'):
            close_button.show()
        else:
            close_button.hide()

        # Update nick
        nick_label.set_max_width_chars(10)
        (tab_label_str, tab_label_color) = ctrl.get_tab_label(chatstate)
        nick_label.set_markup(tab_label_str)
        if tab_label_color:
            nick_label.override_color(Gtk.StateFlags.NORMAL, tab_label_color)
            nick_label.override_color(Gtk.StateFlags.ACTIVE, tab_label_color)

        tab_img = ctrl.get_tab_image()
        if tab_img:
            if tab_img.get_storage_type() == Gtk.ImageType.ANIMATION:
                status_img.set_from_animation(tab_img.get_animation())
            else:
                status_img.set_from_pixbuf(tab_img.get_pixbuf())

        self.show_icon()

    def repaint_themed_widgets(self):
        """
        Repaint controls in the window with theme color
        """
        # iterate through controls and repaint
        for ctrl in self.controls():
            ctrl.repaint_themed_widgets()

    def _widget_to_control(self, widget):
        for ctrl in self.controls():
            if ctrl.widget == widget:
                return ctrl
        return None

    def get_active_control(self):
        notebook = self.notebook
        active_widget = notebook.get_nth_page(notebook.get_current_page())
        return self._widget_to_control(active_widget)

    def get_active_contact(self):
        ctrl = self.get_active_control()
        if ctrl:
            return ctrl.contact
        return None

    def get_active_jid(self):
        contact = self.get_active_contact()
        if contact:
            return contact.jid
        return None

    def is_active(self):
        return self.window.is_active()

    def get_origin(self):
        return self.window.get_window().get_origin()

    def get_control(self, key, acct):
        """
        Return the MessageControl for jid or n, where n is a notebook page index.
        When key is an int index acct may be None
        """

        if isinstance(key, str):
            jid = key
            try:
                return self._controls[acct][jid]
            except Exception:
                return None
        else:
            page_num = key
            notebook = self.notebook
            if page_num is None:
                page_num = notebook.get_current_page()
            nth_child = notebook.get_nth_page(page_num)
            return self._widget_to_control(nth_child)

    def has_control(self, jid, acct):
        return (acct in self._controls and jid in self._controls[acct])

    def change_key(self, old_jid, new_jid, acct):
        """
        Change the JID key of a control
        """
        try:
            # Check if controls exists
            ctrl = self._controls[acct][old_jid]
        except KeyError:
            return

        if new_jid in self._controls[acct]:
            self.remove_tab(self._controls[acct][new_jid],
                self.CLOSE_CLOSE_BUTTON, force=True)

        self._controls[acct][new_jid] = ctrl
        del self._controls[acct][old_jid]

        if old_jid in gajim.last_message_time[acct]:
            gajim.last_message_time[acct][new_jid] = \
                    gajim.last_message_time[acct][old_jid]
            del gajim.last_message_time[acct][old_jid]

    def controls(self):
        for jid_dict in list(self._controls.values()):
            for ctrl in list(jid_dict.values()):
                yield ctrl

    def get_nb_controls(self):
        return sum(len(jid_dict) for jid_dict in self._controls.values())

    def move_to_next_unread_tab(self, forward):
        ind = self.notebook.get_current_page()
        current = ind
        found = False
        first_composing_ind = -1  # id of first composing ctrl to switch to
        # if no others controls have awaiting events
        # loop until finding an unread tab or having done a complete cycle
        while True:
            if forward == True: # look for the first unread tab on the right
                ind = ind + 1
                if ind >= self.notebook.get_n_pages():
                    ind = 0
            else: # look for the first unread tab on the right
                ind = ind - 1
                if ind < 0:
                    ind = self.notebook.get_n_pages() - 1
            ctrl = self.get_control(ind, None)
            if ctrl.get_nb_unread() > 0:
                found = True
                break # found
            elif gajim.config.get('ctrl_tab_go_to_next_composing') :
                # Search for a composing contact
                contact = ctrl.contact
                if first_composing_ind == -1 and contact.chatstate == 'composing':
                # If no composing contact found yet, check if this one is composing
                    first_composing_ind = ind
            if ind == current:
                break # a complete cycle without finding an unread tab
        if found:
            self.notebook.set_current_page(ind)
        elif first_composing_ind != -1:
            self.notebook.set_current_page(first_composing_ind)
        else: # not found and nobody composing
            if forward: # CTRL + TAB
                if current < (self.notebook.get_n_pages() - 1):
                    self.notebook.next_page()
                else: # traverse for ever (eg. don't stop at last tab)
                    self.notebook.set_current_page(0)
            else: # CTRL + SHIFT + TAB
                if current > 0:
                    self.notebook.prev_page()
                else: # traverse for ever (eg. don't stop at first tab)
                    self.notebook.set_current_page(
                            self.notebook.get_n_pages() - 1)

    def popup_menu(self, event):
        menu = self.get_active_control().prepare_context_menu()
        # show the menu
        menu.attach_to_widget(gajim.interface.roster.window, None)
        menu.show_all()
        menu.popup(None, None, None, None, event.button, event.time)

    def _on_notebook_switch_page(self, notebook, page, page_num):
        old_no = notebook.get_current_page()
        if old_no >= 0:
            old_ctrl = self._widget_to_control(notebook.get_nth_page(old_no))
            old_ctrl.set_control_active(False)

        new_ctrl = self._widget_to_control(notebook.get_nth_page(page_num))
        new_ctrl.set_control_active(True)
        self.show_title(control = new_ctrl)

        control = self.get_active_control()
        if isinstance(control, ChatControlBase):
            control.msg_textview.grab_focus()

    def _on_notebook_key_press(self, widget, event):
        # when tab itself is selected,
        # make sure <- and -> are allowed for navigating between tabs
        if event.keyval in (Gdk.KEY_Left, Gdk.KEY_Right):
            return False

        control = self.get_active_control()

        if event.get_state() & Gdk.ModifierType.SHIFT_MASK:
            # CTRL + SHIFT + TAB
            if event.get_state() & Gdk.ModifierType.CONTROL_MASK and \
            event.keyval == Gdk.KEY_ISO_Left_Tab:
                self.move_to_next_unread_tab(False)
                return True
            # SHIFT + PAGE_[UP|DOWN]: send to conv_textview
            elif event.keyval in (Gdk.KEY_Page_Down, Gdk.KEY_Page_Up):
                control.conv_textview.tv.event(event)
                return True
        elif event.get_state() & Gdk.ModifierType.CONTROL_MASK:
            if event.keyval == Gdk.KEY_Tab: # CTRL + TAB
                self.move_to_next_unread_tab(True)
                return True
            # Ctrl+PageUP / DOWN has to be handled by notebook
            elif event.keyval == Gdk.KEY_Page_Down:
                self.move_to_next_unread_tab(True)
                return True
            elif event.keyval == Gdk.KEY_Page_Up:
                self.move_to_next_unread_tab(False)
                return True
        if event.keyval in (Gdk.KEY_Shift_L, Gdk.KEY_Shift_R,
        Gdk.KEY_Control_L, Gdk.KEY_Control_R, Gdk.KEY_Caps_Lock,
        Gdk.KEY_Shift_Lock, Gdk.KEY_Meta_L, Gdk.KEY_Meta_R,
        Gdk.KEY_Alt_L, Gdk.KEY_Alt_R, Gdk.KEY_Super_L,
        Gdk.KEY_Super_R, Gdk.KEY_Hyper_L, Gdk.KEY_Hyper_R):
            return True

        if isinstance(control, ChatControlBase):
            # we forwarded it to message textview
            control.msg_textview.event(event)
            control.msg_textview.grab_focus()

    def get_tab_at_xy(self, x, y):
        """
        Return the tab under xy and if its nearer from left or right side of the
        tab
        """
        page_num = -1
        to_right = False
        horiz = self.notebook.get_tab_pos() == Gtk.PositionType.TOP or \
                self.notebook.get_tab_pos() == Gtk.PositionType.BOTTOM
        for i in list(range(self.notebook.get_n_pages())):
            page = self.notebook.get_nth_page(i)
            tab = self.notebook.get_tab_label(page)
            tab_alloc = tab.get_allocation()
            if horiz:
                if (x >= tab_alloc.x) and \
                (x <= (tab_alloc.x + tab_alloc.width)):
                    page_num = i
                    if x >= tab_alloc.x + (tab_alloc.width / 2.0):
                        to_right = True
                    break
            else:
                if (y >= tab_alloc.y) and \
                (y <= (tab_alloc.y + tab_alloc.height)):
                    page_num = i

                    if y > tab_alloc.y + (tab_alloc.height / 2.0):
                        to_right = True
                    break
        return (page_num, to_right)

    def find_page_num_according_to_tab_label(self, tab_label):
        """
        Find the page num of the tab label
        """
        page_num = -1
        for i in list(range(self.notebook.get_n_pages())):
            page = self.notebook.get_nth_page(i)
            tab = self.notebook.get_tab_label(page)
            if tab == tab_label:
                page_num = i
                break
        return page_num

################################################################################
class MessageWindowMgr(GObject.GObject):
    """
    A manager and factory for MessageWindow objects
    """

    __gsignals__ = {
            'window-delete': (GObject.SignalFlags.RUN_LAST, None, (object,)),
    }

    # These constants map to common.config.opt_one_window_types indices
    (
            ONE_MSG_WINDOW_NEVER,
            ONE_MSG_WINDOW_ALWAYS,
            ONE_MSG_WINDOW_ALWAYS_WITH_ROSTER,
            ONE_MSG_WINDOW_PERACCT,
            ONE_MSG_WINDOW_PERTYPE,
    ) = range(5)
    # A key constant for the main window in ONE_MSG_WINDOW_ALWAYS mode
    MAIN_WIN = 'main'
    # A key constant for the main window in ONE_MSG_WINDOW_ALWAYS_WITH_ROSTER mode
    ROSTER_MAIN_WIN = 'roster'

    def __init__(self, parent_window, parent_paned):
        """
        A dictionary of windows; the key depends on the config:
            ONE_MSG_WINDOW_NEVER: The key is the contact JID
            ONE_MSG_WINDOW_ALWAYS: The key is MessageWindowMgr.MAIN_WIN
            ONE_MSG_WINDOW_ALWAYS_WITH_ROSTER: The key is MessageWindowMgr.MAIN_WIN
            ONE_MSG_WINDOW_PERACCT: The key is the account name
            ONE_MSG_WINDOW_PERTYPE: The key is a message type constant
        """
        GObject.GObject.__init__(self)
        self._windows = {}

        # Map the mode to a int constant for frequent compares
        mode = gajim.config.get('one_message_window')
        self.mode = common.config.opt_one_window_types.index(mode)

        self.parent_win = parent_window
        self.parent_paned = parent_paned

    def change_account_name(self, old_name, new_name):
        for win in self.windows():
            win.change_account_name(old_name, new_name)

    def _new_window(self, acct, type_):
        parent_win = None
        parent_paned = None
        if self.mode == self.ONE_MSG_WINDOW_ALWAYS_WITH_ROSTER:
            parent_win = self.parent_win
            parent_paned = self.parent_paned
        win = MessageWindow(acct, type_, parent_win, parent_paned)
        # we track the lifetime of this window
        win.window.connect('delete-event', self._on_window_delete)
        win.window.connect('destroy', self._on_window_destroy)
        return win

    def _gtk_win_to_msg_win(self, gtk_win):
        for w in self.windows():
            if w.window == gtk_win:
                return w
        return None

    def get_window(self, jid, acct):
        for win in self.windows():
            if win.has_control(jid, acct):
                return win

        return None

    def has_window(self, jid, acct):
        return self.get_window(jid, acct) is not None

    def one_window_opened(self, contact=None, acct=None, type_=None):
        try:
            return \
                self._windows[self._mode_to_key(contact, acct, type_)] is not None
        except KeyError:
            return False

    def _resize_window(self, win, acct, type_):
        """
        Resizes window according to config settings
        """
        if self.mode in (self.ONE_MSG_WINDOW_ALWAYS,
                        self.ONE_MSG_WINDOW_ALWAYS_WITH_ROSTER):
            size = (gajim.config.get('msgwin-width'),
                    gajim.config.get('msgwin-height'))
            if self.mode == self.ONE_MSG_WINDOW_ALWAYS_WITH_ROSTER:
                parent_size = win.window.get_size()
                # Need to add the size of the now visible paned handle, otherwise
                # the saved width of the message window decreases by this amount
                s = GObject.Value()
                s.init(GObject.TYPE_INT)
                win.parent_paned.style_get_property('handle-size', s)
                handle_size = s.get_int()
                size = (parent_size[0] + size[0] + handle_size, size[1])
        elif self.mode == self.ONE_MSG_WINDOW_PERACCT:
            size = (gajim.config.get_per('accounts', acct, 'msgwin-width'),
                    gajim.config.get_per('accounts', acct, 'msgwin-height'))
        elif self.mode in (self.ONE_MSG_WINDOW_NEVER, self.ONE_MSG_WINDOW_PERTYPE):
            if type_ == message_control.TYPE_PM:
                type_ = message_control.TYPE_CHAT
            opt_width = type_ + '-msgwin-width'
            opt_height = type_ + '-msgwin-height'
            size = (gajim.config.get(opt_width), gajim.config.get(opt_height))
        else:
            return
        win.resize(size[0], size[1])
        if win.parent_paned:
            win.parent_paned.set_position(gajim.config.get('roster_hpaned_position'))

    def _position_window(self, win, acct, type_):
        """
        Moves window according to config settings
        """
        if (self.mode in [self.ONE_MSG_WINDOW_NEVER,
        self.ONE_MSG_WINDOW_ALWAYS_WITH_ROSTER]):
            return

        if self.mode == self.ONE_MSG_WINDOW_ALWAYS:
            pos = (gajim.config.get('msgwin-x-position'),
                    gajim.config.get('msgwin-y-position'))
        elif self.mode == self.ONE_MSG_WINDOW_PERACCT:
            pos = (gajim.config.get_per('accounts', acct, 'msgwin-x-position'),
                    gajim.config.get_per('accounts', acct, 'msgwin-y-position'))
        elif self.mode == self.ONE_MSG_WINDOW_PERTYPE:
            pos = (gajim.config.get(type_ + '-msgwin-x-position'),
                    gajim.config.get(type_ + '-msgwin-y-position'))
        else:
            return

        gtkgui_helpers.move_window(win.window, pos[0], pos[1])

    def _mode_to_key(self, contact, acct, type_, resource = None):
        if self.mode == self.ONE_MSG_WINDOW_NEVER:
            key = acct + contact.jid
            if resource:
                key += '/' + resource
            return key
        elif self.mode == self.ONE_MSG_WINDOW_ALWAYS:
            return self.MAIN_WIN
        elif self.mode == self.ONE_MSG_WINDOW_ALWAYS_WITH_ROSTER:
            return self.ROSTER_MAIN_WIN
        elif self.mode == self.ONE_MSG_WINDOW_PERACCT:
            return acct
        elif self.mode == self.ONE_MSG_WINDOW_PERTYPE:
            return type_

    def create_window(self, contact, acct, type_, resource = None):
        win_acct = None
        win_type = None
        win_role = None # X11 window role

        win_key = self._mode_to_key(contact, acct, type_, resource)
        if self.mode == self.ONE_MSG_WINDOW_PERACCT:
            win_acct = acct
            win_role = acct
        elif self.mode == self.ONE_MSG_WINDOW_PERTYPE:
            win_type = type_
            win_role = type_
        elif self.mode == self.ONE_MSG_WINDOW_NEVER:
            win_type = type_
            win_role = contact.jid
        elif self.mode == self.ONE_MSG_WINDOW_ALWAYS:
            win_role = 'messages'

        win = None
        try:
            win = self._windows[win_key]
        except KeyError:
            win = self._new_window(win_acct, win_type)

        if win_role:
            win.window.set_role(win_role)

        # Position and size window based on saved state and window mode
        if not self.one_window_opened(contact, acct, type_):
            if gajim.config.get('msgwin-max-state'):
                win.window.maximize()
            else:
                self._resize_window(win, acct, type_)
                self._position_window(win, acct, type_)

        self._windows[win_key] = win
        return win

    def change_key(self, old_jid, new_jid, acct):
        win = self.get_window(old_jid, acct)
        if self.mode == self.ONE_MSG_WINDOW_NEVER:
            old_key = acct + old_jid
            if old_jid not in self._windows:
                return
            new_key = acct + new_jid
            self._windows[new_key] = self._windows[old_key]
            del self._windows[old_key]
        win.change_key(old_jid, new_jid, acct)

    def _on_window_delete(self, win, event):
        self.save_state(self._gtk_win_to_msg_win(win))
        gajim.interface.save_config()
        return False

    def _on_window_destroy(self, win):
        for k in self._windows.keys():
            if self._windows[k].window == win:
                self.emit('window-delete', self._windows[k])
                del self._windows[k]
                return

    def get_control(self, jid, acct):
        """
        Amongst all windows, return the MessageControl for jid
        """
        win = self.get_window(jid, acct)
        if win:
            return win.get_control(jid, acct)
        return None

    def search_control(self, jid, account, resource=None):
        """
        Search windows with this policy:
        1. try to find already opened tab for resource
        2. find the tab for this jid with ctrl.resource not set
        3. there is none
        """
        fjid = jid
        if resource:
            fjid += '/' + resource
        ctrl = self.get_control(fjid, account)
        if ctrl:
            return ctrl
        win = self.get_window(jid, account)
        if win:
            ctrl = win.get_control(jid, account)
            if not ctrl.resource and ctrl.type_id != message_control.TYPE_GC:
                return ctrl
        return None

    def get_gc_control(self, jid, acct):
        """
        Same as get_control. Was briefly required, is not any more. May be useful
        some day in the future?
        """
        ctrl = self.get_control(jid, acct)
        if ctrl and ctrl.type_id == message_control.TYPE_GC:
            return ctrl
        return None

    def get_controls(self, type_=None, acct=None):
        ctrls = []
        for c in self.controls():
            if acct and c.account != acct:
                continue
            if not type_ or c.type_id == type_:
                ctrls.append(c)
        return ctrls

    def windows(self):
        for w in list(self._windows.values()):
            yield w

    def controls(self):
        for w in self._windows.values():
            for c in w.controls():
                yield c

    def shutdown(self, width_adjust=0):
        for w in self.windows():
            self.save_state(w, width_adjust)
            if not w.parent_paned:
                w.window.hide()
                w.window.destroy()

        gajim.interface.save_config()

    def save_state(self, msg_win, width_adjust=0):
        # Save window size and position
        max_win_key = 'msgwin-max-state'
        pos_x_key = 'msgwin-x-position'
        pos_y_key = 'msgwin-y-position'
        size_width_key = 'msgwin-width'
        size_height_key = 'msgwin-height'

        acct = None
        x, y = msg_win.window.get_position()
        width, height = msg_win.window.get_size()

        # If any of these values seem bogus don't update.
        if x < 0 or y < 0 or width < 0 or height < 0:
            return

        elif self.mode == self.ONE_MSG_WINDOW_PERACCT:
            acct = msg_win.account
        elif self.mode == self.ONE_MSG_WINDOW_PERTYPE:
            type_ = msg_win.type_
            pos_x_key = type_ + '-msgwin-x-position'
            pos_y_key = type_ + '-msgwin-y-position'
            size_width_key = type_ + '-msgwin-width'
            size_height_key = type_ + '-msgwin-height'
        elif self.mode == self.ONE_MSG_WINDOW_NEVER:
            type_ = msg_win.type_
            size_width_key = type_ + '-msgwin-width'
            size_height_key = type_ + '-msgwin-height'
        elif self.mode == self.ONE_MSG_WINDOW_ALWAYS_WITH_ROSTER:
            # Ignore any hpaned width
            width = msg_win.notebook.get_allocation().width

        if acct:
            gajim.config.set_per('accounts', acct, size_width_key, width)
            gajim.config.set_per('accounts', acct, size_height_key, height)

            if self.mode != self.ONE_MSG_WINDOW_NEVER:
                gajim.config.set_per('accounts', acct, pos_x_key, x)
                gajim.config.set_per('accounts', acct, pos_y_key, y)

        else:
            win_maximized = msg_win.window.get_window().get_state() == \
                    Gdk.WindowState.MAXIMIZED
            gajim.config.set(max_win_key, win_maximized)
            width += width_adjust
            gajim.config.set(size_width_key, width)
            gajim.config.set(size_height_key, height)

            if self.mode != self.ONE_MSG_WINDOW_NEVER:
                gajim.config.set(pos_x_key, x)
                gajim.config.set(pos_y_key, y)

    def reconfig(self):
        for w in self.windows():
            self.save_state(w)
        mode = gajim.config.get('one_message_window')
        if self.mode == common.config.opt_one_window_types.index(mode):
            # No change
            return
        self.mode = common.config.opt_one_window_types.index(mode)

        controls = []
        for w in self.windows():
            # Note, we are taking care not to hide/delete the roster window when the
            # MessageWindow is embedded.
            if not w.parent_paned:
                w.window.hide()
            else:
                # Stash current size so it can be restored if the MessageWindow
                # is not longer embedded
                roster_width = w.parent_paned.get_position()
                gajim.config.set('roster_width', roster_width)

            while w.notebook.get_n_pages():
                page = w.notebook.get_nth_page(0)
                ctrl = w._widget_to_control(page)
                w.notebook.remove_page(0)
                page.unparent()
                controls.append(ctrl)

            # Must clear _controls to prevent MessageControl.shutdown calls
            w._controls = {}
            if not w.parent_paned:
                w.window.destroy()
            else:
                # Don't close parent window, just remove the child
                child = w.parent_paned.get_child2()
                w.parent_paned.remove(child)
                gajim.interface.roster.xml.get_object('show_roster_menuitem').\
                    set_sensitive(False)
                gtkgui_helpers.resize_window(w.window,
                        gajim.config.get('roster_width'),
                        gajim.config.get('roster_height'))

        self._windows = {}

        for ctrl in controls:
            mw = self.get_window(ctrl.contact.jid, ctrl.account)
            if not mw:
                mw = self.create_window(ctrl.contact, ctrl.account,
                                        ctrl.type_id)
            ctrl.parent_win = mw
            mw.new_tab(ctrl)

    def save_opened_controls(self):
        if not gajim.config.get('remember_opened_chat_controls'):
            return
        chat_controls = {}
        for acct in gajim.connections:
            chat_controls[acct] = []
        for ctrl in self.get_controls(type_=message_control.TYPE_CHAT):
            acct = ctrl.account
            if ctrl.contact.jid not in chat_controls[acct]:
                chat_controls[acct].append(ctrl.contact.jid)
        for acct in gajim.connections:
            gajim.config.set_per('accounts', acct, 'opened_chat_controls',
                ','.join(chat_controls[acct]))
