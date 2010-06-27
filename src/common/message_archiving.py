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

import common.xmpp

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

    def request_message_archiving_preferences(self):
        iq_ = common.xmpp.Iq('get')
        iq_.setTag('pref', namespace=common.xmpp.NS_ARCHIVE)
        self.connection.send(iq_)

    def set_pref(self, name, **data):
        '''
        data contains names and values of pref name attributes.
        '''
        iq_ = common.xmpp.Iq('set')
        pref = iq_.setTag('pref', namespace=common.xmpp.NS_ARCHIVE)
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
        iq_ = common.xmpp.Iq('set')
        itemremove = iq_.setTag('itemremove', namespace=common.xmpp.NS_ARCHIVE)
        item = itemremove.setTag('item')
        item.setAttr('jid', jid)
        self.connection.send(iq_)

    def get_item_pref(self, jid):
        jid = common.xmpp.JID(jid)
        if unicode(jid) in self.items:
            return self.items[jid]

        if jid.getStripped() in self.items:
            return self.items[jid.getStripped()]

        if jid.getDomain() in self.items:
            return self.items[jid.getDomain()]

        return self.default

    def logging_preference(self, jid, initiator_options=None):
        otr = self.get_item_pref(jid)['otr']
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
        if iq_obj.getType() == 'error':
            self.dispatch('ARCHIVING_ERROR', iq_obj.getErrorMsg())
            return
        elif iq_obj.getType() not in ('result', 'set'):
            return

        if iq_obj.getTag('pref'):
            pref = iq_obj.getTag('pref')

            if pref.getTag('auto'):
                self.auto = pref.getTagAttr('auto', 'save')
                log.debug('archiving preference: auto: %s' % self.auto)
                self.dispatch('ARCHIVING_CHANGED', ('auto',
                        self.auto))

            method_auto = pref.getTag('method', attrs={'type': 'auto'})
            if method_auto:
                self.method_auto = method_auto.getAttr('use')
                self.dispatch('ARCHIVING_CHANGED', ('method_auto',
                        self.method_auto))

            method_local = pref.getTag('method', attrs={'type': 'local'})
            if method_local:
                self.method_local = method_local.getAttr('use')
                self.dispatch('ARCHIVING_CHANGED', ('method_local',
                        self.method_local))

            method_manual = pref.getTag('method', attrs={'type': 'manual'})
            if method_manual:
                self.method_manual = method_manual.getAttr('use')
                self.dispatch('ARCHIVING_CHANGED', ('method_manual',
                        self.method_manual))

            log.debug('archiving preferences: method auto: %s, local: %s, '
                    'manual: %s' % (self.method_auto, self.method_local,
                    self.method_manual))

            if pref.getTag('default'):
                default = pref.getTag('default')
                log.debug('archiving preferences: default otr: %s, save: %s, '
                        'expire: %s, unset: %s' % (default.getAttr('otr'),
                        default.getAttr('save'), default.getAttr('expire'),
                        default.getAttr('unset')))
                self.default = {
                        'expire': default.getAttr('expire'),
                        'otr': default.getAttr('otr'),
                        'save': default.getAttr('save'),
                        'unset': default.getAttr('unset')}
                self.dispatch('ARCHIVING_CHANGED', ('default',
                        self.default))
            for item in pref.getTags('item'):
                log.debug('archiving preferences for jid %s: otr: %s, save: %s, '
                        'expire: %s' % (item.getAttr('jid'), item.getAttr('otr'),
                        item.getAttr('save'), item.getAttr('expire')))
                self.items[item.getAttr('jid')] = {
                        'expire': item.getAttr('expire'),
                        'otr': item.getAttr('otr'), 'save': item.getAttr('save')}
                self.dispatch('ARCHIVING_CHANGED', ('item',
                        item.getAttr('jid'), self.items[item.getAttr('jid')]))
        elif iq_obj.getTag('itemremove'):
            for item in pref.getTags('item'):
                del self.items[item.getAttr('jid')]
                self.dispatch('ARCHIVING_CHANGED', ('itemremove',
                        item.getAttr('jid')))

        raise common.xmpp.NodeProcessed

    def request_collections_list_page(self, with_='', start=None, end=None,
    after=None, max=30, exact_match=False):
        iq_ = common.xmpp.Iq('get')
        list_ = iq_.setTag('list', namespace=common.xmpp.NS_ARCHIVE)
        if with_:
            list_.setAttr('with', with_)
            if exact_match:
                list_.setAttr('exactmatch', 'true')
        if start:
            list_.setAttr('start', start)
        if end:
            list_.setAttr('end', end)
        set_ = list_.setTag('set', namespace=common.xmpp.NS_RSM)
        set_.setTagData('max', max)
        if after:
            set_.setTagData('after', after)
        id_ = self.connection.getAnID()
        iq_.setID(id_)
        self.awaiting_answers[id_] = (ARCHIVING_COLLECTIONS_ARRIVED, )
        self.connection.send(iq_)

    def request_collection_page(self, with_, start, end=None, after=None,
    max=30, exact_match=False):
        iq_ = common.xmpp.Iq('get')
        retrieve = iq_.setTag('retrieve', namespace=common.xmpp.NS_ARCHIVE,
                attrs={'with': with_, 'start': start})
        if exact_match:
            retrieve.setAttr('exactmatch', 'true')
        set_ = retrieve.setTag('set', namespace=common.xmpp.NS_RSM)
        set_.setTagData('max', max)
        if after:
            set_.setTagData('after', after)
        id_ = self.connection.getAnID()
        iq_.setID(id_)
        self.awaiting_answers[id_] = (ARCHIVING_COLLECTION_ARRIVED, )
        self.connection.send(iq_)

    def remove_collection(self, with_='', start=None, end=None,
    exact_match=False, open=False):
        iq_ = common.xmpp.Iq('set')
        remove = iq_.setTag('remove', namespace=common.xmpp.NS_ARCHIVE)
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
        iq_ = common.xmpp.Iq('get')
        moified = iq_.setTag('modified', namespace=common.xmpp.NS_ARCHIVE,
                attrs={'start': start})
        set_ = moified.setTag('set', namespace=common.xmpp.NS_RSM)
        set_.setTagData('max', max)
        id_ = self.connection.getAnID()
        iq_.setID(id_)
        self.awaiting_answers[id_] = (ARCHIVING_MODIFICATIONS_ARRIVED, )
        self.connection.send(iq_)
