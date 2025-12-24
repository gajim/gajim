# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# XEP-0045: Multi-User Chat
# XEP-0249: Direct MUC Invitations

from __future__ import annotations

from typing import Any

import copy
import logging
import time
from collections import defaultdict
from collections.abc import Sequence

import nbxmpp
from gi.repository import GLib
from nbxmpp.const import Affiliation
from nbxmpp.const import InviteType
from nbxmpp.const import StatusCode
from nbxmpp.errors import StanzaError
from nbxmpp.modules.dataforms import SimpleDataForm
from nbxmpp.modules.muc.util import MucInfoResult
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.protocol import Message
from nbxmpp.protocol import Presence
from nbxmpp.structs import AffiliationResult
from nbxmpp.structs import CommonError
from nbxmpp.structs import CommonResult
from nbxmpp.structs import DiscoInfo
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import MucConfigResult
from nbxmpp.structs import PresenceProperties
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import VoiceRequest
from nbxmpp.task import Task

from gajim.common import app
from gajim.common import events
from gajim.common import helpers
from gajim.common import types
from gajim.common.const import ClientState
from gajim.common.const import MUCJoinedState
from gajim.common.events import MucAdded
from gajim.common.events import MucDecline
from gajim.common.events import MucInvitation
from gajim.common.helpers import to_user_string
from gajim.common.modules.base import BaseModule
from gajim.common.modules.bits_of_binary import store_bob_data
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.structs import MUCData
from gajim.common.structs import MUCPresenceData
from gajim.common.util.datetime import utc_now
from gajim.common.util.muc import get_default_muc_config
from gajim.common.util.muc import get_group_chat_nick

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
        'request_disco_info',
    ]

    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='presence',
                          callback=self._on_muc_user_presence,
                          typ='available',
                          ns=Namespace.MUC_USER,
                          priority=49),
            StanzaHandler(name='presence',
                          callback=self._on_muc_user_presence,
                          typ='unavailable',
                          ns=Namespace.MUC_USER,
                          priority=49),
            StanzaHandler(name='message',
                          callback=self._on_muc_normal_user_message,
                          typ='normal',
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
                          priority=49),
            StanzaHandler(name='message',
                          typ='error',
                          callback=self._message_error_received,
                          priority=49),
        ]

        self._con.connect_signal('state-changed',
                                 self._on_client_state_changed)
        self._con.connect_signal('resume-failed',
                                 self._on_client_resume_failed)

        self._rejoin_muc: set[JID] = set()
        self._rejoin_timeouts: dict[JID, int] = {}
        self._muc_service_jid = None
        self._joined_users: defaultdict[
            JID, dict[str, MUCPresenceData]] = defaultdict(dict)
        self._mucs: dict[JID, MUCData] = {}
        self._muc_nicknames = {}
        self._muc_affiliations = AffiliationManager()
        self._voice_requests: dict[
            GroupchatContact, list[VoiceRequest]] = defaultdict(list)
        self._sent_voice_requests: dict[
            JID, list[str]] = defaultdict(list)

    def _on_resume_failed(self,
                          _client: types.Client,
                          _signal_name: str
                          ) -> None:
        self._reset_presence()

    def _on_state_changed(self,
                          _client: types.Client,
                          _signal_name: str,
                          state: ClientState
                          ) -> None:
        if state.is_disconnected:
            self._reset_presence()

    @property
    def supported(self) -> bool:
        return self._muc_service_jid is not None

    @property
    def service_jid(self) -> JID | None:
        return self._muc_service_jid

    def pass_disco(self, info: DiscoInfo) -> None:
        if info.is_gateway:
            return

        for identity in info.identities:
            if identity.category != 'conference':
                continue
            if identity.type != 'text':
                continue
            if Namespace.MUC in info.features:
                self._log.info('Discovered MUC: %s', info.jid)
                self._muc_service_jid = info.jid
                raise nbxmpp.NodeProcessed

    def get_muc_data(self, room_jid: JID) -> MUCData | None:
        return self._mucs.get(room_jid)

    def set_password(self, room_jid: JID, password: str) -> None:
        muc_data = self.get_muc_data(room_jid)
        muc_data.password = password

    def _get_mucs_with_state(self, states: list[MUCJoinedState]):
        return [muc for muc in self._mucs.values() if muc.state in states]

    def _set_muc_state(self, room_jid: JID, state: MUCJoinedState) -> None:
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

    def _reset_state(self) -> None:
        self._remove_all_timeouts()
        for muc in self._mucs.values():
            self._joined_users.pop(muc.jid, None)
            self._set_muc_state(muc.jid, MUCJoinedState.NOT_JOINED)
            room = self._get_contact(muc.jid)
            assert isinstance(room, GroupchatContact)
            room.set_not_joined()
            room.notify('room-left')

        self._joined_users.clear()

    def _create_muc_data(self,
                         room_jid: JID,
                         nick: str | None,
                         password: str | None,
                         config: dict[str, Any] | None
                         ) -> MUCData:
        if not nick:
            nick = get_group_chat_nick(self._account, room_jid)

        # Fetch data from bookmarks
        bookmark = self._con.get_module('Bookmarks').get_bookmark(room_jid)
        if bookmark is not None:
            if bookmark.password is not None:
                password = bookmark.password

        return MUCData(str(room_jid), nick, None, password, config)

    def join(self,
             jid: JID,
             nick: str | None = None,
             password: str | None = None,
             config: dict[str, Any] | None = None
             ) -> None:
        if not app.account_is_available(self._account):
            return

        self._con.get_module('Contacts').add_contact(jid, groupchat=True)

        muc_data = self._mucs.get(jid)
        if muc_data is None:
            muc_data = self._create_muc_data(jid, nick, password, config)
            self._mucs[jid] = muc_data
            self._push_muc_added_event(jid)

        elif nick is not None:
            # Currently MUCData is never discarded so if it exists it contains
            # the nickname of a previous join. The user may chose now on a new
            # join a different nickname, so update MUCData here.
            muc_data.nick = nick

        if muc_data.state not in (MUCJoinedState.NOT_JOINED,
                                  MUCJoinedState.PASSWORD_REQUEST):
            self._log.warning('Can’t join MUC %s, state: %s',
                              jid, muc_data.state)
            return

        disco_info = app.storage.cache.get_last_disco_info(muc_data.jid,
                                                           max_age=60)
        if disco_info is None:
            self._set_muc_state(muc_data.jid, MUCJoinedState.BEFORE_JOINING)
            self._con.get_module('Discovery').disco_muc(
                muc_data.jid,
                callback=self._on_disco_result)  # type: ignore
        else:
            self._join(muc_data)

    def create(self, jid: JID, config: dict[str, Any]) -> None:
        if not app.account_is_available(self._account):
            return

        self._con.get_module('Contacts').add_contact(jid, groupchat=True)
        muc_data = self._create_muc_data(jid, None, None, config)
        self._mucs[jid] = muc_data
        self._create(muc_data)
        self._push_muc_added_event(jid, select_chat=True)

    def _push_muc_added_event(self,
                              jid: JID,
                              select_chat: bool = False
                              ) -> None:

        app.ged.raise_event(MucAdded(account=self._account,
                                     jid=jid,
                                     select_chat=select_chat))

    def _on_disco_result(self, task: Task) -> None:
        try:
            result = task.finish()
        except StanzaError as error:
            jid = error.jid
            self._log.info('Disco %s failed: %s', jid, error.get_text())
            muc_data = self._mucs.get(jid)
            muc_data.error = 'join-failed'
            error_text = helpers.to_user_string(error)
            muc_data.error_text = error_text
            self._set_muc_state(jid, MUCJoinedState.NOT_JOINED)
            room = self._get_contact(jid)
            room.notify('room-join-failed', error_text)
            return

        muc_data = self._mucs.get(result.info.jid)
        if muc_data is None:
            self._log.warning('MUC Data not found, join aborted')
            return
        self._join(muc_data)

    def _join(self, muc_data: MUCData) -> None:
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

    def _rejoin(self, room_jid: JID) -> bool:
        if not self._client.state.is_available:
            return True

        muc_data = self._mucs[room_jid]
        if muc_data.state.is_not_joined:
            self._log.info('Rejoin %s', room_jid)
            self._join(muc_data)
        return True

    def _create(self, muc_data: MUCData) -> None:
        presence = self._con.get_module('Presence').get_presence(
            muc_data.occupant_jid,
            show=self._con.status,
            status=self._con.status_message)

        presence.setTag(Namespace.MUC + ' x')

        self._log.info('Create MUC: %s', muc_data.jid)
        self._set_muc_state(muc_data.jid, MUCJoinedState.CREATING)
        self._con.send_stanza(presence)

    def leave(self,
              room_jid: JID,
              reason: str | None = None,
              unregister: bool = False,
              ) -> None:
        self._log.info('Leave MUC: %s', room_jid)

        self._con.get_module('Bookmarks').modify(room_jid, autojoin=False)

        muc_data = self._mucs.get(room_jid)
        if muc_data is None:
            return

        self._remove_rejoin_timeout(room_jid)

        if muc_data.state.is_not_joined:
            return


        self._con.get_module('Presence').send_presence(
            muc_data.occupant_jid,
            typ='unavailable',
            status=reason,
            caps=False)

        self._set_muc_state(room_jid, MUCJoinedState.NOT_JOINED)
        room = self._get_contact(room_jid)
        assert isinstance(room, GroupchatContact)
        room.set_not_joined()
        room.notify('room-left')

        if not unregister:
            return

        contact = self._con.get_module('Contacts').get_contact(room_jid)
        assert isinstance(contact, GroupchatContact)
        self._con.get_module('Register').unregister(
            jid=contact.jid,
            callback=self._unregister_callback,
        )

    def _unregister_callback(self, task: Task) -> None:
        try:
            task.finish()
        except StanzaError as error:
            self._log.error('Error while unregistering from MUC: %s',
                            to_user_string(error))

    def abort_join(self, room_jid: JID) -> None:
        self._remove_rejoin_timeout(room_jid)

        muc = self._mucs[room_jid]
        self._con.get_module('Presence').send_presence(
            muc.occupant_jid,
            typ='unavailable',
            caps=False)

        self._set_muc_state(room_jid, MUCJoinedState.NOT_JOINED)

    def configure_room(self, room_jid: JID) -> None:
        self._nbxmpp('MUC').request_config(room_jid,
                                           callback=self._on_room_config)  # type: ignore

    def _on_room_config(self, task: Task) -> None:
        try:
            result = task.finish()
        except StanzaError as error:
            self._log.info(error)

            room = self._get_contact(error.jid.bare)
            error_text = helpers.to_user_string(error)
            room.notfiy('room-config-failed', error_text)
            return

        assert isinstance(result, MucConfigResult)
        self._log.info('Configure room: %s', result.jid)

        muc_data = self._mucs[result.jid]
        self._apply_config(result.form, muc_data.config)
        self.set_config(result.jid,
                        result.form,
                        callback=self._on_config_result)

    @staticmethod
    def _apply_config(form: SimpleDataForm,
                      config: dict[str, Any] | None = None
                      ) -> None:
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

    def _on_config_result(self, task: Task) -> None:
        try:
            result = task.finish()
        except StanzaError as error:
            self._log.info(error)

            room = self._get_contact(error.jid.bare)
            error_text = helpers.to_user_string(error)
            room.notfiy('room-config-failed', error_text)
            return

        assert isinstance(result, CommonResult)
        self._con.get_module('Discovery').disco_muc(
            result.jid, callback=self._on_disco_result_after_config)   # type: ignore

    def _on_disco_result_after_config(self, task: Task) -> None:
        try:
            result = task.finish()
        except StanzaError as error:
            self._log.info('Disco %s failed: %s', error.jid, error.get_text())
            return

        assert isinstance(result, MucInfoResult)
        jid = result.info.jid
        assert jid is not None
        muc_data = self._mucs[jid]
        self._room_join_complete(muc_data)

        self._log.info('Configuration finished: %s', jid)

        room = self._get_contact(jid.new_as_bare())
        event = events.MUCRoomConfigFinished(
            timestamp=utc_now())

        assert isinstance(room, GroupchatContact)
        app.storage.events.store(room, event)
        room.notify('room-config-finished', event)

    def _request_affiliation_list(self, room_jid: JID) -> None:
        # Don't request affiliation outcast, it is rarley needed and
        # can be requested on demand rather than on each join

        for affiliation in ('owner', 'admin', 'member'):
            self.get_affiliation(
                room_jid,
                affiliation,
                callback=self._on_affiliations_received,
                user_data=(room_jid, affiliation)
            )

    def _on_affiliations_received(self, task: Task) -> None:
        jid, affiliation = task.get_user_data()
        try:
            result = task.finish()
        except StanzaError as error:
            self._log.info('Affiliation request failed: %s %s', jid, error)
            self._muc_affiliations.remove_affiliation(jid, affiliation)
            return

        assert isinstance(result, AffiliationResult)
        self._muc_affiliations.add_affiliation_result(affiliation, result)

        room = self._get_contact(jid)
        assert isinstance(room, GroupchatContact)
        room.notify('room-affiliations-received', affiliation)

    def get_affiliations(
        self,
        room_jid: JID,
        *,
        include_outcast: bool = False
    ) -> dict[str, list[JID]]:

        return self._muc_affiliations.get_users(
            room_jid, include_outcast=include_outcast)

    def update_presence(self) -> None:
        mucs = self._get_mucs_with_state([MUCJoinedState.JOINED,
                                          MUCJoinedState.JOINING])

        status, message, idle = self._con.get_presence_state()
        for muc_data in mucs:
            self._con.get_module('Presence').send_presence(
                muc_data.occupant_jid,
                show=status,
                status=message,
                idle_time=idle)

    def change_nick(self, room_jid: JID, new_nick: str) -> None:
        status, message, _idle = self._con.get_presence_state()
        self._con.get_module('Presence').send_presence(
            f'{room_jid}/{new_nick}',
            show=status,
            status=message)

    def _on_error_presence(self,
                           _con: types.NBXMPPClient,
                           _stanza: Presence,
                           properties: PresenceProperties
                           ) -> None:

        assert properties.jid is not None
        room_jid = properties.jid.new_as_bare()
        muc_data = self._mucs.get(room_jid)
        if muc_data is None:
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
                self._set_muc_state(room_jid, MUCJoinedState.PASSWORD_REQUEST)
                room.notify('room-password-required')

            else:
                self._set_muc_state(room_jid, MUCJoinedState.NOT_JOINED)
                if room_jid not in self._rejoin_muc:
                    muc_data.error = 'join-failed'
                    assert isinstance(properties.error, CommonError)
                    muc_data.error_text = helpers.to_user_string(
                        properties.error)
                    room.notify('room-join-failed', muc_data.error_text)

        elif muc_data.state == MUCJoinedState.CREATING:
            self._set_muc_state(room_jid, MUCJoinedState.NOT_JOINED)
            muc_data.error = 'creation-failed'
            assert isinstance(properties.error, CommonError)
            muc_data.error_text = helpers.to_user_string(properties.error)
            room.notify('room-creation-failed', muc_data.error_text)

        elif muc_data.state == MUCJoinedState.CAPTCHA_REQUEST:
            self._set_muc_state(room_jid, MUCJoinedState.CAPTCHA_FAILED)
            self._set_muc_state(room_jid, MUCJoinedState.NOT_JOINED)
            muc_data.error = 'captcha-failed'
            assert isinstance(properties.error, CommonError)
            muc_data.error_text = helpers.to_user_string(properties.error)
            room.notify('room-captcha-error', muc_data.error_text)

        elif muc_data.state == MUCJoinedState.CAPTCHA_FAILED:
            self._set_muc_state(room_jid, MUCJoinedState.NOT_JOINED)

        else:
            error = helpers.to_user_string(properties.error)
            event = events.MUCRoomPresenceError(
                timestamp=utc_now(),
                error=error)
            assert isinstance(room, GroupchatContact)
            app.storage.events.store(room, event)
            room.notify('room-presence-error', event)

    def _on_muc_user_presence(self,
                              _con: types.NBXMPPClient,
                              stanza: Presence,
                              properties: PresenceProperties
                              ) -> None:

        assert properties.type is not None
        assert properties.muc_jid is not None
        room_jid = properties.muc_jid
        if room_jid not in self._mucs:
            self._log.warning('Presence from unknown MUC')
            self._log.warning(stanza)
            return

        muc_data = self._mucs[room_jid]
        assert properties.jid is not None
        occupant = self._get_contact(properties.jid, groupchat=True)
        room = self._get_contact(properties.jid.new_as_bare())
        assert isinstance(room, GroupchatContact)

        timestamp = utc_now()

        if properties.muc_destroyed is not None:
            self._log.info('MUC destroyed: %s', room_jid)
            self._set_muc_state(room_jid, MUCJoinedState.NOT_JOINED)
            self._con.get_module('Bookmarks').remove(room_jid)
            room.set_not_joined()

            event = events.MUCRoomDestroyed(
                timestamp=timestamp,
                reason=properties.muc_destroyed.reason,
                alternate=properties.muc_destroyed.alternate)
            assert isinstance(room, GroupchatContact)
            app.storage.events.store(room, event)

            room.notify('room-destroyed', event)
            return

        if properties.is_nickname_changed:
            assert properties.muc_user is not None
            if properties.is_muc_self_presence:
                muc_data.nick = properties.muc_user.nick
                self._con.get_module('Bookmarks').modify(muc_data.jid,
                                                         nick=muc_data.nick)

            initiator = 'Server' if properties.is_nickname_modified else 'User'
            self._log.info('%s nickname changed: %s to %s',
                           initiator,
                           properties.jid,
                           properties.muc_user.nick)

            # We receive only the unavailable presence here, so we take
            # the current presence and create a new contact with it, before we
            # update the presence.
            nickname = properties.muc_user.nick
            new_occupant = room.add_resource(nickname)
            new_occupant.set_presence(occupant.presence)
            self._joined_users[room.jid][nickname] = occupant.presence

            presence = self._process_user_presence(properties)
            self._process_occupant_presence_change(properties,
                                                   presence,
                                                   occupant)

            event = events.MUCNicknameChanged(
                timestamp=timestamp,
                is_self=properties.is_muc_self_presence,
                new_name=new_occupant.name,
                old_name=occupant.name)

            assert isinstance(room, GroupchatContact)
            app.storage.events.store(room, event)

            room.notify('user-nickname-changed', event, occupant, new_occupant)
            return

        is_joined = self._is_user_joined(properties.jid)
        if not is_joined and properties.type.is_available:
            if properties.is_muc_self_presence:
                self._log.info('Self presence: %s', properties.jid)
                if muc_data.state == MUCJoinedState.JOINING:
                    if room.supports(Namespace.OCCUPANT_ID):
                        muc_data.occupant_id = properties.occupant_id

                    if (properties.is_nickname_modified or
                            muc_data.nick != properties.muc_nickname):
                        muc_data.nick = properties.muc_nickname
                        self._log.info('Server modified nickname to: %s',
                                       properties.muc_nickname)

                elif muc_data.state == MUCJoinedState.CREATING:
                    if properties.is_new_room:
                        muc_data.occupant_id = properties.occupant_id
                        self.configure_room(room_jid)

            presence = self._process_user_presence(properties)
            self._process_occupant_presence_change(properties,
                                                   presence,
                                                   occupant)
            return

        if properties.is_muc_self_presence and properties.is_kicked:
            self._set_muc_state(room_jid, MUCJoinedState.NOT_JOINED)
            room.set_not_joined()

            assert properties.muc_user is not None

            event = events.MUCRoomKicked(
                timestamp=timestamp,
                status_codes=properties.muc_status_codes,
                reason=properties.muc_user.reason,
                actor=properties.muc_user.actor)
            assert isinstance(room, GroupchatContact)
            app.storage.events.store(room, event)
            room.notify('room-kicked', event)

            status_codes = properties.muc_status_codes or []
            if StatusCode.REMOVED_SERVICE_SHUTDOWN in status_codes:
                self._start_rejoin_timeout(room_jid)
            return

        if properties.is_muc_self_presence and properties.type.is_unavailable:
            # Its not a kick, so this is the reflection of our own
            # unavailable presence, because we left the MUC
            return

        if properties.jid.resource is None:
            # prosody allows broadcasting "unavailable" presences from
            # offline room members
            return

        try:
            presence = self._process_user_presence(properties)
        except KeyError:
            # Sometimes it seems to happen that we get unavailable presence
            # from occupants we don’t know
            log.warning('Unexpected presence received')
            log.warning(stanza)
            return

        self._process_occupant_presence_change(properties, presence, occupant)

    def _process_occupant_presence_change(
            self,
            properties: PresenceProperties,
            presence: MUCPresenceData,
            occupant: GroupchatParticipant) -> None:

        timestamp = utc_now()

        if not occupant.is_available and presence.available:

            event = events.MUCUserJoined(
                timestamp=timestamp,
                is_self=properties.is_muc_self_presence,
                nick=occupant.name,
                status_codes=properties.muc_status_codes)

            if occupant.room.is_joined or properties.is_muc_self_presence:
                # Don’t store initial presences on join
                app.storage.events.store(occupant.room, event)

            occupant.update_presence(presence)
            occupant.notify('user-joined', event)
            return

        if not presence.available:
            assert properties.muc_user is not None

            event = events.MUCUserLeft(
                timestamp=timestamp,
                is_self=properties.is_muc_self_presence,
                nick=occupant.name,
                status_codes=properties.muc_status_codes,
                reason=properties.muc_user.reason,
                actor=properties.muc_user.actor)

            app.storage.events.store(occupant.room, event)
            occupant.update_presence(presence)
            occupant.notify('user-left', event)
            return

        signals_and_events: list[tuple[str, Any]] = []

        if occupant.affiliation != presence.affiliation:
            assert properties.muc_user is not None

            event = events.MUCUserAffiliationChanged(
                timestamp=timestamp,
                is_self=properties.is_muc_self_presence,
                nick=occupant.name,
                affiliation=presence.affiliation,
                reason=properties.muc_user.reason,
                actor=properties.muc_user.actor)

            app.storage.events.store(occupant.room, event)
            assert properties.muc_jid is not None
            if presence.real_jid is not None:
                self._muc_affiliations.change_user_affiliation(
                    properties.muc_jid, presence.affiliation, presence.real_jid)
            signals_and_events.append(('user-affiliation-changed', event))

        if occupant.role != presence.role:
            assert properties.muc_user is not None

            event = events.MUCUserRoleChanged(
                timestamp=timestamp,
                is_self=properties.is_muc_self_presence,
                nick=occupant.name,
                role=presence.role,
                reason=properties.muc_user.reason,
                actor=properties.muc_user.actor)

            app.storage.events.store(occupant.room, event)
            signals_and_events.append(('user-role-changed', event))

        if (occupant.status != presence.status or
                occupant.show != presence.show):

            event = events.MUCUserStatusShowChanged(
                timestamp=timestamp,
                is_self=properties.is_muc_self_presence,
                nick=occupant.name,
                status=properties.status,
                show_value=properties.show.value)

            app.storage.events.store(occupant, event)
            app.storage.events.store(occupant.room, event)
            signals_and_events.append(('user-status-show-changed', event))

        if occupant.hats != presence.hats:
            if presence.hats:
                hats = [h.title for h in presence.hats.get_hats()]
            else:
                hats = None
            event = events.MUCUserHatsChanged(
                timestamp=timestamp,
                is_self=properties.is_muc_self_presence,
                nick=occupant.name,
                hats=hats,
            )

            app.storage.events.store(occupant, event)
            app.storage.events.store(occupant.room, event)
            signals_and_events.append(('user-hats-changed', event))

        occupant.update_presence(presence)
        for signal, event in signals_and_events:
            occupant.notify(signal, event)

    def _on_muc_normal_user_message(self,
                                    _con: types.NBXMPPClient,
                                    stanza: Presence,
                                    properties: MessageProperties) -> None:
        if not properties.muc_user or not properties.muc_user.jid:
            return

        if not properties.muc_user.affiliation and not properties.muc_user.role:
            return

        room_jid = properties.muc_jid
        if room_jid not in self._mucs:
            self._log.warning('Message from unknown MUC')
            self._log.warning(stanza)
            return

        assert room_jid is not None
        room = self._get_contact(room_jid)
        assert isinstance(room, GroupchatContact)

        if properties.muc_user.nick is not None:
            nick = properties.muc_user.nick
        else:
            contact = self._get_contact(properties.muc_user.jid)
            if isinstance(contact, BareContact):
                nick = contact.name
            else:
                nick = str(properties.muc_user.jid)

        assert properties.muc_user.affiliation is not None
        event = events.MUCAffiliationChanged(
            timestamp=utc_now(),
            nick=nick,
            affiliation=properties.muc_user.affiliation,
        )
        app.storage.events.store(room, event)
        self._muc_affiliations.change_user_affiliation(
            room_jid, properties.muc_user.affiliation, properties.muc_user.jid)
        room.notify('room-affiliation-changed', event)

    def _process_user_presence(self,
                               properties: PresenceProperties
                               ) -> MUCPresenceData:
        assert properties.jid is not None
        jid = properties.jid
        group_contact = self._client.get_module('Contacts').get_contact(
            jid.bare, groupchat=True)
        occupant_id = None
        if group_contact.supports(Namespace.OCCUPANT_ID):
            occupant_id = properties.occupant_id

        muc_presence = MUCPresenceData.from_presence(properties, occupant_id)
        assert jid.resource is not None
        if not muc_presence.available:
            self._joined_users[jid.new_as_bare()].pop(jid.resource)
        else:
            self._joined_users[jid.new_as_bare()][jid.resource] = muc_presence
        return muc_presence

    def _is_user_joined(self, jid: JID | None) -> bool:
        try:
            self._joined_users[jid.new_as_bare()][jid.resource]
        except KeyError:
            return False
        return True

    def get_joined_users(self, jid: JID) -> list[str]:
        return list(self._joined_users[jid].keys())

    def _start_rejoin_timeout(self, room_jid: JID) -> None:
        self._remove_rejoin_timeout(room_jid)
        self._rejoin_muc.add(room_jid)
        self._log.info('Start rejoin timeout for: %s', room_jid)
        id_ = GLib.timeout_add_seconds(10, self._rejoin, room_jid)
        self._rejoin_timeouts[room_jid] = id_

    def _remove_rejoin_timeout(self, room_jid: JID) -> None:
        self._rejoin_muc.discard(room_jid)
        id_ = self._rejoin_timeouts.get(room_jid)
        if id_ is not None:
            self._log.info('Remove rejoin timeout for: %s', room_jid)
            GLib.source_remove(id_)
            del self._rejoin_timeouts[room_jid]

    def _on_subject_change(self,
                           _con: types.NBXMPPClient,
                           _stanza: Message,
                           properties: MessageProperties
                           ) -> None:

        if not properties.is_muc_subject:
            return

        assert properties.jid is not None
        room_jid = properties.jid.new_as_bare()

        muc_data = self._mucs.get(room_jid)
        if muc_data is None:
            self._log.warning('No MUCData found for %s', room_jid)
            return

        room = self._get_contact(JID.from_string(room_jid))
        assert isinstance(room, GroupchatContact)

        old_subject = muc_data.subject

        muc_subject = properties.muc_subject
        assert muc_subject is not None
        muc_data.subject = muc_subject

        if muc_subject.timestamp is None:
            muc_subject = muc_subject._replace(timestamp=time.time())

        if old_subject is None:
            muc_data.last_subject_timestamp = time.time()
            room.notify('room-subject', muc_subject)

        elif old_subject.text != muc_subject.text:
            # Check if we already showed that subject (rejoin)
            muc_data.last_subject_timestamp = time.time()
            room.notify('room-subject', muc_subject)

        if muc_data.state == MUCJoinedState.JOINING:
            self._room_join_complete(muc_data)
            self._request_affiliation_list(muc_data.jid)
            room.notify('room-joined')

        raise nbxmpp.NodeProcessed

    def cancel_password_request(self, room_jid: JID) -> None:
        self._set_muc_state(room_jid, MUCJoinedState.NOT_JOINED)

    def _room_join_complete(self, muc_data: MUCData) -> None:
        # Reset errors from previous tries, otherwise when we are
        # disconnected from the room, the ChatFunctionPage will be shown
        muc_data.error = None
        muc_data.error_text = None

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

    def request_voice(self, jid: JID) -> None:
        message_id = self._nbxmpp("MUC").request_voice(jid)
        self._sent_voice_requests[jid].append(message_id)

    def _on_voice_request(self,
                          _con: types.NBXMPPClient,
                          _stanza: Message,
                          properties: MessageProperties
                          ) -> None:
        if not properties.is_voice_request:
            return

        assert properties.jid is not None
        room = self._get_contact(properties.jid.new_as_bare())
        assert isinstance(room, GroupchatContact)
        assert properties.voice_request is not None

        self._voice_requests[room].append(properties.voice_request)
        room.notify('room-voice-request', properties)

        raise nbxmpp.NodeProcessed

    def get_voice_requests(self,
                           contact: GroupchatContact
                           ) -> list[VoiceRequest]:

        return self._voice_requests.get(contact, [])

    def approve_voice_request(self,
                              contact: GroupchatContact,
                              voice_request: VoiceRequest
                              ) -> None:

        self._voice_requests[contact].remove(voice_request)
        self._nbxmpp('MUC').approve_voice_request(contact.jid, voice_request)

    def decline_voice_request(self,
                              contact: GroupchatContact,
                              voice_request: VoiceRequest
                              ) -> None:

        self._voice_requests[contact].remove(voice_request)

    def _message_error_received(self,
                                _con: types.NBXMPPClient,
                                stanza: nbxmpp.Message,
                                properties: MessageProperties
                                ) -> None:

        remote_jid = properties.remote_jid
        assert remote_jid is not None
        message_id = properties.id
        if message_id is None:
            self._log.warning('Received error without message id')
            self._log.warning(stanza)
            return

        # We handle only voice request errors for now
        requests = self._sent_voice_requests.get(remote_jid, [])
        if message_id not in requests:
            return

        room = self._get_contact(remote_jid, groupchat=True)
        assert isinstance(room, GroupchatContact)

        assert properties.error is not None
        error = helpers.to_user_string(properties.error)
        event = events.MUCRoomVoiceRequestError(
            timestamp=utc_now(),
            message_id=message_id,
            error=error
        )

        app.storage.events.store(room, event)

        room.notify('room-voice-request-error', event)
        raise nbxmpp.NodeProcessed

    def _on_captcha_challenge(self,
                              _con: types.NBXMPPClient,
                              _stanza: Message,
                              properties: MessageProperties
                              ) -> None:
        if not properties.is_captcha_challenge:
            return

        if properties.is_mam_message:
            # Some servers store captcha challenges in MAM, don’t process them
            self._log.warning('Ignore captcha challenge received from MAM')
            raise nbxmpp.NodeProcessed

        assert properties.jid is not None
        muc_data = self._mucs.get(properties.jid)
        if muc_data is None:
            return

        if muc_data.state != MUCJoinedState.JOINING:
            self._log.warning('Received captcha request but state != %s',
                              MUCJoinedState.JOINING)
            return

        self._log.info('Captcha challenge received from %s', properties.jid)

        assert properties.captcha is not None
        store_bob_data(properties.captcha.bob_data)
        muc_data.captcha_id = properties.id
        muc_data.captcha_form = properties.captcha.form

        self._set_muc_state(properties.jid, MUCJoinedState.CAPTCHA_REQUEST)
        self._remove_rejoin_timeout(properties.jid)

        room = self._get_contact(properties.jid.new_as_bare())
        room.notify('room-captcha-challenge')

        raise nbxmpp.NodeProcessed

    def cancel_captcha(self, room_jid: JID) -> None:
        muc_data = self._mucs.get(room_jid)
        if muc_data is None:
            return

        if muc_data.captcha_id is None:
            self._log.warning('No captcha message id available')
            return
        self._nbxmpp('MUC').cancel_captcha(room_jid, muc_data.captcha_id)
        self._set_muc_state(room_jid, MUCJoinedState.CAPTCHA_FAILED)
        self._set_muc_state(room_jid, MUCJoinedState.NOT_JOINED)

    def send_captcha(self,
                     room_jid: JID,
                     form_node: SimpleDataForm
                     ) -> None:
        self._set_muc_state(room_jid, MUCJoinedState.JOINING)
        self._nbxmpp('MUC').send_captcha(room_jid,
                                         form_node,
                                         callback=self._on_captcha_result)  # type: ignore

    def _on_captcha_result(self, task: Task) -> None:
        try:
            task.finish()
        except StanzaError as error:
            muc_data = self._mucs.get(error.jid)
            if muc_data is None:
                return
            self._set_muc_state(error.jid, MUCJoinedState.CAPTCHA_FAILED)
            room = self._get_contact(error.jid)
            error_text = helpers.to_user_string(error)
            room.notify('room-captcha-error', error_text)

    def _on_config_change(self,
                          _con: types.NBXMPPClient,
                          _stanza: Message,
                          properties: MessageProperties
                          ) -> None:
        if not properties.is_muc_config_change:
            return

        self._log.info('Received config change: %s %s',
                       properties.muc_jid, properties.muc_status_codes)

        assert properties.muc_status_codes is not None
        event = events.MUCRoomConfigChanged(
            timestamp=utc_now(),
            status_codes=properties.muc_status_codes)

        assert properties.muc_jid is not None
        room = self._get_contact(properties.muc_jid)

        assert isinstance(room, GroupchatContact)
        app.storage.events.store(room, event)

        room.notify('room-config-changed', event)

        raise nbxmpp.NodeProcessed

    def _on_invite_or_decline(self,
                              _con: types.NBXMPPClient,
                              _stanza: Message,
                              properties: MessageProperties
                              ) -> None:

        assert properties.from_ is not None
        if properties.from_.bare_match(self._get_own_bare_jid()):
            # Invite/Decline sent by us and received via MAM or Carbons
            # TODO: It could make sense to delete a pending invite
            # if another device of ours decline the invite
            self._log.warning('Ignored MUC Invite/Decline sent by other device')
            return

        if properties.muc_decline is not None:
            data = properties.muc_decline
            contact = self._get_contact(data.muc, groupchat=True)

            self._log.info('Invite declined from: %s, reason: %s',
                           data.from_, data.reason)

            app.ged.raise_event(
                MucDecline(account=self._account,
                           **data._asdict()))
            raise nbxmpp.NodeProcessed

        if properties.muc_invite is not None:
            data = properties.muc_invite
            contact = self._get_contact(data.muc, groupchat=True)
            assert isinstance(contact, GroupchatContact)

            self._log.info('Invite from: %s, to: %s', data.from_, data.muc)

            if contact.is_joined:
                # We are already in groupchat. Ignore invitation
                self._log.info('We are already in this room')
                raise nbxmpp.NodeProcessed

            self._con.get_module('Discovery').disco_muc(
                data.muc,
                request_vcard=True,
                callback=self._on_disco_result_after_invite,  # type: ignore
                user_data=data)  # type: ignore

            raise nbxmpp.NodeProcessed

    def _on_disco_result_after_invite(self, task: Task) -> None:
        try:
            result = task.finish()
        except StanzaError as error:
            self._log.warning(error)
            return

        invite_data = task.get_user_data()
        app.ged.raise_event(
            MucInvitation(account=self._account,
                          info=result.info,
                          **invite_data._asdict()))

    def invite(self,
               room: JID,
               jid: JID,
               reason: str | None = None,
               continue_: bool = False
               ) -> str:

        room_contact = self._get_contact(room, groupchat=True)
        assert isinstance(room_contact, GroupchatContact)
        disco = room_contact.get_disco()
        assert disco is not None

        if disco.muc_is_members_only:
            self_contact = room_contact.get_self()
            assert self_contact is not None
            affiliation = self_contact.affiliation
            admin = affiliation.is_owner or affiliation.is_admin
            if admin:
                self.set_affiliation(
                    room, {jid: {'affiliation': 'member'}})
                type_ = InviteType.DIRECT
            else:
                type_ = InviteType.MEDIATED
        else:
            type_ = InviteType.DIRECT

        password = self._mucs[room].password
        self._log.info('Invite %s to %s', jid, room)
        return self._nbxmpp('MUC').invite(
            room, jid, password, reason, continue_, type_)

    def moderate_messages(
        self,
        namespace: str,
        jid: JID,
        moderate_ids: Sequence[str],
        reason: str | None
    ) -> None:

        for moderation_id in moderate_ids:
            self._nbxmpp('MUC').moderate_message(namespace, jid, moderation_id, reason)

    def _on_client_state_changed(self,
                                 _client: types.Client,
                                 _signal_name: str,
                                 state: ClientState
                                 ) -> None:
        if state.is_disconnected:
            self._reset_state()

    def _on_client_resume_failed(self,
                                 _client: types.Client,
                                 _signal_name: str
                                 ) -> None:
        self._reset_state()

    def _remove_all_timeouts(self) -> None:
        for room_jid in list(self._rejoin_timeouts.keys()):
            self._remove_rejoin_timeout(room_jid)

    def cleanup(self) -> None:
        BaseModule.cleanup(self)
        self._remove_all_timeouts()


class AffiliationManager:
    def __init__(self) -> None:
        self._affiliations: dict[JID, dict[str, list[JID]]] = defaultdict(
            lambda: defaultdict(list))

    def add_affiliation_result(
        self,
        affiliation: str,
        result: AffiliationResult
    ) -> None:
        user_jids = [jid.new_as_bare() for jid in result.users]
        log.info("AffiliationManager: Add result: %s %s %s",
                 result.jid, affiliation, list(map(str, user_jids)))
        self._affiliations[result.jid][affiliation] = user_jids

    def remove_affiliation(self, muc_jid: JID, affiliation: str) -> None:
        log.info("AffiliationManager: Remove affiliation: %s %s",
                 muc_jid, affiliation)
        try:
            del self._affiliations[muc_jid][affiliation]
        except KeyError:
            pass

    def add_user_affiliation(
        self,
        muc_jid: JID,
        affiliation: Affiliation,
        user_real_jid: JID
    ) -> None:
        log.info("AffiliationManager: Add user: %s %s %s",
                 muc_jid, affiliation, user_real_jid)
        self._affiliations[muc_jid][affiliation.value].append(user_real_jid)

    def remove_user_affiliation(self, muc_jid: JID, user_real_jid: JID) -> None:
        log.info("AffiliationManager: Remove user: %s %s", muc_jid, user_real_jid)
        for jids in self._affiliations.get(muc_jid, {}).values():
            if user_real_jid in jids:
                jids.remove(user_real_jid)
                return

    def change_user_affiliation(
        self,
        muc_jid: JID,
        affiliation: Affiliation,
        user_real_jid: JID
    ) -> None:
        log.info("AffiliationManager: Change user affiliation: %s %s %s",
                 muc_jid, affiliation, user_real_jid)

        self.remove_user_affiliation(muc_jid, user_real_jid)
        if affiliation == Affiliation.NONE:
            return

        self.add_user_affiliation(muc_jid, affiliation, user_real_jid)

    def get_users(
        self,
        jid: JID,
        *,
        include_outcast: bool = False
    ) -> dict[str, list[JID]]:

        affiliations = copy.deepcopy(self._affiliations[jid])
        if not include_outcast:
            affiliations.pop("outcast", None)
        return affiliations
