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

import logging
import base64
import binascii

import nbxmpp

from gajim.common import app
from gajim.common.const import PEPEventType
from gajim.common.exceptions import StanzaMalformed
from gajim.common.modules.pep import AbstractPEPModule, AbstractPEPData

log = logging.getLogger('gajim.c.m.user_avatar')


class UserAvatarData(AbstractPEPData):

    type_ = PEPEventType.AVATAR

    def __init__(self, avatar):
        self._pep_specific_data = avatar


class UserAvatar(AbstractPEPModule):

    name = 'user-avatar'
    namespace = 'urn:xmpp:avatar:metadata'
    pep_class = UserAvatarData
    store_publish = False
    _log = log

    def __init__(self, con):
        AbstractPEPModule.__init__(self, con, con.name)

        self.handlers = []

    def get_pubsub_avatar(self, jid, item_id):
        log.info('Request: %s %s', jid, item_id)
        self._con.get_module('PubSub').send_pb_retrieve(
            jid, 'urn:xmpp:avatar:data', item_id, self._avatar_received)

    def _validate_avatar_node(self, stanza):
        jid = stanza.getFrom()
        if jid is None:
            jid = self._con.get_own_jid().getStripped()
        else:
            jid = jid.getStripped()

        if nbxmpp.isErrorNode(stanza):
            raise StanzaMalformed(stanza.getErrorMsg())

        pubsub_node = stanza.getTag('pubsub')
        if pubsub_node is None:
            raise StanzaMalformed('No pubsub node', stanza)

        items_node = pubsub_node.getTag('items')
        if items_node is None:
            raise StanzaMalformed('No items node', stanza)

        if items_node.getAttr('node') != 'urn:xmpp:avatar:data':
            raise StanzaMalformed('Wrong namespace', stanza)

        item = items_node.getTag('item')
        if item is None:
            raise StanzaMalformed('No item node', stanza)

        sha = item.getAttr('id')
        data_tag = item.getTag('data', namespace='urn:xmpp:avatar:data')
        if sha is None or data_tag is None:
            raise StanzaMalformed('No id attr or data node found', stanza)

        data = data_tag.getData()
        if data is None:
            raise StanzaMalformed('Data node empty', stanza)

        data = base64.b64decode(data.encode('utf-8'))

        return jid, sha, data

    def _avatar_received(self, _con, stanza):
        try:
            jid, sha, data = self._validate_avatar_node(stanza)
        except (StanzaMalformed, binascii.Error) as error:
            log.warning('Error: %s %s', stanza.getFrom(), error)
            return

        log.info('Received Avatar: %s %s', jid, sha)
        app.interface.save_avatar(data)

        if self._con.get_own_jid().bareMatch(jid):
            app.config.set_per('accounts', self._account, 'avatar_sha', sha)
        else:
            own_jid = self._con.get_own_jid().getStripped()
            app.logger.set_avatar_sha(own_jid, jid, sha)

        app.contacts.set_avatar(self._account, jid, sha)
        app.interface.update_avatar(self._account, jid)

    def _extract_info(self, item):
        metadata = item.getTag('metadata', namespace=self.namespace)
        if metadata is None:
            raise StanzaMalformed('No metadata node')

        info = metadata.getTags('info', one=True)
        if not info:
            return None

        avatar = info.getAttrs()
        return avatar or None

    def _notification_received(self, jid, user_pep):
        avatar = user_pep._pep_specific_data
        own_jid = self._con.get_own_jid()
        if avatar is None:
            # Remove avatar
            log.info('Remove: %s', jid)
            app.contacts.set_avatar(self._account, str(jid), None)
            app.logger.set_avatar_sha(own_jid.getStripped(), str(jid), None)
            app.interface.update_avatar(self._account, str(jid))
        else:
            if own_jid.bareMatch(jid):
                sha = app.config.get_per(
                    'accounts', self._account, 'avatar_sha')
            else:
                sha = app.contacts.get_avatar_sha(self._account, str(jid))

            if sha == avatar['id']:
                log.info('Avatar already known: %s %s',
                         jid, avatar['id'])
                return
            self.get_pubsub_avatar(jid, avatar['id'])

    def _build_node(self, data):
        raise NotImplementedError

    def send(self, data):
        # Not implemented yet
        return

    def retract(self):
        # Not implemented yet
        return


def get_instance(*args, **kwargs):
    return UserAvatar(*args, **kwargs), 'UserAvatar'
