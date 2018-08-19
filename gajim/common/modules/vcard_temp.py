# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

# XEP-0054: vcard-temp

import os
import hashlib
import binascii
import base64
import logging

import nbxmpp

from gajim.common import app
from gajim.common import configpaths
from gajim.common.const import RequestAvatar
from gajim.common.nec import NetworkIncomingEvent
from gajim.common.connection_handlers_events import InformationEvent

log = logging.getLogger('gajim.c.m.vcard')


class VCardTemp:
    def __init__(self, con):
        self._con = con
        self._account = con.name

        self.handlers = []

        self._own_vcard = None
        self.own_vcard_received = False
        self.room_jids = []
        self.supported = False

    def pass_disco(self, from_, identities, features, data, node):
        if nbxmpp.NS_VCARD not in features:
            return

        self.supported = True
        log.info('Discovered vcard-temp: %s', from_)
        # TODO: Move this GUI code out
        action = app.app.lookup_action('%s-profile' % self._account)
        action.set_enabled(True)

    def _node_to_dict(self, node):
        dict_ = {}
        for info in node.getChildren():
            name = info.getName()
            if name in ('ADR', 'TEL', 'EMAIL'):  # we can have several
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

    def request_vcard(self, callback=RequestAvatar.SELF, jid=None,
                      room=False, sha=None):
        if not app.account_is_connected(self._account):
            return

        if isinstance(callback, RequestAvatar):
            if callback == RequestAvatar.SELF:
                if not self.supported:
                    return
                callback = self._on_own_avatar_received
            elif callback == RequestAvatar.ROOM:
                callback = self._on_room_avatar_received
            elif callback == RequestAvatar.USER:
                callback = self._on_avatar_received

        if room:
            room_jid = app.get_room_from_fjid(jid)
            if room_jid not in self.room_jids:
                self.room_jids.append(room_jid)

        iq = nbxmpp.Iq(typ='get')
        if jid:
            iq.setTo(jid)
        iq.setQuery('vCard').setNamespace(nbxmpp.NS_VCARD)

        own_jid = self._con.get_own_jid().getStripped()
        log.info('Request: %s, expected sha: %s', jid or own_jid, sha)

        self._con.connection.SendAndCallForResponse(
            iq, self._parse_vcard, {'callback': callback, 'expected_sha': sha})

    def send_vcard(self, vcard, sha):
        if not app.account_is_connected(self._account):
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

        log.info('Upload avatar: %s %s', self._account, sha)

        self._con.connection.SendAndCallForResponse(
            iq, self._avatar_publish_result, {'sha': sha})

    def upload_room_avatar(self, room_jid, data):
        iq = nbxmpp.Iq(typ='set', to=room_jid)
        vcard = iq.addChild('vCard', namespace=nbxmpp.NS_VCARD)
        photo = vcard.addChild('PHOTO')
        photo.addChild('TYPE', payload='image/png')
        photo.addChild('BINVAL', payload=data)

        log.info('Upload avatar: %s', room_jid)
        self._con.connection.SendAndCallForResponse(
            iq, self._upload_room_avatar_result)

    def _upload_room_avatar_result(self, stanza):
        if not nbxmpp.isResultNode(stanza):
            reason = stanza.getErrorMsg() or stanza.getError()
            app.nec.push_incoming_event(InformationEvent(
                None, dialog_name='avatar-upload-error', args=reason))

    def _avatar_publish_result(self, con, stanza, sha):
        if stanza.getType() == 'result':
            current_sha = app.config.get_per(
                'accounts', self._account, 'avatar_sha')
            if (current_sha != sha and not app.is_invisible(self._account)):
                if not app.account_is_connected(self._account):
                    return
                app.config.set_per(
                    'accounts', self._account, 'avatar_sha', sha or '')
                own_jid = self._con.get_own_jid().getStripped()
                app.contacts.set_avatar(self._account, own_jid, sha)
                self._con.get_module('VCardAvatars').send_avatar_presence(
                    force=True)
            log.info('%s: Published: %s', self._account, sha)
            app.nec.push_incoming_event(
                VcardPublishedEvent(None, conn=self._con))

        elif stanza.getType() == 'error':
            app.nec.push_incoming_event(
                VcardNotPublishedEvent(None, conn=self._con))

    def _get_vcard_photo(self, vcard, jid):
        try:
            photo = vcard['PHOTO']['BINVAL']
        except (KeyError, AttributeError, TypeError):
            avatar_sha = None
            photo_decoded = None
        else:
            if photo == '':
                avatar_sha = None
                photo_decoded = None
            else:
                try:
                    photo_decoded = base64.b64decode(photo.encode('utf-8'))
                except binascii.Error as error:
                    log.warning('Invalid avatar for %s: %s', jid, error)
                    return None, None
                avatar_sha = hashlib.sha1(photo_decoded).hexdigest()

        return avatar_sha, photo_decoded

    def _parse_vcard(self, con, stanza, callback, expected_sha):
        frm_jid = stanza.getFrom()
        room = False
        if frm_jid is None:
            frm_jid = self._con.get_own_jid()
        elif frm_jid.getStripped() in self.room_jids:
            room = True

        resource = frm_jid.getResource()
        jid = frm_jid.getStripped()

        stanza_error = stanza.getError()
        if stanza_error in ('service-unavailable', 'item-not-found',
                            'not-allowed'):
            log.info('vCard not available: %s %s', frm_jid, stanza_error)
            callback(jid, resource, room, {}, expected_sha)
            return

        vcard_node = stanza.getTag('vCard', namespace=nbxmpp.NS_VCARD)
        if vcard_node is None:
            log.info('vCard not available: %s', frm_jid)
            log.debug(stanza)
            return
        vcard = self._node_to_dict(vcard_node)

        if self._con.get_own_jid().bareMatch(jid):
            if 'NICKNAME' in vcard:
                app.nicks[self._account] = vcard['NICKNAME']
            elif 'FN' in vcard:
                app.nicks[self._account] = vcard['FN']

        app.nec.push_incoming_event(
            VcardReceivedEvent(None, conn=self._con,
                               vcard_dict=vcard,
                               jid=jid))

        callback(jid, resource, room, vcard, expected_sha)

    def _on_own_avatar_received(self, jid, resource, room, vcard, *args):
        avatar_sha, photo_decoded = self._get_vcard_photo(vcard, jid)

        log.info('Received own vcard, avatar sha is: %s', avatar_sha)

        self._own_vcard = vcard
        self.own_vcard_received = True
        if avatar_sha is None:
            log.info('No avatar found')
            app.config.set_per('accounts', self._account, 'avatar_sha', '')
            self._con.get_module('VCardAvatars').send_avatar_presence(force=True)
            return

        current_sha = app.config.get_per('accounts', self._account, 'avatar_sha')
        if current_sha == avatar_sha:
            path = os.path.join(configpaths.get('AVATAR'), current_sha)
            if not os.path.isfile(path):
                log.info('Caching: %s', current_sha)
                app.interface.save_avatar(photo_decoded)
            self._con.get_module('VCardAvatars').send_avatar_presence()
        else:
            app.interface.save_avatar(photo_decoded)

        app.config.set_per('accounts', self._account, 'avatar_sha', avatar_sha)
        if app.is_invisible(self._account):
            log.info('We are invisible, not advertising avatar')
            return

        self._con.get_module('VCardAvatars').send_avatar_presence(force=True)

    def _on_room_avatar_received(self, jid, resource, room, vcard,
                                 expected_sha):
        avatar_sha, photo_decoded = self._get_vcard_photo(vcard, jid)
        if expected_sha != avatar_sha:
            log.warning('Avatar mismatch: %s %s', jid, avatar_sha)
            return

        app.interface.save_avatar(photo_decoded)

        log.info('Received: %s %s', jid, avatar_sha)
        app.contacts.set_avatar(self._account, jid, avatar_sha)
        app.interface.update_avatar(self._account, jid, room_avatar=True)

    def _on_avatar_received(self, jid, resource, room, vcard, expected_sha):
        request_jid = jid
        if room:
            request_jid = '%s/%s' % (jid, resource)

        avatar_sha, photo_decoded = self._get_vcard_photo(vcard, request_jid)
        if expected_sha != avatar_sha:
            log.warning('Received: avatar mismatch: %s %s',
                        request_jid, avatar_sha)
            return

        app.interface.save_avatar(photo_decoded)

        # Received vCard from a contact
        if room:
            log.info('Received: %s %s', resource, avatar_sha)
            contact = app.contacts.get_gc_contact(self._account, jid, resource)
            if contact is not None:
                contact.avatar_sha = avatar_sha
                app.interface.update_avatar(contact=contact)
        else:
            log.info('Received: %s %s', jid, avatar_sha)
            own_jid = self._con.get_own_jid().getStripped()
            app.logger.set_avatar_sha(own_jid, jid, avatar_sha)
            app.contacts.set_avatar(self._account, jid, avatar_sha)
            app.interface.update_avatar(self._account, jid)

    def get_vard_name(self):
        name = ''
        vcard = self._own_vcard
        if not vcard:
            return name

        if 'N' in vcard:
            if 'GIVEN' in vcard['N'] and 'FAMILY' in vcard['N']:
                name = vcard['N']['GIVEN'] + ' ' + vcard['N']['FAMILY']
        if not name and 'FN' in vcard:
            name = vcard['FN']
        return name


class VcardPublishedEvent(NetworkIncomingEvent):
    name = 'vcard-published'
    base_network_events = []


class VcardNotPublishedEvent(NetworkIncomingEvent):
    name = 'vcard-not-published'
    base_network_events = []


class VcardReceivedEvent(NetworkIncomingEvent):
    name = 'vcard-received'
    base_network_events = []


def get_instance(*args, **kwargs):
    return VCardTemp(*args, **kwargs), 'VCardTemp'
