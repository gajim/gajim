# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# Iq handler

from __future__ import annotations

import nbxmpp
from nbxmpp.structs import IqProperties
from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common import types
from gajim.common.events import FileRequestError
from gajim.common.events import FileSendError
from gajim.common.file_props import FilesProp
from gajim.common.helpers import to_user_string
from gajim.common.modules.base import BaseModule


class Iq(BaseModule):
    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self._iq_error_received,
                          typ='error',
                          priority=51),
        ]

    def _iq_error_received(self,
                           _con: types.xmppClient,
                           _stanza: nbxmpp.protocol.Iq,
                           properties: IqProperties
                           ) -> None:
        self._log.info('Error: %s', properties.error)
        assert properties.error is not None
        if properties.error.condition in ('jid-malformed',
                                          'forbidden',
                                          'not-acceptable'):
            sid = self._get_sid(properties.id)
            file_props = FilesProp.getFileProp(self._account, sid)
            if file_props:
                if properties.error.condition == 'jid-malformed':
                    file_props.error = -3
                else:
                    file_props.error = -4
                app.ged.raise_event(
                    FileRequestError(
                        conn=self._con,
                        jid=properties.jid.bare,
                        file_props=file_props,
                        error_msg=to_user_string(properties.error)))
                self._con.get_module('Bytestream').disconnect_transfer(
                    file_props)
                raise nbxmpp.NodeProcessed

        if properties.error.condition == 'item-not-found':
            sid = self._get_sid(properties.id)
            file_props = FilesProp.getFileProp(self._account, sid)
            if file_props:
                app.ged.raise_event(
                    FileSendError(account=self._account,
                                  jid=str(properties.jid),
                                  file_props=file_props,
                                  error_msg=''))
                self._con.get_module('Bytestream').disconnect_transfer(
                    file_props)
                raise nbxmpp.NodeProcessed

        self._log.error('Received iq error with unknown id: %s',
                        properties.error)

        raise nbxmpp.NodeProcessed

    @staticmethod
    def _get_sid(id_: str) -> str:
        sid = id_
        if len(id_) > 3 and id_[2] == '_':
            sid = id_[3:]
        return sid
