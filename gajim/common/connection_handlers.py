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

import operator
from time import time as time_time

import nbxmpp

from gajim.common import modules
from gajim.common import helpers
from gajim.common import app
from gajim.common import jingle_xtls
from gajim.common.caps_cache import muc_caps_cache
from gajim.common.protocol.bytestream import ConnectionSocks5Bytestream
from gajim.common.protocol.bytestream import ConnectionIBBytestream
from gajim.common.connection_handlers_events import *

from gajim.common import ged
from gajim.common.nec import NetworkEvent
from gajim.common.const import KindConstant

from gajim.common.jingle import ConnectionJingle

import logging
log = logging.getLogger('gajim.c.connection_handlers')

# kind of events we can wait for an answer
AGENT_REMOVED = 'agent_removed'

# basic connection handlers used here and in zeroconf
class ConnectionHandlersBase:
    def __init__(self):
        # List of IDs we are waiting answers for {id: (type_of_request, data), }
        self.awaiting_answers = {}
        # List of IDs that will produce a timeout is answer doesn't arrive
        # {time_of_the_timeout: (id, message to send to gui), }
        self.awaiting_timeouts = {}

        # keep track of sessions this connection has with other JIDs
        self.sessions = {}

        # IDs of sent messages (https://trac.gajim.org/ticket/8222)
        self.sent_message_ids = []

        # We decrypt GPG messages one after the other. Keep queue in mem
        self.gpg_messages_to_decrypt = []

        app.ged.register_event_handler('presence-received', ged.CORE,
            self._nec_presence_received)
        app.ged.register_event_handler('gc-message-received', ged.CORE,
            self._nec_gc_message_received)

    def cleanup(self):
        app.ged.remove_event_handler('presence-received', ged.CORE,
            self._nec_presence_received)
        app.ged.remove_event_handler('gc-message-received', ged.CORE,
            self._nec_gc_message_received)

    def _nec_presence_received(self, obj):
        account = obj.conn.name
        if account != self.name:
            return
        jid = obj.jid
        resource = obj.resource or ''

        statuss = ['offline', 'error', 'online', 'chat', 'away', 'xa', 'dnd',
            'invisible']
        obj.old_show = 0
        obj.new_show = statuss.index(obj.show)

        obj.contact_list = []

        highest = app.contacts.get_contact_with_highest_priority(account, jid)
        obj.was_highest = (highest and highest.resource == resource)

        # Update contact
        obj.contact_list = app.contacts.get_contacts(account, jid)
        obj.contact = None
        resources = []
        for c in obj.contact_list:
            resources.append(c.resource)
            if c.resource == resource:
                obj.contact = c
                break

        if obj.contact:
            if obj.contact.show in statuss:
                obj.old_show = statuss.index(obj.contact.show)
            # nick changed
            if obj.contact_nickname is not None and \
            obj.contact.contact_name != obj.contact_nickname:
                obj.contact.contact_name = obj.contact_nickname
                obj.need_redraw = True

            elif obj.old_show != obj.new_show or obj.contact.status != \
            obj.status:
                obj.need_redraw = True
        else:
            obj.contact = app.contacts.get_first_contact_from_jid(account,
                jid)
            if not obj.contact:
                # Presence of another resource of our jid
                # Create self contact and add to roster
                if resource == obj.conn.server_resource:
                    return
                # Ignore offline presence of unknown self resource
                if obj.new_show < 2:
                    return
                obj.contact = app.contacts.create_self_contact(jid=jid,
                    account=account, show=obj.show, status=obj.status,
                    priority=obj.prio, keyID=obj.keyID,
                    resource=obj.resource)
                app.contacts.add_contact(account, obj.contact)
                obj.contact_list.append(obj.contact)
            elif obj.contact.show in statuss:
                obj.old_show = statuss.index(obj.contact.show)
            if (resources != [''] and (len(obj.contact_list) != 1 or \
            obj.contact_list[0].show not in ('not in roster', 'offline'))) and \
            not app.jid_is_transport(jid):
                # Another resource of an existing contact connected
                obj.old_show = 0
                obj.contact = app.contacts.copy_contact(obj.contact)
                obj.contact_list.append(obj.contact)
            obj.contact.resource = resource

            obj.need_add_in_roster = True

        if not app.jid_is_transport(jid) and len(obj.contact_list) == 1:
            # It's not an agent
            if obj.old_show == 0 and obj.new_show > 1:
                if not jid in app.newly_added[account]:
                    app.newly_added[account].append(jid)
                if jid in app.to_be_removed[account]:
                    app.to_be_removed[account].remove(jid)
            elif obj.old_show > 1 and obj.new_show == 0 and \
            obj.conn.connected > 1:
                if not jid in app.to_be_removed[account]:
                    app.to_be_removed[account].append(jid)
                if jid in app.newly_added[account]:
                    app.newly_added[account].remove(jid)
                obj.need_redraw = True

        obj.contact.show = obj.show
        obj.contact.status = obj.status
        obj.contact.priority = obj.prio
        attached_keys = app.config.get_per('accounts', account,
            'attached_gpg_keys').split()
        if jid in attached_keys:
            obj.contact.keyID = attached_keys[attached_keys.index(jid) + 1]
        else:
            # Do not override assigned key
            obj.contact.keyID = obj.keyID
        obj.contact.contact_nickname = obj.contact_nickname
        obj.contact.idle_time = obj.idle_time

        if app.jid_is_transport(jid):
            return

        # It isn't an agent
        # reset chatstate if needed:
        # (when contact signs out or has errors)
        if obj.show in ('offline', 'error'):
            obj.contact.our_chatstate = obj.contact.chatstate = None

            # TODO: This causes problems when another
            # resource signs off!
            self.stop_all_active_file_transfers(obj.contact)

        if app.config.get('log_contact_status_changes') and \
        app.config.should_log(self.name, obj.jid):
            show = app.logger.convert_show_values_to_db_api_values(obj.show)
            if show is not None:
                app.logger.insert_into_logs(self.name,
                                            nbxmpp.JID(obj.jid).getStripped(),
                                            time_time(),
                                            KindConstant.STATUS,
                                            message=obj.status,
                                            show=show)

    def _check_for_mam_compliance(self, room_jid, stanza_id):
        namespace = muc_caps_cache.get_mam_namespace(room_jid)
        if stanza_id is None and namespace == nbxmpp.NS_MAM_2:
            log.warning('%s announces mam:2 without stanza-id', room_jid)

    def _nec_gc_message_received(self, obj):
        if obj.conn.name != self.name:
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
        else:
            return self.make_new_session(fjid, thread_id)

    def find_session(self, jid, thread_id):
        try:
            if not thread_id:
                return self.find_null_session(jid)
            else:
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
            return sorted(chat_sessions, key=operator.attrgetter('last_send'))[
                -1]
        else:
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
        if not type_ == 'pm':
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

        # IDs of disco#items requests
        self.disco_items_ids = []
        # IDs of disco#info requests
        self.disco_info_ids = []

        self.continue_connect_info = None

        # If handlers have been registered
        self.handlers_registered = False

        app.nec.register_incoming_event(StreamConflictReceivedEvent)
        app.nec.register_incoming_event(NotificationEvent)

        app.ged.register_event_handler('agent-removed', ged.CORE,
            self._nec_agent_removed)

    def cleanup(self):
        ConnectionHandlersBase.cleanup(self)
        app.ged.remove_event_handler('agent-removed', ged.CORE,
            self._nec_agent_removed)

    def _ErrorCB(self, con, iq_obj):
        log.debug('ErrorCB')
        app.nec.push_incoming_event(IqErrorReceivedEvent(None, conn=self,
            stanza=iq_obj))

    def _IqCB(self, con, iq_obj):
        id_ = iq_obj.getID()

        app.nec.push_incoming_event(NetworkEvent('raw-iq-received',
            conn=self, stanza=iq_obj))

        # Check if we were waiting a timeout for this id
        found_tim = None
        for tim in self.awaiting_timeouts:
            if id_ == self.awaiting_timeouts[tim][0]:
                found_tim = tim
                break
        if found_tim:
            del self.awaiting_timeouts[found_tim]

        if id_ not in self.awaiting_answers:
            return

        if self.awaiting_answers[id_][0] == AGENT_REMOVED:
            jid = self.awaiting_answers[id_][1]
            app.nec.push_incoming_event(AgentRemovedEvent(None, conn=self,
                agent=jid))
            del self.awaiting_answers[id_]

    def _dispatch_gc_msg_with_captcha(self, stanza, msg_obj):
        msg_obj.stanza = stanza
        app.nec.push_incoming_event(GcMessageReceivedEvent(None,
            conn=self, msg_obj=msg_obj))

    def _on_bob_received(self, conn, result, cid):
        """
        Called when we receive BoB data
        """
        if cid not in self.awaiting_cids:
            return

        if result.getType() == 'result':
            data = result.getTags('data', namespace=nbxmpp.NS_BOB)
            if data.getAttr('cid') == cid:
                for func in self.awaiting_cids[cid]:
                    cb = func[0]
                    args = func[1]
                    pos = func[2]
                    bob_data = data.getData()
                    def recurs(node, cid, data):
                        if node.getData() == 'cid:' + cid:
                            node.setData(data)
                        else:
                            for child in node.getChildren():
                                recurs(child, cid, data)
                    recurs(args[pos], cid, bob_data)
                    cb(*args)
                del self.awaiting_cids[cid]
                return

        # An error occured, call callback without modifying data.
        for func in self.awaiting_cids[cid]:
            cb = func[0]
            args = func[1]
            cb(*args)
        del self.awaiting_cids[cid]

    def get_bob_data(self, cid, to, callback, args, position):
        """
        Request for BoB (XEP-0231) and when data will arrive, call callback
        with given args, after having replaced cid by it's data in
        args[position]
        """
        if cid in self.awaiting_cids:
            self.awaiting_cids[cid].appends((callback, args, position))
        else:
            self.awaiting_cids[cid] = [(callback, args, position)]
        iq = nbxmpp.Iq(to=to, typ='get')
        data = iq.addChild(name='data', attrs={'cid': cid},
            namespace=nbxmpp.NS_BOB)
        self.connection.SendAndCallForResponse(iq, self._on_bob_received,
            {'cid': cid})

    def _nec_agent_removed(self, obj):
        if obj.conn.name != self.name:
            return
        for jid in obj.jid_list:
            log.debug('Removing contact %s due to unregistered transport %s' % \
                (jid, obj.agent))
            self.get_module('Presence').unsubscribe(jid)
            # Transport contacts can't have 2 resources
            if jid in app.to_be_removed[self.name]:
                # This way we'll really remove it
                app.to_be_removed[self.name].remove(jid)

    def discover_ft_proxies(self):
        cfg_proxies = app.config.get_per('accounts', self.name,
            'file_transfer_proxies')
        our_jid = helpers.parse_jid(app.get_jid_from_account(self.name) + \
            '/' + self.server_resource)
        testit = app.config.get_per('accounts', self.name,
            'test_ft_proxies_on_startup')
        if cfg_proxies:
            proxies = [e.strip() for e in cfg_proxies.split(',')]
            for proxy in proxies:
                app.proxy65_manager.resolve(proxy, self.connection, our_jid,
                    testit=testit)

    def send_first_presence(self):
        if self.connected > 1 and self.continue_connect_info:
            msg = self.continue_connect_info[1]
            sign_msg = self.continue_connect_info[2]
            signed = ''
            send_first_presence = True
            if sign_msg:
                signed = self.get_signed_presence(msg,
                    self._send_first_presence)
                if signed is None:
                    app.nec.push_incoming_event(GPGPasswordRequiredEvent(None,
                        conn=self, callback=self._send_first_presence))
                    # _send_first_presence will be called when user enter
                    # passphrase
                    send_first_presence = False
            if send_first_presence:
                self._send_first_presence(signed)

    def _send_first_presence(self, signed=''):
        show = self.continue_connect_info[0]
        msg = self.continue_connect_info[1]
        sign_msg = self.continue_connect_info[2]
        if sign_msg and not signed:
            signed = self.get_signed_presence(msg)
            if signed is None:
                app.nec.push_incoming_event(BadGPGPassphraseEvent(None,
                    conn=self))
                self.USE_GPG = False
                signed = ''
        self.connected = app.SHOW_LIST.index(show)
        sshow = helpers.get_xmpp_show(show)
        # send our presence
        if show == 'invisible':
            self.send_invisible_presence(msg, signed, True)
            return
        if show not in ['offline', 'online', 'chat', 'away', 'xa', 'dnd']:
            return
        priority = app.get_priority(self.name, sshow)

        self.get_module('Presence').send_presence(
            priority=priority,
            show=sshow,
            status=msg,
            sign=signed)

        if self.connection:
            self.priority = priority
        app.nec.push_incoming_event(OurShowEvent(None, conn=self,
            show=show))

        if not self.avatar_conversion:
            # ask our VCard
            self.get_module('VCardTemp').request_vcard()

        # Get bookmarks
        self.get_module('Bookmarks').get_bookmarks()

        # Get annotations from private namespace
        self.get_module('Annotations').get_annotations()

        # Inform GUI we just signed in
        app.nec.push_incoming_event(SignedInEvent(None, conn=self))
        self.get_module('PEP').send_stored_publish()
        self.continue_connect_info = None

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
        con.RegisterHandler('iq', self._ErrorCB, 'error')
        con.RegisterHandler('iq', self._IqCB)
        con.RegisterHandler('iq', self._ResultCB, 'result')
        con.RegisterHandler('unknown', self._StreamCB,
            nbxmpp.NS_XMPP_STREAMS, xmlns=nbxmpp.NS_STREAMS)
        con.RegisterHandler('iq', self._PubkeyGetCB, 'get',
            nbxmpp.NS_PUBKEY_PUBKEY)
        con.RegisterHandler('iq', self._PubkeyResultCB, 'result',
            nbxmpp.NS_PUBKEY_PUBKEY)

        for handler in modules.get_handlers(self):
            con.RegisterHandler(*handler)
        self.handlers_registered = True

    def _unregister_handlers(self):
        if not self.connection:
            return
        for handler in modules.get_handlers(self):
            self.connection.UnregisterHandler(*handler)
        self.handlers_registered = False
