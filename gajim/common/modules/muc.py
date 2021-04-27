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

import logging
from collections import defaultdict

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.const import InviteType
from nbxmpp.const import PresenceType
from nbxmpp.const import StatusCode
from nbxmpp.structs import StanzaHandler
from nbxmpp.errors import StanzaError

from gi.repository import GLib

from gajim.common import app
from gajim.common import helpers
from gajim.common.const import KindConstant
from gajim.common.const import MUCJoinedState
from gajim.common.helpers import AdditionalDataDict
from gajim.common.helpers import get_default_muc_config
from gajim.common.helpers import get_group_chat_nick
from gajim.common.structs import MUCData
from gajim.common.structs import MUCPresenceData
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
        'approve_voice_request',
        'destroy',
        'request_disco_info'
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='presence',
                          callback=self._on_muc_user_presence,
                          ns=Namespace.MUC_USER,
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
                          ns=Namespace.MUC_USER,
                          priority=49),
            StanzaHandler(name='message',
                          callback=self._on_invite_or_decline,
                          typ='normal',
                          ns=Namespace.MUC_USER,
                          priority=49),
            StanzaHandler(name='message',
                          callback=self._on_invite_or_decline,
                          ns=Namespace.CONFERENCE,
                          priority=49),
            StanzaHandler(name='message',
                          callback=self._on_captcha_challenge,
                          ns=Namespace.CAPTCHA,
                          priority=49),
            StanzaHandler(name='message',
                          callback=self._on_voice_request,
                          ns=Namespace.DATA,
                          priority=49)
        ]

        self._con.connect_signal('state-changed',
                                 self._on_client_state_changed)
        self._con.connect_signal('resume-failed',
                                 self._on_client_resume_failed)

        self._rejoin_muc = set()
        self._join_timeouts = {}
        self._rejoin_timeouts = {}
        self._muc_service_jid = None
        self._joined_users = defaultdict(dict)
        self._mucs = {}
        self._muc_nicknames = {}

    def _on_resume_failed(self, _client, _signal_name):
        self._reset_presence()

    def _on_state_changed(self, _client, _signal_name, state):
        if state.is_disconnected:
            self._reset_presence()

    @property
    def supported(self):
        return self._muc_service_jid is not None

    @property
    def service_jid(self):
        return self._muc_service_jid

    def pass_disco(self, info):
        for identity in info.identities:
            if identity.category != 'conference':
                continue
            if identity.type != 'text':
                continue
            if Namespace.MUC in info.features:
                self._log.info('Discovered MUC: %s', info.jid)
                self._muc_service_jid = info.jid
                raise nbxmpp.NodeProcessed

    def get_muc_data(self, room_jid):
        return self._mucs.get(room_jid)

    def set_password(self, room_jid, password):
        muc_data = self.get_muc_data(room_jid)
        muc_data.password = password

    def _get_mucs_with_state(self, states):
        return [muc for muc in self._mucs.values() if muc.state in states]

    def _set_muc_state(self, room_jid, state):
        try:
            muc = self._mucs[room_jid]
        except KeyError:
            raise ValueError('set_muc_state() called '
                             'on unknown muc: %s' % room_jid)

        if muc.state == state:
            return

        self._log.info('Set MUC state: %s %s', room_jid, state)

        muc.state = state
        contact = self._get_contact(room_jid, groupchat=True)
        contact.notify('state-changed')

    def _reset_state(self):
        for room_jid in list(self._rejoin_timeouts.keys()):
            self._remove_rejoin_timeout(room_jid)

        for room_jid in list(self._join_timeouts.keys()):
            self._remove_join_timeout(room_jid)

        for muc in self._mucs.values():
            self._joined_users.pop(muc.jid, None)
            self._set_muc_state(muc.jid, MUCJoinedState.NOT_JOINED)
            room = self._get_contact(muc.jid)
            room.set_not_joined()
            room.notify('room-left')

        self._joined_users.clear()

    def _create_muc_data(self, room_jid, nick, password, config):
        if not nick:
            nick = get_group_chat_nick(self._account, room_jid)

        # Fetch data from bookmarks
        bookmark = self._con.get_module('Bookmarks').get_bookmark(room_jid)
        if bookmark is not None:
            if bookmark.password is not None:
                password = bookmark.password

        return MUCData(room_jid, nick, password, config)

    def join(self, jid, nick=None, password=None, config=None):
        if not app.account_is_available(self._account):
            return

        self._con.get_module('Contacts').add_contact(jid, groupchat=True)

        muc_data = self._mucs.get(jid)
        if muc_data is None:
            muc_data = self._create_muc_data(jid, nick, password, config)
            self._mucs[jid] = muc_data
            self._push_muc_added_event(jid)

        if not muc_data.state.is_not_joined:
            self._log.warning('Can’t join MUC %s, state: %s',
                              jid, muc_data.state)
            return

        disco_info = app.storage.cache.get_last_disco_info(muc_data.jid,
                                                           max_age=60)
        if disco_info is None:
            self._set_muc_state(muc_data.jid, MUCJoinedState.JOINING)
            self._con.get_module('Discovery').disco_muc(
                muc_data.jid,
                callback=self._on_disco_result)
        else:
            self._join(muc_data)

    def create(self, muc_data):
        if not app.account_is_available(self._account):
            return

        self._mucs[muc_data.jid] = muc_data
        self._create(muc_data)
        self._push_muc_added_event(muc_data.jid)

    def _push_muc_added_event(self, jid):
        app.nec.push_incoming_event(
            NetworkEvent('muc-added',
                         account=self._account,
                         jid=jid))

    def _on_disco_result(self, task):
        try:
            result = task.finish()
        except StanzaError as error:
            self._log.info('Disco %s failed: %s', error.jid, error.get_text())

            room = self._get_contact(error.jid.bare)
            room.notify('room-join-failed', error)
            return

        muc_data = self._mucs.get(result.info.jid)
        if muc_data is None:
            self._log.warning('MUC Data not found, join aborted')
            return
        self._join(muc_data)

    def _join(self, muc_data):
        presence = self._con.get_module('Presence').get_presence(
            muc_data.occupant_jid,
            show=self._con.status,
            status=self._con.status_message)

        muc_x = presence.setTag(Namespace.MUC + ' x')
        muc_x.setTag('history', {'maxchars': '0'})

        if muc_data.password is not None:
            muc_x.setTagData('password', muc_data.password)

        self._log.info('Join MUC: %s', muc_data.jid)
        self._set_muc_state(muc_data.jid, MUCJoinedState.JOINING)
        self._con.send_stanza(presence)

    def _rejoin(self, room_jid):
        muc_data = self._mucs[room_jid]
        if muc_data.state.is_not_joined:
            self._log.info('Rejoin %s', room_jid)
            self._join(muc_data)
        return True

    def _create(self, muc_data):
        presence = self._con.get_module('Presence').get_presence(
            muc_data.occupant_jid,
            show=self._con.status,
            status=self._con.status_message)

        presence.setTag(Namespace.MUC + ' x')

        self._log.info('Create MUC: %s', muc_data.jid)
        self._set_muc_state(muc_data.jid, MUCJoinedState.CREATING)
        self._con.send_stanza(presence)

    def leave(self, room_jid, reason=None):
        self._log.info('Leave MUC: %s', room_jid)

        self._con.get_module('Bookmarks').modify(room_jid, autojoin=False)

        muc_data = self._mucs.get(room_jid)
        if muc_data is None:
            return

        if muc_data.state.is_not_joined:
            return

        self._remove_join_timeout(room_jid)
        self._remove_rejoin_timeout(room_jid)

        self._con.get_module('Presence').send_presence(
            muc_data.occupant_jid,
            typ='unavailable',
            status=reason,
            caps=False)

        self._set_muc_state(room_jid, MUCJoinedState.NOT_JOINED)
        room = self._get_contact(room_jid)
        room.set_not_joined()
        room.notify('room-left')

    def configure_room(self, room_jid):
        self._nbxmpp('MUC').request_config(room_jid,
                                           callback=self._on_room_config)

    def _on_room_config(self, task):
        try:
            result = task.finish()
        except StanzaError as error:
            self._log.info(error)

            room = self._get_contact(error.jid.bare)
            room.notfiy('room-config-failed', error)
            return

        self._log.info('Configure room: %s', result.jid)

        muc_data = self._mucs[result.jid]
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

    def _on_config_result(self, task):
        try:
            result = task.finish()
        except StanzaError as error:
            self._log.info(error)

            room = self._get_contact(error.jid.bare)
            room.notfiy('room-config-failed', error)
            return

        self._con.get_module('Discovery').disco_muc(
            result.jid, callback=self._on_disco_result_after_config)

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

    def _on_disco_result_after_config(self, task):
        try:
            result = task.finish()
        except StanzaError as error:
            self._log.info('Disco %s failed: %s', error.jid, error.get_text())
            return

        jid = result.info.jid
        muc_data = self._mucs[jid]
        self._room_join_complete(muc_data)

        self._log.info('Configuration finished: %s', jid)

        room = self._get_contact(jid.bare)
        room.notify('room-config-finished')

    def update_presence(self):
        mucs = self._get_mucs_with_state([MUCJoinedState.JOINED,
                                          MUCJoinedState.JOINING])

        status, message, idle = self._con.get_presence_state()
        for muc_data in mucs:
            self._con.get_module('Presence').send_presence(
                muc_data.occupant_jid,
                show=status,
                status=message,
                idle_time=idle)

    def change_nick(self, room_jid, new_nick):
        status, message, _idle = self._con.get_presence_state()
        self._con.get_module('Presence').send_presence(
            '%s/%s' % (room_jid, new_nick),
            show=status,
            status=message)

    def _on_error_presence(self, _con, stanza, properties):
        room_jid = properties.jid.bare
        muc_data = self._mucs.get(room_jid)
        if muc_data is None:
            return

        if properties.jid.resource != muc_data.nick:
            self._log.warning('Unknown error presence')
            self._log.warning(stanza)
            return

        room = self._get_contact(room_jid)

        if muc_data.state == MUCJoinedState.JOINING:
            if properties.error.condition == 'conflict':
                self._remove_rejoin_timeout(room_jid)
                muc_data.nick += '_'
                self._log.info('Nickname conflict: %s change to %s',
                               muc_data.jid, muc_data.nick)
                self._join(muc_data)

            elif properties.error.condition == 'not-authorized':
                self._remove_rejoin_timeout(room_jid)
                self._set_muc_state(room_jid, MUCJoinedState.NOT_JOINED)
                room.notify('room-password-required', properties)

            else:
                self._set_muc_state(room_jid, MUCJoinedState.NOT_JOINED)
                if room_jid not in self._rejoin_muc:
                    room.notify('room-join-failed', properties.error)

        elif muc_data.state == MUCJoinedState.CREATING:
            self._set_muc_state(room_jid, MUCJoinedState.NOT_JOINED)
            room.notify('room-creation-failed', properties)

        elif muc_data.state == MUCJoinedState.CAPTCHA_REQUEST:
            self._set_muc_state(room_jid, MUCJoinedState.CAPTCHA_FAILED)
            self._set_muc_state(room_jid, MUCJoinedState.NOT_JOINED)
            room.notify('room-captcha-error', properties.error)

        elif muc_data.state == MUCJoinedState.CAPTCHA_FAILED:
            self._set_muc_state(room_jid, MUCJoinedState.NOT_JOINED)

        else:
            room.notify('room-presence-error', properties)

    def _on_muc_user_presence(self, _con, stanza, properties):
        if properties.type == PresenceType.ERROR:
            return

        room_jid = str(properties.muc_jid)
        if room_jid not in self._mucs:
            self._log.warning('Presence from unknown MUC')
            self._log.warning(stanza)
            return

        muc_data = self._mucs[room_jid]
        occupant = self._get_contact(properties.jid, groupchat=True)
        room = self._get_contact(properties.jid.bare)

        if properties.is_muc_destroyed:
            self._log.info('MUC destroyed: %s', room_jid)
            self._remove_join_timeout(room_jid)
            self._set_muc_state(room_jid, MUCJoinedState.NOT_JOINED)
            room.set_not_joined()
            room.notify('room-destroyed', properties)
            return

        if properties.is_nickname_changed:
            if properties.is_muc_self_presence:
                muc_data.nick = properties.muc_user.nick
                self._con.get_module('Bookmarks').modify(muc_data.jid,
                                                         nick=muc_data.nick)

            initiator = 'Server' if properties.is_nickname_modified else 'User'
            self._log.info('%s nickname changed: %s to %s',
                           initiator,
                           properties.jid,
                           properties.muc_user.nick)

            # Create a copy of the contact object
            new_occupant = room.add_resource(properties.muc_user.nick)
            new_occupant.set_presence(occupant.presence)

            presence = self._process_user_presence(properties)
            occupant.update_presence(presence, properties)

            # new_nick = properties.muc_user.nick
            # nick = properties.muc_nickname
            # presence_dict = self._joined_users[properties.jid.bare]
            # presence_dict[new_nick] = presence_dict.pop(nick)
            # self._manager.change_nickname
            # TODO remove presence from manager

            room.notify('user-nickname-changed', occupant, properties)
            return

        is_joined = self._is_user_joined(properties.jid)
        if not is_joined and properties.type.is_available:
            if properties.is_muc_self_presence:
                self._log.info('Self presence: %s', properties.jid)
                if muc_data.state == MUCJoinedState.JOINING:
                    if (properties.is_nickname_modified or
                            muc_data.nick != properties.muc_nickname):
                        muc_data.nick = properties.muc_nickname
                        self._log.info('Server modified nickname to: %s',
                                       properties.muc_nickname)

                elif muc_data.state == MUCJoinedState.CREATING:
                    if properties.is_new_room:
                        self.configure_room(room_jid)

                self._start_join_timeout(room_jid)

            presence = self._process_user_presence(properties)
            occupant.update_presence(presence, properties)
            return

        if properties.is_muc_self_presence and properties.is_kicked:
            self._set_muc_state(room_jid, MUCJoinedState.NOT_JOINED)
            room.set_not_joined()
            room.notify('room-kicked', properties)
            status_codes = properties.muc_status_codes or []
            if StatusCode.REMOVED_SERVICE_SHUTDOWN in status_codes:
                self._start_rejoin_timeout(room_jid)
            return

        if properties.is_muc_self_presence and properties.type.is_unavailable:
            # Its not a kick, so this is the reflection of our own
            # unavailable presence, because we left the MUC
            return

        presence = self._process_user_presence(properties)
        occupant.update_presence(presence, properties)

    def _process_user_presence(self, properties):
        jid = properties.jid
        muc_presence = MUCPresenceData.from_presence(properties)
        if not muc_presence.available:
            self._joined_users[jid.bare].pop(jid.resource)
        else:
            self._joined_users[jid.bare][jid.resource] = muc_presence
        return muc_presence

    def _is_user_joined(self, jid):
        try:
            self._joined_users[jid.bare][jid.resource]
        except KeyError:
            return False
        return True

    def get_joined_users(self, jid):
        return list(self._joined_users[jid].keys())

    def _start_rejoin_timeout(self, room_jid):
        self._remove_rejoin_timeout(room_jid)
        self._rejoin_muc.add(room_jid)
        self._log.info('Start rejoin timeout for: %s', room_jid)
        id_ = GLib.timeout_add_seconds(2, self._rejoin, room_jid)
        self._rejoin_timeouts[room_jid] = id_

    def _remove_rejoin_timeout(self, room_jid):
        self._rejoin_muc.discard(room_jid)
        id_ = self._rejoin_timeouts.get(room_jid)
        if id_ is not None:
            self._log.info('Remove rejoin timeout for: %s', room_jid)
            GLib.source_remove(id_)
            del self._rejoin_timeouts[room_jid]

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
                         jid=properties.jid.bare,
                         properties=properties))
        self._log_muc_event(event_name, properties)

    def _log_muc_event(self, event_name, properties):
        # TODO CURRENTLY NOT USED
        if event_name not in ['muc-user-joined',
                              'muc-user-left',
                              'muc-user-status-show-changed']:
            return

        if (not app.settings.get('log_contact_status_changes') or
                not helpers.should_log(self._account, properties.jid)):
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
        show = app.storage.archive.convert_show_values_to_db_api_values(show)

        app.storage.archive.insert_into_logs(
            self._account,
            properties.jid.bare,
            properties.timestamp,
            KindConstant.GCSTATUS,
            contact_name=properties.muc_nickname,
            message=properties.status or None,
            show=show,
            additional_data=additional_data)

    def _on_subject_change(self, _con, _stanza, properties):
        if not properties.is_muc_subject:
            return

        room_jid = properties.jid.bare

        muc_data = self._mucs.get(room_jid)
        if muc_data is None:
            self._log.warning('No MUCData found for %s', room_jid)
            return

        muc_data.subject = properties.subject
        room = self._get_contact(room_jid)
        room.notify('room-subject', properties)

        if muc_data.state == MUCJoinedState.JOINING:
            self._room_join_complete(muc_data)
            room.notify('room-joined')

        raise nbxmpp.NodeProcessed

    def _fake_subject_change(self, room_jid):
        # This is for servers which don’t send empty subjects as part of the
        # event order on joining a MUC. For example jabber.ru
        self._log.warning('Fake subject received for %s', room_jid)
        del self._join_timeouts[room_jid]
        room = self._get_contact(room_jid)
        room.notify('room-joined')

    def _room_join_complete(self, muc_data):
        self._remove_join_timeout(muc_data.jid)
        self._set_muc_state(muc_data.jid, MUCJoinedState.JOINED)
        self._remove_rejoin_timeout(muc_data.jid)

        # We successfully joined a MUC, set add bookmark with autojoin
        self._con.get_module('Bookmarks').add_or_modify(
            muc_data.jid,
            autojoin=True,
            password=muc_data.password,
            nick=muc_data.nick)

        disco_info = app.storage.cache.get_last_disco_info(muc_data.jid)
        if disco_info.has_mam_2:
            self._con.get_module('MAM').request_archive_on_muc_join(
                muc_data.jid)

    def _on_voice_request(self, _con, _stanza, properties):
        if not properties.is_voice_request:
            return

        room = self._get_contact(properties.jid.bare)
        room.notify('room-voice-request', properties)

        raise nbxmpp.NodeProcessed

    def _on_captcha_challenge(self, _con, _stanza, properties):
        if not properties.is_captcha_challenge:
            return

        if properties.is_mam_message:
            # Some servers store captcha challenges in MAM, don’t process them
            self._log.warning('Ignore captcha challenge received from MAM')
            raise nbxmpp.NodeProcessed

        muc_data = self._mucs.get(properties.jid)
        if muc_data is None:
            return

        if muc_data.state != MUCJoinedState.JOINING:
            self._log.warning('Received captcha request but state != %s',
                              MUCJoinedState.JOINING)
            return

        self._log.info('Captcha challenge received from %s', properties.jid)
        store_bob_data(properties.captcha.bob_data)
        muc_data.captcha_id = properties.id

        self._set_muc_state(properties.jid, MUCJoinedState.CAPTCHA_REQUEST)
        self._remove_rejoin_timeout(properties.jid)

        room = self._get_contact(properties.jid.bare)
        room.notify('room-captcha-challenge', properties)

        raise nbxmpp.NodeProcessed

    def cancel_captcha(self, room_jid):
        muc_data = self._mucs.get(room_jid)
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

    def _on_captcha_result(self, task):
        try:
            task.finish()
        except StanzaError as error:
            muc_data = self._mucs.get(error.jid)
            if muc_data is None:
                return
            self._set_muc_state(error.jid, MUCJoinedState.CAPTCHA_FAILED)
            room = self._get_contact(error.jid)
            room.notify('room-captcha-error', error)

    def _on_config_change(self, _con, _stanza, properties):
        if not properties.is_muc_config_change:
            return

        room_jid = str(properties.muc_jid)
        self._log.info('Received config change: %s %s',
                       room_jid, properties.muc_status_codes)

        room = self._get_contact(room_jid)
        room.notify('room-config-changed', properties)

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

            self._con.get_module('Discovery').disco_muc(
                data.muc,
                request_vcard=True,
                callback=self._on_disco_result_after_invite,
                user_data=data)

            raise nbxmpp.NodeProcessed

    def _on_disco_result_after_invite(self, task):
        try:
            result = task.finish()
        except StanzaError as error:
            self._log.warning(error)
            return

        invite_data = task.get_user_data()
        app.nec.push_incoming_event(
            NetworkEvent('muc-invitation',
                         account=self._account,
                         info=result.info,
                         **invite_data._asdict()))

    def invite(self, room, jid, reason=None, continue_=False):
        type_ = InviteType.MEDIATED
        contact = self._get_contact(jid)
        if contact and contact.supports(Namespace.CONFERENCE):
            type_ = InviteType.DIRECT

        password = self._mucs[room].password
        self._log.info('Invite %s to %s', jid, room)
        return self._nbxmpp('MUC').invite(room, jid, reason, password,
                                          continue_, type_)

    def _on_client_state_changed(self, _client, _signal_name, state):
        if state.is_disconnected:
            self._reset_state()

    def _on_client_resume_failed(self, _client, _signal_name):
        self._reset_state()


def get_instance(*args, **kwargs):
    return MUC(*args, **kwargs), 'MUC'
