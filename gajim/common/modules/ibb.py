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
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

# XEP-0047: In-Band Bytestreams

import time

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import NodeProcessed
from nbxmpp.structs import StanzaHandler
from nbxmpp.errors import StanzaError

from gajim.common import app
from gajim.common.helpers import to_user_string
from gajim.common.modules.base import BaseModule
from gajim.common.file_props import FilesProp


class IBB(BaseModule):

    _nbxmpp_extends = 'IBB'
    _nbxmpp_methods = [
        'send_open',
        'send_close',
        'send_data',
        'send_reply',
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self._ibb_received,
                          ns=Namespace.IBB),
        ]

    def _ibb_received(self, _con, stanza, properties):
        if not properties.is_ibb:
            return

        if properties.ibb.type == 'data':
            self._log.info('Data received, sid: %s, seq: %s',
                           properties.ibb.sid, properties.ibb.seq)
            file_props = FilesProp.getFilePropByTransportSid(self._account,
                                                             properties.ibb.sid)
            if not file_props:
                self.send_reply(stanza, nbxmpp.ERR_ITEM_NOT_FOUND)
                raise NodeProcessed

            if file_props.connected:
                self._on_data_received(stanza, file_props, properties)
                self.send_reply(stanza)

        elif properties.ibb.type == 'open':
            self._log.info('Open received, sid: %s, blocksize: %s',
                           properties.ibb.sid, properties.ibb.block_size)

            file_props = FilesProp.getFilePropByTransportSid(self._account,
                                                             properties.ibb.sid)
            if not file_props:
                self.send_reply(stanza, nbxmpp.ERR_ITEM_NOT_FOUND)
                raise NodeProcessed

            file_props.block_size = properties.ibb.block_size
            file_props.direction = '<'
            file_props.seq = 0
            file_props.received_len = 0
            file_props.last_time = time.time()
            file_props.error = 0
            file_props.paused = False
            file_props.connected = True
            file_props.completed = False
            file_props.disconnect_cb = None
            file_props.continue_cb = None
            file_props.syn_id = stanza.getID()
            file_props.fp = open(file_props.file_name, 'wb')
            self.send_reply(stanza)

        elif properties.ibb.type == 'close':
            self._log.info('Close received, sid: %s', properties.ibb.sid)
            file_props = FilesProp.getFilePropByTransportSid(self._account,
                                                             properties.ibb.sid)
            if not file_props:
                self.send_reply(stanza, nbxmpp.ERR_ITEM_NOT_FOUND)
                raise NodeProcessed

            self.send_reply(stanza)
            file_props.fp.close()
            file_props.completed = file_props.received_len >= file_props.size
            if not file_props.completed:
                file_props.error = -1
            app.socks5queue.complete_transfer_cb(self._account, file_props)

        raise NodeProcessed

    def _on_data_received(self, stanza, file_props, properties):
        ibb = properties.ibb
        if ibb.seq != file_props.seq:
            self.send_reply(stanza, nbxmpp.ERR_UNEXPECTED_REQUEST)
            self.send_close(file_props)
            raise NodeProcessed

        self._log.debug('Data received: sid: %s, %s+%s bytes',
                        ibb.sid, file_props.fp.tell(), len(ibb.data))

        file_props.seq += 1
        file_props.started = True
        file_props.fp.write(ibb.data)
        current_time = time.time()
        file_props.elapsed_time += current_time - file_props.last_time
        file_props.last_time = current_time
        file_props.received_len += len(ibb.data)
        app.socks5queue.progress_transfer_cb(self._account, file_props)
        if file_props.received_len >= file_props.size:
            file_props.completed = True

    def send_open(self, to, sid, fp):
        self._log.info('Send open to %s, sid: %s', to, sid)
        file_props = FilesProp.getFilePropBySid(sid)
        file_props.direction = '>'
        file_props.block_size = 4096
        file_props.fp = fp
        file_props.seq = -1
        file_props.error = 0
        file_props.paused = False
        file_props.received_len = 0
        file_props.last_time = time.time()
        file_props.connected = True
        file_props.completed = False
        file_props.disconnect_cb = None
        file_props.continue_cb = None
        self._nbxmpp('IBB').send_open(to,
                                      file_props.transport_sid,
                                      4096,
                                      callback=self._on_open_result,
                                      user_data=file_props)
        return file_props

    def _on_open_result(self, task):
        try:
            task.finish()
        except StanzaError as error:
            app.socks5queue.error_cb('Error', to_user_string(error))
            self._log.warning(error)
            return

        file_props = task.get_user_data()
        self.send_data(file_props)

    def send_close(self, file_props):
        file_props.connected = False
        file_props.fp.close()
        file_props.stopped = True
        to = file_props.receiver
        if file_props.direction == '<':
            to = file_props.sender

        self._log.info('Send close to %s, sid: %s',
                       to, file_props.transport_sid)
        self._nbxmpp('IBB').send_close(to, file_props.transport_sid,
                                       callback=self._on_close_result)

        if file_props.completed:
            app.socks5queue.complete_transfer_cb(self._account, file_props)
        else:
            if file_props.type_ == 's':
                peerjid = file_props.receiver
            else:
                peerjid = file_props.sender
            session = self._con.get_module('Jingle').get_jingle_session(
                peerjid, file_props.sid, 'file')
            # According to the xep, the initiator also cancels
            # the jingle session if there are no more files to send using IBB
            if session.weinitiate:
                session.cancel_session()

    def _on_close_result(self, task):
        try:
            task.finish()
        except StanzaError as error:
            app.socks5queue.error_cb('Error', to_user_string(error))
            self._log.warning(error)
            return

    def send_data(self, file_props):
        if file_props.completed:
            self.send_close(file_props)
            return

        chunk = file_props.fp.read(file_props.block_size)
        if chunk:
            file_props.seq += 1
            file_props.started = True
            if file_props.seq == 65536:
                file_props.seq = 0

            self._log.info('Send data to %s, sid: %s',
                           file_props.receiver, file_props.transport_sid)
            self._nbxmpp('IBB').send_data(file_props.receiver,
                                          file_props.transport_sid,
                                          file_props.seq,
                                          chunk,
                                          callback=self._on_data_result,
                                          user_data=file_props)
            current_time = time.time()
            file_props.elapsed_time += current_time - file_props.last_time
            file_props.last_time = current_time
            file_props.received_len += len(chunk)
            if file_props.size == file_props.received_len:
                file_props.completed = True
            app.socks5queue.progress_transfer_cb(self._account, file_props)

    def _on_data_result(self, task):
        try:
            task.finish()
        except StanzaError as error:
            app.socks5queue.error_cb('Error', to_user_string(error))
            self._log.warning(error)
            return

        file_props = task.get_user_data()
        self.send_data(file_props)


def get_instance(*args, **kwargs):
    return IBB(*args, **kwargs), 'IBB'
