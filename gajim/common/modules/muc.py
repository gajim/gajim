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
from functools import partial

import nbxmpp
from nbxmpp.const import InviteType
from nbxmpp.const import PresenceType
from nbxmpp.const import Error
from nbxmpp.structs import StanzaHandler
from nbxmpp.util import is_error_result

from gajim.common import app
from gajim.common import helpers
from gajim.common.const import KindConstant
from gajim.common.const import MUCJoinedState
from gajim.common.structs import MUCData
from gajim.common.helpers import AdditionalDataDict
from gajim.common import idle
from gajim.common.caps_cache import muc_caps_cache
from gajim.common.nec import NetworkEvent
from gajim.common.modules.bits_of_binary import store_bob_data
from gajim.common.modules.base import BaseModule


log = logging.getLogger('gajim.c.m.muc')


class MUC(BaseModule):

    _nbxmpp_extends = 'MUC'
    _nbxmpp_methods = [
        'get_affiliation',
        'set_role',
        'set_affiliation',
        'set_config',
        'set_subject',
        'cancel_config',
        'send_captcha',
        'decline',
        'invite',
        'request_config',
        'request_voice',
        'destroy',
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='presence',
                          callback=self._on_muc_user_presence,
                          ns=nbxmpp.NS_MUC_USER,
                          priority=49),
            StanzaHandler(name='presence',
                          callback=self._on_muc_presence,
                          typ='error',
                          ns=nbxmpp.NS_MUC,
                          priority=49),
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

        self._register_callback('request_config', self._config_received)

        self._muc_data = {}

    def pass_disco(self, from_, identities, features, _data, _node):
        for identity in identities:
            if identity.get('category') != 'conference':
                continue
            if identity.get('type') != 'text':
                continue
            if nbxmpp.NS_MUC in features:
                self._log.info('Discovered MUC: %s', from_)
                # TODO: make this nicer
                self._con.muc_jid['jabber'] = from_
                raise nbxmpp.NodeProcessed

    def _get_muc_data(self, room_jid):
        return self._muc_data[room_jid]

    def _set_muc_state(self, room_jid, state):
        if self._muc_data[room_jid].state == state:
            return
        self._log.info('Set MUC state: %s %s', room_jid, state)
        self._muc_data[room_jid].state = state

    def _get_muc_state(self, room_jid):
        return self._muc_data[room_jid].state

    def join(self, room_jid, nick, password, rejoin=False):
        if not app.account_is_connected(self._account):
            return

        self._muc_data[room_jid] = MUCData(room_jid, nick, password, rejoin)

        self._con.get_module('Discovery').disco_muc(
            room_jid, partial(self._join, room_jid))

    def _join(self, room_jid):
        show = helpers.get_xmpp_show(app.SHOW_LIST[self._con.connected])
        muc = self._get_muc_data(room_jid)

        presence = self._con.get_module('Presence').get_presence(
            '%s/%s' % (room_jid, muc.nick),
            show=show,
            status=self._con.status)

        muc_x = presence.setTag(nbxmpp.NS_MUC + ' x')
        if room_jid is not None:
            self._add_history_query(muc_x, room_jid, muc.rejoin)

        if muc.password is not None:
            muc_x.setTagData('password', muc.password)

        self._log.info('Join MUC: %s', room_jid)
        self._set_muc_state(room_jid, MUCJoinedState.JOINING)
        self._con.connection.send(presence)

    def leave(self, room_jid):
        self._log.info('Leave MUC: %s', room_jid)
        self._set_muc_state(room_jid, MUCJoinedState.NOT_JOINED)
        muc = self._get_muc_data(room_jid)
        self._con.get_module('Presence').send_presence(
            '%s/%s' % (room_jid, muc.nick),
            typ='unavailable')

    def send_muc_presence(self, room_jid, auto=False):
        show = app.SHOW_LIST[self._con.connected]
        if show in ('invisible', 'offline'):
            # FIXME: Check if this
            return

        muc = self._get_muc_data(room_jid)
        status = self._con.status

        xmpp_show = helpers.get_xmpp_show(show)

        idle_time = None
        if auto and app.is_installed('IDLE') and app.config.get('autoaway'):
            idle_sec = idle.Monitor.get_idle_sec()
            idle_time = time.strftime('%Y-%m-%dT%H:%M:%SZ',
                                      time.gmtime(time.time() - idle_sec))

        full_jid = '%s/%s' % (room_jid, muc.nick)

        self._log.info('Send presence: %s, show: %s, status: %s, idle_time: %s',
                       full_jid, xmpp_show, status, idle_time)

        self._con.get_module('Presence').send_presence(
            full_jid,
            show=xmpp_show,
            status=status,
            caps=True,
            idle_time=idle_time)

    def change_nick(self, room_jid, new_nick):
        show = helpers.get_xmpp_show(app.SHOW_LIST[self._con.connected])
        self._con.get_module('Presence').send_presence(
            '%s/%s' % (room_jid, new_nick),
            show=show,
            status=self._con.status)

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

    def _on_muc_presence(self, _con, _stanza, properties):
        muc = self._get_muc_data(properties.jid.getBare())
        if (properties.error.type == Error.CONFLICT and
                muc.state == MUCJoinedState.JOINING):
            muc.nick += '_'
            self._log.info('Nickname conflict: %s change to %s',
                           muc.jid, muc.nick)
            self._join(muc.jid)
            return
        self._raise_muc_event('muc-presence-error', properties)

    def _on_muc_user_presence(self, _con, stanza, properties):
        if properties.type == PresenceType.ERROR:
            return

        room_jid = properties.jid.getBare()
        if room_jid not in self._muc_data:
            self._log.warning('Presence from unknown MUC')
            self._log.warning(stanza)
            return

        if properties.is_muc_destroyed:
            for contact in app.contacts.get_gc_contact_list(
                    self._account, room_jid):
                contact.presence = PresenceType.UNAVAILABLE
            self._log.info('MUC destroyed: %s', room_jid)
            self._set_muc_state(room_jid, MUCJoinedState.NOT_JOINED)
            self._raise_muc_event('muc-destroyed', properties)
            return

        contact = app.contacts.get_gc_contact(self._account,
                                              properties.jid.getBare(),
                                              properties.muc_nickname)

        if properties.is_nickname_changed:
            app.contacts.remove_gc_contact(self._account, contact)
            contact.name = properties.muc_user.nick
            app.contacts.add_gc_contact(self._account, contact)
            self._log.info('Nickname changed: %s to %s',
                           properties.jid,
                           properties.muc_user.nick)
            self._get_muc_data(room_jid).nick = properties.muc_user.nick
            self._raise_muc_event('muc-nickname-changed', properties)
            return

        if contact is None and properties.type.is_available:
            self._add_new_muc_contact(properties)
            if properties.is_muc_self_presence:
                self._log.info('Self presence: %s', properties.jid)
                self._raise_muc_event('muc-self-presence', properties)
            else:
                self._log.info('User joined: %s', properties.jid)
                self._raise_muc_event('muc-user-joined', properties)
            return

        if properties.is_muc_self_presence and properties.is_kicked:
            self._set_muc_state(room_jid, MUCJoinedState.NOT_JOINED)
            self._raise_muc_event('muc-self-kicked', properties)
            return

        if properties.is_muc_self_presence and properties.type.is_unavailable:
            # Its not a kick, so this is the reflection of our own
            # unavailable presence, because we left the MUC
            return

        if properties.type.is_unavailable:
            for _event in app.events.get_events(self._account,
                                                jid=str(properties.jid),
                                                types=['pm']):
                contact.show = properties.show
                contact.presence = properties.type
                contact.status = properties.status
                contact.affiliation = properties.affiliation
                app.interface.handle_event(self._account,
                                           str(properties.jid),
                                           'pm')
                # Handle only the first pm event, the rest will be
                # handled by the opened ChatControl
                break

            if contact is None:
                # If contact is None, its probably that a user left from a not
                # insync MUC, can happen on older servers
                self._log.warning('Unknown contact left groupchat: %s',
                                  properties.jid)
            else:
                # We remove the contact from the MUC, but there could be
                # a PrivateChatControl open, so we update the contacts presence
                contact.presence = properties.type
                app.contacts.remove_gc_contact(self._account, contact)
            self._log.info('User %s left', properties.jid)
            self._raise_muc_event('muc-user-left', properties)
            return

        if contact.affiliation != properties.affiliation:
            contact.affiliation = properties.affiliation
            self._log.info('Affiliation changed: %s %s',
                           properties.jid,
                           properties.affiliation)
            self._raise_muc_event('muc-user-affiliation-changed', properties)

        if contact.role != properties.role:
            contact.role = properties.role
            self._log.info('Role changed: %s %s',
                           properties.jid,
                           properties.role)
            self._raise_muc_event('muc-user-role-changed', properties)

        if (contact.status != properties.status or
                contact.show != properties.show):
            contact.status = properties.status
            contact.show = properties.show
            self._log.info('Show/Status changed: %s %s %s',
                           properties.jid,
                           properties.status,
                           properties.show)
            self._raise_muc_event('muc-user-status-show-changed', properties)

    def _raise_muc_event(self, event_name, properties):
        app.nec.push_incoming_event(
            NetworkEvent(event_name,
                         account=self._account,
                         room_jid=properties.jid.getBare(),
                         properties=properties))
        self._log_muc_event(event_name, properties)

    def _log_muc_event(self, event_name, properties):
        if event_name not in ['muc-user-joined',
                              'muc-user-left',
                              'muc-user-status-show-changed']:
            return

        if (not app.config.get('log_contact_status_changes') or
                not app.config.should_log(self._account, properties.jid)):
            return

        additional_data = AdditionalDataDict()
        if properties.muc_user is not None:
            if properties.muc_user.jid is not None:
                additional_data.set_value(
                    'gajim', 'real_jid', str(properties.muc_user.jid))

        # TODO: Refactor
        if properties.type == PresenceType.UNAVAILABLE:
            show = 'offline'
        else:
            show = properties.show.value
        show = app.logger.convert_show_values_to_db_api_values(show)

        app.logger.insert_into_logs(
            self._account,
            properties.jid.getBare(),
            properties.timestamp,
            KindConstant.GCSTATUS,
            contact_name=properties.muc_nickname,
            message=properties.status or None,
            show=show,
            additional_data=additional_data)

    def _add_new_muc_contact(self, properties):
        real_jid = None
        if properties.muc_user.jid is not None:
            real_jid = str(properties.muc_user.jid)
        contact = app.contacts.create_gc_contact(
            room_jid=properties.jid.getBare(),
            account=self._account,
            name=properties.muc_nickname,
            show=properties.show,
            status=properties.status,
            presence=properties.type,
            role=properties.role,
            affiliation=properties.affiliation,
            jid=real_jid,
            avatar_sha=properties.avatar_sha)
        app.contacts.add_gc_contact(self._account, contact)

    def _on_subject_change(self, _con, _stanza, properties):
        if not properties.is_muc_subject:
            return

        jid = properties.jid.getBare()
        contact = app.contacts.get_groupchat_contact(self._account, jid)
        if contact is None:
            return

        contact.status = properties.subject

        app.nec.push_incoming_event(
            NetworkEvent('muc-subject',
                         account=self._account,
                         room_jid=jid,
                         subject=properties.subject,
                         nickname=properties.muc_nickname,
                         user_timestamp=properties.user_timestamp))

        if self._get_muc_state(jid) == MUCJoinedState.JOINING:
            self._set_muc_state(jid, MUCJoinedState.JOINED)

        raise nbxmpp.NodeProcessed

    def _on_voice_request(self, _con, _stanza, properties):
        if not properties.is_voice_request:
            return

        jid = str(properties.jid)
        contact = app.contacts.get_groupchat_contact(self._account, jid)
        if contact is None:
            return

        app.nec.push_incoming_event(
            NetworkEvent('muc-voice-approval',
                         account=self._account,
                         room_jid=properties.jid.getBare(),
                         form=properties.voice_request.form))
        raise nbxmpp.NodeProcessed

    def _on_captcha_challenge(self, _con, _stanza, properties):
        if not properties.is_captcha_challenge:
            return

        contact = app.contacts.get_groupchat_contact(self._account,
                                                     str(properties.jid))
        if contact is None:
            return

        self._log.info('Captcha challenge received from %s', properties.jid)
        store_bob_data(properties.captcha.bob_data)

        app.nec.push_incoming_event(
            NetworkEvent('muc-captcha-challenge',
                         account=self._account,
                         room_jid=properties.jid.getBare(),
                         form=properties.captcha.form))
        raise nbxmpp.NodeProcessed

    def _on_config_change(self, _con, _stanza, properties):
        if not properties.is_muc_config_change:
            return

        room_jid = properties.jid.getBare()
        self._log.info('Received config change: %s %s',
                       room_jid, properties.muc_status_codes)
        app.nec.push_incoming_event(
            NetworkEvent('muc-config-changed',
                         account=self._account,
                         room_jid=room_jid,
                         status_codes=properties.muc_status_codes))
        raise nbxmpp.NodeProcessed

    def _on_invite_or_decline(self, _con, _stanza, properties):
        if properties.muc_decline is not None:
            data = properties.muc_decline
            if helpers.ignore_contact(self._account, data.from_):
                raise nbxmpp.NodeProcessed

            self._log.info('Invite declined from: %s, reason: %s',
                           data.from_, data.reason)

            app.nec.push_incoming_event(
                NetworkEvent('muc-decline',
                             account=self._account,
                             **data._asdict()))
            raise nbxmpp.NodeProcessed

        if properties.muc_invite is not None:
            data = properties.muc_invite
            if helpers.ignore_contact(self._account, data.from_):
                raise nbxmpp.NodeProcessed

            self._log.info('Invite from: %s, to: %s', data.from_, data.muc)

            if app.in_groupchat(self._account, data.muc):
                # We are already in groupchat. Ignore invitation
                self._log.info('We are already in this room')
                raise nbxmpp.NodeProcessed

            app.nec.push_incoming_event(
                NetworkEvent('muc-invitation',
                             account=self._account,
                             **data._asdict()))
            raise nbxmpp.NodeProcessed

    def invite(self, room, to, reason=None, continue_=False):
        type_ = InviteType.MEDIATED
        contact = app.contacts.get_contact_from_full_jid(self._account, to)
        if contact and contact.supports(nbxmpp.NS_CONFERENCE):
            type_ = InviteType.DIRECT

        password = app.gc_passwords.get(room, None)
        self._nbxmpp('MUC').invite(room, to, reason, password, continue_, type_)

    def _config_received(self, result):
        if is_error_result(result):
            return

        app.nec.push_incoming_event(NetworkEvent(
            'muc-config',
            conn=self._con,
            dataform=result.form,
            jid=result.jid))


def get_instance(*args, **kwargs):
    return MUC(*args, **kwargs), 'MUC'
