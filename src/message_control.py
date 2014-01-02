# -*- coding:utf-8 -*-
## src/message_control.py
##
## Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
##                    Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006-2007 Jean-Marie Traissard <jim AT lapin.org>
##                         Travis Shirk <travis AT pobox.com>
## Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2007 Julien Pivotto <roidelapluie AT gmail.com>
##                    Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
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

import gtkgui_helpers

from common import gajim
from common import helpers
from common import ged
from common.stanza_session import EncryptedStanzaSession, ArchivingStanzaSession

# Derived types MUST register their type IDs here if custom behavor is required
TYPE_CHAT = 'chat'
TYPE_GC = 'gc'
TYPE_PM = 'pm'

####################

class MessageControl(object):
    """
    An abstract base widget that can embed in the Gtk.Notebook of a
    MessageWindow
    """

    def __init__(self, type_id, parent_win, widget_name, contact, account,
    resource=None):
        # dict { cb id : widget}
        # keep all registered callbacks of widgets, created by self.xml
        self.handlers = {}
        self.type_id = type_id
        self.parent_win = parent_win
        self.widget_name = widget_name
        self.contact = contact
        self.account = account
        self.hide_chat_buttons = False
        self.resource = resource

        self.session = None

        gajim.last_message_time[self.account][self.get_full_jid()] = 0

        self.xml = gtkgui_helpers.get_gtk_builder('%s.ui' % widget_name)
        self.widget = self.xml.get_object('%s_hbox' % widget_name)

        gajim.ged.register_event_handler('message-outgoing', ged.OUT_GUI1,
            self._nec_message_outgoing)

    def get_full_jid(self):
        fjid = self.contact.jid
        if self.resource:
            fjid += '/' + self.resource
        return fjid

    def set_control_active(self, state):
        """
        Called when the control becomes active (state is True) or inactive (state
        is False)
        """
        pass  # Derived classes MUST implement this method

    def minimizable(self):
        """
        Called to check if control can be minimized

        Derived classes MAY implement this.
        """
        return False

    def safe_shutdown(self):
        """
        Called to check if control can be closed without loosing data.
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

    def shutdown(self):
        """
        Derived classes MUST implement this
        """
        gajim.ged.remove_event_handler('message-outgoing', ged.OUT_GUI1,
            self._nec_message_outgoing)

    def repaint_themed_widgets(self):
        """
        Derived classes SHOULD implement this
        """
        pass

    def update_ui(self):
        """
        Derived classes SHOULD implement this
        """
        pass

    def toggle_emoticons(self):
        """
        Derived classes MAY implement this
        """
        pass

    def update_font(self):
        """
        Derived classes SHOULD implement this
        """
        pass

    def update_tags(self):
        """
        Derived classes SHOULD implement this
        """
        pass

    def get_tab_label(self, chatstate):
        """
        Return a suitable tab label string. Returns a tuple such as: (label_str,
        color) either of which can be None if chatstate is given that means we
        have HE SENT US a chatstate and we want it displayed

        Derivded classes MUST implement this.
        """
        # Return a markup'd label and optional Gtk.Color in a tupple like:
        # return (label_str, None)
        pass

    def get_tab_image(self, count_unread=True):
        # Return a suitable tab image for display.
        # None clears any current label.
        return None

    def prepare_context_menu(self):
        """
        Derived classes SHOULD implement this
        """
        return None

    def chat_buttons_set_visible(self, state):
        """
        Derived classes MAY implement this
        """
        self.hide_chat_buttons = state

    def got_connected(self):
        pass

    def got_disconnected(self):
        pass

    def get_specific_unread(self):
        return len(gajim.events.get_events(self.account,
                self.contact.jid))

    def set_session(self, session):
        oldsession = None
        if hasattr(self, 'session'):
            oldsession = self.session

        if oldsession and session == oldsession:
            return

        self.session = session

        if session:
            session.control = self

        if oldsession:
            oldsession.control = None

        crypto_changed = bool(session and isinstance(session,
            EncryptedStanzaSession) and session.enable_encryption) != \
            bool(oldsession and isinstance(oldsession, EncryptedStanzaSession) \
            and oldsession.enable_encryption)

        archiving_changed = bool(session and isinstance(session,
            ArchivingStanzaSession) and session.archiving) != \
            bool(oldsession and isinstance(oldsession,
            ArchivingStanzaSession) and oldsession.archiving)

        if crypto_changed or archiving_changed:
            self.print_session_details(oldsession)

    def remove_session(self, session):
        if session != self.session:
            return
        self.session.control = None
        self.session = None

    def _nec_message_outgoing(self, obj):
        # Send the given message to the active tab.
        # Doesn't return None if error
        if obj.control != self:
            return

        obj.message = helpers.remove_invalid_xml_chars(obj.message)
        obj.original_message = obj.message

        conn = gajim.connections[self.account]

        if not self.session:
            if not obj.resource:
                if self.resource:
                    obj.resource = self.resource
                else:
                    obj.resource = self.contact.resource
            sess = conn.find_controlless_session(obj.jid, resource=obj.resource)

            if self.resource:
                obj.jid += '/' + self.resource

            if not sess:
                if self.type_id == TYPE_PM:
                    sess = conn.make_new_session(obj.jid, type_='pm')
                else:
                    sess = conn.make_new_session(obj.jid)

            self.set_session(sess)

        obj.session = self.session
