# Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
#                    Junglecow J <junglecow AT gmail.com>
# Copyright (C) 2006-2007 Tomasz Melcer <liori AT exroot.org>
#                         Travis Shirk <travis AT pobox.com>
#                         Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2007 Julien Pivotto <roidelapluie AT gmail.com>
# Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
#                         Jean-Marie Traissard <jim AT lapin.org>
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

import logging
import operator

import nbxmpp

from gajim.common import app
from gajim.common.connection_handlers_events import PresenceReceivedEvent
from gajim.common.connection_handlers_events import NotificationEvent


log = logging.getLogger('gajim.c.connection_handlers')

# basic connection handlers used here and in zeroconf
class ConnectionHandlersBase:
    def __init__(self):
        # keep track of sessions this connection has with other JIDs
        self.sessions = {}

    def get_sessions(self, jid):
        """
        Get all sessions for the given full jid
        """
        if not app.interface.is_pm_contact(jid, self.name):
            jid = app.get_jid_without_resource(jid)

        try:
            return list(self.sessions[jid].values())
        except KeyError:
            return []

    def get_or_create_session(self, fjid, thread_id):
        """
        Return an existing session between this connection and 'jid', returns a
        new one if none exist
        """
        pm = True
        jid = fjid

        if not app.interface.is_pm_contact(fjid, self.name):
            pm = False
            jid = app.get_jid_without_resource(fjid)

        session = self.find_session(jid, thread_id)

        if session:
            return session

        if pm:
            return self.make_new_session(fjid, thread_id, type_='pm')
        return self.make_new_session(fjid, thread_id)

    def find_session(self, jid, thread_id):
        try:
            if not thread_id:
                return self.find_null_session(jid)
            return self.sessions[jid][thread_id]
        except KeyError:
            return None

    def terminate_sessions(self):
        self.sessions = {}

    def delete_session(self, jid, thread_id):
        if not jid in self.sessions:
            jid = app.get_jid_without_resource(jid)
        if not jid in self.sessions:
            return

        del self.sessions[jid][thread_id]

        if not self.sessions[jid]:
            del self.sessions[jid]

    def find_null_session(self, jid):
        """
        Find all of the sessions between us and a remote jid in which we haven't
        received a thread_id yet and returns the session that we last sent a
        message to
        """
        sessions = list(self.sessions[jid].values())

        # sessions that we haven't received a thread ID in
        idless = [s for s in sessions if not s.received_thread_id]

        # filter out everything except the default session type
        chat_sessions = [s for s in idless if isinstance(s,
            app.default_session_type)]

        if chat_sessions:
            # return the session that we last sent a message in
            return sorted(chat_sessions,
                          key=operator.attrgetter('last_send'))[-1]
        return None

    def get_latest_session(self, jid):
        """
        Get the session that we last sent a message to
        """
        if jid not in self.sessions:
            return None
        sessions = self.sessions[jid].values()
        if not sessions:
            return None
        return sorted(sessions, key=operator.attrgetter('last_send'))[-1]

    def find_controlless_session(self, jid, resource=None):
        """
        Find an active session that doesn't have a control attached
        """
        try:
            sessions = list(self.sessions[jid].values())

            # filter out everything except the default session type
            chat_sessions = [s for s in sessions if isinstance(s,
                app.default_session_type)]

            orphaned = [s for s in chat_sessions if not s.control]

            if resource:
                orphaned = [s for s in orphaned if s.resource == resource]

            return orphaned[0]
        except (KeyError, IndexError):
            return None

    def make_new_session(self, jid, thread_id=None, type_='chat', cls=None):
        """
        Create and register a new session

        thread_id=None to generate one.
        type_ should be 'chat' or 'pm'.
        """
        if not cls:
            cls = app.default_session_type

        sess = cls(self, nbxmpp.JID.from_string(jid), thread_id, type_)

        # determine if this session is a pm session
        # if not, discard the resource so that all sessions are stored bare
        if type_ != 'pm':
            jid = app.get_jid_without_resource(jid)

        if not jid in self.sessions:
            self.sessions[jid] = {}

        self.sessions[jid][sess.thread_id] = sess

        return sess

class ConnectionHandlers(ConnectionHandlersBase):
    def __init__(self):
        ConnectionHandlersBase.__init__(self)

        app.nec.register_incoming_event(PresenceReceivedEvent)
        app.nec.register_incoming_event(NotificationEvent)
