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

# XEP-0045: Multi-User Chat
# XEP-0249: Direct MUC Invitations

import time
import logging

import nbxmpp
from nbxmpp.const import InviteType
from nbxmpp.structs import StanzaHandler

from gajim.common import i18n
from gajim.common import app
from gajim.common import helpers
from gajim.common.caps_cache import muc_caps_cache
from gajim.common.nec import NetworkEvent
from gajim.common.modules.bits_of_binary import store_bob_data

log = logging.getLogger('gajim.c.m.muc')


class MUC:
    def __init__(self, con):
        self._con = con
        self._account = con.name

        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._on_subject_change,
                          typ='groupchat',
                          priority=49),
            StanzaHandler(name='message',
                          callback=self._on_config_change,
                          ns=nbxmpp.NS_MUC_USER,
                          priority=49),
            StanzaHandler(name='message',
                          callback=self._on_invite_or_decline,
                          typ='normal',
                          ns=nbxmpp.NS_MUC_USER,
                          priority=49),
            StanzaHandler(name='message',
                          callback=self._on_invite_or_decline,
                          ns=nbxmpp.NS_CONFERENCE,
                          priority=49),
            StanzaHandler(name='message',
                          callback=self._on_captcha_challenge,
                          ns=nbxmpp.NS_CAPTCHA,
                          priority=49),
            StanzaHandler(name='message',
                          callback=self._on_voice_request,
                          ns=nbxmpp.NS_DATA,
                          priority=49)
        ]

        self._nbmxpp_methods = [
            'get_affiliation',
            'set_role',
            'set_affiliation',
            'set_config',
            'set_subject',
            'cancel_config',
            'send_captcha',
            'decline',
            'request_voice'
            'destroy',
        ]

    def __getattr__(self, key):
        if key in self._nbmxpp_methods:
            if not app.account_is_connected(self._account):
                log.warning('Account %s not connected, cant use %s',
                            self._account, key)
                return
            module = self._con.connection.get_module('MUC')
            return getattr(module, key)

    def pass_disco(self, from_, identities, features, _data, _node):
        for identity in identities:
            if identity.get('category') != 'conference':
                continue
            if identity.get('type') != 'text':
                continue
            if nbxmpp.NS_MUC in features:
                log.info('Discovered MUC: %s', from_)
                # TODO: make this nicer
                self._con.muc_jid['jabber'] = from_
                raise nbxmpp.NodeProcessed

    def send_muc_join_presence(self, *args, room_jid=None, password=None,
                               rejoin=False, **kwargs):
        if not app.account_is_connected(self._account):
            return
        presence = self._con.get_module('Presence').get_presence(
            *args, **kwargs)

        muc_x = presence.setTag(nbxmpp.NS_MUC + ' x')
        if room_jid is not None:
            self._add_history_query(muc_x, room_jid, rejoin)

        if password is not None:
            muc_x.setTagData('password', password)

        log.debug('Send MUC join presence:\n%s', presence)

        self._con.connection.send(presence)

    def _add_history_query(self, muc_x, room_jid, rejoin):
        last_date = app.logger.get_room_last_message_time(
            self._account, room_jid)
        if not last_date:
            last_date = 0

        if muc_caps_cache.has_mam(room_jid):
            # The room is MAM capable dont get MUC History
            muc_x.setTag('history', {'maxchars': '0'})
        else:
            # Request MUC History (not MAM)
            tags = {}
            timeout = app.config.get_per('rooms', room_jid,
                                         'muc_restore_timeout')
            if timeout is None or timeout == -2:
                timeout = app.config.get('muc_restore_timeout')
            if last_date == 0 and timeout >= 0:
                last_date = time.time() - timeout * 60
            elif not rejoin and timeout >= 0:
                last_date = max(last_date, time.time() - timeout * 60)
            last_date = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(
                last_date))
            tags['since'] = last_date

            nb = app.config.get_per('rooms', room_jid, 'muc_restore_lines')
            if nb is None or nb == -2:
                nb = app.config.get('muc_restore_lines')
            if nb >= 0:
                tags['maxstanzas'] = nb
            if tags:
                muc_x.setTag('history', tags)

    def _on_subject_change(self, _con, _stanza, properties):
        if not properties.is_muc_subject:
            return

        jid = properties.jid.getBare()
        contact = app.contacts.get_groupchat_contact(self._account, jid)
        if contact is None:
            return

        contact.status = properties.subject

        app.nec.push_incoming_event(
            NetworkEvent('gc-subject-received',
                         account=self._account,
                         jid=jid,
                         subject=properties.subject,
                         nickname=properties.muc_nickname,
                         user_timestamp=properties.user_timestamp))
        raise nbxmpp.NodeProcessed

    def _on_voice_request(self, _con, _stanza, properties):
        if not properties.is_voice_request:
            return

        jid = str(properties.jid)
        contact = app.contacts.get_groupchat_contact(self._account, jid)
        if contact is None:
            return

        app.nec.push_incoming_event(
            NetworkEvent('voice-approval',
                         account=self._account,
                         jid=jid,
                         form=properties.voice_request.form))
        raise nbxmpp.NodeProcessed

    def _on_captcha_challenge(self, _con, _stanza, properties):
        if not properties.is_captcha_challenge:
            return

        contact = app.contacts.get_groupchat_contact(self._account,
                                                     str(properties.jid))
        if contact is None:
            return

        log.info('Captcha challenge received from %s', properties.jid)
        store_bob_data(properties.captcha.bob_data)

        app.nec.push_incoming_event(
            NetworkEvent('captcha-challenge',
                         account=self._account,
                         jid=properties.jid,
                         form=properties.captcha.form))
        raise nbxmpp.NodeProcessed

    def _on_config_change(self, _con, _stanza, properties):
        if not properties.is_muc_config_change:
            return

        log.info('Received config change: %s %s',
                 properties.jid, properties.muc_status_codes)
        app.nec.push_incoming_event(
            NetworkEvent('gc-config-changed-received',
                         account=self._account,
                         jid=properties.jid,
                         status_codes=properties.muc_status_codes))
        raise nbxmpp.NodeProcessed

    def _on_invite_or_decline(self, _con, _stanza, properties):
        if properties.muc_decline is not None:
            data = properties.muc_decline
            if helpers.ignore_contact(self._account, data.from_):
                raise nbxmpp.NodeProcessed

            log.info('Invite declined from: %s, reason: %s',
                     data.from_, data.reason)

            app.nec.push_incoming_event(
                NetworkEvent('gc-decline-received',
                             account=self._account,
                             **data._asdict()))
            raise nbxmpp.NodeProcessed

        if properties.muc_invite is not None:
            data = properties.muc_invite
            if helpers.ignore_contact(self._account, data.from_):
                raise nbxmpp.NodeProcessed

            log.info('Invite from: %s, to: %s', data.from_, data.muc)

            if app.in_groupchat(self._account, data.muc):
                # We are already in groupchat. Ignore invitation
                log.info('We are already in this room')
                raise nbxmpp.NodeProcessed

            app.nec.push_incoming_event(
                NetworkEvent('gc-invitation-received',
                             account=self._account,
                             **data._asdict()))
            raise nbxmpp.NodeProcessed

    def invite(self, room, to, reason=None, continue_=False):
        if not app.account_is_connected(self._account):
            return

        type_ = InviteType.MEDIATED
        contact = app.contacts.get_contact_from_full_jid(self._account, to)
        if contact and contact.supports(nbxmpp.NS_CONFERENCE):
            type_ = InviteType.DIRECT

        password = app.gc_passwords.get(room, None)
        self._con.connection.get_module('MUC').invite(
            room, to, reason, password, continue_, type_)

    def request_config(self, room_jid):
        if not app.account_is_connected(self._account):
            return

        self._con.connection.get_module('MUC').request_config(
            room_jid, i18n.LANG, callback=self._config_received)

    def _config_received(self, result):
        if result.is_error:
            return

        app.nec.push_incoming_event(NetworkEvent(
            'muc-owner-received',
            conn=self._con,
            dataform=result.form,
            jid=result.jid))


def get_instance(*args, **kwargs):
    return MUC(*args, **kwargs), 'MUC'
