# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

# XEP-0030: Service Discovery

from __future__ import annotations

from typing import Optional
from typing import Union

import nbxmpp
from nbxmpp.errors import StanzaError
from nbxmpp.errors import is_error
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.protocol import JID
from nbxmpp.structs import DiscoInfo
from nbxmpp.structs import IqProperties
from nbxmpp.structs import StanzaHandler
from nbxmpp.task import Task

from gajim.common import app
from gajim.common import types
from gajim.common.events import ServerDiscoReceived
from gajim.common.events import MucDiscoUpdate
from gajim.common.modules.util import as_task
from gajim.common.modules.base import BaseModule


class Discovery(BaseModule):

    _nbxmpp_extends = 'Discovery'
    _nbxmpp_methods = [
        'disco_info',
        'disco_items',
    ]

    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self._answer_disco_info,
                          typ='get',
                          ns=Namespace.DISCO_INFO),
            StanzaHandler(name='iq',
                          callback=self._answer_disco_items,
                          typ='get',
                          ns=Namespace.DISCO_ITEMS),
        ]

        self._account_info: Optional[DiscoInfo] = None
        self._server_info: Optional[DiscoInfo] = None

    @property
    def account_info(self) -> Optional[DiscoInfo]:
        return self._account_info

    @property
    def server_info(self) -> Optional[DiscoInfo]:
        return self._server_info

    def discover_server_items(self) -> None:
        server = self._con.get_own_jid().domain
        self.disco_items(server, callback=self._server_items_received)

    def _server_items_received(self, task: Task) -> None:
        try:
            result = task.finish()
        except StanzaError as error:
            self._log.warning('Server disco failed')
            self._log.error(error)
            return

        self._log.info('Server items received')
        self._log.debug(result)
        for item in result.items:
            if item.node is not None:
                # Only disco components
                continue
            self.disco_info(item.jid, callback=self._server_items_info_received)

    def _server_items_info_received(self, task: Task) -> None:
        try:
            result = task.finish()
        except StanzaError as error:
            self._log.warning('Server item disco info failed')
            self._log.warning(error)
            return

        self._log.info('Server item info received: %s', result.jid)
        self._parse_transports(result)
        try:
            self._con.get_module('MUC').pass_disco(result)
            self._con.get_module('HTTPUpload').pass_disco(result)
            self._con.get_module('Bytestream').pass_disco(result)
        except nbxmpp.NodeProcessed:
            pass

        app.ged.raise_event(ServerDiscoReceived())

    def discover_account_info(self) -> None:
        own_jid = self._con.get_own_jid().bare
        self.disco_info(own_jid, callback=self._account_info_received)

    def _account_info_received(self, task: Task) -> None:
        try:
            result = task.finish()
        except StanzaError as error:
            self._log.warning('Account disco info failed')
            self._log.warning(error)
            return

        self._log.info('Account info received: %s', result.jid)

        self._account_info = result

        self._con.get_module('MAM').pass_disco(result)
        self._con.get_module('PEP').pass_disco(result)
        self._con.get_module('PubSub').pass_disco(result)
        self._con.get_module('Bookmarks').pass_disco(result)
        self._con.get_module('VCardAvatars').pass_disco(result)

        self._con.get_module('Caps').update_caps()

    def discover_server_info(self) -> None:
        # Calling this method starts the connect_maschine()
        server = self._con.get_own_jid().domain
        self.disco_info(server, callback=self._server_info_received)

    def _server_info_received(self, task: Task) -> None:
        try:
            result = task.finish()
        except StanzaError as error:
            self._log.error('Server disco info failed')
            self._log.error(error)
            return

        self._log.info('Server info received: %s', result.jid)

        self._server_info = result

        self._con.get_module('SecLabels').pass_disco(result)
        self._con.get_module('Blocking').pass_disco(result)
        self._con.get_module('VCardTemp').pass_disco(result)
        self._con.get_module('Carbons').pass_disco(result)
        self._con.get_module('HTTPUpload').pass_disco(result)
        self._con.get_module('Register').pass_disco(result)

        self._con.connect_machine(restart=True)

    def _parse_transports(self, info: DiscoInfo) -> None:
        for identity in info.identities:
            if identity.category not in ('gateway', 'headline'):
                continue

            self._log.info('Found transport: %s %s %s',
                           info.jid, identity.category, identity.type)

            jid = str(info.jid)
            if jid not in app.transport_type:
                app.transport_type[jid] = identity.type

            if identity.type in self._con.available_transports:
                self._con.available_transports[identity.type].append(jid)
            else:
                self._con.available_transports[identity.type] = [jid]

    def _answer_disco_items(self,
                            _con: types.xmppClient,
                            stanza: Iq,
                            _properties: IqProperties
                            ) -> None:
        from_ = stanza.getFrom()
        self._log.info('Answer disco items to %s', from_)

        node = stanza.getTagAttr('query', 'node')
        if node is None:
            result = stanza.buildReply('result')
            self._con.connection.send(result)
            raise nbxmpp.NodeProcessed

    def _answer_disco_info(self,
                           _con: types.xmppClient,
                           stanza: Iq,
                           _properties: IqProperties
                           ) -> None:
        from_ = stanza.getFrom()
        self._log.info('Answer disco info %s', from_)
        if str(from_).startswith('echo.'):
            # Service that echos all stanzas, ignore it
            raise nbxmpp.NodeProcessed

    @as_task
    def disco_muc(self,
                  jid: Union[JID, str],
                  request_vcard: bool = False,
                  allow_redirect: bool = False
                  ):

        _task = yield  # noqa: F841

        self._log.info('Request MUC info for %s', jid)

        result = yield self._nbxmpp('MUC').request_info(
            jid,
            request_vcard=request_vcard,
            allow_redirect=allow_redirect)

        if is_error(result):
            raise result

        if result.redirected:
            self._log.info('MUC info received after redirect: %s -> %s',
                           jid, result.info.jid)
        else:
            self._log.info('MUC info received: %s', result.info.jid)

        app.storage.cache.set_last_disco_info(result.info.jid, result.info)

        if result.vcard is not None:
            avatar, avatar_sha = result.vcard.get_avatar()
            if avatar is not None:
                if not app.interface.avatar_exists(avatar_sha):
                    app.interface.save_avatar(avatar)

                app.storage.cache.set_muc(result.info.jid, 'avatar', avatar_sha)
                app.app.avatar_storage.invalidate_cache(result.info.jid)

        self._con.get_module('VCardAvatars').muc_disco_info_update(result.info)
        app.ged.raise_event(MucDiscoUpdate(
            account=self._account,
            jid=result.info.jid))

        yield result

    @as_task
    def disco_contact(self, contact: types.ContactT):
        _task = yield  # noqa: F841

        result = yield self.disco_info(contact.jid)
        if is_error(result):
            raise result

        self._log.info('Disco Info received: %s', contact.jid)

        app.storage.cache.set_last_disco_info(result.jid,
                                              result,
                                              cache_only=True)

        contact = self._con.get_module('Contacts').get_contact(result.jid)
        contact.notify('caps-update')
