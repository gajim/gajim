# -*- coding:utf-8 -*-
## src/common/connection_handlers.py
##
## Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
##                    Junglecow J <junglecow AT gmail.com>
## Copyright (C) 2006-2007 Tomasz Melcer <liori AT exroot.org>
##                         Travis Shirk <travis AT pobox.com>
##                         Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2007 Julien Pivotto <roidelapluie AT gmail.com>
## Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
##                         Jean-Marie Traissard <jim AT lapin.org>
##                         Stephan Erb <steve-e AT h3c.de>
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

import os
import base64
import operator
import hashlib

from time import (altzone, daylight, gmtime, localtime, strftime,
        time as time_time, timezone, tzname)

from gi.repository import GLib

import nbxmpp
from gajim.common import caps_cache as capscache

from gajim.common.pep import LOCATION_DATA
from gajim.common import helpers
from gajim.common import app
from gajim.common import exceptions
from gajim.common import dataforms
from gajim.common import jingle_xtls
from gajim.common import sleepy
from gajim.common.commands import ConnectionCommands
from gajim.common.pubsub import ConnectionPubSub
from gajim.common.protocol.caps import ConnectionCaps
from gajim.common.protocol.bytestream import ConnectionSocks5Bytestream
from gajim.common.protocol.bytestream import ConnectionIBBytestream
from gajim.common.message_archiving import ConnectionArchive313
from gajim.common.connection_handlers_events import *

from gajim.common import ged
from gajim.common import nec
from gajim.common.nec import NetworkEvent

from gajim.common.jingle import ConnectionJingle

import logging
log = logging.getLogger('gajim.c.connection_handlers')

# kind of events we can wait for an answer
VCARD_PUBLISHED = 'vcard_published'
VCARD_ARRIVED = 'vcard_arrived'
AGENT_REMOVED = 'agent_removed'
METACONTACTS_ARRIVED = 'metacontacts_arrived'
ROSTER_ARRIVED = 'roster_arrived'
DELIMITER_ARRIVED = 'delimiter_arrived'
PRIVACY_ARRIVED = 'privacy_arrived'
BLOCKING_ARRIVED = 'blocking_arrived'
PEP_CONFIG = 'pep_config'


class ConnectionDisco:
    """
    Holds xmpppy handlers and public methods for discover services
    """

    def discoverItems(self, jid, node=None, id_prefix=None):
        """
        According to XEP-0030:
            jid is mandatory;
            name, node, action is optional.
        """
        id_ = self._discover(nbxmpp.NS_DISCO_ITEMS, jid, node, id_prefix)
        self.disco_items_ids.append(id_)

    def discoverInfo(self, jid, node=None, id_prefix=None):
        """
        According to XEP-0030:
            For identity: category, type is mandatory, name is optional.
            For feature: var is mandatory.
        """
        id_ = self._discover(nbxmpp.NS_DISCO_INFO, jid, node, id_prefix)
        self.disco_info_ids.append(id_)

    def request_register_agent_info(self, agent):
        if not self.connection or self.connected < 2:
            return None
        iq = nbxmpp.Iq('get', nbxmpp.NS_REGISTER, to=agent)
        id_ = self.connection.getAnID()
        iq.setID(id_)
        # Wait the answer during 30 secondes
        self.awaiting_timeouts[app.idlequeue.current_time() + 30] = (id_,
            _('Registration information for transport %s has not arrived in '
            'time') % agent)
        self.connection.SendAndCallForResponse(iq, self._ReceivedRegInfo,
            {'agent': agent})

    def _agent_registered_cb(self, con, resp, agent):
        if resp.getType() == 'result':
            app.nec.push_incoming_event(InformationEvent(None, conn=self,
                level='info', pri_txt=_('Registration succeeded'), sec_txt=_(
                'Registration with agent %s succeeded') % agent))
            self.request_subscription(agent, auto_auth=True)
            self.agent_registrations[agent]['roster_push'] = True
            if self.agent_registrations[agent]['sub_received']:
                p = nbxmpp.Presence(agent, 'subscribed')
                p = self.add_sha(p)
                self.connection.send(p)
        if resp.getType() == 'error':
            app.nec.push_incoming_event(InformationEvent(None, conn=self,
                level='error', pri_txt=_('Registration failed'), sec_txt=_(
                'Registration with agent %(agent)s failed with error %(error)s:'
                ' %(error_msg)s') % {'agent': agent, 'error': resp.getError(),
                'error_msg': resp.getErrorMsg()}))

    def register_agent(self, agent, info, is_form=False):
        if not self.connection or self.connected < 2:
            return
        if is_form:
            iq = nbxmpp.Iq('set', nbxmpp.NS_REGISTER, to=agent)
            query = iq.setQuery()
            info.setAttr('type', 'submit')
            query.addChild(node=info)
            self.connection.SendAndCallForResponse(iq,
                self._agent_registered_cb, {'agent': agent})
        else:
            # fixed: blocking
            nbxmpp.features_nb.register(self.connection, agent, info,
                self._agent_registered_cb, {'agent': agent})
        self.agent_registrations[agent] = {'roster_push': False,
            'sub_received': False}

    def _discover(self, ns, jid, node=None, id_prefix=None):
        if not self.connection or self.connected < 2:
            return
        iq = nbxmpp.Iq(typ='get', to=jid, queryNS=ns)
        id_ = self.connection.getAnID()
        if id_prefix:
            id_ = id_prefix + id_
        iq.setID(id_)
        if node:
            iq.setQuerynode(node)
        self.connection.send(iq)
        return id_

    def _ReceivedRegInfo(self, con, resp, agent):
        nbxmpp.features_nb._ReceivedRegInfo(con, resp, agent)
        self._IqCB(con, resp)

    def _discoGetCB(self, con, iq_obj):
        """
        Get disco info
        """
        if not self.connection or self.connected < 2:
            return
        frm = helpers.get_full_jid_from_iq(iq_obj)
        to = iq_obj.getAttr('to')
        id_ = iq_obj.getAttr('id')
        iq = nbxmpp.Iq(to=frm, typ='result', queryNS=nbxmpp.NS_DISCO, frm=to)
        iq.setAttr('id', id_)
        query = iq.setTag('query')
        query.setAttr('node', 'http://gajim.org#' + app.version.split('-', 1)[
            0])
        for f in (nbxmpp.NS_BYTESTREAM, nbxmpp.NS_SI, nbxmpp.NS_FILE,
        nbxmpp.NS_COMMANDS, nbxmpp.NS_JINGLE_FILE_TRANSFER_5,
        nbxmpp.NS_JINGLE_XTLS, nbxmpp.NS_PUBKEY_PUBKEY, nbxmpp.NS_PUBKEY_REVOKE,
        nbxmpp.NS_PUBKEY_ATTEST):
            feature = nbxmpp.Node('feature')
            feature.setAttr('var', f)
            query.addChild(node=feature)

        self.connection.send(iq)
        raise nbxmpp.NodeProcessed

    def _DiscoverItemsErrorCB(self, con, iq_obj):
        log.debug('DiscoverItemsErrorCB')
        app.nec.push_incoming_event(AgentItemsErrorReceivedEvent(None,
            conn=self, stanza=iq_obj))

    def _DiscoverItemsCB(self, con, iq_obj):
        log.debug('DiscoverItemsCB')
        app.nec.push_incoming_event(AgentItemsReceivedEvent(None, conn=self,
            stanza=iq_obj))

    def _DiscoverItemsGetCB(self, con, iq_obj):
        log.debug('DiscoverItemsGetCB')

        if not self.connection or self.connected < 2:
            return

        if self.commandItemsQuery(con, iq_obj):
            raise nbxmpp.NodeProcessed
        node = iq_obj.getTagAttr('query', 'node')
        if node is None:
            result = iq_obj.buildReply('result')
            self.connection.send(result)
            raise nbxmpp.NodeProcessed
        if node == nbxmpp.NS_COMMANDS:
            self.commandListQuery(con, iq_obj)
            raise nbxmpp.NodeProcessed

    def _DiscoverInfoGetCB(self, con, iq_obj):
        log.debug('DiscoverInfoGetCB')
        if not self.connection or self.connected < 2:
            return
        node = iq_obj.getQuerynode()

        if self.commandInfoQuery(con, iq_obj):
            raise nbxmpp.NodeProcessed

        id_ = iq_obj.getAttr('id')
        if id_[:6] == 'Gajim_':
            # We get this request from echo.server
            raise nbxmpp.NodeProcessed

        iq = iq_obj.buildReply('result')
        q = iq.setQuery()
        if node:
            q.setAttr('node', node)
        q.addChild('identity', attrs=app.gajim_identity)
        client_version = 'http://gajim.org#' + app.caps_hash[self.name]

        if node in (None, client_version):
            for f in app.gajim_common_features:
                q.addChild('feature', attrs={'var': f})
            for f in app.gajim_optional_features[self.name]:
                q.addChild('feature', attrs={'var': f})

        if q.getChildren():
            self.connection.send(iq)
            raise nbxmpp.NodeProcessed

    def _DiscoverInfoErrorCB(self, con, iq_obj):
        log.debug('DiscoverInfoErrorCB')
        app.nec.push_incoming_event(AgentInfoErrorReceivedEvent(None,
            conn=self, stanza=iq_obj))

    def _DiscoverInfoCB(self, con, iq_obj):
        log.debug('DiscoverInfoCB')
        if not self.connection or self.connected < 2:
            return
        app.nec.push_incoming_event(AgentInfoReceivedEvent(None, conn=self,
            stanza=iq_obj))

class ConnectionVcard:
    def __init__(self):
        self.vcard_sha = None
        self.vcard_shas = {} # sha of contacts
        # list of gc jids so that vcard are saved in a folder
        self.room_jids = []

    def add_sha(self, p, send_caps=True):
        c = p.setTag('x', namespace=nbxmpp.NS_VCARD_UPDATE)
        if self.vcard_sha is not None:
            c.setTagData('photo', self.vcard_sha)
        if send_caps:
            return self._add_caps(p)
        return p

    def _add_caps(self, p):
        ''' advertise our capabilities in presence stanza (xep-0115)'''
        c = p.setTag('c', namespace=nbxmpp.NS_CAPS)
        c.setAttr('hash', 'sha-1')
        c.setAttr('node', 'http://gajim.org')
        c.setAttr('ver', app.caps_hash[self.name])
        return p

    def _node_to_dict(self, node):
        dict_ = {}
        for info in node.getChildren():
            name = info.getName()
            if name in ('ADR', 'TEL', 'EMAIL'): # we can have several
                dict_.setdefault(name, [])
                entry = {}
                for c in info.getChildren():
                    entry[c.getName()] = c.getData()
                dict_[name].append(entry)
            elif info.getChildren() == []:
                dict_[name] = info.getData()
            else:
                dict_[name] = {}
                for c in info.getChildren():
                    dict_[name][c.getName()] = c.getData()
        return dict_

    def _save_vcard_to_hd(self, full_jid, card):
        jid, nick = app.get_room_and_nick_from_fjid(full_jid)
        puny_jid = helpers.sanitize_filename(jid)
        path = os.path.join(app.VCARD_PATH, puny_jid)
        if jid in self.room_jids or os.path.isdir(path):
            if not nick:
                return
            # remove room_jid file if needed
            if os.path.isfile(path):
                os.remove(path)
            # create folder if needed
            if not os.path.isdir(path):
                os.mkdir(path, 0o700)
            puny_nick = helpers.sanitize_filename(nick)
            path_to_file = os.path.join(app.VCARD_PATH, puny_jid, puny_nick)
        else:
            path_to_file = path
        try:
            fil = open(path_to_file, 'w', encoding='utf-8')
            fil.write(str(card))
            fil.close()
        except IOError as e:
            app.nec.push_incoming_event(InformationEvent(None, conn=self,
                level='error', pri_txt=_('Disk Write Error'), sec_txt=str(e)))

    def get_cached_vcard(self, fjid, is_fake_jid=False):
        """
        Return the vcard as a dict.
        Return {} if vcard was too old.
        Return None if we don't have cached vcard.
        """
        jid, nick = app.get_room_and_nick_from_fjid(fjid)
        puny_jid = helpers.sanitize_filename(jid)
        if is_fake_jid:
            puny_nick = helpers.sanitize_filename(nick)
            path_to_file = os.path.join(app.VCARD_PATH, puny_jid, puny_nick)
        else:
            path_to_file = os.path.join(app.VCARD_PATH, puny_jid)
        if not os.path.isfile(path_to_file):
            return None
        # We have the vcard cached
        f = open(path_to_file, encoding='utf-8')
        c = f.read()
        f.close()
        try:
            card = nbxmpp.Node(node=c)
        except Exception:
            # We are unable to parse it. Remove it
            os.remove(path_to_file)
            return None
        vcard = self._node_to_dict(card)
        if 'PHOTO' in vcard:
            if not isinstance(vcard['PHOTO'], dict):
                del vcard['PHOTO']
            elif 'SHA' in vcard['PHOTO']:
                cached_sha = vcard['PHOTO']['SHA']
                if jid in self.vcard_shas and self.vcard_shas[jid] != \
                cached_sha:
                    # user change his vcard so don't use the cached one
                    return {}
        vcard['jid'] = jid
        vcard['resource'] = app.get_resource_from_jid(fjid)
        return vcard

    def request_vcard(self, jid=None, groupchat_jid=None):
        """
        Request the VCARD

        If groupchat_jid is not null, it means we request a vcard to a fake jid,
        like in private messages in groupchat. jid can be the real jid of the
        contact, but we want to consider it comes from a fake jid
        """
        if not self.connection or self.connected < 2:
            return
        iq = nbxmpp.Iq(typ='get')
        if jid:
            iq.setTo(jid)
        iq.setQuery('vCard').setNamespace(nbxmpp.NS_VCARD)

        id_ = self.connection.getAnID()
        iq.setID(id_)
        j = jid
        if not j:
            j = app.get_jid_from_account(self.name)
        self.awaiting_answers[id_] = (VCARD_ARRIVED, j, groupchat_jid)
        if groupchat_jid:
            room_jid = app.get_room_and_nick_from_fjid(groupchat_jid)[0]
            if not room_jid in self.room_jids:
                self.room_jids.append(room_jid)
            self.groupchat_jids[id_] = groupchat_jid
        self.connection.send(iq)

    def send_vcard(self, vcard):
        if not self.connection or self.connected < 2:
            return
        iq = nbxmpp.Iq(typ='set')
        iq2 = iq.setTag(nbxmpp.NS_VCARD + ' vCard')
        for i in vcard:
            if i == 'jid':
                continue
            if isinstance(vcard[i], dict):
                iq3 = iq2.addChild(i)
                for j in vcard[i]:
                    iq3.addChild(j).setData(vcard[i][j])
            elif isinstance(vcard[i], list):
                for j in vcard[i]:
                    iq3 = iq2.addChild(i)
                    for k in j:
                        iq3.addChild(k).setData(j[k])
            else:
                iq2.addChild(i).setData(vcard[i])

        id_ = self.connection.getAnID()
        iq.setID(id_)
        self.connection.send(iq)

        our_jid = app.get_jid_from_account(self.name)
        # Add the sha of the avatar
        if 'PHOTO' in vcard and isinstance(vcard['PHOTO'], dict) and \
        'BINVAL' in vcard['PHOTO']:
            photo = vcard['PHOTO']['BINVAL']
            photo_decoded = base64.b64decode(photo.encode('utf-8'))
            app.interface.save_avatar_files(our_jid, photo_decoded)
            avatar_sha = hashlib.sha1(photo_decoded).hexdigest()
            iq2.getTag('PHOTO').setTagData('SHA', avatar_sha)
        else:
            app.interface.remove_avatar_files(our_jid)

        self.awaiting_answers[id_] = (VCARD_PUBLISHED, iq2)

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

        if self.awaiting_answers[id_][0] == VCARD_PUBLISHED:
            if iq_obj.getType() == 'result':
                vcard_iq = self.awaiting_answers[id_][1]
                # Save vcard to HD
                if vcard_iq.getTag('PHOTO') and vcard_iq.getTag('PHOTO').getTag(
                'SHA'):
                    new_sha = vcard_iq.getTag('PHOTO').getTagData('SHA')
                else:
                    new_sha = ''

                # Save it to file
                our_jid = app.get_jid_from_account(self.name)
                self._save_vcard_to_hd(our_jid, vcard_iq)

                # Send new presence if sha changed and we are not invisible
                if self.vcard_sha != new_sha and app.SHOW_LIST[
                self.connected] != 'invisible':
                    if not self.connection or self.connected < 2:
                        del self.awaiting_answers[id_]
                        return
                    self.vcard_sha = new_sha
                    sshow = helpers.get_xmpp_show(app.SHOW_LIST[
                        self.connected])
                    p = nbxmpp.Presence(typ=None, priority=self.priority,
                        show=sshow, status=self.status)
                    p = self.add_sha(p)
                    self.connection.send(p)
                app.nec.push_incoming_event(VcardPublishedEvent(None,
                    conn=self))
            elif iq_obj.getType() == 'error':
                app.nec.push_incoming_event(VcardNotPublishedEvent(None,
                    conn=self))
            del self.awaiting_answers[id_]
        elif self.awaiting_answers[id_][0] == VCARD_ARRIVED:
            # If vcard is empty, we send to the interface an empty vcard so that
            # it knows it arrived
            jid = self.awaiting_answers[id_][1]
            groupchat_jid = self.awaiting_answers[id_][2]
            frm = jid
            if groupchat_jid:
                # We do as if it comes from the fake_jid
                frm = groupchat_jid
            our_jid = app.get_jid_from_account(self.name)
            if (not iq_obj.getTag('vCard') and iq_obj.getType() == 'result') or\
            iq_obj.getType() == 'error':
                if id_ in self.groupchat_jids:
                    frm = self.groupchat_jids[id_]
                    del self.groupchat_jids[id_]
                if frm:
                    # Write an empty file
                    self._save_vcard_to_hd(frm, '')
                jid, resource = app.get_room_and_nick_from_fjid(frm)
                vcard = {'jid': jid, 'resource': resource}
                app.nec.push_incoming_event(VcardReceivedEvent(None,
                    conn=self, vcard_dict=vcard))
            del self.awaiting_answers[id_]
        elif self.awaiting_answers[id_][0] == AGENT_REMOVED:
            jid = self.awaiting_answers[id_][1]
            app.nec.push_incoming_event(AgentRemovedEvent(None, conn=self,
                agent=jid))
            del self.awaiting_answers[id_]
        elif self.awaiting_answers[id_][0] == METACONTACTS_ARRIVED:
            if not self.connection:
                return
            if iq_obj.getType() == 'result':
                app.nec.push_incoming_event(MetacontactsReceivedEvent(None,
                    conn=self, stanza=iq_obj))
            else:
                if iq_obj.getErrorCode() not in ('403', '406', '404'):
                    self.private_storage_supported = False
            self.get_roster_delimiter()
            del self.awaiting_answers[id_]
        elif self.awaiting_answers[id_][0] == DELIMITER_ARRIVED:
            del self.awaiting_answers[id_]
            if not self.connection:
                return
            if iq_obj.getType() == 'result':
                query = iq_obj.getTag('query')
                if not query:
                    return
                delimiter = query.getTagData('roster')
                if delimiter:
                    self.nested_group_delimiter = delimiter
                else:
                    self.set_roster_delimiter('::')
            else:
                self.private_storage_supported = False

            # We can now continue connection by requesting the roster
            self.request_roster()
        elif self.awaiting_answers[id_][0] == ROSTER_ARRIVED:
            if iq_obj.getType() == 'result':
                if not iq_obj.getTag('query'):
                    account_jid = app.get_jid_from_account(self.name)
                    roster_data = app.logger.get_roster(account_jid)
                    roster = self.connection.getRoster(force=True)
                    roster.setRaw(roster_data)
                self._getRoster()
            elif iq_obj.getType() == 'error':
                self.roster_supported = False
                self.discoverItems(app.config.get_per('accounts', self.name,
                    'hostname'), id_prefix='Gajim_')
                if app.config.get_per('accounts', self.name,
                'use_ft_proxies'):
                    self.discover_ft_proxies()
                app.nec.push_incoming_event(RosterReceivedEvent(None,
                    conn=self))
            GLib.timeout_add_seconds(10, self.discover_servers)
            del self.awaiting_answers[id_]
        elif self.awaiting_answers[id_][0] == PRIVACY_ARRIVED:
            del self.awaiting_answers[id_]
            if iq_obj.getType() != 'error':
                for list_ in iq_obj.getQueryPayload():
                    if list_.getName() == 'default':
                        self.privacy_default_list = list_.getAttr('name')
                        self.get_privacy_list(self.privacy_default_list)
                        break
                # Ask metacontacts before roster
                self.get_metacontacts()
            else:
                # That should never happen, but as it's blocking in the
                # connection process, we don't take the risk
                self.privacy_rules_supported = False
                self._continue_connection_request_privacy()
        elif self.awaiting_answers[id_][0] == BLOCKING_ARRIVED:
            del self.awaiting_answers[id_]
            if iq_obj.getType() == 'result':
                list_node = iq_obj.getTag('blocklist')
                if not list_node:
                    return
                self.blocked_contacts = []
                for i in list_node.iterTags('item'):
                    self.blocked_contacts.append(i.getAttr('jid'))
        elif self.awaiting_answers[id_][0] == PEP_CONFIG:
            del self.awaiting_answers[id_]
            if iq_obj.getType() == 'error':
                return
            if not iq_obj.getTag('pubsub'):
                return
            conf = iq_obj.getTag('pubsub').getTag('configure')
            if not conf:
                return
            node = conf.getAttr('node')
            form_tag = conf.getTag('x', namespace=nbxmpp.NS_DATA)
            if form_tag:
                form = dataforms.ExtendForm(node=form_tag)
                app.nec.push_incoming_event(PEPConfigReceivedEvent(None,
                    conn=self, node=node, form=form))

    def _vCardCB(self, con, vc):
        """
        Called when we receive a vCard Parse the vCard and send it to plugins
        """
        if not vc.getTag('vCard'):
            return
        if not vc.getTag('vCard').getNamespace() == nbxmpp.NS_VCARD:
            return
        id_ = vc.getID()
        frm_iq = vc.getFrom()
        our_jid = app.get_jid_from_account(self.name)
        resource = ''
        if id_ in self.groupchat_jids:
            who = self.groupchat_jids[id_]
            frm, resource = app.get_room_and_nick_from_fjid(who)
            del self.groupchat_jids[id_]
        elif frm_iq:
            who = helpers.get_full_jid_from_iq(vc)
            frm, resource = app.get_room_and_nick_from_fjid(who)
        else:
            who = frm = our_jid
        card = vc.getChildren()[0]
        vcard = self._node_to_dict(card)
        photo_decoded = None
        if 'PHOTO' in vcard and isinstance(vcard['PHOTO'], dict) and \
        'BINVAL' in vcard['PHOTO']:
            photo = vcard['PHOTO']['BINVAL']
            try:
                photo_decoded = base64.b64decode(photo.encode('utf-8'))
                avatar_sha = hashlib.sha1(photo_decoded).hexdigest()
            except Exception:
                avatar_sha = ''
        else:
            avatar_sha = ''

        if avatar_sha:
            card.getTag('PHOTO').setTagData('SHA', avatar_sha)

        # Save it to file
        self._save_vcard_to_hd(who, card)
        # Save the decoded avatar to a separate file too, and generate files
        # for dbus notifications
        puny_jid = helpers.sanitize_filename(frm)
        puny_nick = None
        begin_path = os.path.join(app.AVATAR_PATH, puny_jid)
        frm_jid = frm
        if frm in self.room_jids:
            puny_nick = helpers.sanitize_filename(resource)
            # create folder if needed
            if not os.path.isdir(begin_path):
                os.mkdir(begin_path, 0o700)
            begin_path = os.path.join(begin_path, puny_nick)
            frm_jid += '/' + resource
        if photo_decoded:
            avatar_file = begin_path + '_notif_size_colored.png'
            if frm_jid == our_jid and avatar_sha != self.vcard_sha:
                app.interface.save_avatar_files(frm, photo_decoded, puny_nick)
            elif frm_jid != our_jid and (not os.path.exists(avatar_file) or \
            frm_jid not in self.vcard_shas or \
            avatar_sha != self.vcard_shas[frm_jid]):
                app.interface.save_avatar_files(frm, photo_decoded, puny_nick)
                if avatar_sha:
                    self.vcard_shas[frm_jid] = avatar_sha
            elif frm in self.vcard_shas:
                del self.vcard_shas[frm]
        else:
            for ext in ('.jpeg', '.png', '_notif_size_bw.png',
            '_notif_size_colored.png'):
                path = begin_path + ext
                if os.path.isfile(path):
                    os.remove(path)

        vcard['jid'] = frm
        vcard['resource'] = resource
        app.nec.push_incoming_event(VcardReceivedEvent(None, conn=self,
            vcard_dict=vcard))
        if frm_jid == our_jid:
            # we re-send our presence with sha if has changed and if we are
            # not invisible
            if self.vcard_sha == avatar_sha:
                return
            self.vcard_sha = avatar_sha
            if app.SHOW_LIST[self.connected] == 'invisible':
                return
            if not self.connection:
                return
            sshow = helpers.get_xmpp_show(app.SHOW_LIST[self.connected])
            p = nbxmpp.Presence(typ=None, priority=self.priority,
                show=sshow, status=self.status)
            p = self.add_sha(p)
            self.connection.send(p)


class ConnectionPEP(object):

    def __init__(self, account, dispatcher, pubsub_connection):
        self._account = account
        self._dispatcher = dispatcher
        self._pubsub_connection = pubsub_connection
        self.reset_awaiting_pep()

    def pep_change_account_name(self, new_name):
        self._account = new_name

    def reset_awaiting_pep(self):
        self.to_be_sent_activity = None
        self.to_be_sent_mood = None
        self.to_be_sent_tune = None
        self.to_be_sent_nick = None
        self.to_be_sent_location = None

    def send_awaiting_pep(self):
        """
        Send pep info that were waiting for connection
        """
        if self.to_be_sent_activity:
            self.send_activity(*self.to_be_sent_activity)
        if self.to_be_sent_mood:
            self.send_mood(*self.to_be_sent_mood)
        if self.to_be_sent_tune:
            self.send_tune(*self.to_be_sent_tune)
        if self.to_be_sent_nick:
            self.send_nick(self.to_be_sent_nick)
        if self.to_be_sent_location:
            self.send_location(self.to_be_sent_location)
        self.reset_awaiting_pep()

    def _pubsubEventCB(self, xmpp_dispatcher, msg):
        ''' Called when we receive <message /> with pubsub event. '''
        app.nec.push_incoming_event(PEPReceivedEvent(None, conn=self,
            stanza=msg))

    def send_activity(self, activity, subactivity=None, message=None):
        if self.connected == 1:
            # We are connecting, keep activity in mem and send it when we'll be
            # connected
            self.to_be_sent_activity = (activity, subactivity, message)
            return
        if not self.pep_supported:
            return
        item = nbxmpp.Node('activity', {'xmlns': nbxmpp.NS_ACTIVITY})
        if activity:
            i = item.addChild(activity)
        if subactivity:
            i.addChild(subactivity)
        if message:
            i = item.addChild('text')
            i.addData(message)
        self._pubsub_connection.send_pb_publish('', nbxmpp.NS_ACTIVITY, item,
            '0')

    def retract_activity(self):
        if not self.pep_supported:
            return
        self.send_activity(None)
        # not all client support new XEP, so we still retract
        self._pubsub_connection.send_pb_retract('', nbxmpp.NS_ACTIVITY, '0')

    def send_mood(self, mood, message=None):
        if self.connected == 1:
            # We are connecting, keep mood in mem and send it when we'll be
            # connected
            self.to_be_sent_mood = (mood, message)
            return
        if not self.pep_supported:
            return
        item = nbxmpp.Node('mood', {'xmlns': nbxmpp.NS_MOOD})
        if mood:
            item.addChild(mood)
        if message:
            i = item.addChild('text')
            i.addData(message)
        self._pubsub_connection.send_pb_publish('', nbxmpp.NS_MOOD, item, '0')

    def retract_mood(self):
        if not self.pep_supported:
            return
        self.send_mood(None)
        # not all client support new XEP, so we still retract
        self._pubsub_connection.send_pb_retract('', nbxmpp.NS_MOOD, '0')

    def send_tune(self, artist='', title='', source='', track=0, length=0,
    items=None):
        if self.connected == 1:
            # We are connecting, keep tune in mem and send it when we'll be
            # connected
            self.to_be_sent_tune = (artist, title, source, track, length, items)
            return
        if not self.pep_supported:
            return
        item = nbxmpp.Node('tune', {'xmlns': nbxmpp.NS_TUNE})
        if artist:
            i = item.addChild('artist')
            i.addData(artist)
        if title:
            i = item.addChild('title')
            i.addData(title)
        if source:
            i = item.addChild('source')
            i.addData(source)
        if track:
            i = item.addChild('track')
            i.addData(track)
        if length:
            i = item.addChild('length')
            i.addData(length)
        if items:
            item.addChild(payload=items)
        self._pubsub_connection.send_pb_publish('', nbxmpp.NS_TUNE, item, '0')

    def retract_tune(self):
        if not self.pep_supported:
            return
        self.send_tune(None)
        # not all client support new XEP, so we still retract
        self._pubsub_connection.send_pb_retract('', nbxmpp.NS_TUNE, '0')

    def send_nickname(self, nick):
        if self.connected == 1:
            # We are connecting, keep nick in mem and send it when we'll be
            # connected
            self.to_be_sent_nick = nick
            return
        if not self.pep_supported:
            return
        item = nbxmpp.Node('nick', {'xmlns': nbxmpp.NS_NICK})
        item.addData(nick)
        self._pubsub_connection.send_pb_publish('', nbxmpp.NS_NICK, item, '0')

    def retract_nickname(self):
        if not self.pep_supported:
            return

        self._pubsub_connection.send_pb_retract('', nbxmpp.NS_NICK, '0')

    def send_location(self, info):
        if self.connected == 1:
            # We are connecting, keep location in mem and send it when we'll be
            # connected
            self.to_be_sent_location = info
            return
        if not self.pep_supported:
            return
        item = nbxmpp.Node('geoloc', {'xmlns': nbxmpp.NS_LOCATION})
        for field in LOCATION_DATA:
            if info.get(field, None):
                i = item.addChild(field)
                i.addData(info[field])
        self._pubsub_connection.send_pb_publish('', nbxmpp.NS_LOCATION, item, '0')

    def retract_location(self):
        if not self.pep_supported:
            return
        self.send_location({})
        # not all client support new XEP, so we still retract
        self._pubsub_connection.send_pb_retract('', nbxmpp.NS_LOCATION, '0')

# basic connection handlers used here and in zeroconf
class ConnectionHandlersBase:
    def __init__(self):
        # List of IDs we are waiting answers for {id: (type_of_request, data), }
        self.awaiting_answers = {}
        # List of IDs that will produce a timeout is answer doesn't arrive
        # {time_of_the_timeout: (id, message to send to gui), }
        self.awaiting_timeouts = {}
        # keep the jids we auto added (transports contacts) to not send the
        # SUBSCRIBED event to gui
        self.automatically_added = []

        # keep track of sessions this connection has with other JIDs
        self.sessions = {}

        # IDs of sent messages (https://trac.gajim.org/ticket/8222)
        self.sent_message_ids = []

        self.received_message_hashes = []

        # We decrypt GPG messages one after the other. Keep queue in mem
        self.gpg_messages_to_decrypt = []

        app.ged.register_event_handler('iq-error-received', ged.CORE,
            self._nec_iq_error_received)
        app.ged.register_event_handler('presence-received', ged.CORE,
            self._nec_presence_received)
        app.ged.register_event_handler('gc-presence-received', ged.CORE,
            self._nec_gc_presence_received)
        app.ged.register_event_handler('message-received', ged.CORE,
            self._nec_message_received)
        app.ged.register_event_handler('mam-message-received', ged.CORE,
            self._nec_message_received)
        app.ged.register_event_handler('decrypted-message-received', ged.CORE,
            self._nec_decrypted_message_received)
        app.ged.register_event_handler('gc-message-received', ged.CORE,
            self._nec_gc_message_received)

    def cleanup(self):
        app.ged.remove_event_handler('iq-error-received', ged.CORE,
            self._nec_iq_error_received)
        app.ged.remove_event_handler('presence-received', ged.CORE,
            self._nec_presence_received)
        app.ged.remove_event_handler('gc-presence-received', ged.CORE,
            self._nec_gc_presence_received)
        app.ged.remove_event_handler('message-received', ged.CORE,
            self._nec_message_received)
        app.ged.remove_event_handler('mam-message-received', ged.CORE,
            self._nec_message_received)
        app.ged.remove_event_handler('decrypted-message-received', ged.CORE,
            self._nec_decrypted_message_received)
        app.ged.remove_event_handler('gc-message-received', ged.CORE,
            self._nec_gc_message_received)

    def _nec_iq_error_received(self, obj):
        if obj.conn.name != self.name:
            return

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

        if obj.avatar_sha is not None and obj.ptype != 'error':
            if obj.jid not in self.vcard_shas:
                cached_vcard = self.get_cached_vcard(obj.jid)
                if cached_vcard and 'PHOTO' in cached_vcard and \
                'SHA' in cached_vcard['PHOTO']:
                    self.vcard_shas[obj.jid] = cached_vcard['PHOTO']['SHA']
                else:
                    self.vcard_shas[obj.jid] = ''
            if obj.avatar_sha != self.vcard_shas[obj.jid]:
                # avatar has been updated
                self.request_vcard(obj.jid)

        if obj.contact:
            if obj.contact.show in statuss:
                obj.old_show = statuss.index(obj.contact.show)
            # nick changed
            if obj.contact_nickname is not None and \
            obj.contact.contact_name != obj.contact_nickname:
                obj.contact.contact_name = obj.contact_nickname
                obj.need_redraw = True

            if obj.old_show == obj.new_show and obj.contact.status == \
            obj.status and obj.contact.priority == obj.prio and \
            obj.contact.idle_time == obj.idle_time: # no change
                return True
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

            # disable encryption, since if any messages are
            # lost they'll be not decryptable (note that
            # this contradicts XEP-0201 - trying to get that
            # in the XEP, though)

            # there won't be any sessions here if the contact terminated
            # their sessions before going offline (which we do)
            for sess in self.get_sessions(jid):
                sess_fjid = sess.jid.getStripped()
                if sess.resource:
                    sess_fjid += '/' + sess.resource
                if obj.fjid != sess_fjid:
                    continue
                if sess.control:
                    sess.control.no_autonegotiation = False
                if sess.enable_encryption:
                    sess.terminate_e2e()

        if app.config.get('log_contact_status_changes') and \
        app.config.should_log(self.name, obj.jid):
            show = app.logger.convert_show_values_to_db_api_values(obj.show)
            if show is not None:
                app.logger.insert_into_logs(nbxmpp.JID(obj.jid).getStripped(),
                                              time_time(),
                                              KindConstant.STATUS,
                                              message=obj.status,
                                              show=show)

    def _nec_gc_presence_received(self, obj):
        if obj.conn.name != self.name:
            return
        for sess in self.get_sessions(obj.fjid):
            if obj.fjid != sess.jid:
                continue
            if sess.enable_encryption:
                sess.terminate_e2e()

    def _nec_message_received(self, obj):
        if obj.conn.name != self.name:
            return

        app.plugin_manager.extension_point(
            'decrypt', self, obj, self._on_message_received)
        if not obj.encrypted:
            self._on_message_received(obj)

    def _on_message_received(self, obj):
        if isinstance(obj, MessageReceivedEvent):
            app.nec.push_incoming_event(
                DecryptedMessageReceivedEvent(None, conn=self, msg_obj=obj))
        else:
            app.nec.push_incoming_event(
                MamDecryptedMessageReceivedEvent(None, **vars(obj)))

    def _nec_decrypted_message_received(self, obj):
        if obj.conn.name != self.name:
            return

        # Receipt requested
        # TODO: We shouldn't answer if we're invisible!
        contact = app.contacts.get_contact(self.name, obj.jid)
        nick = obj.resource
        gc_contact = app.contacts.get_gc_contact(self.name, obj.jid, nick)
        if obj.sent:
            jid_to = obj.stanza.getFrom()
        else:
            jid_to = obj.stanza.getTo()
        reply = False
        if not jid_to:
            reply = True
        else:
            fjid_to = helpers.parse_jid(str(jid_to))
            jid_to = app.get_jid_without_resource(fjid_to)
            if jid_to == app.get_jid_from_account(self.name):
                reply = True

        if obj.jid != app.get_jid_from_account(self.name):
            if obj.receipt_request_tag and app.config.get_per('accounts',
            self.name, 'answer_receipts') and ((contact and contact.sub \
            not in ('to', 'none')) or gc_contact) and obj.mtype != 'error' and \
            reply:
                receipt = nbxmpp.Message(to=obj.fjid, typ='chat')
                receipt.setTag('received', namespace='urn:xmpp:receipts',
                    attrs={'id': obj.id_})

                if obj.thread_id:
                    receipt.setThread(obj.thread_id)
                self.connection.send(receipt)

        # We got our message's receipt
        if obj.receipt_received_tag and app.config.get_per('accounts',
        self.name, 'request_receipt'):
            ctrl = obj.session.control
            if not ctrl:
                # Received <message> doesn't have the <thread> element
                # or control is not bound to session?
                # --> search for it
                ctrl = app.interface.msg_win_mgr.search_control(obj.jid,
                    obj.conn.name, obj.resource)
            
            if ctrl:
                id_ = obj.receipt_received_tag.getAttr('id')
                if not id_:
                    # old XEP implementation
                    id_ = obj.id_
                ctrl.conv_textview.show_xep0184_ack(id_)

        if obj.mtype == 'error':
            if not obj.msgtxt:
                obj.msgtxt = _('message')
            self.dispatch_error_message(obj.stanza, obj.msgtxt,
                obj.session, obj.fjid, obj.timestamp)
            return True
        elif obj.mtype == 'groupchat':
            app.nec.push_incoming_event(GcMessageReceivedEvent(None,
                conn=self, msg_obj=obj))
            return True

    def _nec_gc_message_received(self, obj):
        if app.config.should_log(obj.conn.name, obj.jid) and not \
        obj.timestamp < obj.conn.last_history_time[obj.jid] and obj.msgtxt and \
        obj.nick:
            # if not obj.nick, it means message comes from room itself
            # usually it hold description and can be send at each connection
            # so don't store it in logs
            app.logger.insert_into_logs(obj.jid,
                                          obj.timestamp,
                                          KindConstant.GC_MSG,
                                          message=obj.msgtxt,
                                          contact_name=obj.nick,
                                          additional_data=obj.additional_data)
            # store in memory time of last message logged.
            # this will also be saved in rooms_last_message_time table
            # when we quit this muc
            obj.conn.last_history_time[obj.jid] = obj.timestamp

    # process and dispatch an error message
    def dispatch_error_message(self, msg, msgtxt, session, frm, tim):
        error_msg = msg.getErrorMsg()

        if not error_msg:
            error_msg = msgtxt
            msgtxt = None

        subject = msg.getSubject()

        if session.is_loggable():
            app.logger.insert_into_logs(nbxmpp.JID(frm).getStripped(),
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

    def terminate_sessions(self, send_termination=False):
        """
        Send termination messages and delete all active sessions
        """
        for jid in self.sessions:
            for thread_id in self.sessions[jid]:
                self.sessions[jid][thread_id].terminate(send_termination)

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

class ConnectionHandlers(ConnectionArchive313,
ConnectionVcard, ConnectionSocks5Bytestream, ConnectionDisco,
ConnectionCommands, ConnectionPubSub, ConnectionPEP, ConnectionCaps,
ConnectionHandlersBase, ConnectionJingle, ConnectionIBBytestream):
    def __init__(self):
        ConnectionArchive313.__init__(self)
        ConnectionVcard.__init__(self)
        ConnectionSocks5Bytestream.__init__(self)
        ConnectionIBBytestream.__init__(self)
        ConnectionCommands.__init__(self)
        ConnectionPubSub.__init__(self)
        ConnectionPEP.__init__(self, account=self.name, dispatcher=self,
            pubsub_connection=self)

        # Handle presences BEFORE caps
        app.nec.register_incoming_event(PresenceReceivedEvent)

        ConnectionCaps.__init__(self, account=self.name,
            capscache=capscache.capscache,
            client_caps_factory=capscache.create_suitable_client_caps)
        ConnectionJingle.__init__(self)
        ConnectionHandlersBase.__init__(self)
        self.gmail_url = None

        # keep the latest subscribed event for each jid to prevent loop when we
        # acknowledge presences
        self.subscribed_events = {}
        # IDs of jabber:iq:version requests
        self.version_ids = []
        # IDs of urn:xmpp:time requests
        self.entity_time_ids = []
        # IDs of disco#items requests
        self.disco_items_ids = []
        # IDs of disco#info requests
        self.disco_info_ids = []
        # ID of urn:xmpp:ping requests
        self.awaiting_xmpp_ping_id = None
        self.continue_connect_info = None

        self.privacy_default_list = None

        self.gmail_last_tid = None
        self.gmail_last_time = None

        app.nec.register_incoming_event(PrivateStorageBookmarksReceivedEvent)
        app.nec.register_incoming_event(BookmarksReceivedEvent)
        app.nec.register_incoming_event(
            PrivateStorageRosternotesReceivedEvent)
        app.nec.register_incoming_event(RosternotesReceivedEvent)
        app.nec.register_incoming_event(StreamConflictReceivedEvent)
        app.nec.register_incoming_event(StreamOtherHostReceivedEvent)
        app.nec.register_incoming_event(MessageReceivedEvent)
        app.nec.register_incoming_event(ArchivingErrorReceivedEvent)
        app.nec.register_incoming_event(
            Archiving313PreferencesChangedReceivedEvent)
        app.nec.register_incoming_event(
            ArchivingFinishedLegacyReceivedEvent)
        app.nec.register_incoming_event(
            ArchivingFinishedReceivedEvent)
        app.nec.register_incoming_event(NotificationEvent)

        app.ged.register_event_handler('http-auth-received', ged.CORE,
            self._nec_http_auth_received)
        app.ged.register_event_handler('version-request-received', ged.CORE,
            self._nec_version_request_received)
        app.ged.register_event_handler('last-request-received', ged.CORE,
            self._nec_last_request_received)
        app.ged.register_event_handler('time-request-received', ged.CORE,
            self._nec_time_request_received)
        app.ged.register_event_handler('time-revised-request-received',
            ged.CORE, self._nec_time_revised_request_received)
        app.ged.register_event_handler('roster-set-received',
            ged.CORE, self._nec_roster_set_received)
        app.ged.register_event_handler('private-storage-bookmarks-received',
            ged.CORE, self._nec_private_storate_bookmarks_received)
        app.ged.register_event_handler('private-storage-rosternotes-received',
            ged.CORE, self._nec_private_storate_rosternotes_received)
        app.ged.register_event_handler('roster-received', ged.CORE,
            self._nec_roster_received)
        app.ged.register_event_handler('iq-error-received', ged.CORE,
            self._nec_iq_error_received)
        app.ged.register_event_handler('gmail-new-mail-received', ged.CORE,
            self._nec_gmail_new_mail_received)
        app.ged.register_event_handler('ping-received', ged.CORE,
            self._nec_ping_received)
        app.ged.register_event_handler('subscribe-presence-received',
            ged.CORE, self._nec_subscribe_presence_received)
        app.ged.register_event_handler('subscribed-presence-received',
            ged.CORE, self._nec_subscribed_presence_received)
        app.ged.register_event_handler('subscribed-presence-received',
            ged.POSTGUI, self._nec_subscribed_presence_received_end)
        app.ged.register_event_handler('unsubscribed-presence-received',
            ged.CORE, self._nec_unsubscribed_presence_received)
        app.ged.register_event_handler('unsubscribed-presence-received',
            ged.POSTGUI, self._nec_unsubscribed_presence_received_end)
        app.ged.register_event_handler('agent-removed', ged.CORE,
            self._nec_agent_removed)
        app.ged.register_event_handler('stream-other-host-received', ged.CORE,
            self._nec_stream_other_host_received)
        app.ged.register_event_handler('blocking', ged.CORE,
            self._nec_blocking)

    def cleanup(self):
        ConnectionHandlersBase.cleanup(self)
        ConnectionCaps.cleanup(self)
        ConnectionArchive313.cleanup(self)
        ConnectionPubSub.cleanup(self)
        app.ged.remove_event_handler('http-auth-received', ged.CORE,
            self._nec_http_auth_received)
        app.ged.remove_event_handler('version-request-received', ged.CORE,
            self._nec_version_request_received)
        app.ged.remove_event_handler('last-request-received', ged.CORE,
            self._nec_last_request_received)
        app.ged.remove_event_handler('time-request-received', ged.CORE,
            self._nec_time_request_received)
        app.ged.remove_event_handler('time-revised-request-received',
            ged.CORE, self._nec_time_revised_request_received)
        app.ged.remove_event_handler('roster-set-received',
            ged.CORE, self._nec_roster_set_received)
        app.ged.remove_event_handler('private-storage-bookmarks-received',
            ged.CORE, self._nec_private_storate_bookmarks_received)
        app.ged.remove_event_handler('private-storage-rosternotes-received',
            ged.CORE, self._nec_private_storate_rosternotes_received)
        app.ged.remove_event_handler('roster-received', ged.CORE,
            self._nec_roster_received)
        app.ged.remove_event_handler('iq-error-received', ged.CORE,
            self._nec_iq_error_received)
        app.ged.remove_event_handler('gmail-new-mail-received', ged.CORE,
            self._nec_gmail_new_mail_received)
        app.ged.remove_event_handler('ping-received', ged.CORE,
            self._nec_ping_received)
        app.ged.remove_event_handler('subscribe-presence-received',
            ged.CORE, self._nec_subscribe_presence_received)
        app.ged.remove_event_handler('subscribed-presence-received',
            ged.CORE, self._nec_subscribed_presence_received)
        app.ged.remove_event_handler('subscribed-presence-received',
            ged.POSTGUI, self._nec_subscribed_presence_received_end)
        app.ged.remove_event_handler('unsubscribed-presence-received',
            ged.CORE, self._nec_unsubscribed_presence_received)
        app.ged.remove_event_handler('unsubscribed-presence-received',
            ged.POSTGUI, self._nec_unsubscribed_presence_received_end)
        app.ged.remove_event_handler('agent-removed', ged.CORE,
            self._nec_agent_removed)
        app.ged.remove_event_handler('stream-other-host-received', ged.CORE,
            self._nec_stream_other_host_received)
        app.ged.remove_event_handler('blocking', ged.CORE, self._nec_blocking)

    def build_http_auth_answer(self, iq_obj, answer):
        if not self.connection or self.connected < 2:
            return
        if answer == 'yes':
            confirm = iq_obj.getTag('confirm')
            reply = iq_obj.buildReply('result')
            if iq_obj.getName() == 'message':
                reply.addChild(node=confirm)
            self.connection.send(reply)
        elif answer == 'no':
            err = nbxmpp.Error(iq_obj, nbxmpp.protocol.ERR_NOT_AUTHORIZED)
            self.connection.send(err)

    def _nec_http_auth_received(self, obj):
        if obj.conn.name != self.name:
            return
        if obj.opt in ('yes', 'no'):
            obj.conn.build_http_auth_answer(obj.stanza, obj.opt)
            return True

    def _HttpAuthCB(self, con, iq_obj):
        log.debug('HttpAuthCB')
        app.nec.push_incoming_event(HttpAuthReceivedEvent(None, conn=self,
            stanza=iq_obj))
        raise nbxmpp.NodeProcessed

    def _ErrorCB(self, con, iq_obj):
        log.debug('ErrorCB')
        app.nec.push_incoming_event(IqErrorReceivedEvent(None, conn=self,
            stanza=iq_obj))

    def _nec_iq_error_received(self, obj):
        if obj.conn.name != self.name:
            return
        if obj.id_ in self.version_ids:
            app.nec.push_incoming_event(VersionResultReceivedEvent(None,
                conn=self, stanza=obj.stanza))
            return True
        if obj.id_ in self.entity_time_ids:
            app.nec.push_incoming_event(TimeResultReceivedEvent(None,
                conn=self, stanza=obj.stanza))
            return True
        if obj.id_ in self.disco_items_ids:
            app.nec.push_incoming_event(AgentItemsErrorReceivedEvent(None,
                conn=self, stanza=obj.stanza))
            return True
        if obj.id_ in self.disco_info_ids:
            app.nec.push_incoming_event(AgentInfoErrorReceivedEvent(None,
                conn=self, stanza=obj.stanza))
            return True

    def _nec_private_storate_bookmarks_received(self, obj):
        if obj.conn.name != self.name:
            return
        resend_to_pubsub = False
        bm_jids = [b['jid'] for b in self.bookmarks]
        for bm in obj.bookmarks:
            if bm['jid'] not in bm_jids:
                self.bookmarks.append(bm)
                # We got a bookmark that was not in pubsub
                resend_to_pubsub = True
        if self.pubsub_supported and resend_to_pubsub:
            self.store_bookmarks('pubsub')

    def _nec_private_storate_rosternotes_received(self, obj):
        if obj.conn.name != self.name:
            return
        for jid in obj.annotations:
            self.annotations[jid] = obj.annotations[jid]

    def _PrivateCB(self, con, iq_obj):
        """
        Private Data (XEP 048 and 049)
        """
        log.debug('PrivateCB')
        app.nec.push_incoming_event(PrivateStorageReceivedEvent(None,
            conn=self, stanza=iq_obj))

    def _SecLabelCB(self, con, iq_obj):
        """
        Security Label callback, used for catalogues.
        """
        log.debug('SecLabelCB')
        query = iq_obj.getTag('catalog')
        to = query.getAttr('to')
        items = query.getTags('item')
        labels = {}
        ll = []
        default = None
        for item in items:
            label = item.getAttr('selector')
            labels[label] = item.getTag('securitylabel')
            ll.append(label)
            if item.getAttr('default') == 'true':
                default = label
        if to not in self.seclabel_catalogues:
            self.seclabel_catalogues[to] = [[], None, None, None]
        self.seclabel_catalogues[to][1] = labels
        self.seclabel_catalogues[to][2] = ll
        self.seclabel_catalogues[to][3] = default
        for callback in self.seclabel_catalogues[to][0]:
            callback()
        self.seclabel_catalogues[to][0] = []

    def seclabel_catalogue_request(self, to, callback):
        if to not in self.seclabel_catalogues:
            self.seclabel_catalogues[to] = [[], None, None, None]
        self.seclabel_catalogues[to][0].append(callback)

    def _rosterSetCB(self, con, iq_obj):
        log.debug('rosterSetCB')
        app.nec.push_incoming_event(RosterSetReceivedEvent(None, conn=self,
            stanza=iq_obj))
        raise nbxmpp.NodeProcessed

    def _nec_roster_set_received(self, obj):
        if obj.conn.name != self.name:
            return
        for jid in obj.items:
            item = obj.items[jid]
            app.nec.push_incoming_event(RosterInfoEvent(None, conn=self,
                jid=jid, nickname=item['name'], sub=item['sub'],
                ask=item['ask'], groups=item['groups']))
            account_jid = app.get_jid_from_account(self.name)
            app.logger.add_or_update_contact(account_jid, jid, item['name'],
                item['sub'], item['ask'], item['groups'])
        if obj.version:
            app.config.set_per('accounts', self.name, 'roster_version',
                obj.version)

    def _VersionCB(self, con, iq_obj):
        log.debug('VersionCB')
        if not self.connection or self.connected < 2:
            return
        app.nec.push_incoming_event(VersionRequestEvent(None, conn=self,
            stanza=iq_obj))
        raise nbxmpp.NodeProcessed

    def _nec_version_request_received(self, obj):
        if obj.conn.name != self.name:
            return
        send_os = app.config.get_per('accounts', self.name, 'send_os_info')
        if send_os:
            iq_obj = obj.stanza.buildReply('result')
            qp = iq_obj.getQuery()
            qp.setTagData('name', 'Gajim')
            qp.setTagData('version', app.version)
            qp.setTagData('os', helpers.get_os_info())
        else:
            iq_obj = obj.stanza.buildReply('error')
            err = nbxmpp.ErrorNode(name=nbxmpp.NS_STANZAS + \
                ' service-unavailable')
            iq_obj.addChild(node=err)
        self.connection.send(iq_obj)

    def _LastCB(self, con, iq_obj):
        log.debug('LastCB')
        if not self.connection or self.connected < 2:
            return
        app.nec.push_incoming_event(LastRequestEvent(None, conn=self,
            stanza=iq_obj))
        raise nbxmpp.NodeProcessed

    def _nec_last_request_received(self, obj):
        if obj.conn.name != self.name:
            return
        if app.HAVE_IDLE and app.config.get_per('accounts', self.name,
        'send_idle_time'):
            iq_obj = obj.stanza.buildReply('result')
            qp = iq_obj.setQuery()
            qp.attrs['seconds'] = int(app.interface.sleeper.getIdleSec())
        else:
            iq_obj = obj.stanza.buildReply('error')
            err = nbxmpp.ErrorNode(name=nbxmpp.NS_STANZAS + \
                ' service-unavailable')
            iq_obj.addChild(node=err)
        self.connection.send(iq_obj)

    def _VersionResultCB(self, con, iq_obj):
        log.debug('VersionResultCB')
        app.nec.push_incoming_event(VersionResultReceivedEvent(None,
            conn=self, stanza=iq_obj))

    def _TimeCB(self, con, iq_obj):
        log.debug('TimeCB')
        if not self.connection or self.connected < 2:
            return
        app.nec.push_incoming_event(TimeRequestEvent(None, conn=self,
            stanza=iq_obj))
        raise nbxmpp.NodeProcessed

    def _nec_time_request_received(self, obj):
        if obj.conn.name != self.name:
            return
        if app.config.get_per('accounts', self.name, 'send_time_info'):
            iq_obj = obj.stanza.buildReply('result')
            qp = iq_obj.setQuery()
            qp.setTagData('utc', strftime('%Y%m%dT%H:%M:%S', gmtime()))
            qp.setTagData('tz', tzname[daylight])
            qp.setTagData('display', strftime('%c', localtime()))
        else:
            iq_obj = obj.stanza.buildReply('error')
            err = nbxmpp.ErrorNode(name=nbxmpp.NS_STANZAS + \
                ' service-unavailable')
            iq_obj.addChild(node=err)
        self.connection.send(iq_obj)

    def _TimeRevisedCB(self, con, iq_obj):
        log.debug('TimeRevisedCB')
        if not self.connection or self.connected < 2:
            return
        app.nec.push_incoming_event(TimeRevisedRequestEvent(None, conn=self,
            stanza=iq_obj))
        raise nbxmpp.NodeProcessed

    def _nec_time_revised_request_received(self, obj):
        if obj.conn.name != self.name:
            return
        if app.config.get_per('accounts', self.name, 'send_time_info'):
            iq_obj = obj.stanza.buildReply('result')
            qp = iq_obj.setTag('time', namespace=nbxmpp.NS_TIME_REVISED)
            qp.setTagData('utc', strftime('%Y-%m-%dT%H:%M:%SZ', gmtime()))
            isdst = localtime().tm_isdst
            zone = -(timezone, altzone)[isdst] / 60.0
            tzo = (zone / 60, abs(zone % 60))
            qp.setTagData('tzo', '%+03d:%02d' % (tzo))
        else:
            iq_obj = obj.stanza.buildReply('error')
            err = nbxmpp.ErrorNode(name=nbxmpp.NS_STANZAS + \
                ' service-unavailable')
            iq_obj.addChild(node=err)
        self.connection.send(iq_obj)

    def _TimeRevisedResultCB(self, con, iq_obj):
        log.debug('TimeRevisedResultCB')
        app.nec.push_incoming_event(TimeResultReceivedEvent(None, conn=self,
            stanza=iq_obj))

    def _gMailNewMailCB(self, con, iq_obj):
        """
        Called when we get notified of new mail messages in gmail account
        """
        log.debug('gMailNewMailCB')
        app.nec.push_incoming_event(GmailNewMailReceivedEvent(None, conn=self,
            stanza=iq_obj))
        raise nbxmpp.NodeProcessed

    def _nec_gmail_new_mail_received(self, obj):
        if obj.conn.name != self.name:
            return
        if not self.connection or self.connected < 2:
            return
        # we'll now ask the server for the exact number of new messages
        jid = app.get_jid_from_account(self.name)
        log.debug('Got notification of new gmail e-mail on %s. Asking the '
            'server for more info.' % jid)
        iq = nbxmpp.Iq(typ='get')
        query = iq.setTag('query')
        query.setNamespace(nbxmpp.NS_GMAILNOTIFY)
        # we want only be notified about newer mails
        if self.gmail_last_tid:
            query.setAttr('newer-than-tid', self.gmail_last_tid)
        if self.gmail_last_time:
            query.setAttr('newer-than-time', self.gmail_last_time)
        self.connection.send(iq)

    def _gMailQueryCB(self, con, iq_obj):
        """
        Called when we receive results from Querying the server for mail messages
        in gmail account
        """
        log.debug('gMailQueryCB')
        app.nec.push_incoming_event(GMailQueryReceivedEvent(None, conn=self,
            stanza=iq_obj))
        raise nbxmpp.NodeProcessed

    def _rosterItemExchangeCB(self, con, msg):
        """
        XEP-0144 Roster Item Echange
        """
        log.debug('rosterItemExchangeCB')
        app.nec.push_incoming_event(RosterItemExchangeEvent(None, conn=self,
            stanza=msg))
        raise nbxmpp.NodeProcessed

    def _messageCB(self, con, msg):
        """
        Called when we receive a message
        """
        log.debug('MessageCB')

        app.nec.push_incoming_event(NetworkEvent('raw-message-received',
            conn=self, stanza=msg, account=self.name))

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
            data = msg.getTags('data', namespace=nbxmpp.NS_BOB)
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

    def _presenceCB(self, con, prs):
        """
        Called when we receive a presence
        """
        log.debug('PresenceCB')
        app.nec.push_incoming_event(NetworkEvent('raw-pres-received',
            conn=self, stanza=prs))

    def _nec_subscribe_presence_received(self, obj):
        account = obj.conn.name
        if account != self.name:
            return
        if app.jid_is_transport(obj.fjid) and obj.fjid in \
        self.agent_registrations:
            self.agent_registrations[obj.fjid]['sub_received'] = True
            if not self.agent_registrations[obj.fjid]['roster_push']:
                # We'll reply after roster push result
                return True
        if app.config.get_per('accounts', self.name, 'autoauth') or \
        app.jid_is_transport(obj.fjid) or obj.jid in self.jids_for_auto_auth \
        or obj.transport_auto_auth:
            if self.connection:
                p = nbxmpp.Presence(obj.fjid, 'subscribed')
                p = self.add_sha(p)
                self.connection.send(p)
            if app.jid_is_transport(obj.fjid) or obj.transport_auto_auth:
                #TODO!?!?
                #self.show = 'offline'
                #self.status = 'offline'
                #emit NOTIFY
                pass
            if obj.transport_auto_auth:
                self.automatically_added.append(obj.jid)
                self.request_subscription(obj.jid, name=obj.user_nick)
            return True
        if not obj.status:
            obj.status = _('I would like to add you to my roster.')

    def _nec_subscribed_presence_received(self, obj):
        account = obj.conn.name
        if account != self.name:
            return
        # BE CAREFUL: no con.updateRosterItem() in a callback
        if obj.jid in self.automatically_added:
            self.automatically_added.remove(obj.jid)
            return True
        # detect a subscription loop
        if obj.jid not in self.subscribed_events:
            self.subscribed_events[obj.jid] = []
        self.subscribed_events[obj.jid].append(time_time())
        block = False
        if len(self.subscribed_events[obj.jid]) > 5:
            if time_time() - self.subscribed_events[obj.jid][0] < 5:
                block = True
            self.subscribed_events[obj.jid] = \
                self.subscribed_events[obj.jid][1:]
        if block:
            app.config.set_per('account', self.name, 'dont_ack_subscription',
                True)
            return True

    def _nec_subscribed_presence_received_end(self, obj):
        account = obj.conn.name
        if account != self.name:
            return
        if not app.config.get_per('accounts', account,
        'dont_ack_subscription'):
            self.ack_subscribed(obj.jid)

    def _nec_unsubscribed_presence_received(self, obj):
        account = obj.conn.name
        if account != self.name:
            return
        # detect a unsubscription loop
        if obj.jid not in self.subscribed_events:
            self.subscribed_events[obj.jid] = []
        self.subscribed_events[obj.jid].append(time_time())
        block = False
        if len(self.subscribed_events[obj.jid]) > 5:
            if time_time() - self.subscribed_events[obj.jid][0] < 5:
                block = True
            self.subscribed_events[obj.jid] = \
                self.subscribed_events[obj.jid][1:]
        if block:
            app.config.set_per('account', self.name, 'dont_ack_subscription',
                True)
            return True

    def _nec_unsubscribed_presence_received_end(self, obj):
        account = obj.conn.name
        if account != self.name:
            return
        if not app.config.get_per('accounts', account,
        'dont_ack_subscription'):
            self.ack_unsubscribed(obj.jid)

    def _nec_agent_removed(self, obj):
        if obj.conn.name != self.name:
            return
        for jid in obj.jid_list:
            log.debug('Removing contact %s due to unregistered transport %s' % \
                (jid, obj.agent))
            self.unsubscribe(jid)
            # Transport contacts can't have 2 resources
            if jid in app.to_be_removed[self.name]:
                # This way we'll really remove it
                app.to_be_removed[self.name].remove(jid)

    def _StanzaArrivedCB(self, con, obj):
        self.last_io = app.idlequeue.current_time()

    def _MucOwnerCB(self, con, iq_obj):
        log.debug('MucOwnerCB')
        app.nec.push_incoming_event(MucOwnerReceivedEvent(None, conn=self,
            stanza=iq_obj))

    def _MucAdminCB(self, con, iq_obj):
        log.debug('MucAdminCB')
        app.nec.push_incoming_event(MucAdminReceivedEvent(None, conn=self,
            stanza=iq_obj))

    def _IqPingCB(self, con, iq_obj):
        log.debug('IqPingCB')
        app.nec.push_incoming_event(PingReceivedEvent(None, conn=self,
            stanza=iq_obj))
        raise nbxmpp.NodeProcessed

    def _nec_ping_received(self, obj):
        if obj.conn.name != self.name:
            return
        if not self.connection or self.connected < 2:
            return
        iq_obj = obj.stanza.buildReply('result')
        q = iq_obj.getTag('ping')
        if q:
            iq_obj.delChild(q)
        self.connection.send(iq_obj)

    def _PrivacySetCB(self, con, iq_obj):
        """
        Privacy lists (XEP 016)

        A list has been set.
        """
        log.debug('PrivacySetCB')
        if not self.connection or self.connected < 2:
            return
        result = iq_obj.buildReply('result')
        q = result.getTag('query')
        if q:
            result.delChild(q)
        self.connection.send(result)

        for list_ in iq_obj.getQueryPayload():
            if list_.getName() == 'list':
                self.get_privacy_list(list_.getAttr('name'))

        raise nbxmpp.NodeProcessed

    def _getRoster(self):
        log.debug('getRosterCB')
        if not self.connection:
            return
        self.connection.getRoster(self._on_roster_set)
        self.discoverItems(app.config.get_per('accounts', self.name,
            'hostname'), id_prefix='Gajim_')
        if app.config.get_per('accounts', self.name, 'use_ft_proxies'):
            self.discover_ft_proxies()

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

    def discover_servers(self):
        if not self.connection:
            return
        servers = []
        for c in app.contacts.iter_contacts(self.name):
            s = app.get_server_from_jid(c.jid)
            if s not in servers and s not in app.transport_type:
                servers.append(s)
        for s in servers:
            self.discoverInfo(s)

    def _on_roster_set(self, roster):
        app.nec.push_incoming_event(RosterReceivedEvent(None, conn=self,
            xmpp_roster=roster))

    def _nec_roster_received(self, obj):
        if obj.conn.name != self.name:
            return
        our_jid = app.get_jid_from_account(self.name)
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

        if obj.received_from_server:
            for jid in obj.roster:
                if jid != our_jid and app.jid_is_transport(jid) and \
                not app.get_transport_name_from_jid(jid):
                    # we can't determine which iconset to use
                    self.discoverInfo(jid)

            app.logger.replace_roster(self.name, obj.version, obj.roster)

        for contact in app.contacts.iter_contacts(self.name):
            if not contact.is_groupchat() and contact.jid not in obj.roster\
            and contact.jid != our_jid:
                app.nec.push_incoming_event(RosterInfoEvent(None,
                    conn=self, jid=contact.jid, nickname=None, sub=None,
                    ask=None, groups=()))
        for jid, info in obj.roster.items():
            app.nec.push_incoming_event(RosterInfoEvent(None,
                conn=self, jid=jid, nickname=info['name'],
                sub=info['subscription'], ask=info['ask'],
                groups=info['groups']))

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
        our_jid = helpers.parse_jid(app.get_jid_from_account(self.name))
        vcard = self.get_cached_vcard(our_jid)
        if vcard and 'PHOTO' in vcard and 'SHA' in vcard['PHOTO']:
            self.vcard_sha = vcard['PHOTO']['SHA']
        p = nbxmpp.Presence(typ=None, priority=priority, show=sshow)
        p = self.add_sha(p)
        if msg:
            p.setStatus(msg)
        if signed:
            p.setTag(nbxmpp.NS_SIGNED + ' x').setData(signed)

        if self.connection:
            self.connection.send(p)
            self.priority = priority
        app.nec.push_incoming_event(OurShowEvent(None, conn=self,
            show=show))
        if self.vcard_supported:
            # ask our VCard
            self.request_vcard(None)

        # Get bookmarks from private namespace
        self.get_bookmarks()

        # Get annotations from private namespace
        self.get_annotations()

        # Inform GUI we just signed in
        app.nec.push_incoming_event(SignedInEvent(None, conn=self))
        self.send_awaiting_pep()
        self.continue_connect_info = None
        # hashes of already received messages
        self.received_message_hashes = []

    def request_gmail_notifications(self):
        if not self.connection or self.connected < 2:
            return
        # It's a gmail account,
        # inform the server that we want e-mail notifications
        our_jid = helpers.parse_jid(app.get_jid_from_account(self.name))
        log.debug(('%s is a gmail account. Setting option '
            'to get e-mail notifications on the server.') % (our_jid))
        iq = nbxmpp.Iq(typ='set', to=our_jid)
        iq.setAttr('id', 'MailNotify')
        query = iq.setTag('usersetting')
        query.setNamespace(nbxmpp.NS_GTALKSETTING)
        query = query.setTag('mailnotifications')
        query.setAttr('value', 'true')
        self.connection.send(iq)
        # Ask how many messages there are now
        iq = nbxmpp.Iq(typ='get')
        iq.setID(self.connection.getAnID())
        query = iq.setTag('query')
        query.setNamespace(nbxmpp.NS_GMAILNOTIFY)
        self.connection.send(iq)

    def _SearchCB(self, con, iq_obj):
        log.debug('SearchCB')
        app.nec.push_incoming_event(SearchFormReceivedEvent(None,
            conn=self, stanza=iq_obj))

    def _search_fields_received(self, con, iq_obj):
        jid = jid = helpers.get_jid_from_iq(iq_obj)
        tag = iq_obj.getTag('query', namespace = nbxmpp.NS_SEARCH)
        if not tag:
            self.dispatch('SEARCH_FORM', (jid, None, False))
            return
        df = tag.getTag('x', namespace=nbxmpp.NS_DATA)
        if df:
            self.dispatch('SEARCH_FORM', (jid, df, True))
            return
        df = {}
        for i in iq_obj.getQueryPayload():
            df[i.getName()] = i.getData()
        self.dispatch('SEARCH_FORM', (jid, df, False))

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

    def _BlockingSetCB(self, con, iq_obj):
        log.debug('_BlockingSetCB')
        app.nec.push_incoming_event(BlockingEvent(None, conn=self,
            stanza=iq_obj))
        raise nbxmpp.NodeProcessed

    def _nec_blocking(self, obj):
        if obj.conn.name != self.name:
            return
        if obj.unblock_all:
            self.blocked_contacts = []
        else:
            for jid in obj.blocked_jids:
                if jid not in self.blocked_contacts:
                    self.blocked_contacts.append(jid)
            for jid in obj.unblocked_jids:
                if jid in self.blocked_contacts:
                    self.blocked_contacts.remove(jid)

    def _nec_stream_other_host_received(self, obj):
        if obj.conn.name != self.name:
            return
        self.redirected = obj.redirected

    def _StreamCB(self, con, obj):
        log.debug('StreamCB')
        app.nec.push_incoming_event(StreamReceivedEvent(None,
            conn=self, stanza=obj))

    def _register_handlers(self, con, con_type):
        # try to find another way to register handlers in each class
        # that defines handlers
        con.RegisterHandler('message', self._messageCB)
        con.RegisterHandler('presence', self._presenceCB)
        # We use makefirst so that this handler is called before _messageCB, and
        # can prevent calling it when it's not needed.
        # We also don't check for namespace, else it cannot stop _messageCB to
        # be called
        con.RegisterHandler('message', self._pubsubEventCB, makefirst=True)
        con.RegisterHandler('iq', self._vCardCB, 'result', nbxmpp.NS_VCARD)
        con.RegisterHandler('iq', self._rosterSetCB, 'set', nbxmpp.NS_ROSTER)
        con.RegisterHandler('iq', self._siSetCB, 'set', nbxmpp.NS_SI)
        con.RegisterHandler('iq', self._rosterItemExchangeCB, 'set',
            nbxmpp.NS_ROSTERX)
        con.RegisterHandler('iq', self._siErrorCB, 'error', nbxmpp.NS_SI)
        con.RegisterHandler('iq', self._siResultCB, 'result', nbxmpp.NS_SI)
        con.RegisterHandler('iq', self._discoGetCB, 'get', nbxmpp.NS_DISCO)
        con.RegisterHandler('iq', self._bytestreamSetCB, 'set',
            nbxmpp.NS_BYTESTREAM)
        con.RegisterHandler('iq', self._bytestreamResultCB, 'result',
            nbxmpp.NS_BYTESTREAM)
        con.RegisterHandler('iq', self._bytestreamErrorCB, 'error',
            nbxmpp.NS_BYTESTREAM)
        con.RegisterHandlerOnce('iq', self.IBBAllIqHandler)
        con.RegisterHandler('iq', self.IBBIqHandler, ns=nbxmpp.NS_IBB)
        con.RegisterHandler('message', self.IBBMessageHandler, ns=nbxmpp.NS_IBB)
        con.RegisterHandler('iq', self._DiscoverItemsCB, 'result',
            nbxmpp.NS_DISCO_ITEMS)
        con.RegisterHandler('iq', self._DiscoverItemsErrorCB, 'error',
            nbxmpp.NS_DISCO_ITEMS)
        con.RegisterHandler('iq', self._DiscoverInfoCB, 'result',
            nbxmpp.NS_DISCO_INFO)
        con.RegisterHandler('iq', self._DiscoverInfoErrorCB, 'error',
            nbxmpp.NS_DISCO_INFO)
        con.RegisterHandler('iq', self._VersionCB, 'get', nbxmpp.NS_VERSION)
        con.RegisterHandler('iq', self._TimeCB, 'get', nbxmpp.NS_TIME)
        con.RegisterHandler('iq', self._TimeRevisedCB, 'get',
            nbxmpp.NS_TIME_REVISED)
        con.RegisterHandler('iq', self._LastCB, 'get', nbxmpp.NS_LAST)
        con.RegisterHandler('iq', self._VersionResultCB, 'result',
            nbxmpp.NS_VERSION)
        con.RegisterHandler('iq', self._TimeRevisedResultCB, 'result',
            nbxmpp.NS_TIME_REVISED)
        con.RegisterHandler('iq', self._MucOwnerCB, 'result',
            nbxmpp.NS_MUC_OWNER)
        con.RegisterHandler('iq', self._MucAdminCB, 'result',
            nbxmpp.NS_MUC_ADMIN)
        con.RegisterHandler('iq', self._PrivateCB, 'result', nbxmpp.NS_PRIVATE)
        con.RegisterHandler('iq', self._SecLabelCB, 'result',
            nbxmpp.NS_SECLABEL_CATALOG)
        con.RegisterHandler('iq', self._HttpAuthCB, 'get', nbxmpp.NS_HTTP_AUTH)
        con.RegisterHandler('iq', self._CommandExecuteCB, 'set',
            nbxmpp.NS_COMMANDS)
        con.RegisterHandler('iq', self._gMailNewMailCB, 'set',
            nbxmpp.NS_GMAILNOTIFY)
        con.RegisterHandler('iq', self._gMailQueryCB, 'result',
            nbxmpp.NS_GMAILNOTIFY)
        con.RegisterHandler('iq', self._DiscoverInfoGetCB, 'get',
            nbxmpp.NS_DISCO_INFO)
        con.RegisterHandler('iq', self._DiscoverItemsGetCB, 'get',
            nbxmpp.NS_DISCO_ITEMS)
        con.RegisterHandler('iq', self._IqPingCB, 'get', nbxmpp.NS_PING)
        con.RegisterHandler('iq', self._SearchCB, 'result', nbxmpp.NS_SEARCH)
        con.RegisterHandler('iq', self._PrivacySetCB, 'set', nbxmpp.NS_PRIVACY)
        con.RegisterHandler('iq', self._ArchiveCB, ns=nbxmpp.NS_MAM)
        con.RegisterHandler('iq', self._ArchiveCB, ns=nbxmpp.NS_MAM_1)
        con.RegisterHandler('iq', self._ArchiveCB, ns=nbxmpp.NS_MAM_2)
        con.RegisterHandler('iq', self._PubSubCB, 'result')
        con.RegisterHandler('iq', self._PubSubErrorCB, 'error')
        con.RegisterHandler('iq', self._JingleCB, 'result')
        con.RegisterHandler('iq', self._JingleCB, 'error')
        con.RegisterHandler('iq', self._JingleCB, 'set', nbxmpp.NS_JINGLE)
        con.RegisterHandler('iq', self._ErrorCB, 'error')
        con.RegisterHandler('iq', self._IqCB)
        con.RegisterHandler('iq', self._StanzaArrivedCB)
        con.RegisterHandler('iq', self._ResultCB, 'result')
        con.RegisterHandler('presence', self._StanzaArrivedCB)
        con.RegisterHandler('message', self._StanzaArrivedCB)
        con.RegisterHandler('unknown', self._StreamCB,
            nbxmpp.NS_XMPP_STREAMS, xmlns=nbxmpp.NS_STREAMS)
        con.RegisterHandler('iq', self._PubkeyGetCB, 'get',
            nbxmpp.NS_PUBKEY_PUBKEY)
        con.RegisterHandler('iq', self._PubkeyResultCB, 'result',
            nbxmpp.NS_PUBKEY_PUBKEY)
        con.RegisterHandler('iq', self._BlockingSetCB, 'set',
            nbxmpp.NS_BLOCKING)
