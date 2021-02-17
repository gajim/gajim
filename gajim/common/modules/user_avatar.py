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

from nbxmpp.namespaces import Namespace
from nbxmpp.modules.util import is_error

from gajim.common import app
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import event_node
from gajim.common.modules.util import as_task

class UserAvatar(BaseModule):

    _nbxmpp_extends = 'UserAvatar'
    _nbxmpp_methods = [
        'request_avatar_metadata',
        'request_avatar_data',
        'set_avatar',
        'set_access_model'
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)
        self._register_pubsub_handler(self._avatar_metadata_received)

    @event_node(Namespace.AVATAR_METADATA)
    def _avatar_metadata_received(self, _con, _stanza, properties):
        if properties.pubsub_event.retracted:
            return

        metadata = properties.pubsub_event.data
        jid = properties.jid
        contact = self._con.get_module('Contacts').get_contact(jid)

        if metadata is None or not metadata.infos:
            self._log.info('No avatar published: %s', jid)
            app.storage.cache.set_contact(jid, 'avatar', None)
            contact.update_avatar(None)

        else:
            sha = contact.avatar_sha
            if contact.avatar_sha:
                if sha in metadata.avatar_shas:
                    self._log.info('Avatar already known: %s %s', jid, sha)
                    return

                if app.interface.avatar_exists(sha):
                    contact.update_avatar(sha)
                    return

            self._log.info('Request: %s %s', jid, metadata.default)
            self._request_avatar_data(contact, metadata.default)

    @as_task
    def _request_avatar_data(self, contact, sha):
        _task = yield

        avatar = yield self._nbxmpp('UserAvatar').request_avatar_data(
            sha, jid=contact.jid)

        if avatar is None:
            self._log.warning('%s advertised %s but data node is empty',
                              contact.jid, sha)
            return

        if avatar is None:
            self._log.warning('%s advertised %s but data node is empty',
                              jid, avatar_info.id)
            return

        if is_error(avatar):
            self._log.warning(avatar)
            return

        self._log.info('Received Avatar: %s %s', contact.jid, avatar.sha)
        app.interface.save_avatar(avatar.data)
        contact.update_avatar(avatar.sha)


def get_instance(*args, **kwargs):
    return UserAvatar(*args, **kwargs), 'UserAvatar'
