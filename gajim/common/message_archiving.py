# -*- coding:utf-8 -*-
## src/common/message_archiving.py
##
## Copyright (C) 2009 Anaël Verrier <elghinn AT free.fr>
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

import logging
from datetime import datetime, timedelta

import nbxmpp

from gajim.common import app
from gajim.common import ged
from gajim.common.logger import KindConstant, JIDConstant
from gajim.common.const import ArchiveState
import gajim.common.connection_handlers_events as ev

log = logging.getLogger('gajim.c.message_archiving')


class ConnectionArchive313:
    def __init__(self):
        self.archiving_313_supported = False
        self.mam_awaiting_disco_result = {}
        self.iq_answer = []
        self.mam_query_ids = []
        app.nec.register_incoming_event(ev.MamMessageReceivedEvent)
        app.nec.register_incoming_event(ev.MamGcMessageReceivedEvent)
        app.ged.register_event_handler('agent-info-error-received', ged.CORE,
            self._nec_agent_info_error)
        app.ged.register_event_handler('agent-info-received', ged.CORE,
            self._nec_agent_info)
        app.ged.register_event_handler('mam-decrypted-message-received',
            ged.CORE, self._nec_mam_decrypted_message_received)
        app.ged.register_event_handler(
            'archiving-313-preferences-changed-received', ged.CORE,
            self._nec_archiving_313_preferences_changed_received)

    def cleanup(self):
        app.ged.remove_event_handler('agent-info-error-received', ged.CORE,
            self._nec_agent_info_error)
        app.ged.remove_event_handler('agent-info-received', ged.CORE,
            self._nec_agent_info)
        app.ged.remove_event_handler('mam-decrypted-message-received',
            ged.CORE, self._nec_mam_decrypted_message_received)
        app.ged.remove_event_handler(
            'archiving-313-preferences-changed-received', ged.CORE,
            self._nec_archiving_313_preferences_changed_received)

    def _nec_archiving_313_preferences_changed_received(self, obj):
        if obj.id in self.iq_answer:
            obj.answer = True

    def _nec_agent_info_error(self, obj):
        if obj.jid in self.mam_awaiting_disco_result:
            log.warn('Unable to discover %s, ignoring those logs', obj.jid)
            del self.mam_awaiting_disco_result[obj.jid]

    def _nec_agent_info(self, obj):
        if obj.jid not in self.mam_awaiting_disco_result:
            return

        for identity in obj.identities:
            if identity['category'] != 'conference':
                continue
            # it's a groupchat
            for msg_obj in self.mam_awaiting_disco_result[obj.jid]:
                app.logger.insert_jid(msg_obj.with_.getStripped(),
                                        type_=JIDConstant.ROOM_TYPE)
                app.nec.push_incoming_event(
                    ev.MamDecryptedMessageReceivedEvent(
                        None, disco=True, **vars(msg_obj)))
            del self.mam_awaiting_disco_result[obj.jid]
            return
        # it's not a groupchat
        for msg_obj in self.mam_awaiting_disco_result[obj.jid]:
            app.logger.insert_jid(msg_obj.with_.getStripped())
            app.nec.push_incoming_event(
                ev.MamDecryptedMessageReceivedEvent(
                    None, disco=True, **vars(msg_obj)))
        del self.mam_awaiting_disco_result[obj.jid]

    @staticmethod
    def parse_iq(stanza, query_id):
        if not nbxmpp.isResultNode(stanza):
            log.error('Error on MAM query: %s', stanza.getError())
            raise InvalidMamIQ

        fin = stanza.getTag('fin')
        if fin is None:
            log.error('Malformed MAM query result received: %s', stanza)
            raise InvalidMamIQ

        if fin.getAttr('queryid') != query_id:
            log.error('Result with unknown query id received')
            raise InvalidMamIQ

        set_ = fin.getTag('set', namespace=nbxmpp.NS_RSM)
        if set_ is None:
            log.error(
                'Malformed MAM query result received (no "set" Node): %s',
                stanza)
            raise InvalidMamIQ
        return fin, set_

    def parse_from_jid(self, stanza):
        jid = stanza.getFrom()
        if jid is None:
            # No from means, iq from our own archive
            jid = self.get_own_jid().getStripped()
        else:
            jid = jid.getStripped()
        return jid

    def _result_finished(self, conn, stanza, query_id, start_date, groupchat):
        try:
            fin, set_ = self.parse_iq(stanza, query_id)
        except InvalidMamIQ:
            return

        last = set_.getTagData('last')
        if last is None:
            log.info('End of MAM query, no items retrieved')
            return

        jid = self.parse_from_jid(stanza)
        complete = fin.getAttr('complete')
        app.logger.set_archive_timestamp(jid, last_mam_id=last)
        if complete != 'true':
            self.mam_query_ids.remove(query_id)
            query_id = self.get_query_id()
            query = self.get_archive_query(query_id, jid=jid, after=last)
            self._send_archive_query(query, query_id, groupchat=groupchat)
        else:
            self.mam_query_ids.remove(query_id)
            if start_date is not None:
                app.logger.set_archive_timestamp(
                    jid,
                    last_mam_id=last,
                    oldest_mam_timestamp=start_date.timestamp())
            log.info('End of MAM query, last mam id: %s', last)

    def _intervall_result_finished(self, conn, stanza, query_id,
                                   start_date, end_date, event_id):
        try:
            fin, set_ = self.parse_iq(stanza, query_id)
        except InvalidMamIQ:
            return

        self.mam_query_ids.remove(query_id)
        jid = self.parse_from_jid(stanza)
        if start_date:
            timestamp = start_date.timestamp()
        else:
            timestamp = ArchiveState.ALL

        last = set_.getTagData('last')
        if last is None:
            app.nec.push_incoming_event(ev.ArchivingIntervalFinished(
                None, event_id=event_id))
            app.logger.set_archive_timestamp(
                jid, oldest_mam_timestamp=timestamp)
            log.info('End of MAM query, no items retrieved')
            return

        complete = fin.getAttr('complete')
        if complete != 'true':
            self.request_archive_interval(event_id, start_date, end_date, last)
        else:
            log.info('query finished')
            app.logger.set_archive_timestamp(
                jid, oldest_mam_timestamp=timestamp)
            app.nec.push_incoming_event(ev.ArchivingIntervalFinished(
                None, event_id=event_id, stanza=stanza))

    def _received_count(self, conn, stanza, query_id, event_id):
        try:
            _, set_ = self.parse_iq(stanza, query_id)
        except InvalidMamIQ:
            return

        self.mam_query_ids.remove(query_id)

        count = set_.getTagData('count')
        log.info('message count received: %s', count)
        app.nec.push_incoming_event(ev.ArchivingCountReceived(
            None, event_id=event_id, count=count))

    def _nec_mam_decrypted_message_received(self, obj):
        if obj.conn.name != self.name:
            return
        # if self.archiving_namespace != nbxmpp.NS_MAM_2:
        # Fallback duplicate search without stanza-id
        duplicate = app.logger.search_for_duplicate(
            obj.with_, obj.timestamp, obj.msgtxt)
        if duplicate:
            # dont propagate the event further
            return True
        app.logger.insert_into_logs(self.name,
                                    obj.with_,
                                    obj.timestamp,
                                    obj.kind,
                                    unread=False,
                                    message=obj.msgtxt,
                                    contact_name=obj.nick,
                                    additional_data=obj.additional_data,
                                    stanza_id=obj.unique_id)

    def get_query_id(self):
        query_id = self.connection.getAnID()
        self.mam_query_ids.append(query_id)
        return query_id

    def request_archive_on_signin(self):
        own_jid = self.get_own_jid().getStripped()
        archive = app.logger.get_archive_timestamp(own_jid)

        # Migration of last_mam_id from config to DB
        if archive is not None:
            mam_id = archive.last_mam_id
        else:
            mam_id = app.config.get_per('accounts', self.name, 'last_mam_id')

        start_date = None
        query_id = self.get_query_id()
        if mam_id:
            log.info('MAM query after: %s', mam_id)
            query = self.get_archive_query(query_id, after=mam_id)
        else:
            # First Start, we request the last week
            start_date = datetime.utcnow() - timedelta(days=7)
            log.info('First start: query archive start: %s', start_date)
            query = self.get_archive_query(query_id, start=start_date)
        self._send_archive_query(query, query_id, start_date)

    def request_archive_on_muc_join(self, jid):
        archive = app.logger.get_archive_timestamp(
            jid, type_=JIDConstant.ROOM_TYPE)
        query_id = self.get_query_id()
        start_date = None
        if archive is not None:
            log.info('Query Groupchat MAM Archive %s after %s:',
                     jid, archive.last_mam_id)
            query = self.get_archive_query(
                query_id, jid=jid, after=archive.last_mam_id)
        else:
            # First Start, we dont request history
            # Depending on what a MUC saves, there could be thousands
            # of Messages even in just one day.
            start_date = datetime.utcnow() - timedelta(days=1)
            log.info('First join: query archive %s from: %s', jid, start_date)
            query = self.get_archive_query(query_id, jid=jid, start=start_date)
        self._send_archive_query(query, query_id, start_date, groupchat=True)

    def request_archive_count(self, event_id, start_date, end_date):
        query_id = self.get_query_id()
        query = self.get_archive_query(
            query_id, start=start_date, end=end_date, max_=0)
        self.connection.SendAndCallForResponse(
            query, self._received_count, {'query_id': query_id,
                                          'event_id': event_id})

    def request_archive_interval(self, event_id, start_date,
                                 end_date, after=None):
        query_id = self.get_query_id()
        query = self.get_archive_query(query_id, start=start_date,
                                       end=end_date, after=after, max_=30)
        app.nec.push_incoming_event(ev.ArchivingQueryID(
            None, event_id=event_id, query_id=query_id))
        self.connection.SendAndCallForResponse(
            query, self._intervall_result_finished, {'query_id': query_id,
                                                     'start_date': start_date,
                                                     'end_date': end_date,
                                                     'event_id': event_id})

    def _send_archive_query(self, query, query_id, start_date=None,
                            groupchat=False):
        self.connection.SendAndCallForResponse(
            query, self._result_finished, {'query_id': query_id,
                                           'start_date': start_date,
                                           'groupchat': groupchat})

    def get_archive_query(self, query_id, jid=None, start=None, end=None, with_=None,
                          after=None, max_=30):
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

    def request_archive_preferences(self):
        if not app.account_is_connected(self.name):
            return
        iq = nbxmpp.Iq(typ='get')
        id_ = self.connection.getAnID()
        iq.setID(id_)
        iq.addChild(name='prefs', namespace=self.archiving_namespace)
        self.connection.send(iq)

    def set_archive_preferences(self, items, default):
        if not app.account_is_connected(self.name):
            return
        iq = nbxmpp.Iq(typ='set')
        id_ = self.connection.getAnID()
        self.iq_answer.append(id_)
        iq.setID(id_)
        prefs = iq.addChild(name='prefs', namespace=self.archiving_namespace, attrs={'default': default})
        always = prefs.addChild(name='always')
        never = prefs.addChild(name='never')
        for item in items:
            jid, preference = item
            if preference == 'always':
                always.addChild(name='jid').setData(jid)
            else:
                never.addChild(name='jid').setData(jid)
        self.connection.send(iq)

    def _ArchiveCB(self, con, iq_obj):
        app.nec.push_incoming_event(ev.ArchivingReceivedEvent(None, conn=self,
            stanza=iq_obj))
        raise nbxmpp.NodeProcessed


class InvalidMamIQ(Exception):
    pass
