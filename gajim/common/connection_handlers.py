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
from gajim.common import ged
from gajim.common import helpers
from gajim.common import jingle_xtls
from gajim.common.caps_cache import muc_caps_cache
from gajim.common.const import KindConstant
from gajim.common.jingle import ConnectionJingle
from gajim.common.protocol.bytestream import ConnectionSocks5Bytestream
from gajim.common.protocol.bytestream import ConnectionIBBytestream
from gajim.common.connection_handlers_events import StreamReceivedEvent
from gajim.common.connection_handlers_events import MessageErrorEvent
from gajim.common.connection_handlers_events import PresenceReceivedEvent
from gajim.common.connection_handlers_events import StreamConflictReceivedEvent
from gajim.common.connection_handlers_events import NotificationEvent


log = logging.getLogger('gajim.c.connection_handlers')

# basic connection handlers used here and in zeroconf
class ConnectionHandlersBase:
    def __init__(self):
        # keep track of sessions this connection has with other JIDs
        self.sessions = {}

        # IDs of sent messages (https://trac.gajim.org/ticket/8222)
        self.sent_message_ids = []

        # We decrypt GPG messages one after the other. Keep queue in mem
        self.gpg_messages_to_decrypt = []

        app.ged.register_event_handler('gc-message-received', ged.CORE,
            self._nec_gc_message_received)

    def cleanup(self):
        app.ged.remove_event_handler('gc-message-received', ged.CORE,
            self._nec_gc_message_received)

    def _check_for_mam_compliance(self, room_jid, stanza_id):
        namespace = muc_caps_cache.get_mam_namespace(room_jid)
        if stanza_id is None and namespace == nbxmpp.NS_MAM_2:
            log.warning('%s announces mam:2 without stanza-id', room_jid)

    def _nec_gc_message_received(self, obj):
        if obj.conn.name != self.name:
            return

        if obj.stanza.getType() == 'error':
            return

        self._check_for_mam_compliance(obj.jid, obj.stanza_id)

        if (app.config.should_log(obj.conn.name, obj.jid) and
                obj.msgtxt and obj.nick):
            # if not obj.nick, it means message comes from room itself
            # usually it hold description and can be send at each connection
            # so don't store it in logs
            app.logger.insert_into_logs(self.name,
                                        obj.jid,
                                        obj.timestamp,
                                        KindConstant.GC_MSG,
                                        message=obj.msgtxt,
                                        contact_name=obj.nick,
                                        additional_data=obj.additional_data,
                                        stanza_id=obj.stanza_id)
            app.logger.set_room_last_message_time(obj.room_jid, obj.timestamp)
            self.get_module('MAM').save_archive_id(
                obj.room_jid, obj.stanza_id, obj.timestamp)

    # process and dispatch an error message
    def dispatch_error_message(self, msg, msgtxt, session, frm, tim):
        error_msg = msg.getErrorMsg()

        if not error_msg:
            error_msg = msgtxt
            msgtxt = None

        subject = msg.getSubject()

        if session.is_loggable():
            app.logger.insert_into_logs(self.name,
                                        nbxmpp.JID(frm).getStripped(),
                                        tim,
                                        KindConstant.ERROR,
                                        message=error_msg,
                                        subject=subject)

        app.nec.push_incoming_event(MessageErrorEvent(None, conn=self,
            fjid=frm, error_code=msg.getErrorCode(), error_msg=error_msg,
            msg=msgtxt, time_=tim, session=session, stanza=msg))

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

        sess = cls(self, nbxmpp.JID(jid), thread_id, type_)

        # determine if this session is a pm session
        # if not, discard the resource so that all sessions are stored bare
        if type_ != 'pm':
            jid = app.get_jid_without_resource(jid)

        if not jid in self.sessions:
            self.sessions[jid] = {}

        self.sessions[jid][sess.thread_id] = sess

        return sess

class ConnectionHandlers(ConnectionSocks5Bytestream,
                         ConnectionHandlersBase,
                         ConnectionJingle, ConnectionIBBytestream):
    def __init__(self):
        ConnectionSocks5Bytestream.__init__(self)
        ConnectionIBBytestream.__init__(self)

        # Handle presences BEFORE caps
        app.nec.register_incoming_event(PresenceReceivedEvent)

        ConnectionJingle.__init__(self)
        ConnectionHandlersBase.__init__(self)

        self.continue_connect_info = None

        app.nec.register_incoming_event(StreamConflictReceivedEvent)
        app.nec.register_incoming_event(NotificationEvent)

    def cleanup(self):
        ConnectionHandlersBase.cleanup(self)

    def _PubkeyGetCB(self, con, iq_obj):
        log.info('PubkeyGetCB')
        jid_from = helpers.get_full_jid_from_iq(iq_obj)
        sid = iq_obj.getAttr('id')
        jingle_xtls.send_cert(con, jid_from, sid)
        raise nbxmpp.NodeProcessed

    def _PubkeyResultCB(self, con, iq_obj):
        log.info('PubkeyResultCB')
        jid_from = helpers.get_full_jid_from_iq(iq_obj)
        jingle_xtls.handle_new_cert(con, iq_obj, jid_from)

    def _StreamCB(self, con, obj):
        log.debug('StreamCB')
        app.nec.push_incoming_event(StreamReceivedEvent(None,
            conn=self, stanza=obj))

    def _register_handlers(self, con, con_type):
        # try to find another way to register handlers in each class
        # that defines handlers

        con.RegisterHandler('iq', self._siSetCB, 'set', nbxmpp.NS_SI)
        con.RegisterHandler('iq', self._siErrorCB, 'error', nbxmpp.NS_SI)
        con.RegisterHandler('iq', self._siResultCB, 'result', nbxmpp.NS_SI)
        con.RegisterHandler('iq', self._bytestreamSetCB, 'set',
            nbxmpp.NS_BYTESTREAM)
        con.RegisterHandler('iq', self._bytestreamResultCB, 'result',
            nbxmpp.NS_BYTESTREAM)
        con.RegisterHandler('iq', self._bytestreamErrorCB, 'error',
            nbxmpp.NS_BYTESTREAM)
        con.RegisterHandlerOnce('iq', self.IBBAllIqHandler)
        con.RegisterHandler('iq', self.IBBIqHandler, ns=nbxmpp.NS_IBB)
        con.RegisterHandler('message', self.IBBMessageHandler, ns=nbxmpp.NS_IBB)

        con.RegisterHandler('iq', self._JingleCB, 'result')
        con.RegisterHandler('iq', self._JingleCB, 'error')
        con.RegisterHandler('iq', self._JingleCB, 'set', nbxmpp.NS_JINGLE)
        con.RegisterHandler('iq', self._ResultCB, 'result')
        con.RegisterHandler('unknown', self._StreamCB,
            nbxmpp.NS_XMPP_STREAMS, xmlns=nbxmpp.NS_STREAMS)
        con.RegisterHandler('iq', self._PubkeyGetCB, 'get',
            nbxmpp.NS_PUBKEY_PUBKEY)
        con.RegisterHandler('iq', self._PubkeyResultCB, 'result',
            nbxmpp.NS_PUBKEY_PUBKEY)
