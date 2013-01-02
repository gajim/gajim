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
from common.connection_handlers_events import ArchivingReceivedEvent

import logging
log = logging.getLogger('gajim.c.message_archiving')

ARCHIVING_COLLECTIONS_ARRIVED = 'archiving_collections_arrived'
ARCHIVING_COLLECTION_ARRIVED = 'archiving_collection_arrived'
ARCHIVING_MODIFICATIONS_ARRIVED = 'archiving_modifications_arrived'

class ConnectionArchive:
    def __init__(self):
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

    def cleanup(self):
        gajim.ged.remove_event_handler(
            'archiving-preferences-changed-received', ged.CORE,
            self._nec_archiving_changed_received)

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
        log.debug('_ArchiveCB %s' % iq_obj.getType())
        gajim.nec.push_incoming_event(ArchivingReceivedEvent(None, conn=self,
            stanza=iq_obj))
        raise nbxmpp.NodeProcessed

    def _nec_archiving_changed_received(self, obj):
        if obj.conn.name != self.name:
            return
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
