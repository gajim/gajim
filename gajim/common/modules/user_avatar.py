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
from nbxmpp.util import is_error_result

from gajim.common import app
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import event_node


class UserAvatar(BaseModule):

    _nbxmpp_extends = 'UserAvatar'
    _nbxmpp_methods = [
        'request_avatar'
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)
        self._register_pubsub_handler(self._avatar_metadata_received)

    @event_node(Namespace.AVATAR_METADATA)
    def _avatar_metadata_received(self, _con, _stanza, properties):
        if properties.pubsub_event.retracted:
            return

        data = properties.pubsub_event.data
        jid = str(properties.jid)
        own_jid = self._con.get_own_jid().getBare()

        if data is None:
            # Remove avatar
            self._log.info('Remove: %s', jid)
            app.contacts.set_avatar(self._account, jid, None)
            app.logger.set_avatar_sha(own_jid, jid, None)
            app.interface.update_avatar(self._account, jid)
        else:
            if properties.is_self_message:
                sha = app.settings.get_account_setting(self._account,
                                                       'avatar_sha')
            else:
                sha = app.contacts.get_avatar_sha(self._account, jid)

            if sha == data.id:
                self._log.info('Avatar already known: %s %s', jid, data.id)
                return

            self._log.info('Request: %s %s', jid, data.id)
            self._nbxmpp('UserAvatar').request_avatar(
                jid, data.id, callback=self._avatar_received)

    def _avatar_received(self, result):
        if is_error_result(result):
            self._log.info(result)
            return

        self._log.info('Received Avatar: %s %s', result.jid, result.sha)
        app.interface.save_avatar(result.data)

        if self._con.get_own_jid().bareMatch(result.jid):
            app.settings.set_account_setting(self._account,
                                             'avatar_sha',
                                             result.sha)
        else:
            own_jid = self._con.get_own_jid().getBare()
            app.logger.set_avatar_sha(own_jid, str(result.jid), result.sha)

        app.contacts.set_avatar(self._account, str(result.jid), result.sha)
        app.interface.update_avatar(self._account, str(result.jid))


def get_instance(*args, **kwargs):
    return UserAvatar(*args, **kwargs), 'UserAvatar'
