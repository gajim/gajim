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

# XEP-0084: User Avatar

from __future__ import annotations

from typing import Generator

from nbxmpp.modules.user_avatar import AvatarData
from nbxmpp.modules.util import is_error
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Message
from nbxmpp.structs import MessageProperties

from gajim.common import app
from gajim.common import types
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import as_task
from gajim.common.modules.util import event_node


class UserAvatar(BaseModule):

    _nbxmpp_extends = 'UserAvatar'
    _nbxmpp_methods = [
        'request_avatar_metadata',
        'request_avatar_data',
        'set_avatar',
        'set_access_model'
    ]

    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)
        self._register_pubsub_handler(self._avatar_metadata_received)

    @event_node(Namespace.AVATAR_METADATA)
    def _avatar_metadata_received(self,
                                  _con: types.xmppClient,
                                  _stanza: Message,
                                  properties: MessageProperties
                                  ) -> None:
        if properties.pubsub_event.retracted:
            return

        metadata = properties.pubsub_event.data
        jid = properties.jid
        contact = self._con.get_module('Contacts').get_contact(jid)

        if metadata is None or not metadata.infos:
            self._log.info('No avatar published: %s', jid)
            contact.update_avatar(None)
            return

        sha = contact.avatar_sha
        if sha is not None:
            if (sha in metadata.avatar_shas and
                    app.app.avatar_storage.avatar_exists(sha)):
                self._log.info('Avatar already known: %s %s', jid, sha)
                return

        if app.app.avatar_storage.avatar_exists(metadata.default):
            self._log.info('Avatar found in cache, update: %s %s',
                           jid, metadata.default)
            contact.update_avatar(metadata.default)
            return

        # There are following cases this code is reached:
        # - We lost the avatar cache
        # - We use an outdated avatar
        # - We currently have no avatar set
        #
        # Reset the sha, because we don’t know if the avatar data query will
        # succeed. This forces an update of the avatar if the query succeeds.
        contact.update_avatar(None)
        self._request_avatar_data(contact, metadata.default)

    @as_task
    def _request_avatar_data(self,
                             contact: types.ChatContactT,
                             sha: str
                             ) -> Generator[AvatarData | None, None, None]:

        self._log.info('Request: %s %s', contact.jid, sha)

        _task = yield  # noqa: F841

        avatar = yield self._nbxmpp('UserAvatar').request_avatar_data(
            sha, jid=contact.jid)

        if avatar is None:
            self._log.warning('%s advertised %s but data node is empty',
                              contact.jid, sha)
            return

        if is_error(avatar):
            self._log.warning(avatar)
            return

        self._log.info('Received Avatar: %s %s', contact.jid, avatar.sha)
        app.app.avatar_storage.save_avatar(avatar.data)
        contact.update_avatar(avatar.sha)
