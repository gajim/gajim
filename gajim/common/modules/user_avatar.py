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
        jid = str(properties.jid)

        if metadata is None or not metadata.infos:
            self._log.info('No avatar published: %s', jid)
            app.contacts.set_avatar(self._account, jid, None)
            self._con.get_module('Roster').set_avatar_sha(jid, None)
            app.interface.update_avatar(self._account, jid)
        else:
            if properties.is_self_message:
                sha = app.settings.get_account_setting(self._account,
                                                       'avatar_sha')
            else:
                sha = app.contacts.get_avatar_sha(self._account, jid)

            if sha in metadata.avatar_shas:
                self._log.info('Avatar already known: %s %s', jid, sha)
                return

            avatar_info = metadata.infos[0]
            self._log.info('Request: %s %s', jid, avatar_info.id)
            self._request_avatar_data(jid, avatar_info)

    @as_task
    def _request_avatar_data(self, jid, avatar_info):
        _task = yield

        avatar = yield self._nbxmpp('UserAvatar').request_avatar_data(
            avatar_info.id, jid=jid)

        if avatar is None:
            self._log.warning('%s advertised %s but data node is empty',
                              jid, avatar_info.id)
            return

        if is_error(avatar):
            self._log.warning(avatar)
            return

        self._log.info('Received Avatar: %s %s', jid, avatar.sha)
        app.interface.save_avatar(avatar.data)

        if self._con.get_own_jid().bare_match(jid):
            app.settings.set_account_setting(self._account,
                                             'avatar_sha',
                                             avatar.sha)
        else:
            self._con.get_module('Roster').set_avatar_sha(
                str(jid), avatar.sha)

        app.contacts.set_avatar(self._account, str(jid), avatar.sha)
        app.interface.update_avatar(self._account, str(jid))


def get_instance(*args, **kwargs):
    return UserAvatar(*args, **kwargs), 'UserAvatar'
