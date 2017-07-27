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

import nbxmpp
from common import gajim
from common import ged
from common import helpers
import common.connection_handlers_events as ev

from calendar import timegm
from time import localtime
from datetime import datetime, timedelta

import logging
log = logging.getLogger('gajim.c.message_archiving')

ARCHIVING_COLLECTIONS_ARRIVED = 'archiving_collections_arrived'
ARCHIVING_COLLECTION_ARRIVED = 'archiving_collection_arrived'
ARCHIVING_MODIFICATIONS_ARRIVED = 'archiving_modifications_arrived'

class ConnectionArchive:
    def __init__(self):
        pass


class ConnectionArchive313(ConnectionArchive):
    def __init__(self):
        ConnectionArchive.__init__(self)
        self.archiving_313_supported = False
        self.mam_awaiting_disco_result = {}
        self.iq_answer = []
        self.mam_query_date = None
        self.mam_query_id = None
        gajim.nec.register_incoming_event(ev.MamMessageReceivedEvent)
        gajim.ged.register_event_handler('archiving-finished-legacy', ged.CORE,
            self._nec_result_finished)
        gajim.ged.register_event_handler('archiving-finished', ged.CORE,
            self._nec_result_finished)
        gajim.ged.register_event_handler('agent-info-error-received', ged.CORE,
            self._nec_agent_info_error)
        gajim.ged.register_event_handler('agent-info-received', ged.CORE,
            self._nec_agent_info)
        gajim.ged.register_event_handler('mam-decrypted-message-received',
            ged.CORE, self._nec_mam_decrypted_message_received)
        gajim.ged.register_event_handler(
            'archiving-313-preferences-changed-received', ged.CORE,
            self._nec_archiving_313_preferences_changed_received)

    def cleanup(self):
        gajim.ged.remove_event_handler('archiving-finished-legacy', ged.CORE,
            self._nec_result_finished)
        gajim.ged.remove_event_handler('archiving-finished', ged.CORE,
            self._nec_result_finished)
        gajim.ged.remove_event_handler('agent-info-error-received', ged.CORE,
            self._nec_agent_info_error)
        gajim.ged.remove_event_handler('agent-info-received', ged.CORE,
            self._nec_agent_info)
        gajim.ged.remove_event_handler('mam-decrypted-message-received',
            ged.CORE, self._nec_mam_decrypted_message_received)
        gajim.ged.remove_event_handler(
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
        if obj.jid in self.mam_awaiting_disco_result:
            for identity in obj.identities:
                if identity['category'] == 'conference':
                    # it's a groupchat
                    for with_, direction, tim, msg_txt in \
                    self.mam_awaiting_disco_result[obj.jid]:
                        gajim.logger.get_jid_id(with_, 'ROOM')
                        gajim.logger.save_if_not_exists(with_, direction, tim,
                            msg=msg_txt, is_pm=True)
                    del self.mam_awaiting_disco_result[obj.jid]
                    return
            # it's not a groupchat
            for with_, direction, tim, msg_txt in \
            self.mam_awaiting_disco_result[obj.jid]:
                gajim.logger.get_jid_id(with_)
                gajim.logger.save_if_not_exists(with_, direction, tim,
                    msg=msg_txt)
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
                gajim.config.set_per('accounts', self.name, 'last_mam_id', last)
                if complete != 'true':
                    self.request_archive(self.get_query_id(), after=last)
            if complete == 'true':
                self.mam_query_id = None
                if self.mam_query_date:
                    gajim.config.set_per(
                        'accounts', self.name,
                        'mam_start_date', self.mam_query_date.timestamp())
                    self.mam_query_date = None

    def _nec_mam_decrypted_message_received(self, obj):
        if obj.conn.name != self.name:
            return
        gajim.logger.save_if_not_exists(obj.with_, obj.direction, obj.timestamp,
            msg=obj.msgtxt, additional_data=obj.additional_data)

    def get_query_id(self):
        self.mam_query_id = self.connection.getAnID()
        return self.mam_query_id

    def request_archive_on_signin(self):
        mam_id = gajim.config.get_per('accounts', self.name, 'last_mam_id')
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
        if not gajim.account_is_connected(self.name):
            return
        iq = nbxmpp.Iq(typ='get')
        id_ = self.connection.getAnID()
        iq.setID(id_)
        iq.addChild(name='prefs', namespace=self.archiving_namespace)
        self.connection.send(iq)

    def set_archive_preferences(self, items, default):
        if not gajim.account_is_connected(self.name):
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

class ConnectionArchive136(ConnectionArchive):
    def __init__(self):
        ConnectionArchive.__init__(self)
        self.archiving_136_supported = False
        self.archive_auto_supported = False
        self.archive_manage_supported = False
        self.archive_manual_supported = False
        self.archive_pref_supported = False
        self.auto = None
        self.method_auto = None
        self.method_local = None
        self.method_manual = None
        self.default = None
        self.items = {}
        gajim.ged.register_event_handler(
            'archiving-preferences-changed-received', ged.CORE,
            self._nec_archiving_changed_received)
        gajim.ged.register_event_handler('raw-iq-received', ged.CORE,
            self._nec_raw_iq_136_received)

    def cleanup(self):
        gajim.ged.remove_event_handler(
            'archiving-preferences-changed-received', ged.CORE,
            self._nec_archiving_changed_received)
        gajim.ged.remove_event_handler('raw-iq-received', ged.CORE,
            self._nec_raw_iq_136_received)

    def _nec_raw_iq_136_received(self, obj):
        if obj.conn.name != self.name:
            return

        id_ = obj.stanza.getID()
        if id_ not in self.awaiting_answers:
            return

        if self.awaiting_answers[id_][0] == ARCHIVING_COLLECTIONS_ARRIVED:
            del self.awaiting_answers[id_]
            # TODO
            print('ARCHIVING_COLLECTIONS_ARRIVED')

        elif self.awaiting_answers[id_][0] == ARCHIVING_COLLECTION_ARRIVED:
            def save_if_not_exists(with_, nick, direction, tim, payload):
                assert len(payload) == 1, 'got several archiving messages in' +\
                    ' the same time %s' % ''.join(payload)
                if payload[0].getName() == 'body':
                    gajim.logger.save_if_not_exists(with_, direction, tim,
                        msg=payload[0].getData(), nick=nick)
                elif payload[0].getName() == 'message':
                    print('Not implemented')
            chat = obj.stanza.getTag('chat')
            if chat:
                with_ = chat.getAttr('with')
                start_ = chat.getAttr('start')
                tim = helpers.datetime_tuple(start_)
                tim = timegm(tim)
                nb = 0
                for element in chat.getChildren():
                    try:
                        secs = int(element.getAttr('secs'))
                    except TypeError:
                        secs = 0
                    if secs:
                        tim += secs
                    nick = element.getAttr('name')
                    if element.getName() == 'from':
                        save_if_not_exists(with_, nick, 'from', localtime(tim),
                            element.getPayload())
                        nb += 1
                    if element.getName() == 'to':
                        save_if_not_exists(with_, nick, 'to', localtime(tim),
                            element.getPayload())
                        nb += 1
                set_ = chat.getTag('set')
                first = set_.getTag('first')
                if first:
                    try:
                        index = int(first.getAttr('index'))
                    except TypeError:
                        index = 0
                try:
                    count = int(set_.getTagData('count'))
                except TypeError:
                    count = 0
                if count > index + nb:
                    # Request the next page
                    after = element.getTagData('last')
                    self.request_collection_page(with_, start_, after=after)
            del self.awaiting_answers[id_]

        elif self.awaiting_answers[id_][0] == ARCHIVING_MODIFICATIONS_ARRIVED:
            modified = obj.stanza.getTag('modified')
            if modified:
                for element in modified.getChildren():
                    if element.getName() == 'changed':
                        with_ = element.getAttr('with')
                        start_ = element.getAttr('start')
                        self.request_collection_page(with_, start_)
                    #elif element.getName() == 'removed':
                        # do nothing
            del self.awaiting_answers[id_]

    def request_message_archiving_preferences(self):
        iq_ = nbxmpp.Iq('get')
        iq_.setTag('pref', namespace=nbxmpp.NS_ARCHIVE)
        self.connection.send(iq_)

    def set_pref(self, name, **data):
        '''
        data contains names and values of pref name attributes.
        '''
        iq_ = nbxmpp.Iq('set')
        pref = iq_.setTag('pref', namespace=nbxmpp.NS_ARCHIVE)
        tag = pref.setTag(name)
        for key, value in data.items():
            if value is not None:
                tag.setAttr(key, value)
        self.connection.send(iq_)

    def set_auto(self, save):
        self.set_pref('auto', save=save)

    def set_method(self, type, use):
        self.set_pref('method', type=type, use=use)

    def set_default(self, otr, save, expire=None):
        self.set_pref('default', otr=otr, save=save, expire=expire)

    def append_or_update_item(self, jid, otr, save, expire):
        self.set_pref('item', jid=jid, otr=otr, save=save)

    def remove_item(self, jid):
        iq_ = nbxmpp.Iq('set')
        itemremove = iq_.setTag('itemremove', namespace=nbxmpp.NS_ARCHIVE)
        item = itemremove.setTag('item')
        item.setAttr('jid', jid)
        self.connection.send(iq_)

    def stop_archiving_session(self, thread_id):
        iq_ = nbxmpp.Iq('set')
        pref = iq_.setTag('pref', namespace=nbxmpp.NS_ARCHIVE)
        session = pref.setTag('session', attrs={'thread': thread_id,
            'save': 'false', 'otr': 'concede'})
        self.connection.send(iq_)

    def get_item_pref(self, jid):
        jid = nbxmpp.JID(jid)
        if str(jid) in self.items:
            return self.items[jid]

        if jid.getStripped() in self.items:
            return self.items[jid.getStripped()]

        if jid.getDomain() in self.items:
            return self.items[jid.getDomain()]

        return self.default

    def logging_preference(self, jid, initiator_options=None):
        otr = self.get_item_pref(jid)
        if not otr:
            return
        otr = otr['otr']
        if initiator_options:
            if ((initiator_options == ['mustnot'] and otr == 'forbid') or
            (initiator_options == ['may'] and otr == 'require')):
                return None

            if (initiator_options == ['mustnot'] or
            (initiator_options[0] == 'mustnot' and
            otr not in ('opppose', 'forbid')) or
            (initiator_options == ['may', 'mustnot'] and
            otr in ('require', 'prefer'))):
                return 'mustnot'

            return 'may'

        if otr == 'require':
            return ['mustnot']

        if otr in ('prefer', 'approve'):
            return ['mustnot', 'may']

        if otr in ('concede', 'oppose'):
            return ['may', 'mustnot']

        # otr == 'forbid'
        return ['may']

    def _ArchiveCB(self, con, iq_obj):
        gajim.nec.push_incoming_event(ev.ArchivingReceivedEvent(None, conn=self,
            stanza=iq_obj))
        raise nbxmpp.NodeProcessed

    def _nec_archiving_changed_received(self, obj):
        if obj.conn.name != self.name:
            return
        for key in ('auto', 'default'):
            if key not in obj.conf:
                self.archiving_136_supported = False
                self.archive_auto_supported = False
                self.archive_manage_supported = False
                self.archive_manual_supported = False
                self.archive_pref_supported = False
                return True
        for key in ('auto', 'method_auto', 'method_local', 'method_manual',
        'default'):
            if key in obj.conf:
                self.__dict__[key] = obj.conf[key]

        for jid, pref in obj.new_items.items():
            self.items[jid] = pref

        for jid in obj.removed_items:
            del self.items[jid]

    def request_collections_list_page(self, with_='', start=None, end=None,
    after=None, max=30, exact_match=False):
        iq_ = nbxmpp.Iq('get')
        list_ = iq_.setTag('list', namespace=nbxmpp.NS_ARCHIVE)
        if with_:
            list_.setAttr('with', with_)
            if exact_match:
                list_.setAttr('exactmatch', 'true')
        if start:
            list_.setAttr('start', start)
        if end:
            list_.setAttr('end', end)
        set_ = list_.setTag('set', namespace=nbxmpp.NS_RSM)
        set_.setTagData('max', max)
        if after:
            set_.setTagData('after', after)
        id_ = self.connection.getAnID()
        iq_.setID(id_)
        self.awaiting_answers[id_] = (ARCHIVING_COLLECTIONS_ARRIVED, )
        self.connection.send(iq_)

    def request_collection_page(self, with_, start, end=None, after=None,
    max=30, exact_match=False):
        iq_ = nbxmpp.Iq('get')
        retrieve = iq_.setTag('retrieve', namespace=nbxmpp.NS_ARCHIVE,
                attrs={'with': with_, 'start': start})
        if exact_match:
            retrieve.setAttr('exactmatch', 'true')
        set_ = retrieve.setTag('set', namespace=nbxmpp.NS_RSM)
        set_.setTagData('max', max)
        if after:
            set_.setTagData('after', after)
        id_ = self.connection.getAnID()
        iq_.setID(id_)
        self.awaiting_answers[id_] = (ARCHIVING_COLLECTION_ARRIVED, )
        self.connection.send(iq_)

    def remove_collection(self, with_='', start=None, end=None,
    exact_match=False, open=False):
        iq_ = nbxmpp.Iq('set')
        remove = iq_.setTag('remove', namespace=nbxmpp.NS_ARCHIVE)
        if with_:
            remove.setAttr('with', with_)
            if exact_match:
                remove.setAttr('exactmatch', 'true')
        if start:
            remove.setAttr('start', start)
        if end:
            remove.setAttr('end', end)
        if open:
            remove.setAttr('open', 'true')
        self.connection.send(iq_)

    def request_modifications_page(self, start, max=30):
        iq_ = nbxmpp.Iq('get')
        moified = iq_.setTag('modified', namespace=nbxmpp.NS_ARCHIVE,
                attrs={'start': start})
        set_ = moified.setTag('set', namespace=nbxmpp.NS_RSM)
        set_.setTagData('max', max)
        id_ = self.connection.getAnID()
        iq_.setID(id_)
        self.awaiting_answers[id_] = (ARCHIVING_MODIFICATIONS_ARRIVED, )
        self.connection.send(iq_)
