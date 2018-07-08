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
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

# XEP-0313: Message Archive Management

import logging
from datetime import datetime, timedelta

import nbxmpp

from gajim.common import app
from gajim.common.nec import NetworkIncomingEvent
from gajim.common.const import ArchiveState, JIDConstant, KindConstant
from gajim.common.caps_cache import muc_caps_cache
from gajim.common.modules.misc import parse_delay
from gajim.common.modules.misc import parse_oob
from gajim.common.modules.misc import parse_correction
from gajim.common.modules.misc import parse_eme

log = logging.getLogger('gajim.c.m.archiving')


class MAM:
    def __init__(self, con):
        self._con = con
        self._account = con.name

        self.handlers = [
            ('message', self._mam_message_received, nbxmpp.NS_MAM_1),
            ('message', self._mam_message_received, nbxmpp.NS_MAM_2)
        ]

        self.available = False
        self.archiving_namespace = None
        self._mam_query_ids = {}

    def _from_valid_archive(self, stanza, message, groupchat):
        if groupchat:
            expected_archive = message.getFrom()
        else:
            expected_archive = self._con.get_own_jid()

        archive_jid = stanza.getFrom()
        if archive_jid is None:
            if groupchat:
                return
            # Message from our own archive
            return self._con.get_own_jid()
        else:
            if archive_jid.bareMatch(expected_archive):
                return archive_jid

    @staticmethod
    def _is_self_message(message, groupchat):
        if groupchat:
            return False
        frm = message.getFrom()
        to = message.getTo()
        return frm.bareMatch(to)

    @staticmethod
    def _is_muc_pm(message, groupchat, with_):
        if groupchat:
            return False
        muc_user = message.getTag('x', namespace=nbxmpp.NS_MUC_USER)
        if muc_user is not None:
            return muc_user.getChildren() == []
        else:
            # muc#user namespace was added in MUC 1.28 so we need a fallback
            # Check if we know the jid, otherwise disco it
            if app.logger.jid_is_room_jid(with_.getStripped()):
                return True
            return False

    def _get_unique_id(self, result, message, groupchat, self_message, muc_pm):
        stanza_id = result.getAttr('id')
        if groupchat:
            return stanza_id, None

        origin_id = message.getOriginID()
        if self_message:
            return None, origin_id

        if muc_pm:
            return stanza_id, origin_id

        if self._con.get_own_jid().bareMatch(message.getFrom()):
            # message we sent
            return stanza_id, origin_id

        # A message we received
        return stanza_id, None

    def _mam_message_received(self, conn, stanza):
        app.nec.push_incoming_event(
            NetworkIncomingEvent('raw-mam-message-received',
                                 conn=self._con,
                                 stanza=stanza))

        result = stanza.getTag('result', protocol=True)
        queryid = result.getAttr('queryid')
        forwarded = result.getTag('forwarded',
                                  namespace=nbxmpp.NS_FORWARD,
                                  protocol=True)
        message = forwarded.getTag('message', protocol=True)

        groupchat = message.getType() == 'groupchat'

        archive_jid = self._from_valid_archive(stanza, message, groupchat)
        if archive_jid is None:
            log.warning('Message from invalid archive %s', stanza)
            raise nbxmpp.NodeProcessed

        log.info('Received message from archive: %s', archive_jid)
        if not self._is_valid_request(archive_jid, queryid):
            log.warning('Invalid MAM Message: unknown query id')
            log.debug(stanza)
            raise nbxmpp.NodeProcessed

        # Timestamp parsing
        timestamp = parse_delay(forwarded)
        if timestamp is None:
            raise nbxmpp.NodeProcessed

        user_timestamp = parse_delay(message)

        # Fix for self messaging
        if not groupchat:
            to = message.getTo()
            if to is None:
                # Some servers dont set the 'to' attribute when
                # we send a message to ourself
                message.setTo(self._con.get_own_jid())

        event_attrs = {}

        if groupchat:
            event_attrs.update(self._parse_gc_attrs(message))
        else:
            event_attrs.update(self._parse_chat_attrs(message))

        self_message = self._is_self_message(message, groupchat)
        muc_pm = self._is_muc_pm(message, groupchat, event_attrs['with_'])

        stanza_id, origin_id = self._get_unique_id(
            result, message, groupchat, self_message, muc_pm)
        message_id = message.getID()

        # Check for duplicates
        namespace = self.archiving_namespace
        if groupchat:
            namespace = muc_caps_cache.get_mam_namespace(
                archive_jid.getStripped())

        if namespace == nbxmpp.NS_MAM_2:
            # Search only with stanza-id for duplicates on mam:2
            if app.logger.find_stanza_id(self._account,
                                         archive_jid.getStripped(),
                                         stanza_id,
                                         origin_id,
                                         groupchat=groupchat):
                log.info('Found duplicate with stanza-id')
                raise nbxmpp.NodeProcessed

        msgtxt = message.getTagData('body')

        event_attrs.update(
            {'conn': self._con,
             'additional_data': {},
             'encrypted': False,
             'timestamp': timestamp,
             'user_timestamp': user_timestamp,
             'self_message': self_message,
             'groupchat': groupchat,
             'muc_pm': muc_pm,
             'stanza_id': stanza_id,
             'origin_id': origin_id,
             'message_id': message_id,
             'correct_id': None,
             'archive_jid': archive_jid,
             'msgtxt': msgtxt,
             'message': message,
             'namespace': namespace,
             })

        if groupchat:
            event = MamGcMessageReceivedEvent(None, **event_attrs)
        else:
            event = MamMessageReceivedEvent(None, **event_attrs)

        app.plugin_manager.extension_point(
            'decrypt', self._con, event, self._decryption_finished)

        if not event.encrypted:
            eme = parse_eme(event.message)
            if eme is not None:
                event.msgtxt = eme
            self._decryption_finished(event)

        raise nbxmpp.NodeProcessed

    def _parse_gc_attrs(self, message):
        with_ = message.getFrom()
        nick = message.getFrom().getResource()

        # Get the real jid if we have it
        real_jid = None
        muc_user = message.getTag('x', namespace=nbxmpp.NS_MUC_USER)
        if muc_user is not None:
            real_jid = muc_user.getTagAttr('item', 'jid')
            if real_jid is not None:
                real_jid = nbxmpp.JID(real_jid)

        return {'with_': with_,
                'nick': nick,
                'real_jid': real_jid,
                'kind': KindConstant.GC_MSG}

    def _parse_chat_attrs(self, message):
        frm = message.getFrom()
        to = message.getTo()
        if frm.bareMatch(self._con.get_own_jid()):
            with_ = to
            kind = KindConstant.CHAT_MSG_SENT
        else:
            with_ = frm
            kind = KindConstant.CHAT_MSG_RECV

        return {'with_': with_,
                'nick': None,
                'kind': kind}

    def _decryption_finished(self, event):
        if not event.msgtxt:
            # For example Chatstates, Receipts, Chatmarkers
            log.debug(event.message.getProperties())
            return
        log.debug(event.msgtxt)

        event.correct_id = parse_correction(event.message)
        parse_oob(event.message, event.additional_data)

        with_ = event.with_.getStripped()
        if event.muc_pm:
            # we store the message with the full JID
            with_ = str(event.with_)

        stanza_id = event.stanza_id
        if event.self_message:
            # Self messages can only be deduped with origin-id
            if event.origin_id is None:
                log.warning('Self message without origin-id found')
                return
            stanza_id = event.origin_id

        if event.namespace == nbxmpp.NS_MAM_1:
            if app.logger.search_for_duplicate(
                    self._account, with_, event.timestamp, event.msgtxt):
                log.info('Found duplicate with fallback for mam:1')
                return

        app.logger.insert_into_logs(self._account,
                                    with_,
                                    event.timestamp,
                                    event.kind,
                                    unread=False,
                                    message=event.msgtxt,
                                    contact_name=event.nick,
                                    additional_data=event.additional_data,
                                    stanza_id=stanza_id)

        app.nec.push_incoming_event(
            MamDecryptedMessageReceived(None, **vars(event)))

    def _is_valid_request(self, jid, query_id):
        if query_id is None:
            return False

        valid_id = self._mam_query_ids.get(jid.getStripped(), None)
        return valid_id == query_id

    def _get_query_id(self, jid):
        query_id = self._con.connection.getAnID()
        self._mam_query_ids[jid] = query_id
        return query_id

    @staticmethod
    def _parse_iq(stanza):
        if not nbxmpp.isResultNode(stanza):
            log.error('Error on MAM query: %s', stanza.getError())
            raise InvalidMamIQ

        fin = stanza.getTag('fin')
        if fin is None:
            log.error('Malformed MAM query result received: %s', stanza)
            raise InvalidMamIQ

        set_ = fin.getTag('set', namespace=nbxmpp.NS_RSM)
        if set_ is None:
            log.error(
                'Malformed MAM query result received (no "set" Node): %s',
                stanza)
            raise InvalidMamIQ
        return fin, set_

    def _get_from_jid(self, stanza):
        jid = stanza.getFrom()
        if jid is None:
            # No from means, iq from our own archive
            jid = self._con.get_own_jid().getStripped()
        else:
            jid = jid.getStripped()
        return jid

    def request_archive_count(self, start_date, end_date):
        jid = self._con.get_own_jid().getStripped()
        log.info('Request archive count from: %s', jid)
        query_id = self._get_query_id(jid)
        query = self._get_archive_query(
            query_id, start=start_date, end=end_date, max_=0)
        self._con.connection.SendAndCallForResponse(
            query, self._received_count, {'query_id': query_id})
        return query_id

    def _received_count(self, conn, stanza, query_id):
        try:
            _, set_ = self._parse_iq(stanza)
        except InvalidMamIQ:
            return

        jid = self._get_from_jid(stanza)
        self._mam_query_ids.pop(jid)

        count = set_.getTagData('count')
        log.info('Received archive count: %s', count)
        app.nec.push_incoming_event(ArchivingCountReceived(
            None, query_id=query_id, count=count))

    def request_archive_on_signin(self):
        own_jid = self._con.get_own_jid().getStripped()

        if own_jid in self._mam_query_ids:
            log.warning('MAM request for %s already running', own_jid)
            return

        archive = app.logger.get_archive_timestamp(own_jid)

        # Migration of last_mam_id from config to DB
        if archive is not None:
            mam_id = archive.last_mam_id
        else:
            mam_id = app.config.get_per(
                'accounts', self._account, 'last_mam_id')
            if mam_id:
                app.config.del_per('accounts', self._account, 'last_mam_id')

        start_date = None
        query_id = self._get_query_id(own_jid)
        if mam_id:
            log.info('MAM query after: %s', mam_id)
            query = self._get_archive_query(query_id, after=mam_id)
        else:
            # First Start, we request the last week
            start_date = datetime.utcnow() - timedelta(days=7)
            log.info('First start: query archive start: %s', start_date)
            query = self._get_archive_query(query_id, start=start_date)
        self._send_archive_query(query, query_id, start_date)

    def request_archive_on_muc_join(self, jid):
        archive = app.logger.get_archive_timestamp(
            jid, type_=JIDConstant.ROOM_TYPE)
        query_id = self._get_query_id(jid)
        start_date = None
        if archive is not None:
            log.info('Request from archive %s after %s:',
                     jid, archive.last_mam_id)
            query = self._get_archive_query(
                query_id, jid=jid, after=archive.last_mam_id)
        else:
            # First Start, we dont request history
            # Depending on what a MUC saves, there could be thousands
            # of Messages even in just one day.
            start_date = datetime.utcnow() - timedelta(days=1)
            log.info('First join: query archive %s from: %s', jid, start_date)
            query = self._get_archive_query(query_id, jid=jid, start=start_date)
        self._send_archive_query(query, query_id, start_date, groupchat=True)

    def _send_archive_query(self, query, query_id, start_date=None,
                            groupchat=False):
        self._con.connection.SendAndCallForResponse(
            query, self._result_finished, {'query_id': query_id,
                                           'start_date': start_date,
                                           'groupchat': groupchat})

    def _result_finished(self, conn, stanza, query_id, start_date, groupchat):
        try:
            fin, set_ = self._parse_iq(stanza)
        except InvalidMamIQ:
            return

        jid = self._get_from_jid(stanza)

        last = set_.getTagData('last')
        if last is None:
            log.info('End of MAM query, no items retrieved')
            self._mam_query_ids.pop(jid)
            return

        complete = fin.getAttr('complete')
        app.logger.set_archive_timestamp(jid, last_mam_id=last)
        if complete != 'true':
            self._mam_query_ids.pop(jid)
            query_id = self._get_query_id(jid)
            query = self._get_archive_query(query_id, jid=jid, after=last)
            self._send_archive_query(query, query_id, groupchat=groupchat)
        else:
            self._mam_query_ids.pop(jid)
            if start_date is not None:
                app.logger.set_archive_timestamp(
                    jid,
                    last_mam_id=last,
                    oldest_mam_timestamp=start_date.timestamp())
            log.info('End of MAM query, last mam id: %s', last)

    def request_archive_interval(self, start_date, end_date, after=None,
                                 query_id=None):
        jid = self._con.get_own_jid().getStripped()
        if after is None:
            log.info('Request intervall from %s to %s from %s',
                     start_date, end_date, jid)
        else:
            log.info('Query page after %s from %s',
                     after, jid)
        if query_id is None:
            query_id = self._get_query_id(jid)
        self._mam_query_ids[jid] = query_id
        query = self._get_archive_query(query_id, start=start_date,
                                        end=end_date, after=after, max_=30)

        self._con.connection.SendAndCallForResponse(
            query, self._intervall_result, {'query_id': query_id,
                                            'start_date': start_date,
                                            'end_date': end_date})
        return query_id

    def _intervall_result(self, conn, stanza, query_id,
                          start_date, end_date):
        try:
            fin, set_ = self._parse_iq(stanza)
        except InvalidMamIQ:
            return

        jid = self._get_from_jid(stanza)
        self._mam_query_ids.pop(jid)
        if start_date:
            timestamp = start_date.timestamp()
        else:
            timestamp = ArchiveState.ALL

        last = set_.getTagData('last')
        if last is None:
            app.nec.push_incoming_event(ArchivingIntervalFinished(
                None, query_id=query_id))
            app.logger.set_archive_timestamp(
                jid, oldest_mam_timestamp=timestamp)
            log.info('End of MAM request, no items retrieved')
            return

        complete = fin.getAttr('complete')
        if complete != 'true':
            self.request_archive_interval(start_date, end_date, last, query_id)
        else:
            log.info('Request finished')
            app.logger.set_archive_timestamp(
                jid, oldest_mam_timestamp=timestamp)
            app.nec.push_incoming_event(ArchivingIntervalFinished(
                None, query_id=query_id))

    def _get_archive_query(self, query_id, jid=None, start=None, end=None,
                           with_=None, after=None, max_=30):
        # Muc archive query?
        namespace = muc_caps_cache.get_mam_namespace(jid)
        if namespace is None:
            # Query to our own archive
            namespace = self.archiving_namespace

        iq = nbxmpp.Iq('set', to=jid)
        query = iq.addChild('query', namespace=namespace)
        form = query.addChild(node=nbxmpp.DataForm(typ='submit'))
        field = nbxmpp.DataField(typ='hidden',
                                 name='FORM_TYPE',
                                 value=namespace)
        form.addChild(node=field)
        if start:
            field = nbxmpp.DataField(typ='text-single',
                                     name='start',
                                     value=start.strftime('%Y-%m-%dT%H:%M:%SZ'))
            form.addChild(node=field)
        if end:
            field = nbxmpp.DataField(typ='text-single',
                                     name='end',
                                     value=end.strftime('%Y-%m-%dT%H:%M:%SZ'))
            form.addChild(node=field)
        if with_:
            field = nbxmpp.DataField(typ='jid-single', name='with', value=with_)
            form.addChild(node=field)

        set_ = query.setTag('set', namespace=nbxmpp.NS_RSM)
        set_.setTagData('max', max_)
        if after:
            set_.setTagData('after', after)
        query.setAttr('queryid', query_id)
        return iq

    def request_mam_preferences(self):
        log.info('Request MAM preferences')
        iq = nbxmpp.Iq('get', self.archiving_namespace)
        iq.setQuery('prefs')
        self._con.connection.SendAndCallForResponse(
            iq, self._preferences_received)

    def _preferences_received(self, stanza):
        if not nbxmpp.isResultNode(stanza):
            log.info('Error: %s', stanza.getError())
            app.nec.push_incoming_event(MAMPreferenceError(
                None, conn=self._con, error=stanza.getError()))
            return

        log.info('Received MAM preferences')
        prefs = stanza.getTag('prefs', namespace=self.archiving_namespace)
        if prefs is None:
            log.error('Malformed stanza (no prefs node): %s', stanza)
            return

        rules = []
        default = prefs.getAttr('default')
        for item in prefs.getTag('always').getTags('jid'):
            rules.append((item.getData(), 'Always'))

        for item in prefs.getTag('never').getTags('jid'):
            rules.append((item.getData(), 'Never'))

        app.nec.push_incoming_event(MAMPreferenceReceived(
            None, conn=self._con, rules=rules, default=default))

    def set_mam_preferences(self, rules, default):
        iq = nbxmpp.Iq(typ='set')
        prefs = iq.addChild(name='prefs',
                            namespace=self.archiving_namespace,
                            attrs={'default': default})
        always = prefs.addChild(name='always')
        never = prefs.addChild(name='never')
        for item in rules:
            jid, archive = item
            if archive:
                always.addChild(name='jid').setData(jid)
            else:
                never.addChild(name='jid').setData(jid)

        self._con.connection.SendAndCallForResponse(
            iq, self._preferences_saved)

    def _preferences_saved(self, stanza):
        if not nbxmpp.isResultNode(stanza):
            log.info('Error: %s', stanza.getError())
            app.nec.push_incoming_event(MAMPreferenceError(
                None, conn=self._con, error=stanza.getError()))
        else:
            log.info('Preferences saved')
            app.nec.push_incoming_event(
                MAMPreferenceSaved(None, conn=self._con))


class MamMessageReceivedEvent(NetworkIncomingEvent):
    name = 'mam-message-received'


class MamGcMessageReceivedEvent(NetworkIncomingEvent):
    name = 'mam-message-received'


class MamDecryptedMessageReceived(NetworkIncomingEvent):
    name = 'mam-decrypted-message-received'


class MAMPreferenceError(NetworkIncomingEvent):
    name = 'mam-prefs-error'


class MAMPreferenceReceived(NetworkIncomingEvent):
    name = 'mam-prefs-received'


class MAMPreferenceSaved(NetworkIncomingEvent):
    name = 'mam-prefs-saved'


class ArchivingCountReceived(NetworkIncomingEvent):
    name = 'archiving-count-received'


class ArchivingIntervalFinished(NetworkIncomingEvent):
    name = 'archiving-interval-finished'


class ArchivingErrorReceived(NetworkIncomingEvent):
    name = 'archiving-error-received'


class InvalidMamIQ(Exception):
    pass


def get_instance(*args, **kwargs):
    return MAM(*args, **kwargs), 'MAM'
