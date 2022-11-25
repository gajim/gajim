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

# XEP-0153: vCard-Based Avatars

from __future__ import annotations

from typing import Any
from typing import Callable
from typing import Generator
from typing import Optional

import weakref

from nbxmpp.const import AvatarState
from nbxmpp.modules.util import is_error
from nbxmpp.modules.vcard_temp import VCard
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.protocol import Presence
from nbxmpp.structs import DiscoInfo
from nbxmpp.structs import PresenceProperties
from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common import types
from gajim.common.task_manager import Task
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import as_task
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.modules.contacts import BareContact


class VCardAvatars(BaseModule):
    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)
        self._requested_shas: list[str] = []

        self.handlers = [
            StanzaHandler(name='presence',
                          typ='available',
                          callback=self._presence_received,
                          ns=Namespace.VCARD_UPDATE,
                          priority=51),
        ]

        self.avatar_conversion_available = False

        self._muc_avatar_cache: dict[JID, str] = {}

    def pass_disco(self, info: DiscoInfo) -> None:
        is_available = Namespace.VCARD_CONVERSION in info.features
        self.avatar_conversion_available = is_available
        self._log.info('Discovered Avatar Conversion')

    def get_avatar_sha(self, jid: JID) -> Optional[str]:
        return self._muc_avatar_cache.get(jid)

    @as_task
    def _request_vcard(self,
                       contact: types.ChatContactT,
                       expected_sha: str
                       ) -> Generator[VCard, None, None]:
        _task = yield  # noqa: F841

        vcard = yield self._con.get_module('VCardTemp').request_vcard(
            jid=contact.jid)

        if is_error(vcard):
            self._log.warning(vcard)
            return

        avatar, avatar_sha = vcard.get_avatar()
        if avatar is None:
            self._log.info('Avatar missing: %s %s', contact.jid, expected_sha)
            return

        if expected_sha != avatar_sha:
            self._log.warning('Avatar mismatch: %s %s != %s',
                              contact.jid,
                              expected_sha,
                              avatar_sha)
            return

        self._log.info('Received: %s %s', contact.jid, avatar_sha)
        app.app.avatar_storage.save_avatar(avatar)

        if isinstance(contact, BareContact):
            app.storage.cache.set_contact(contact.jid, 'avatar', avatar_sha)

        elif isinstance(contact, GroupchatContact):
            app.storage.cache.set_muc(contact.jid, 'avatar', avatar_sha)

        else:
            self._muc_avatar_cache[contact.jid] = avatar_sha

        contact.update_avatar(avatar_sha)

    def _presence_received(self,
                           _con: types.xmppClient,
                           _stanza: Presence,
                           properties: PresenceProperties
                           ) -> None:

        if properties.avatar_state in (AvatarState.IGNORE,
                                       AvatarState.NOT_READY):
            return

        if self._con.get_own_jid().bare_match(properties.jid):
            return

        if properties.from_muc:
            self._muc_update_received(properties)

        else:
            jid = properties.jid.new_as_bare()
            muc = self._con.get_module('MUC').get_muc_data(properties.jid)
            self._process_update(jid,
                                 properties.avatar_state,
                                 properties.avatar_sha,
                                 muc is not None)

    def muc_disco_info_update(self, disco_info: DiscoInfo) -> None:
        if not disco_info.supports(Namespace.VCARD):
            return

        field_var = '{http://modules.prosody.im/mod_vcard_muc}avatar#sha1'
        if not disco_info.has_field(Namespace.MUC_INFO, field_var):
            # Workaround so we don’t delete the avatar for servers that don’t
            # support sha in disco info. Once there is a accepted XEP this
            # can be removed
            return

        avatar_sha = disco_info.get_field_value(Namespace.MUC_INFO, field_var)
        state = AvatarState.EMPTY if not avatar_sha else AvatarState.ADVERTISED
        self._process_update(disco_info.jid, state, avatar_sha, True)

    def _process_update(self,
                        jid: JID,
                        state: AvatarState,
                        avatar_sha: str,
                        groupchat: bool
                        ) -> None:
        contact = self._con.get_module('Contacts').get_contact(
            jid, groupchat=groupchat)

        if state == AvatarState.EMPTY:
            # Empty <photo/> tag, means no avatar is advertised
            self._log.info('%s has no avatar published', jid)
            if groupchat:
                app.storage.cache.set_muc(jid, 'avatar', None)
            else:
                app.storage.cache.set_contact(jid, 'avatar', None)

            contact.update_avatar(avatar_sha)

        else:
            self._log.info('Update: %s %s', jid, avatar_sha)

            if avatar_sha == contact.avatar_sha:
                self._log.info('Avatar already known: %s %s', jid, avatar_sha)
                return

            if app.app.avatar_storage.avatar_exists(avatar_sha):
                # Check if the avatar is already in storage
                self._log.info('Found avatar in storage')
                if groupchat:
                    app.storage.cache.set_muc(jid, 'avatar', avatar_sha)
                else:
                    app.storage.cache.set_contact(jid, 'avatar', avatar_sha)

                contact.update_avatar(avatar_sha)
                return

            if avatar_sha not in self._requested_shas:
                self._requested_shas.append(avatar_sha)

                task = VCardAvatarsTask(contact,
                                        avatar_sha,
                                        self._request_vcard)
                app.task_manager.add_task(task)

    def _muc_update_received(self, properties: PresenceProperties) -> None:
        contact = self._con.get_module('Contacts').get_contact(properties.jid,
                                                               groupchat=True)
        assert isinstance(contact, GroupchatParticipant)

        # Custom ejabberd room config option
        allow_query = contact.room.get_config_value('allow_query_users')
        if allow_query is False:
            self._log.debug('Room does not allow IQ queries: %s',
                            contact.room.jid)
            return

        nick = properties.jid.resource

        if properties.avatar_state == AvatarState.EMPTY:
            # Empty <photo/> tag, means no avatar is advertised
            self._log.info('%s has no avatar published', nick)
            self._muc_avatar_cache.pop(properties.jid, None)
            contact.update_avatar()

        else:
            self._log.info('Update: %s %s', nick, properties.avatar_sha)
            if not app.app.avatar_storage.avatar_exists(properties.avatar_sha):
                if properties.avatar_sha not in self._requested_shas:
                    app.log('avatar').info('Request: %s', nick)
                    self._requested_shas.append(properties.avatar_sha)

                    task = VCardAvatarsTask(contact,
                                            properties.avatar_sha,
                                            self._request_vcard)
                    app.task_manager.add_task(task)
                return

            current_avatar_sha = self._muc_avatar_cache.get(properties.jid)
            if current_avatar_sha != properties.avatar_sha:
                self._log.info('%s changed their Avatar: %s',
                               nick, properties.avatar_sha)
                self._muc_avatar_cache[properties.jid] = properties.avatar_sha
                contact.update_avatar()

            else:
                self._log.info('Avatar already known: %s', nick)


class VCardAvatarsTask(Task):
    def __init__(self,
                 contact: Any,
                 sha: str,
                 callback: Callable[..., Any]
                 ) -> None:

        Task.__init__(self)
        self._contact = contact
        self._sha = sha
        self._callback = weakref.WeakMethod(callback)

    def execute(self) -> None:
        callback = self._callback()
        if callback is not None:
            callback(self._contact, self._sha)

    def preconditions_met(self) -> bool:
        try:
            client = app.get_client(self._contact.account)
        except Exception:
            self.set_obsolete()
            return False

        if not client.state.is_available:
            self.set_obsolete()
            return False

        if isinstance(self._contact, GroupchatParticipant):
            if not self._contact.room.is_joined:
                self.set_obsolete()
                return False

        return True

    def __repr__(self) -> str:
        return f'VCardAvatars ({self._contact.jid} {self._sha})'

    def __hash__(self) -> int:
        return hash((self._contact, self._sha))
