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

import hashlib
import binascii
import base64

import nbxmpp
from nbxmpp.namespaces import Namespace

from gajim.common import app
from gajim.common.const import RequestAvatar
from gajim.common.nec import NetworkEvent
from gajim.common.modules.base import BaseModule
from gajim.common.connection_handlers_events import InformationEvent


class VCardTemp(BaseModule):
    def __init__(self, con):
        BaseModule.__init__(self, con)

        self._own_vcard = None
        self.own_vcard_received = False
        self.room_jids = []
        self.supported = False

    def pass_disco(self, info):
        if Namespace.VCARD not in info.features:
            return

        self.supported = True
        self._log.info('Discovered vcard-temp: %s', info.jid)

        app.nec.push_incoming_event(NetworkEvent('feature-discovered',
                                                 account=self._account,
                                                 feature=Namespace.VCARD))

    @staticmethod
    def _node_to_dict(node):
        dict_ = {}
        for info in node.getChildren():
            name = info.getName()
            if name in ('ADR', 'TEL', 'EMAIL'):  # we can have several
                dict_.setdefault(name, [])
                entry = {}
                for child in info.getChildren():
                    entry[child.getName()] = child.getData()
                dict_[name].append(entry)
            elif info.getChildren() == []:
                dict_[name] = info.getData()
            else:
                dict_[name] = {}
                for child in info.getChildren():
                    dict_[name][child.getName()] = child.getData()
        return dict_

    def request_vcard(self, callback=RequestAvatar.SELF, jid=None,
                      room=False, sha=None):
        if not app.account_is_available(self._account):
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
        iq.setQuery('vCard').setNamespace(Namespace.VCARD)

        own_jid = self._con.get_own_jid().getStripped()
        self._log.info('Request: %s, expected sha: %s', jid or own_jid, sha)

        self._con.connection.SendAndCallForResponse(
            iq, self._parse_vcard, {'callback': callback, 'expected_sha': sha})

    def send_vcard(self, vcard, sha):
        if not app.account_is_available(self._account):
            return

        iq = nbxmpp.Iq(typ='set')
        iq2 = iq.setTag(Namespace.VCARD + ' vCard')
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

        self._log.info('Upload avatar: %s %s', self._account, sha)

        self._con.connection.SendAndCallForResponse(
            iq, self._avatar_publish_result, {'sha': sha})

    def upload_room_avatar(self, room_jid, data):
        iq = nbxmpp.Iq(typ='set', to=room_jid)
        vcard = iq.addChild('vCard', namespace=Namespace.VCARD)
        photo = vcard.addChild('PHOTO')
        photo.addChild('TYPE', payload='image/png')
        photo.addChild('BINVAL', payload=data)

        self._log.info('Upload avatar: %s', room_jid)
        self._con.connection.SendAndCallForResponse(
            iq, self._upload_room_avatar_result)

    @staticmethod
    def _upload_room_avatar_result(_nbxmpp_client, stanza):
        if not nbxmpp.isResultNode(stanza):
            reason = stanza.getErrorMsg() or stanza.getError()
            app.nec.push_incoming_event(InformationEvent(
                None, dialog_name='avatar-upload-error', args=reason))

    def _avatar_publish_result(self, _nbxmpp_client, stanza, sha):
        if stanza.getType() == 'result':
            current_sha = app.settings.get_account_setting(self._account,
                                                           'avatar_sha')
            if current_sha != sha:
                if not app.account_is_connected(self._account):
                    return
                app.settings.set_account_setting(
                    self._account, 'avatar_sha', sha or '')
                own_jid = self._con.get_own_jid().getStripped()
                app.contacts.set_avatar(self._account, own_jid, sha)
                app.interface.update_avatar(
                    self._account, self._con.get_own_jid().getStripped())
                self._con.get_module('VCardAvatars').send_avatar_presence(
                    after_publish=True)
            self._log.info('%s: Published: %s', self._account, sha)
            self._con.get_module('MUC').update_presence()
            app.nec.push_incoming_event(
                NetworkEvent('vcard-published', account=self._account))

        elif stanza.getType() == 'error':
            app.nec.push_incoming_event(
                NetworkEvent('vcard-not-published', account=self._account))

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
                    self._log.warning('Invalid avatar for %s: %s', jid, error)
                    return None, None
                avatar_sha = hashlib.sha1(photo_decoded).hexdigest()

        return avatar_sha, photo_decoded

    def _parse_vcard(self, _nbxmpp_client, stanza, callback, expected_sha):
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
            self._log.info('vCard not available: %s %s', frm_jid, stanza_error)
            callback(jid, resource, room, {}, expected_sha)
            return

        vcard_node = stanza.getTag('vCard', namespace=Namespace.VCARD)
        if vcard_node is None:
            self._log.info('vCard not available: %s', frm_jid)
            self._log.debug(stanza)
            return
        vcard = self._node_to_dict(vcard_node)

        if self._con.get_own_jid().bareMatch(jid):
            if 'NICKNAME' in vcard:
                app.nicks[self._account] = vcard['NICKNAME']
            elif 'FN' in vcard:
                app.nicks[self._account] = vcard['FN']

        app.nec.push_incoming_event(NetworkEvent('vcard-received',
                                                 account=self._account,
                                                 jid=jid,
                                                 vcard_dict=vcard))

        callback(jid, resource, room, vcard, expected_sha)

    def _on_own_avatar_received(self, jid, _resource, _room, vcard, *args):
        avatar_sha, photo_decoded = self._get_vcard_photo(vcard, jid)

        self._log.info('Received own vcard, avatar sha is: %s', avatar_sha)

        self._own_vcard = vcard
        self.own_vcard_received = True

        if avatar_sha is None:
            # No avatar found in vcard
            self._log.info('No avatar found')
            app.settings.set_account_setting(self._account, 'avatar_sha', '')
            app.contacts.set_avatar(self._account, jid, avatar_sha)
            self._con.get_module('VCardAvatars').send_avatar_presence(
                force=True)
            return

        # Avatar found in vcard
        current_sha = app.settings.get_account_setting(self._account,
                                                       'avatar_sha')
        if current_sha == avatar_sha:
            self._con.get_module('VCardAvatars').send_avatar_presence()
        else:
            app.interface.save_avatar(photo_decoded)
            app.contacts.set_avatar(self._account, jid, avatar_sha)
            app.settings.set_account_setting(
                self._account, 'avatar_sha', avatar_sha)
            self._con.get_module('VCardAvatars').send_avatar_presence(
                force=True)

        app.interface.update_avatar(self._account, jid)

    def _on_room_avatar_received(self, jid, _resource, _room, vcard,
                                 expected_sha):
        avatar_sha, photo_decoded = self._get_vcard_photo(vcard, jid)
        if expected_sha != avatar_sha:
            self._log.warning('Avatar mismatch: %s %s', jid, avatar_sha)
            return

        app.interface.save_avatar(photo_decoded)

        self._log.info('Received: %s %s', jid, avatar_sha)
        app.logger.set_muc_avatar_sha(jid, avatar_sha)
        app.contacts.set_avatar(self._account, jid, avatar_sha)
        app.interface.update_avatar(self._account, jid, room_avatar=True)

    def _on_avatar_received(self, jid, resource, room, vcard, expected_sha):
        request_jid = jid
        if room:
            request_jid = '%s/%s' % (jid, resource)

        avatar_sha, photo_decoded = self._get_vcard_photo(vcard, request_jid)
        if expected_sha != avatar_sha:
            self._log.warning('Received: avatar mismatch: %s %s',
                              request_jid, avatar_sha)
            return

        app.interface.save_avatar(photo_decoded)

        # Received vCard from a contact
        if room:
            self._log.info('Received: %s %s', resource, avatar_sha)
            contact = app.contacts.get_gc_contact(self._account, jid, resource)
            if contact is not None:
                contact.avatar_sha = avatar_sha
                app.interface.update_avatar(contact=contact)
        else:
            self._log.info('Received: %s %s', jid, avatar_sha)
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


def get_instance(*args, **kwargs):
    return VCardTemp(*args, **kwargs), 'VCardTemp'
