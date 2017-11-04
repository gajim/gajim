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
import gajim.common.connection_handlers_events as ev

log = logging.getLogger('gajim.c.message_archiving')


class ConnectionArchive313:
    def __init__(self):
        self.archiving_313_supported = False
        self.mam_awaiting_disco_result = {}
        self.iq_answer = []
        self.mam_query_date = None
        self.mam_query_id = None
        app.nec.register_incoming_event(ev.MamMessageReceivedEvent)
        app.ged.register_event_handler('archiving-finished-legacy', ged.CORE,
            self._nec_result_finished)
        app.ged.register_event_handler('archiving-finished', ged.CORE,
            self._nec_result_finished)
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
        app.ged.remove_event_handler('archiving-finished-legacy', ged.CORE,
            self._nec_result_finished)
        app.ged.remove_event_handler('archiving-finished', ged.CORE,
            self._nec_result_finished)
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

    def _nec_result_finished(self, obj):
        if obj.conn.name != self.name:
            return

        if obj.query_id != self.mam_query_id:
            return

        set_ = obj.fin.getTag('set', namespace=nbxmpp.NS_RSM)
        if set_:
            last = set_.getTagData('last')
            complete = obj.fin.getAttr('complete')
            if last:
                app.config.set_per('accounts', self.name, 'last_mam_id', last)
                if complete != 'true':
                    self.request_archive(self.get_query_id(), after=last)
            if complete == 'true':
                self.mam_query_id = None
                if self.mam_query_date:
                    app.config.set_per(
                        'accounts', self.name,
                        'mam_start_date', self.mam_query_date.timestamp())
                    self.mam_query_date = None

    def _nec_mam_decrypted_message_received(self, obj):
        if obj.conn.name != self.name:
            return
        duplicate = app.logger.search_for_duplicate(
            obj.with_, obj.timestamp, obj.msgtxt)
        if not duplicate:
            app.logger.insert_into_logs(
                obj.with_, obj.timestamp, obj.kind,
                unread=False,
                message=obj.msgtxt,
                additional_data=obj.additional_data)

    def get_query_id(self):
        self.mam_query_id = self.connection.getAnID()
        return self.mam_query_id

    def request_archive_on_signin(self):
        mam_id = app.config.get_per('accounts', self.name, 'last_mam_id')
        query_id = self.get_query_id()
        if mam_id:
            self.request_archive(query_id, after=mam_id)
        else:
            # First Start, we request the last week
            self.mam_query_date = datetime.utcnow() - timedelta(days=7)
            log.info('First start: query archive start: %s', self.mam_query_date)
            self.request_archive(query_id, start=self.mam_query_date)

    def request_archive(self, query_id, start=None, end=None, with_=None,
                        after=None, max_=30):
        namespace = self.archiving_namespace
        iq = nbxmpp.Iq('set')
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
        id_ = self.connection.getAnID()
        iq.setID(id_)
        self.connection.send(iq)

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
