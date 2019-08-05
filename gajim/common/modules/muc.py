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
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from functools import partial

import nbxmpp
from nbxmpp.const import InviteType
from nbxmpp.const import PresenceType
from nbxmpp.const import Error
from nbxmpp.structs import StanzaHandler
from nbxmpp.util import is_error_result

from gi.repository import GLib

from gajim.common import app
from gajim.common import helpers
from gajim.common.const import KindConstant
from gajim.common.const import MUCJoinedState
from gajim.common.const import SyncThreshold
from gajim.common.helpers import AdditionalDataDict
from gajim.common.helpers import get_default_muc_config
from gajim.common.helpers import get_sync_threshold
from gajim.common.helpers import to_user_string
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
        'cancel_captcha',
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
                          callback=self._on_error_presence,
                          typ='error',
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

        self._muc_data = {}
        self._join_timeouts = {}

    def pass_disco(self, info):
        for identity in info.identities:
            if identity.category != 'conference':
                continue
            if identity.type != 'text':
                continue
            if nbxmpp.NS_MUC in info.features:
                self._log.info('Discovered MUC: %s', info.jid)
                # TODO: make this nicer
                self._con.muc_jid['jabber'] = str(info.jid)
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

    def get_mucs_with_state(self, states):
        return [muc for muc in self._muc_data.values() if muc.state in states]

    def join(self, muc_data):
        if not app.account_is_connected(self._account):
            return

        self._muc_data[muc_data.jid] = muc_data

        self._con.get_module('Discovery').disco_muc(
            muc_data.jid, partial(self._join, muc_data))

    def _join(self, muc_data):
        show = helpers.get_xmpp_show(app.SHOW_LIST[self._con.connected])

        presence = self._con.get_module('Presence').get_presence(
            muc_data.occupant_jid,
            show=show,
            status=self._con.status)

        muc_x = presence.setTag(nbxmpp.NS_MUC + ' x')
        self._add_history_query(muc_x, str(muc_data.jid))

        if muc_data.password is not None:
            muc_x.setTagData('password', muc_data.password)

        self._log.info('Join MUC: %s', muc_data.jid)
        self._set_muc_state(muc_data.jid, MUCJoinedState.JOINING)
        self._con.connection.send(presence)

    def leave(self, room_jid, reason=None):
        self._log.info('Leave MUC: %s', room_jid)
        self._remove_join_timeout(room_jid)
        self._set_muc_state(room_jid, MUCJoinedState.NOT_JOINED)
        muc_data = self._get_muc_data(room_jid)
        self._con.get_module('Presence').send_presence(
            muc_data.occupant_jid,
            typ='unavailable',
            status=reason)
        # We leave a group chat, disable bookmark autojoin
        self._con.get_module('Bookmarks').set_autojoin(room_jid, False)

    def configure_room(self, room_jid):
        self._nbxmpp('MUC').request_config(room_jid,
                                           callback=self._on_room_config)

    def _on_room_config(self, result):
        if is_error_result(result):
            self._log.info(result)
            app.nec.push_incoming_event(NetworkEvent(
                'muc-configuration-failed',
                account=self._account,
                room_jid=result.jid,
                error=result))
            return

        self._log.info('Configure room: %s', result.jid)

        muc_data = self._get_muc_data(result.jid)
        self._apply_config(result.form, muc_data.config)
        self.set_config(result.jid,
                        result.form,
                        callback=self._on_config_result)

    @staticmethod
    def _apply_config(form, config=None):
        default_config = get_default_muc_config()
        if config is not None:
            default_config.update(config)
        for var, value in default_config.items():
            try:
                field = form[var]
            except KeyError:
                pass
            else:
                field.value = value

    def _on_config_result(self, result):
        if is_error_result(result):
            self._log.info(result)
            app.nec.push_incoming_event(NetworkEvent(
                'muc-configuration-failed',
                account=self._account,
                room_jid=result.jid,
                error=result))
            return

        self._log.info('Configuration finished: %s', result.jid)
        app.nec.push_incoming_event(NetworkEvent(
            'muc-configuration-finished',
            account=self._account,
            room_jid=result.jid))

        self._con.get_module('Discovery').disco_muc(
            result.jid, partial(self._on_disco_update, result.jid), update=True)

        # If this is an automatic room creation
        try:
            invites = app.automatic_rooms[self._account][result.jid]['invities']
        except KeyError:
            return

        user_list = {}
        for jid in invites:
            user_list[jid] = {'affiliation': 'member'}
        self.set_affiliation(result.jid, user_list)

        for jid in invites:
            self.invite(result.jid, jid)

    def _on_disco_update(self, room_jid):
        app.nec.push_incoming_event(NetworkEvent(
            'muc-disco-update',
            account=self._account,
            room_jid=room_jid))

    def update_presence(self, auto=False):
        mucs = self.get_mucs_with_state([MUCJoinedState.JOINED,
                                         MUCJoinedState.JOINING])
        for muc_data in mucs:
            self._send_presence(muc_data, auto)

    def _send_presence(self, muc_data, auto):
        show = app.SHOW_LIST[self._con.connected]
        if show in ('invisible', 'offline'):
            # FIXME: Check if this
            return

        status = self._con.status

        xmpp_show = helpers.get_xmpp_show(show)

        idle_time = None
        if auto and app.is_installed('IDLE') and app.config.get('autoaway'):
            idle_sec = idle.Monitor.get_idle_sec()
            idle_time = time.strftime('%Y-%m-%dT%H:%M:%SZ',
                                      time.gmtime(time.time() - idle_sec))

        self._log.info('Send presence: %s, show: %s, status: %s, idle_time: %s',
                       muc_data.occupant_jid, xmpp_show, status, idle_time)

        self._con.get_module('Presence').send_presence(
            muc_data.occupant_jid,
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

    def _add_history_query(self, muc_x, room_jid):
        if muc_caps_cache.has_mam(room_jid):
            # The room is MAM capable dont get MUC History
            muc_x.setTag('history', {'maxchars': '0'})
        else:
            # Request MUC History (not MAM)
            archive = app.logger.get_archive_infos(room_jid)
            threshold = get_sync_threshold(room_jid, archive)

            since_epoch = 0
            if archive is not None and archive.last_muc_timestamp is not None:
                since_epoch = float(archive.last_muc_timestamp)

            since_date = datetime.fromtimestamp(since_epoch, timezone.utc)
            if threshold != SyncThreshold.NO_THRESHOLD:
                now = datetime.now(timezone.utc)
                threshold_date = now - timedelta(days=threshold)
                since_date = max(threshold_date, since_date)

            date_string = since_date.strftime('%Y-%m-%dT%H:%M:%SZ')
            muc_x.setTag('history', {'since': date_string})
            self._log.info('Request MUC history since: %s (%s)',
                           date_string, since_date.timestamp())
            self._log.info('Threshold for %s: %s', room_jid, threshold)

    def _on_error_presence(self, _con, _stanza, properties):
        room_jid = properties.jid.getBare()
        muc_data = self._muc_data.get(room_jid)
        if muc_data is None:
            return

        if muc_data.state == MUCJoinedState.JOINING:
            if properties.error.type == Error.CONFLICT:
                muc_data.nick += '_'
                self._log.info('Nickname conflict: %s change to %s',
                               muc_data.jid, muc_data.nick)
                self._join(muc_data)
            elif properties.error.type == Error.NOT_AUTHORIZED:
                self._raise_muc_event('muc-password-required', properties)
            else:
                self._raise_muc_event('muc-join-failed', properties)
                self._set_muc_state(room_jid, MUCJoinedState.NOT_JOINED)

        elif muc_data.state == MUCJoinedState.CAPTCHA_REQUEST:
            app.nec.push_incoming_event(
                NetworkEvent('muc-captcha-error',
                             account=self._account,
                             room_jid=room_jid,
                             error_text=properties.error.message))
            self._set_muc_state(room_jid, MUCJoinedState.CAPTCHA_FAILED)
            self._set_muc_state(room_jid, MUCJoinedState.NOT_JOINED)

        elif muc_data.state == MUCJoinedState.CAPTCHA_FAILED:
            self._set_muc_state(room_jid, MUCJoinedState.NOT_JOINED)

        else:
            self._raise_muc_event('muc-presence-error', properties)

    def _on_muc_user_presence(self, _con, stanza, properties):
        if properties.type == PresenceType.ERROR:
            return

        room_jid = str(properties.muc_jid)
        if room_jid not in self._muc_data:
            self._log.warning('Presence from unknown MUC')
            self._log.warning(stanza)
            return

        muc_data = self._get_muc_data(room_jid)

        if properties.is_muc_destroyed:
            for contact in app.contacts.get_gc_contact_list(
                    self._account, room_jid):
                contact.presence = PresenceType.UNAVAILABLE
            self._log.info('MUC destroyed: %s', room_jid)
            self._remove_join_timeout(room_jid)
            self._set_muc_state(room_jid, MUCJoinedState.NOT_JOINED)
            self._raise_muc_event('muc-destroyed', properties)
            return

        contact = app.contacts.get_gc_contact(self._account,
                                              room_jid,
                                              properties.muc_nickname)

        if properties.is_nickname_changed:
            if properties.is_muc_self_presence:
                muc_data.nick = properties.muc_user.nick
            app.contacts.remove_gc_contact(self._account, contact)
            contact.name = properties.muc_user.nick
            app.contacts.add_gc_contact(self._account, contact)
            self._log.info('Nickname changed: %s to %s',
                           properties.jid,
                           properties.muc_user.nick)
            self._raise_muc_event('muc-nickname-changed', properties)
            return

        if contact is None and properties.type.is_available:
            self._add_new_muc_contact(properties)
            if properties.is_muc_self_presence:
                self._log.info('Self presence: %s', properties.jid)
                self._raise_muc_event('muc-self-presence', properties)
                if muc_data.state == MUCJoinedState.JOINING:
                    self._start_join_timeout(room_jid)
                if properties.is_new_room:
                    self.configure_room(room_jid)
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

    def _start_join_timeout(self, room_jid):
        self._remove_join_timeout(room_jid)
        self._log.info('Start join timeout for: %s', room_jid)
        id_ = GLib.timeout_add_seconds(
            10, self._fake_subject_change, room_jid)
        self._join_timeouts[room_jid] = id_

    def _remove_join_timeout(self, room_jid):
        id_ = self._join_timeouts.get(room_jid)
        if id_ is not None:
            self._log.info('Remove join timeout for: %s', room_jid)
            GLib.source_remove(id_)
            del self._join_timeouts[room_jid]

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

        self._handle_subject_change(str(properties.muc_jid),
                                    properties.subject,
                                    properties.muc_nickname,
                                    properties.user_timestamp)

        raise nbxmpp.NodeProcessed

    def _fake_subject_change(self, room_jid):
        # This is for servers which dont send empty subjects as part of the
        # event order on joining a MUC. For example jabber.ru
        self._log.warning('Fake subject received for %s', room_jid)
        del self._join_timeouts[room_jid]
        self._handle_subject_change(room_jid, None, None, None)

    def _handle_subject_change(self, room_jid, subject, nickname, timestamp):
        contact = app.contacts.get_groupchat_contact(self._account, room_jid)
        if contact is None:
            return

        contact.status = subject

        app.nec.push_incoming_event(
            NetworkEvent('muc-subject',
                         account=self._account,
                         room_jid=room_jid,
                         subject=subject,
                         nickname=nickname,
                         user_timestamp=timestamp,
                         is_fake=subject is None))

        muc_data = self._get_muc_data(room_jid)
        if muc_data.state == MUCJoinedState.JOINING:
            self._remove_join_timeout(room_jid)
            self._set_muc_state(room_jid, MUCJoinedState.JOINED)

            app.nec.push_incoming_event(
                NetworkEvent('muc-joined',
                             account=self._account,
                             room_jid=room_jid))

            # We successfully joined a MUC, set autojoin bookmark
            self._con.get_module('Bookmarks').add_bookmark(None,
                                                           muc_data.jid,
                                                           True,
                                                           muc_data.password,
                                                           muc_data.nick)

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
                         room_jid=str(properties.muc_jid),
                         form=properties.voice_request.form))
        raise nbxmpp.NodeProcessed

    def _on_captcha_challenge(self, _con, _stanza, properties):
        if not properties.is_captcha_challenge:
            return

        if properties.is_mam_message:
            # Some servers store captcha challenges in MAM, dont process them
            self._log.warning('Ignore captcha challenge received from MAM')
            raise nbxmpp.NodeProcessed

        muc_data = self._muc_data.get(properties.jid)
        if muc_data is None:
            return

        if muc_data.state != MUCJoinedState.JOINING:
            self._log.warning('Received captcha request but state != %s',
                              MUCJoinedState.JOINING)
            return

        contact = app.contacts.get_groupchat_contact(self._account,
                                                     str(properties.jid))
        if contact is None:
            return

        self._log.info('Captcha challenge received from %s', properties.jid)
        store_bob_data(properties.captcha.bob_data)
        muc_data.captcha_id = properties.id

        self._set_muc_state(properties.jid, MUCJoinedState.CAPTCHA_REQUEST)

        app.nec.push_incoming_event(
            NetworkEvent('muc-captcha-challenge',
                         account=self._account,
                         room_jid=properties.jid.getBare(),
                         form=properties.captcha.form))
        raise nbxmpp.NodeProcessed

    def cancel_captcha(self, room_jid):
        muc_data = self._muc_data.get(room_jid)
        if muc_data is None:
            return

        if muc_data.captcha_id is None:
            self._log.warning('No captcha message id available')
            return
        self._nbxmpp('MUC').cancel_captcha(room_jid, muc_data.captcha_id)
        self._set_muc_state(room_jid, MUCJoinedState.CAPTCHA_FAILED)
        self._set_muc_state(room_jid, MUCJoinedState.NOT_JOINED)

    def send_captcha(self, room_jid, form_node):
        self._set_muc_state(room_jid, MUCJoinedState.JOINING)
        self._nbxmpp('MUC').send_captcha(room_jid,
                                         form_node,
                                         callback=self._on_captcha_result)

    def _on_captcha_result(self, result):
        if not is_error_result(result):
            return

        muc_data = self._muc_data.get(result.jid)
        if muc_data is None:
            return
        self._set_muc_state(result.jid, MUCJoinedState.CAPTCHA_FAILED)
        app.nec.push_incoming_event(
            NetworkEvent('muc-captcha-error',
                         account=self._account,
                         room_jid=str(result.jid),
                         error_text=to_user_string(result)))

    def _on_config_change(self, _con, _stanza, properties):
        if not properties.is_muc_config_change:
            return

        room_jid = str(properties.muc_jid)
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
        self._log.info('Inivte %s to %s', to, room)
        self._nbxmpp('MUC').invite(room, to, reason, password, continue_, type_)

    def cleanup(self):
        for room_jid in list(self._join_timeouts.keys()):
            self._remove_join_timeout(room_jid)


def get_instance(*args, **kwargs):
    return MUC(*args, **kwargs), 'MUC'
