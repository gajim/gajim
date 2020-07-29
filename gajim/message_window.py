# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2005-2008 Travis Shirk <travis AT pobox.com>
#                         Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006 Geobert Quach <geobert AT gmail.com>
#                    Dimitur Kirov <dkirov AT gmail.com>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2007 Julien Pivotto <roidelapluie AT gmail.com>
#                    Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
#                    Jonathan Schleifer <js-gajim AT webkeks.org>
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

import logging

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import GLib
from gi.repository import Gio

from gajim.common import app
from gajim.common import ged
from gajim.common.i18n import Q_
from gajim.common.i18n import _
from gajim.common.nec import EventHelper

from gajim import gtkgui_helpers
from gajim.chat_control_base import ChatControlBase
from gajim.chat_control import ChatControl

from gajim.gtk.dialogs import DialogButton
from gajim.gtk.dialogs import NewConfirmationCheckDialog
from gajim.gtk.util import get_icon_name
from gajim.gtk.util import resize_window
from gajim.gtk.util import move_window
from gajim.gtk.util import get_app_icon_list
from gajim.gtk.util import get_builder
from gajim.gtk.util import set_urgency_hint
from gajim.gtk.util import get_app_window
from gajim.gtk.const import ControlType


log = logging.getLogger('gajim.message_window')


WINDOW_TYPES = ['never',
                'always',
                'always_with_roster',
                'peracct',
                'pertype']


class MessageWindow(EventHelper):
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
        EventHelper.__init__(self)
        # A dictionary of dictionaries
        # where _contacts[account][jid] == A MessageControl
        self._controls = {}

        # If None, the window is not tied to any specific account
        self.account = acct
        # If None, the window is not tied to any specific type
        self.type_ = type_
        # dict { handler id: widget}. Keeps callbacks, which
        # lead to circular references
        self.handlers = {}
        # Don't show warning dialogs when we want to delete the window
        self.dont_warn_on_delete = False

        self.widget_name = 'message_window'
        self.xml = get_builder('%s.ui' % self.widget_name)
        self.window = self.xml.get_object(self.widget_name)
        self.window.set_application(app.app)
        self.notebook = self.xml.get_object('notebook')
        self.parent_paned = None

        if parent_window:
            orig_window = self.window
            self.window = parent_window
            self.parent_paned = parent_paned
            old_parent = self.notebook.get_parent()
            old_parent.remove(self.notebook)
            if app.settings.get('roster_on_the_right'):
                child1 = self.parent_paned.get_child1()
                self.parent_paned.remove(child1)
                self.parent_paned.pack1(self.notebook, resize=False)
                self.parent_paned.pack2(child1)
            else:
                self.parent_paned.pack2(self.notebook)
            self.window.lookup_action('show-roster').set_enabled(True)
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

        self._add_actions()

        # gtk+ doesn't make use of the motion notify on gtkwindow by default
        # so this line adds that
        self.window.add_events(Gdk.EventMask.POINTER_MOTION_MASK)

        id_ = self.notebook.connect('switch-page',
            self._on_notebook_switch_page)
        self.handlers[id_] = self.notebook

        # Tab customizations
        pref_pos = app.settings.get('tabs_position')
        if pref_pos == 'bottom':
            nb_pos = Gtk.PositionType.BOTTOM
        elif pref_pos == 'left':
            nb_pos = Gtk.PositionType.LEFT
        elif pref_pos == 'right':
            nb_pos = Gtk.PositionType.RIGHT
        else:
            nb_pos = Gtk.PositionType.TOP
        self.notebook.set_tab_pos(nb_pos)
        window_mode = app.interface.msg_win_mgr.mode
        if app.settings.get('tabs_always_visible') or \
        window_mode == MessageWindowMgr.ONE_MSG_WINDOW_ALWAYS_WITH_ROSTER:
            self.notebook.set_show_tabs(True)
        else:
            self.notebook.set_show_tabs(False)
        self.notebook.set_show_border(app.settings.get('tabs_border'))
        self.show_icon()

        self.register_events([
            ('muc-disco-update', ged.GUI1, self._on_muc_disco_update),
        ])

    def _add_actions(self):
        actions = [
            'change-nickname',
            'change-subject',
            'escape',
            'browse-history',
            'send-file',
            'show-contact-info',
            'show-emoji-chooser',
            'clear-chat',
            'delete-line',
            'close-tab',
            'move-tab-up',
            'move-tab-down',
            'switch-next-tab',
            'switch-prev-tab',
            'switch-next-unread-tab-right'
            'switch-next-unread-tab-left',
            'switch-tab-1',
            'switch-tab-2',
            'switch-tab-3',
            'switch-tab-4',
            'switch-tab-5',
            'switch-tab-6',
            'switch-tab-7',
            'switch-tab-8',
            'switch-tab-9',
            'copy-text',
        ]

        disabled_for_emacs = (
            'browse-history',
            'send-file',
            'close-tab'
        )

        key_theme = Gtk.Settings.get_default().get_property(
            'gtk-key-theme-name')

        for action in actions:
            if key_theme == 'Emacs' and action in disabled_for_emacs:
                continue
            act = Gio.SimpleAction.new(action, None)
            act.connect('activate', self._on_action)
            self.window.add_action(act)

    def _on_action(self, action, _param):
        control = self.get_active_control()
        if not control:
            # No more control in this window
            return

        log.info('Activate action: %s, active control: %s',
                 action.get_name(), control.contact.jid)

        action = action.get_name()

        # Pass the event to the control
        res = control.delegate_action(action)
        if res != Gdk.EVENT_PROPAGATE:
            return res

        if action == 'escape' and app.settings.get('escape_key_closes'):
            self.remove_tab(control, self.CLOSE_ESC)
            return

        if action == 'close-tab':
            self.remove_tab(control, self.CLOSE_CTRL_KEY)
            return

        if action == 'move-tab-up':
            old_position = self.notebook.get_current_page()
            self.notebook.reorder_child(control.widget,
                                        old_position - 1)
            return

        if action == 'move-tab-down':
            old_position = self.notebook.get_current_page()
            total_pages = self.notebook.get_n_pages()
            if old_position == total_pages - 1:
                self.notebook.reorder_child(control.widget, 0)
            else:
                self.notebook.reorder_child(control.widget,
                                            old_position + 1)
            return

        if action == 'switch-next-tab':
            new = self.notebook.get_current_page() + 1
            if new >= self.notebook.get_n_pages():
                new = 0
            self.notebook.set_current_page(new)
            return

        if action == 'switch-prev-tab':
            new = self.notebook.get_current_page() - 1
            if new < 0:
                new = self.notebook.get_n_pages() - 1
            self.notebook.set_current_page(new)
            return

        if action == 'switch-next-unread-tab-right':
            self.move_to_next_unread_tab(True)
            return

        if action == 'switch-next-unread-tab-left':
            self.move_to_next_unread_tab(False)
            return

        if action.startswith('switch-tab-'):
            number = int(action[-1])
            self.notebook.set_current_page(number - 1)
            return

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
        resize_window(self.window, width, height)

    def _on_muc_disco_update(self, event):
        # If there is only one control in a window,
        # the name is shown in the window title
        if self.get_num_controls() != 1:
            return
        ctrl = self.get_active_control()
        if ctrl.contact.jid != event.room_jid:
            return
        self.show_title()

    def _on_window_focus(self, widget, event):
        # on destroy() the window that was last focused gets the focus
        # again. if destroy() is called from the StartChat Dialog, this
        # Window is not yet focused, because present() seems to be asynchronous
        # at least on KDE, and takes time.
        start_chat = get_app_window('StartChatDialog')
        if start_chat is not None and start_chat.ready_to_destroy:
            start_chat.destroy()

        # window received focus, so if we had urgency REMOVE IT
        # NOTE: we do not have to read the message (it maybe in a bg tab)
        # to remove urgency hint so this functions does that
        set_urgency_hint(self.window, False)

        ctrl = self.get_active_control()
        if ctrl:
            ctrl.set_control_active(True)
            # Undo "unread" state display, etc.
            if ctrl.is_groupchat:
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
            def _on_yes1(checked):
                if checked:
                    app.settings.set('confirm_close_multiple_tabs', False)
                self.dont_warn_on_delete = True
                for ctrl in self.controls():
                    if ctrl.minimizable():
                        ctrl.minimize()
                win.destroy()

            if not app.settings.get('confirm_close_multiple_tabs'):
                for ctrl in self.controls():
                    if ctrl.minimizable():
                        ctrl.minimize()
                # destroy window
                return False

            NewConfirmationCheckDialog(
                _('Close Tabs'),
                _('You are about to close several tabs'),
                _('Do you really want to close all of them?'),
                _('_Do not ask me again'),
                [DialogButton.make('Cancel'),
                 DialogButton.make('Accept',
                                   text=_('_Close'),
                                   callback=_on_yes1)],
                transient_for=self.window).show()
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

        self.unregister_events()

    def new_tab(self, control):
        fjid = control.get_full_jid()

        if control.account not in self._controls:
            self._controls[control.account] = {}

        self._controls[control.account][fjid] = control

        if self.get_num_controls() == 2:
            first_widget = self.notebook.get_nth_page(0)
            ctrl = self._widget_to_control(first_widget)
            self.notebook.set_show_tabs(True)
            ctrl.scroll_to_end()

        # Add notebook page and connect up to the tab's close button
        xml = get_builder('message_window.ui', ['chat_tab_ebox'])
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
        position = self.notebook.get_current_page() + 1
        self.notebook.insert_page(control.widget, tab_label_box, position)

        self.notebook.set_tab_reorderable(control.widget, True)

        self.redraw_tab(control)
        if self.parent_paned:
            self.notebook.show_all()
        else:
            self.window.show_all()

        # NOTE: we do not call set_control_active(True) since we don't know
        # whether the tab is the active one.
        self.show_title()
        if self.get_num_controls() == 1:
            GLib.timeout_add(500, control.focus)

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
            GLib.idle_add(ctrl.focus)

    def _on_close_button_clicked(self, button, control):
        """
        When close button is pressed: close a tab
        """
        self.remove_tab(control, self.CLOSE_CLOSE_BUTTON)

    def show_icon(self):
        window_mode = app.interface.msg_win_mgr.mode
        if window_mode in (MessageWindowMgr.ONE_MSG_WINDOW_PERTYPE,
                           MessageWindowMgr.ONE_MSG_WINDOW_NEVER):
            if self.type_ == 'gc':
                icon = get_icon_name('muc-active')
                self.window.set_icon_name(icon)

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
            if (ctrl.is_groupchat and
                    not ctrl.contact.can_notify() and
                    not ctrl.attention_flag):
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

        if control.is_groupchat:
            name = control.contact.get_shown_name()
            urgent = (control.attention_flag or
                      control.contact.can_notify())
        else:
            name = control.contact.get_shown_name()
            if control.resource:
                name += '/' + control.resource

        window_mode = app.interface.msg_win_mgr.mode
        if window_mode == MessageWindowMgr.ONE_MSG_WINDOW_PERTYPE:
            # Show the plural form since number of tabs > 1
            if self.type_ == 'chat':
                label = Q_('?Noun:Chats')
                if self.get_num_controls() == 1:
                    label = name
            elif self.type_ == 'gc':
                label = _('Group Chats')
                if self.get_num_controls() == 1:
                    label = name
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
        set_urgency_hint(self.window, urgent and unread > 0)

    def set_active_tab(self, ctrl):
        ctrl_page = self.notebook.page_num(ctrl.widget)
        self.notebook.set_current_page(ctrl_page)
        self.window.present()
        GLib.idle_add(ctrl.focus)

    def remove_tab(self, ctrl, method, reason=None, force=False):
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
            app.events.remove_events(
                ctrl.account, ctrl.get_full_jid,
                types=['printed_msg', 'chat', 'gc_msg'])

            fjid = ctrl.get_full_jid()
            jid = app.get_jid_without_resource(fjid)

            fctrl = self.get_control(fjid, ctrl.account)
            bctrl = self.get_control(jid, ctrl.account)
            # keep last_message_time around unless this was our last control with
            # that jid
            if not fctrl and not bctrl and \
            fjid in app.last_message_time[ctrl.account]:
                del app.last_message_time[ctrl.account][fjid]

            self.notebook.remove_page(self.notebook.page_num(ctrl.widget))

            del self._controls[ctrl.account][fjid]

            if not self._controls[ctrl.account]:
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
        if self.parent_paned:
            # Do nothing in single window mode
            pass
        elif self.get_num_controls() == 0:
            # These are not called when the window is destroyed like this, fake it
            app.interface.msg_win_mgr._on_window_delete(self.window, None)
            app.interface.msg_win_mgr._on_window_destroy(self.window)
            # dnd clean up
            self.notebook.drag_dest_unset()
            if self.parent_paned:
                # Don't close parent window, just remove the child
                child = self.parent_paned.get_child2()
                self.parent_paned.remove(child)
                self.window.lookup_action('show-roster').set_enabled(False)
            else:
                self.window.destroy()
            return # don't show_title, we are dead
        elif self.get_num_controls() == 1: # we are going from two tabs to one
            window_mode = app.interface.msg_win_mgr.mode
            show_tabs_if_one_tab = app.settings.get('tabs_always_visible') or \
                window_mode == MessageWindowMgr.ONE_MSG_WINDOW_ALWAYS_WITH_ROSTER
            self.notebook.set_show_tabs(show_tabs_if_one_tab)

    def redraw_tab(self, ctrl, chatstate=None):
        tab = self.notebook.get_tab_label(ctrl.widget)
        if not tab:
            return

        hbox = tab.get_children()[0]
        status_img = hbox.get_children()[0]
        nick_label = hbox.get_children()[1]

        # Optionally hide close button
        close_button = hbox.get_children()[2]
        if app.settings.get('tabs_close_button'):
            close_button.show()
        else:
            close_button.hide()

        # Update nick
        if isinstance(ctrl, ChatControl):
            tab_label_str = ctrl.get_tab_label()
            # Set Label Color
            if app.settings.get('show_chatstate_in_tabs'):
                gtkgui_helpers.add_css_class(
                    nick_label, chatstate, 'gajim-state-')
        else:
            tab_label_str, color = ctrl.get_tab_label(chatstate)
            # Set Label Color
            if color == 'active':
                gtkgui_helpers.add_css_class(nick_label, None, 'gajim-state-')
            elif color is not None:
                gtkgui_helpers.add_css_class(nick_label, color, 'gajim-state-')

        nick_label.set_markup(tab_label_str)

        tab_img = ctrl.get_tab_image()
        if tab_img:
            if isinstance(tab_img, Gtk.Image):
                if tab_img.get_storage_type() == Gtk.ImageType.ANIMATION:
                    status_img.set_from_animation(tab_img.get_animation())
                else:
                    status_img.set_from_pixbuf(tab_img.get_pixbuf())
            elif isinstance(tab_img, str):
                status_img.set_from_icon_name(tab_img, Gtk.IconSize.MENU)
            else:
                status_img.set_from_surface(tab_img)

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

    def get_control(self, jid, acct):
        """
        Return the MessageControl for jid
        """
        try:
            return self._controls[acct][jid]
        except Exception:
            return None

    def has_control(self, jid, acct):
        return acct in self._controls and jid in self._controls[acct]

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

        if old_jid in app.last_message_time[acct]:
            app.last_message_time[acct][new_jid] = \
                    app.last_message_time[acct][old_jid]
            del app.last_message_time[acct][old_jid]

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
            if forward is True: # look for the first unread tab on the right
                ind = ind + 1
                if ind >= self.notebook.get_n_pages():
                    ind = 0
            else: # look for the first unread tab on the right
                ind = ind - 1
                if ind < 0:
                    ind = self.notebook.get_n_pages() - 1

            nth_child = self.notebook.get_nth_page(ind)
            ctrl = self._widget_to_control(nth_child)
            if ctrl.get_nb_unread() > 0:
                found = True
                break # found
            if app.settings.get('ctrl_tab_go_to_next_composing'):
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
        if menu is None:
            return
        # show the menu
        menu.attach_to_widget(app.interface.roster.window, None)
        menu.show_all()
        menu.popup(None, None, None, None, event.button, event.time)

    def _on_notebook_switch_page(self, notebook, page, page_num):
        old_no = notebook.get_current_page()
        if old_no >= 0:
            old_ctrl = self._widget_to_control(notebook.get_nth_page(old_no))
            old_ctrl.set_control_active(False)

        new_ctrl = self._widget_to_control(notebook.get_nth_page(page_num))
        new_ctrl.set_control_active(True)
        self.show_title(control=new_ctrl)

        control = self.get_active_control()
        if isinstance(control, ChatControlBase):
            control.focus()

    def get_tab_at_xy(self, x, y):
        """
        Return the tab under xy and if its nearer from left or right side of the
        tab
        """
        page_num = -1
        to_right = False
        horiz = self.notebook.get_tab_pos() == Gtk.PositionType.TOP or \
                self.notebook.get_tab_pos() == Gtk.PositionType.BOTTOM
        for i in range(self.notebook.get_n_pages()):
            page = self.notebook.get_nth_page(i)
            tab = self.notebook.get_tab_label(page)
            tab_alloc = tab.get_allocation()
            if horiz:
                if tab_alloc.x <= x <= (tab_alloc.x + tab_alloc.width):
                    page_num = i
                    if x >= tab_alloc.x + (tab_alloc.width / 2.0):
                        to_right = True
                    break
            else:
                if tab_alloc.y <= y <= (tab_alloc.y + tab_alloc.height):
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
        for i in range(self.notebook.get_n_pages()):
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

    # These constants map to WINDOW_TYPES indices
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
        mode = app.settings.get('one_message_window')
        self.mode = WINDOW_TYPES.index(mode)

        self.parent_win = parent_window
        self.parent_paned = parent_paned

        Gtk.Window.set_default_icon_list(get_app_icon_list(parent_window))

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
        hpaned = app.settings.get('roster_hpaned_position')
        if self.mode in (self.ONE_MSG_WINDOW_ALWAYS,
                         self.ONE_MSG_WINDOW_ALWAYS_WITH_ROSTER):
            size = (app.settings.get('msgwin-width'),
                    app.settings.get('msgwin-height'))
            if self.mode == self.ONE_MSG_WINDOW_ALWAYS_WITH_ROSTER:
                # Add the hpaned position to our message window's size
                size = (hpaned + size[0], size[1])
        elif self.mode == self.ONE_MSG_WINDOW_PERACCT:
            size = (app.config.get_per('accounts', acct, 'msgwin-width'),
                    app.config.get_per('accounts', acct, 'msgwin-height'))
        elif self.mode in (self.ONE_MSG_WINDOW_NEVER, self.ONE_MSG_WINDOW_PERTYPE):
            opt_width = type_ + '-msgwin-width'
            opt_height = type_ + '-msgwin-height'
            size = (app.settings.get(opt_width), app.settings.get(opt_height))
        else:
            return
        win.resize(size[0], size[1])
        if win.parent_paned:
            win.parent_paned.set_position(hpaned)

    def _position_window(self, win, acct, type_):
        """
        Moves window according to config settings
        """
        if (self.mode in [self.ONE_MSG_WINDOW_NEVER,
        self.ONE_MSG_WINDOW_ALWAYS_WITH_ROSTER]):
            return

        if self.mode == self.ONE_MSG_WINDOW_ALWAYS:
            pos = (app.settings.get('msgwin-x-position'),
                    app.settings.get('msgwin-y-position'))
        elif self.mode == self.ONE_MSG_WINDOW_PERACCT:
            pos = (app.config.get_per('accounts', acct, 'msgwin-x-position'),
                    app.config.get_per('accounts', acct, 'msgwin-y-position'))
        elif self.mode == self.ONE_MSG_WINDOW_PERTYPE:
            pos = (app.settings.get(type_ + '-msgwin-x-position'),
                    app.settings.get(type_ + '-msgwin-y-position'))
        else:
            return

        move_window(win.window, pos[0], pos[1])

    def _mode_to_key(self, contact, acct, type_, resource=None):
        if self.mode == self.ONE_MSG_WINDOW_NEVER:
            key = acct + contact.jid
            if resource:
                key += '/' + resource
            return key

        if self.mode == self.ONE_MSG_WINDOW_ALWAYS:
            return self.MAIN_WIN

        if self.mode == self.ONE_MSG_WINDOW_ALWAYS_WITH_ROSTER:
            return self.ROSTER_MAIN_WIN

        if self.mode == self.ONE_MSG_WINDOW_PERACCT:
            return acct

        if self.mode == self.ONE_MSG_WINDOW_PERTYPE:
            return type_

    def create_window(self, contact, acct, type_, resource=None):
        type_ = str(type_)
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
            if app.settings.get('msgwin-max-state'):
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
        app.interface.save_config()
        return False

    def _on_window_destroy(self, win):
        for k in list(self._windows.keys()):
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
            if not ctrl.resource and not ctrl.is_groupchat:
                return ctrl
        return None

    def get_gc_control(self, jid, acct):
        """
        Same as get_control. Was briefly required, is not any more. May be useful
        some day in the future?
        """
        ctrl = self.get_control(jid, acct)
        if ctrl and ctrl.is_groupchat:
            return ctrl
        return None

    def get_controls(self, type_=None, acct=None):
        ctrls = []
        for c in self.controls():
            if acct and c.account != acct:
                continue
            if not type_ or c.type == type_:
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

        app.interface.save_config()

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

        if self.mode == self.ONE_MSG_WINDOW_PERACCT:
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
            # Ignore hpaned separator's width and calculate width ourselves
            win_width = msg_win.window.get_allocation().width
            hpaned_position = app.settings.get('roster_hpaned_position')
            width = win_width - hpaned_position

        if acct:
            app.config.set_per('accounts', acct, size_width_key, width)
            app.config.set_per('accounts', acct, size_height_key, height)

            if self.mode != self.ONE_MSG_WINDOW_NEVER:
                app.config.set_per('accounts', acct, pos_x_key, x)
                app.config.set_per('accounts', acct, pos_y_key, y)

        else:
            win_maximized = msg_win.window.get_window().get_state() == \
                    Gdk.WindowState.MAXIMIZED
            app.settings.set(max_win_key, win_maximized)
            width += width_adjust
            app.settings.set(size_width_key, width)
            app.settings.set(size_height_key, height)

            if self.mode != self.ONE_MSG_WINDOW_NEVER:
                app.settings.set(pos_x_key, x)
                app.settings.set(pos_y_key, y)

    def reconfig(self):
        for w in self.windows():
            self.save_state(w)

        mode = app.settings.get('one_message_window')
        if self.mode == WINDOW_TYPES.index(mode):
            # No change
            return
        self.mode = WINDOW_TYPES.index(mode)

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
                app.settings.set('roster_width', roster_width)

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
                self.parent_win.lookup_action('show-roster').set_enabled(False)
                resize_window(w.window,
                              app.settings.get('roster_width'),
                              app.settings.get('roster_height'))

        self._windows = {}

        for ctrl in controls:
            mw = self.get_window(ctrl.contact.jid, ctrl.account)
            if not mw:
                mw = self.create_window(ctrl.contact, ctrl.account, ctrl.type)
            ctrl.parent_win = mw
            ctrl.add_actions()
            ctrl.update_actions()
            mw.new_tab(ctrl)

    def save_opened_controls(self):
        if not app.settings.get('remember_opened_chat_controls'):
            return
        chat_controls = {}
        for acct in app.connections:
            chat_controls[acct] = []
        for ctrl in self.get_controls(type_=ControlType.CHAT):
            acct = ctrl.account
            if ctrl.contact.jid not in chat_controls[acct]:
                chat_controls[acct].append(ctrl.contact.jid)
        for acct in app.connections:
            app.config.set_per('accounts', acct, 'opened_chat_controls',
                ','.join(chat_controls[acct]))
