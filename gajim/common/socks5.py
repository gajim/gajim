# Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
#                         Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2005-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
#
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

import socket
import struct
import hashlib
import os
import time
import sys
import logging
from errno import EWOULDBLOCK
from errno import ENOBUFS
from errno import EINTR
from errno import EISCONN
from errno import EINPROGRESS
from errno import EAFNOSUPPORT

from nbxmpp.idlequeue import IdleObject

from gajim.common.file_props import FilesProp
from gajim.common import app

log = logging.getLogger('gajim.c.socks5')
MAX_BUFF_LEN = 65536
# after foo seconds without activity label transfer as 'stalled'
STALLED_TIMEOUT = 10
# after foo seconds of waiting to connect, disconnect from
# streamhost and try next one
CONNECT_TIMEOUT = 30
# nothing received for the last foo seconds - stop transfer
# if it is 0, then transfer will wait forever
READ_TIMEOUT = 180
# nothing sent for the last foo seconds - stop transfer
# if it is 0, then transfer will wait forever
SEND_TIMEOUT = 180


class SocksQueue:
    """
    Queue for all file requests objects
    """

    def __init__(self, idlequeue, complete_transfer_cb=None,
    progress_transfer_cb=None, error_cb=None):
        self.connected = 0
        self.readers = {}
        self.senders = {}
        self.idx = 1
        self.listener = None
        self.sha_handlers = {}
        # handle all io events in the global idle queue, instead of processing
        # each foo seconds
        self.idlequeue = idlequeue
        self.complete_transfer_cb = complete_transfer_cb
        self.progress_transfer_cb = progress_transfer_cb
        self.error_cb = error_cb
        self.on_success = {} # {id: cb}
        self.on_failure = {} # {id: cb}

    def start_listener(self, port, sha_str, sha_handler, file_props,
                       typ='sender'):
        """
        Start waiting for incoming connections on (host, port) and do a socks5
        authentication using sid for generated SHA
        """
        log.debug('Start listening for socks5 connection')
        sid = file_props.sid
        self.sha_handlers[sha_str] = (sha_handler, sid)
        if self.listener is None or not self.listener.connections:
            self.listener = Socks5Listener(self.idlequeue, port, file_props)
            self.listener.queue = self
            self.listener.bind()
        else:
            # There is already a listener, we update the file's information
            # on the new connection.
            self.listener.file_props = file_props
        self.connected += 1
        return self.listener

    def send_success_reply(self, file_props, streamhost):
        if file_props.streamhost_used is True:
            for proxy in file_props.proxyhosts:
                if proxy['host'] == streamhost['host']:
                    self.on_success[file_props.transport_sid](proxy)
                    return 1
            return 0
        for host in file_props.streamhosts:
            if host['state'] == 1:
                # on_success callback already called for another host
                return 0 # return 0 to disconnect this one
        streamhost['state'] = 1
        self.on_success[file_props.transport_sid](streamhost)
        return 1

    def connect_to_hosts(self, account, transport_sid, on_success=None,
                         on_failure=None, receiving=True):
        self.on_success[transport_sid] = on_success
        self.on_failure[transport_sid] = on_failure
        file_props = FilesProp.getFilePropByTransportSid(account, transport_sid)
        file_props.failure_cb = on_failure
        streamhosts_to_test = []
        # Remove local IPs to not connect to ourself
        for streamhost in file_props.streamhosts:
            if streamhost['host'] == '127.0.0.1' or streamhost['host'] == '::1':
                continue
            streamhosts_to_test.append(streamhost)
        if not streamhosts_to_test:
            on_failure(file_props.transport_sid)
        # add streamhosts to the queue
        for streamhost in streamhosts_to_test:
            if receiving:
                if 'candidate_id' in streamhost:
                    log.debug('Trying to connect as receiver to cid %s',
                              streamhost['candidate_id'])
                else:
                    log.debug('Trying to connect as receiver to jid %s',
                              streamhost['jid'])
                file_props.type_ = 'r'
                socks5obj = Socks5ReceiverClient(self.idlequeue, streamhost,
                    transport_sid, file_props)
                self.add_sockobj(account, socks5obj)
            else:
                if 'candidate_id' in streamhost:
                    log.debug('Trying to connect as sender to cid %s',
                              streamhost['candidate_id'])
                else:
                    log.debug('Trying to connect as sender to jid %s',
                              streamhost['jid'])
                if file_props.sha_str:
                    idx = file_props.sha_str
                else:
                    idx = self.idx
                    self.idx = self.idx + 1
                file_props.type_ = 's'
                if 'type' in streamhost and streamhost['type'] == 'proxy':
                    file_props.is_a_proxy = True
                    file_props.proxy_sender = streamhost['target']
                    file_props.proxy_receiver = streamhost['initiator']
                socks5obj = Socks5SenderClient(self.idlequeue, idx,
                    self, _sock=None, host=str(streamhost['host']),
                    port=int(streamhost['port']),
                    connected=False, file_props=file_props,
                    initiator=streamhost['initiator'],
                    target=streamhost['target'])
                socks5obj.streamhost = streamhost
                self.add_sockobj(account, socks5obj)

            streamhost['idx'] = socks5obj.queue_idx

    def _socket_connected(self, streamhost, file_props):
        """
        Called when there is a host connected to one of the senders's
        streamhosts. Stop other attempts for connections
        """
        if 'candidate_id' in streamhost:
            log.debug('Connected to cid %s', streamhost['candidate_id'])
        else:
            log.debug('Connected to jid %s', streamhost['jid'])
        for host in file_props.streamhosts:
            if host != streamhost and 'idx' in host:
                if host['state'] == 1:
                    # remove current
                    if file_props.type_ == 's':
                        self.remove_sender(streamhost['idx'], False)
                    else:
                        self.remove_receiver(streamhost['idx'])
                    return
                # set state -2, meaning that this streamhost is stopped,
                # but it may be connected later
                if host['state'] >= 0:
                    if file_props.type_ == 's':
                        self.remove_sender(host['idx'], False)
                    else:
                        self.remove_receiver(host['idx'])
                    host['idx'] = -1
                    host['state'] = -2

    def reconnect_client(self, client, streamhost):
        """
        Check the state of all streamhosts and if all has failed, then emit
        connection failure cb. If there are some which are still not connected
        try to establish connection to one of them
        """
        self.idlequeue.remove_timeout(client.fd)
        self.idlequeue.unplug_idle(client.fd)
        file_props = client.file_props
        streamhost['state'] = -1
        # boolean, indicates that there are hosts, which are not tested yet
        unused_hosts = False
        for host in file_props.streamhosts:
            if 'idx' in host:
                if host['state'] >= 0:
                    return
                if host['state'] == -2:
                    unused_hosts = True
        if unused_hosts:
            for host in file_props.streamhosts:
                if host['state'] == -2:
                    host['state'] = 0
                    # FIXME: make the sender reconnect also
                    client = Socks5ReceiverClient(self.idlequeue, host,
                        client.sid, file_props)
                    self.add_sockobj(client.account, client)
                    host['idx'] = client.queue_idx
            # we still have chances to connect
            return
        if file_props.received_len == 0:
            # there are no other streamhosts and transfer hasn't started
            self._connection_refused(streamhost, file_props, client.queue_idx)
        else:
            # transfer stopped, it is most likely stopped from sender
            client.disconnect()
            file_props.error = -1
            self.process_result(-1, client)

    def _connection_refused(self, streamhost, file_props, idx):
        """
        Called when we loose connection during transfer
        """
        if 'candidate_id' in streamhost:
            log.debug('Connection refused to cid %s',
                      streamhost['candidate_id'])
        else:
            log.debug('Connection refused to jid %s', streamhost['jid'])
        if file_props is None:
            return
        streamhost['state'] = -1
        # FIXME: should only the receiver be remove? what if we are sending?
        self.remove_receiver(idx, False)
        for host in file_props.streamhosts:
            if host['state'] != -1:
                return
        self.readers = {}
        # failure_cb exists - this means that it has never been called
        if file_props.failure_cb:
            file_props.failure_cb(file_props.transport_sid)
            file_props.failure_cb = None

    def add_sockobj(self, account, sockobj):
        """
        Add new file a sockobj type receiver or sender, and use it to connect
        to server
        """
        if sockobj.file_props.type_ == 'r':
            self._add(sockobj, self.readers, sockobj.file_props, self.idx)
        else:
            self._add(sockobj, self.senders, sockobj.file_props, self.idx)
        sockobj.queue_idx = self.idx
        sockobj.queue = self
        sockobj.account = account
        self.idx += 1
        result = sockobj.connect()
        self.connected += 1
        if result is not None:
            result = sockobj.main()
            self.process_result(result, sockobj)
            return 1
        return None

    def _add(self, sockobj, sockobjects, file_props, hash_):
        '''
        Adds the sockobj to the current list of sockobjects
        '''
        keys = (file_props.transport_sid, file_props.name, hash_)
        sockobjects[keys] = sockobj

    def result_sha(self, sha_str, idx):
        if sha_str in self.sha_handlers:
            props = self.sha_handlers[sha_str]
            props[0](props[1], idx)

    def activate_proxy(self, idx):
        if not self.isHashInSockObjs(self.senders, idx):
            return
        for key in list(self.senders):
            if idx in key:
                sender = self.senders[key]
                if sender.file_props.type_ != 's':
                    return
                sender.state = 6
                if sender.connected:
                    sender.file_props.error = 0
                    sender.file_props.disconnect_cb = sender.disconnect
                    sender.file_props.started = True
                    sender.file_props.completed = False
                    sender.file_props.paused = False
                    sender.file_props.stalled = False
                    sender.file_props.elapsed_time = 0
                    sender.file_props.last_time = time.time()
                    sender.file_props.received_len = 0
                    sender.pauses = 0
                    # start sending file to proxy
                    self.idlequeue.set_read_timeout(sender.fd, STALLED_TIMEOUT)
                    self.idlequeue.plug_idle(sender, True, False)
                    result = sender.write_next()
                    self.process_result(result, sender)

    def send_file(self, file_props, account, mode):
        for key in list(self.senders.keys()):
            if file_props.name in key and file_props.transport_sid in key \
            and self.senders[key].mode == mode:
                log.info('socks5: sending file')
                sender = self.senders[key]
                file_props.streamhost_used = True
                sender.account = account
                sender.file_props = file_props
                result = sender.send_file()
                self.process_result(result, sender)

    def isHashInSockObjs(self, sockobjs, hash_):
        '''
        It tells whether there is a particular hash in sockobjs or not
        '''
        for key in sockobjs:
            if hash_ in key:
                return True
        return False

    def on_connection_accepted(self, sock, listener):
        sock_hash = hash(sock)
        if listener.file_props.type_ == 's' and \
        not self.isHashInSockObjs(self.senders, sock_hash):
            sockobj = Socks5SenderServer(self.idlequeue, sock_hash, self,
                sock[0], sock[1][0], sock[1][1],
                file_props=listener.file_props)
            self._add(sockobj, self.senders, listener.file_props, sock_hash)
            # Start waiting for data
            self.idlequeue.plug_idle(sockobj, False, True)
            self.connected += 1
        if listener.file_props.type_ == 'r' and \
        not self.isHashInSockObjs(self.readers, sock_hash):
            sh = {}
            sh['host'] = sock[1][0]
            sh['port'] = sock[1][1]
            sh['initiator'] = None
            sh['target'] = None
            sockobj = Socks5ReceiverServer(idlequeue=self.idlequeue,
                streamhost=sh, transport_sid=None,
                file_props=listener.file_props)

            self._add(sockobj, self.readers, listener.file_props, sock_hash)
            sockobj.set_sock(sock[0])
            sockobj.queue = self
            self.connected += 1

    def process_result(self, result, actor):
        """
        Take appropriate actions upon the result:
                [ 0, - 1 ] complete/end transfer
                [ > 0 ] send progress message
                [ None ] do nothing
        """
        if result is None:
            return
        if result in (0, -1) and self.complete_transfer_cb is not None:
            account = actor.account
            if account is None and actor.file_props.tt_account:
                account = actor.file_props.tt_account
            self.complete_transfer_cb(account, actor.file_props)
        elif self.progress_transfer_cb is not None:
            self.progress_transfer_cb(actor.account, actor.file_props)

    def remove_receiver_by_key(self, key, do_disconnect=True):
        reader = self.readers[key]
        self.idlequeue.unplug_idle(reader.fd)
        self.idlequeue.remove_timeout(reader.fd)
        if do_disconnect:
            reader.disconnect()
        else:
            if reader.streamhost is not None:
                reader.streamhost['state'] = -1
        del self.readers[key]

    def remove_sender_by_key(self, key, do_disconnect=True):
        sender = self.senders[key]
        if do_disconnect:
            sender.disconnect()
        self.idlequeue.unplug_idle(sender.fd)
        self.idlequeue.remove_timeout(sender.fd)
        del self.senders[key]
        if self.connected > 0:
            self.connected -= 1

    def remove_receiver(self, idx, do_disconnect=True, remove_all=False):
        """
        Remove receiver from the list and decrease the number of active
        connections with 1
        """
        if idx != -1:
            for key in list(self.readers.keys()):
                if idx in key:
                    self.remove_receiver_by_key(
                        key, do_disconnect=do_disconnect)
                    if not remove_all:
                        break

    def remove_sender(self, idx, do_disconnect=True, remove_all=False):
        """
        Remove sender from the list of senders and decrease the number of active
        connections with 1
        """
        if idx != -1:
            for key in list(self.senders.keys()):
                if idx in key:
                    self.remove_sender_by_key(key, do_disconnect=do_disconnect)
                    if not remove_all:
                        break
            if not self.senders and self.listener is not None:
                self.listener.disconnect()
                self.listener = None
                self.connected -= 1

    def remove_by_mode(self, transport_sid, mode, do_disconnect=True):
        for (key, sock) in self.senders.copy().items():
            if key[0] == transport_sid and sock.mode == mode:
                self.remove_sender_by_key(key)
        for (key, sock) in self.readers.copy().items():
            if key[0] == transport_sid and sock.mode == mode:
                self.remove_receiver_by_key(key)

    def remove_server(self, transport_sid, do_disconnect=True):
        self.remove_by_mode(transport_sid, 'server')

    def remove_client(self, transport_sid, do_disconnect=True):
        self.remove_by_mode(transport_sid, 'client')

    def remove_other_servers(self, host_to_keep):
        for (key, sock) in self.senders.copy().items():
            if sock.host != host_to_keep and sock.mode == 'server':
                self.remove_sender_by_key(key)

class Socks5:
    def __init__(self, idlequeue, host, port, initiator, target, sid):
        if host is not None:
            try:
                self.host = host
                self.ais = socket.getaddrinfo(host, port, socket.AF_UNSPEC,
                    socket.SOCK_STREAM)
            except socket.gaierror:
                self.ais = None
        self.idlequeue = idlequeue
        self.fd = -1
        self.port = port
        self.initiator = initiator
        self.target = target
        self.sid = sid
        self._sock = None
        self.account = None
        self.state = 0 # not connected
        self.pauses = 0
        self.size = 0
        self.remaining_buff = b''
        self.file = None
        self.connected = False
        self.mode = ''

    def _is_connected(self):
        if self.state < 5:
            return False
        return True

    def connect(self):
        """
        Create the socket and plug it to the idlequeue
        """
        if self.ais is None:
            return None
        for ai in self.ais:
            try:
                self._sock = socket.socket(*ai[:3])
                # this will not block the GUI
                self._sock.setblocking(False)
                self._server = ai[4]
                break
            except socket.error as e:
                if e.errno == EINPROGRESS:
                    break
                # for all other errors, we try other addresses
                continue
        self.fd = self._sock.fileno()
        self.state = 0 # about to be connected
        self.idlequeue.plug_idle(self, True, False)
        self.do_connect()
        self.idlequeue.set_read_timeout(self.fd, CONNECT_TIMEOUT)
        return None

    def do_connect(self):
        try:
            self._sock.connect(self._server)
            self._send = self._sock.send
            self._recv = self._sock.recv
        except Exception as ee:
            errnum = ee.errno
            self.connect_timeout += 1
            if errnum == 111 or self.connect_timeout > 1000:
                self.queue._connection_refused(self.streamhost, self.file_props,
                    self.queue_idx)
                self.connected = False
                return None
            # win32 needs this
            if errnum not in  (10056, EISCONN) or self.state != 0:
                return None
            # socket is already connected
            self._sock.setblocking(False)
            self._send = self._sock.send
            self._recv = self._sock.recv
        self.buff = ''
        self.connected = True
        self.file_props.connected = True
        self.file_props.disconnect_cb = self.disconnect
        self.file_props.paused = False
        self.state = 1 # connected
        # stop all others connections to sender's streamhosts
        self.queue._socket_connected(self.streamhost, self.file_props)
        self.idlequeue.plug_idle(self, True, False)
        return 1 # we are connected

    def read_timeout(self):
        self.idlequeue.remove_timeout(self.fd)
        if self.state > 5:
            # no activity for foo seconds
            if self.file_props.stalled is False:
                self.file_props.stalled = True
                self.queue.process_result(-1, self)
                if not self.file_props.received_len:
                    self.file_props.received_len = 0
                if SEND_TIMEOUT > 0:
                    self.idlequeue.set_read_timeout(self.fd, SEND_TIMEOUT)
            else:
                # stop transfer, there is no error code for this
                self.pollend()
        else:
            if self.mode == 'client':
                self.queue.reconnect_client(self, self.streamhost)

    def open_file_for_reading(self):
        if self.file is None:
            try:
                self.file = open(self.file_props.file_name, 'rb')
                if self.file_props.offset:
                    self.size = self.file_props.offset
                    self.file.seek(self.size)
                    self.file_props.received_len = self.size
            except IOError as e:
                self.close_file()
                raise IOError(str(e))

    def close_file(self):
        # Close file we're sending from
        if self.file:
            if not self.file.closed:
                try:
                    self.file.close()
                except Exception:
                    pass
            self.file = None
        # Close file we're receiving into
        if self.file_props.fd and self.state >= 7:
            try:
                self.file_props.fd.close()
            except Exception:
                pass

    def get_fd(self):
        """
        Test if file is already open and return its fd, or just open the file
        and return the fd
        """
        if self.file_props.fd:
            fd = self.file_props.fd
        else:
            offset = 0
            opt = 'wb'
            if self.file_props.offset:
                offset = self.file_props.offset
                opt = 'ab'
            fd = open(self.file_props.file_name, opt)
            self.file_props.fd = fd
            self.file_props.elapsed_time = 0
            self.file_props.last_time = time.time()
            self.file_props.received_len = offset
        return fd

    def rem_fd(self, fd):
        if self.file_props.fd:
            self.file_props.fd = None
        try:
            fd.close()
        except Exception:
            pass

    def receive(self):
        """
        Read small chunks of data. Call owner's disconnected() method if
        appropriate
        """
        received = b''
        try:
            add = self._recv(64)
        except Exception:
            add = b''
        received += add
        if not add:
            self.disconnect()
        return add

    def send_raw(self, raw_data):
        """
        Write raw outgoing data
        """
        try:
            self._send(raw_data)
        except Exception:
            self.disconnect()
        return len(raw_data)

    def write_next(self):
        if self.remaining_buff != b'':
            buff = self.remaining_buff
        else:
            try:
                self.open_file_for_reading()
            except IOError:
                self.state = 8 # end connection
                self.disconnect()
                self.file_props.error = -7 # unable to read from file
                return -1
            buff = self.file.read(MAX_BUFF_LEN)
        if buff:
            lenn = 0
            try:
                lenn = self._send(buff)
            except socket.error as err:
                if err.errno not in (EINTR, ENOBUFS, EWOULDBLOCK):
                    return self._on_send_exception()
            except Exception as err:
                log.error(err)
                return self._on_send_exception()

            self.size += lenn
            current_time = time.time()
            self.file_props.elapsed_time += current_time - \
                self.file_props.last_time
            self.file_props.last_time = current_time
            self.file_props.received_len = self.size
            if self.size >= self.file_props.size:
                self.state = 8 # end connection
                self.file_props.error = 0
                self.disconnect()
                return -1
            if lenn != len(buff):
                self.remaining_buff = buff[lenn:]
            else:
                self.remaining_buff = b''
            self.state = 7 # continue to write in the socket
            if lenn == 0:
                return None
            self.file_props.stalled = False
            return lenn

        self.state = 8 # end connection
        self.disconnect()
        return -1

    def _on_send_exception(self):
        # peer stopped reading
        self.state = 8 # end connection
        self.disconnect()
        self.file_props.error = -1
        return -1

    def get_file_contents(self, timeout):
        """
        Read file contents from socket and write them to file
        """
        if self.file_props is None or not self.file_props.file_name:
            self.file_props.error = -2
            return None
        fd = None
        if self.remaining_buff != b'':
            try:
                fd = self.get_fd()
            except IOError:
                self.disconnect()
                self.file_props.error = -6 # file system error
                return 0
            fd.write(self.remaining_buff)
            lenn = len(self.remaining_buff)
            current_time = time.time()
            self.file_props.elapsed_time += current_time - \
                self.file_props.last_time
            self.file_props.last_time = current_time
            self.file_props.received_len += lenn
            self.remaining_buff = b''
            if self.file_props.received_len == self.file_props.size:
                self.rem_fd(fd)
                self.disconnect()
                self.file_props.error = 0
                self.file_props.completed = True
                return 0
        else:
            try:
                fd = self.get_fd()
            except IOError:
                self.disconnect()
                self.file_props.error = -6 # file system error
                return 0
            try:
                buff = self._recv(MAX_BUFF_LEN)
            except Exception:
                buff = b''
            current_time = time.time()
            self.file_props.elapsed_time += current_time - \
                self.file_props.last_time
            self.file_props.last_time = current_time
            self.file_props.received_len += len(buff)
            if not buff:
                # Transfer stopped  somehow:
                # reset, paused or network error
                self.rem_fd(fd)
                self.disconnect()
                self.file_props.error = -1
                return 0
            try:
                fd.write(buff)
            except IOError:
                self.rem_fd(fd)
                self.disconnect()
                self.file_props.error = -6 # file system error
                return 0
            if self.file_props.received_len >= self.file_props.size:
                # transfer completed
                self.rem_fd(fd)
                self.disconnect()
                self.file_props.error = 0
                self.file_props.completed = True
                return 0
            # return number of read bytes. It can be used in progressbar
        if fd is not None:
            self.file_props.stalled = False
        if fd is None and self.file_props.stalled is False:
            return None
        if self.file_props.received_len:
            if self.file_props.received_len != 0:
                return self.file_props.received_len
        return None

    def disconnect(self, *args, **kwargs):
        """
        Close open descriptors and remover socket descr. from idleque
        """
        # be sure that we don't leave open file
        self.close_file()
        self.idlequeue.remove_timeout(self.fd)
        self.idlequeue.unplug_idle(self.fd)
        if self.mode == 'server' and self.queue.listener:
            try:
                self.queue.listener.connections.remove(self._sock)
            except ValueError:
                pass # Not in list
            if self.queue.listener.connections == []:
                self.queue.listener.disconnect()
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
            self._sock.close()
        except Exception:
            # socket is already closed
            pass
        self.connected = False
        self.fd = -1
        self.state = -1

    def _get_auth_buff(self):
        """
        Message, that we support 1 one auth mechanism: the 'no auth' mechanism
        """
        return struct.pack('!BBB', 0x05, 0x01, 0x00)

    def _parse_auth_buff(self, buff):
        """
        Parse the initial message and create a list of auth mechanisms
        """
        if buff[0] != 5:
            return None
        num_auth = buff[1]
        return list(buff[2:2+num_auth])

    def _get_auth_response(self):
        """
        Socks version(5), number of extra auth methods (we send 0x00 - no auth)
        """
        return struct.pack('!BB', 0x05, 0x00)

    def _get_connect_buff(self):
        """
        Connect request by domain name
        """
        buff = struct.pack('!BBBBB%dsBB' % len(self.host),
            0x05, 0x01, 0x00, 0x03, len(self.host), self.host.encode('utf-8'),
            self.port >> 8, self.port & 0xff)
        return buff

    def _get_request_buff(self, msg, command=0x01):
        """
        Connect request by domain name, sid sha, instead of domain name (jep
        0096)
        """
        if isinstance(msg, str):
            msg = msg.encode('utf-8')
        buff = struct.pack('!BBBBB%dsBB' % len(msg), 0x05, command, 0x00, 0x03,
            len(msg), msg, 0, 0)
        return buff

    def _parse_request_buff(self, buff):
        try: # don't trust on what comes from the outside
            req_type, host_type, = struct.unpack('!xBxB', buff[:4])
            if host_type == 0x01:
                host_arr = struct.unpack('!iiii', buff[4:8])
                host, = '.'.join(str(s) for s in host_arr)
                host_len = len(host)
            elif host_type == 0x03:
                host_len = buff[4]
                host, = struct.unpack('!%ds' % host_len, buff[5:5 + host_len])
            portlen = len(buff[host_len + 5:])
            if portlen == 1:
                port, = struct.unpack('!B', buff[host_len + 5])
            elif portlen == 2:
                port, = struct.unpack('!H', buff[host_len + 5:])
            # file data, comes with auth message (Gaim bug)
            else:
                port, = struct.unpack('!H', buff[host_len + 5: host_len + 7])
                self.remaining_buff = buff[host_len + 7:]
        except Exception:
            return (None, None, None)
        return (req_type, host, port)

    def read_connect(self):
        """
        Connect response: version, auth method
        """
        buff = self._recv().decode('utf-8')
        try:
            version, method = struct.unpack('!BB', buff)
        except Exception:
            version, method = None, None
        if version != 0x05 or method == 0xff:
            self.disconnect()

    def continue_paused_transfer(self):
        if self.state < 5:
            return
        if self.file_props.type_ == 'r':
            self.idlequeue.plug_idle(self, False, True)
        else:
            self.idlequeue.plug_idle(self, True, False)

    def _get_sha1_auth(self):
        """
        Get sha of sid + Initiator jid + Target jid
        """
        if self.file_props.is_a_proxy:
            return hashlib.sha1(('%s%s%s' % (self.sid,
                self.file_props.proxy_sender, self.file_props.proxy_receiver)).\
                encode('utf-8')).hexdigest()
        return hashlib.sha1(('%s%s%s' % (self.sid, self.initiator,
            self.target)).encode('utf-8')).hexdigest()


class Socks5Sender(IdleObject):
    """
    Class for sending file to socket over socks5
    """
    def __init__(self, idlequeue, sock_hash, parent, _sock, host=None,
                 port=None, connected=True, file_props=None):
        IdleObject.__init__(self)
        self.queue_idx = sock_hash
        self.queue = parent
        self.file_props = file_props
        self.proxy = False
        self._sock = _sock
        if _sock is not None:
            self._sock.setblocking(False)
            self.fd = _sock.fileno()
            self._recv = _sock.recv
            self._send = _sock.send
        self.connected = connected
        self.state = 1 # waiting for first bytes
        self.connect_timeout = 0

        self.file_props.error = 0
        self.file_props.disconnect_cb = self.disconnect
        self.file_props.started = True
        self.file_props.completed = False
        self.file_props.paused = False
        self.file_props.continue_cb = self.continue_paused_transfer
        self.file_props.stalled = False
        self.file_props.connected = True
        self.file_props.elapsed_time = 0
        self.file_props.last_time = time.time()
        self.file_props.received_len = 0

    def start_transfer(self):
        """
        Send the file
        """
        return self.write_next()

    def set_connection_sock(self, _sock):
        self._sock = _sock
        self._sock.setblocking(False)
        self.fd = _sock.fileno()
        self._recv = _sock.recv
        self._send = _sock.send
        self.connected = True
        self.state = 1 # waiting for first bytes
        self.file_props = None
        # start waiting for data
        self.idlequeue.plug_idle(self, False, True)

    def send_file(self):
        """
        Start sending the file over verified connection
        """
        self.pauses = 0
        self.state = 7
        # plug for writing
        self.idlequeue.plug_idle(self, True, False)
        return self.write_next() # initial for nl byte

    def disconnect(self, cb=True):
        """
        Close the socket
        """
        # close connection and remove us from the queue
        Socks5.disconnect(self)
        if self.file_props is not None:
            self.file_props.connected = False
            self.file_props.disconnect_cb = None
        if self.queue is not None:
            self.queue.remove_sender(self.queue_idx, False)


class Socks5Receiver(IdleObject):
    def __init__(self, idlequeue, streamhost, sid, file_props=None):
        IdleObject.__init__(self)
        self.queue_idx = -1
        self.streamhost = streamhost
        self.queue = None
        self.connect_timeout = 0
        self.connected = False
        self.pauses = 0
        self.sid = sid
        self.file_props = file_props
        self.file_props.disconnect_cb = self.disconnect
        self.file_props.error = 0
        self.file_props.started = True
        self.file_props.completed = False
        self.file_props.paused = False
        self.file_props.continue_cb = self.continue_paused_transfer
        self.file_props.stalled = False
        self.file_props.received_len = 0

    def receive_file(self):
        """
        Start receiving the file over verified connection
        """
        if self.file_props.started:
            return
        self.file_props.error = 0
        self.file_props.disconnect_cb = self.disconnect
        self.file_props.started = True
        self.file_props.completed = False
        self.file_props.paused = False
        self.file_props.continue_cb = self.continue_paused_transfer
        self.file_props.stalled = False
        self.file_props.connected = True
        self.file_props.elapsed_time = 0
        self.file_props.last_time = time.time()
        self.file_props.received_len = 0
        self.pauses = 0
        self.state = 7
        # plug for reading
        self.idlequeue.plug_idle(self, False, True)
        return self.get_file_contents(0) # initial for nl byte

    def start_transfer(self):
        """
        Receive the file
        """
        return self.get_file_contents(0)

    def set_sock(self, _sock):
        self._sock = _sock
        self._sock.setblocking(False)
        self.fd = _sock.fileno()
        self._recv = _sock.recv
        self._send = _sock.send
        self.connected = True
        self.state = 1 # waiting for first bytes
        # start waiting for data
        self.idlequeue.plug_idle(self, False, True)

    def disconnect(self, cb=True):
        """
        Close the socket. Remove self from queue if cb is True
        """
        # close connection
        Socks5.disconnect(self)
        if cb is True:
            self.file_props.disconnect_cb = None
        if self.queue is not None:
            self.queue.remove_receiver(self.queue_idx, False)

class Socks5Server(Socks5):

    def __init__(self, idlequeue, host, port, initiator, target, sid):
        Socks5.__init__(self, idlequeue, host, port, initiator, target, sid)
        self.mode = 'server'

    def main(self):
        """
        Initial requests for verifying the connection
        """
        if self.state == 1: # initial read
            buff = self.receive()
            if not self.connected:
                return -1
            mechs = self._parse_auth_buff(buff)
            if mechs is None:
                return -1 # invalid auth methods received
        elif self.state == 3: # get next request
            buff = self.receive()
            req_type, self.sha_msg = self._parse_request_buff(buff)[:2]
            if req_type != 0x01:
                return -1 # request is not of type 'connect'
        self.state += 1 # go to the next step
        # unplug & plug for writing
        self.idlequeue.plug_idle(self, True, False)
        return None

    def pollin(self):
        self.idlequeue.remove_timeout(self.fd)
        if self.connected:
            if self.state < 5:
                result = self.main()
                if self.state == 4:
                    self.queue.result_sha(self.sha_msg, self.queue_idx)
                if result == -1:
                    self.disconnect()
            elif self.state == 5:
                self.state = 7
                if self.file_props.type_ == 's':
                    # We wait for the end of the negotiation to
                    # send the file
                    self.idlequeue.plug_idle(self, False, False)
                else:
                    # We plug for reading
                    self.idlequeue.plug_idle(self, False, True)
                    return
            elif self.state == 7:
                if self.file_props.paused:
                    self.file_props.continue_cb = \
                        self.continue_paused_transfer
                    self.idlequeue.plug_idle(self, False, False)
                    return
                self.idlequeue.set_read_timeout(self.fd, STALLED_TIMEOUT)
                result = self.start_transfer() # send
                self.queue.process_result(result, self)
        else:
            self.disconnect()

    def pollend(self):
        self.state = 8 # end connection
        self.disconnect()
        self.file_props.error = -1
        self.queue.process_result(-1, self)

    def pollout(self):
        if not self.connected:
            self.disconnect()
            return
        self.idlequeue.remove_timeout(self.fd)
        if self.state == 2: # send reply with desired auth type
            self.send_raw(self._get_auth_response())
        elif self.state == 4: # send positive response to the 'connect'
            self.send_raw(self._get_request_buff(self.sha_msg, 0x00))
        elif self.state == 7:
            if self.file_props.paused:
                self.file_props.continue_cb = self.continue_paused_transfer
                self.idlequeue.plug_idle(self, False, False)
                return
            result = self.start_transfer() # send
            self.queue.process_result(result, self)
            if result is None or result <= 0:
                self.disconnect()
                return
            self.idlequeue.set_read_timeout(self.fd, STALLED_TIMEOUT)
        elif self.state == 8:
            self.disconnect()
            return
        else:
            self.disconnect()
        if self.state < 5:
            self.state += 1
            # unplug and plug this time for reading
            self.idlequeue.plug_idle(self, False, True)


class Socks5Client(Socks5):

    def __init__(self, idlequeue, host, port, initiator, target, sid):
        Socks5.__init__(self, idlequeue, host, port, initiator, target, sid)
        self.mode = 'client'

    def main(self, timeout=0):
        """
        Begin negotiation. on success 'address' != 0
        """
        result = 1
        buff = self.receive()
        if buff == b'':
            # end connection
            self.pollend()
            return
        if self.state == 2: # read auth response
            if buff is None or len(buff) != 2:
                return None
            version, method = struct.unpack('!BB', buff[:2])
            if version != 0x05 or method == 0xff:
                self.disconnect()
        elif self.state == 4: # get approve of our request
            if buff is None:
                return None
            sub_buff = buff[:4]
            if len(sub_buff) < 4:
                return None
            version, address_type = struct.unpack('!BxxB', buff[:4])
            addrlen = 0
            if address_type == 0x03:
                addrlen = buff[4]
                # address = struct.unpack('!%ds' % addrlen, buff[5:addrlen + 5])
                portlen = len(buff[addrlen + 5:])
                # if portlen == 1:
                #     port, = struct.unpack('!B', buff[addrlen + 5])
                # elif portlen == 2:
                #     port, = struct.unpack('!H', buff[addrlen + 5:])
                # else: # Gaim bug :)
                #     port, = struct.unpack('!H', buff[addrlen + 5:addrlen + 7])
                if portlen not in (1, 2):
                    self.remaining_buff = buff[addrlen + 7:]

            self.state = 5 # for senders: init file_props and send '\n'
            if self.queue.on_success:
                result = self.queue.send_success_reply(self.file_props,
                    self.streamhost)
                if self.file_props.type_ == 's' and self.proxy:
                    self.queue.process_result(self.send_file(), self)
                    return
                if result == 0:
                    self.state = 8
                    self.disconnect()
        # for senders: init file_props
        if result == 1 and self.state == 5:
            if self.file_props.type_ == 's':
                self.file_props.error = 0
                self.file_props.disconnect_cb = self.disconnect
                self.file_props.started = True
                self.file_props.completed = False
                self.file_props.paused = False
                self.file_props.stalled = False
                self.file_props.elapsed_time = 0
                self.file_props.last_time = time.time()
                self.file_props.received_len = 0
                self.pauses = 0
                # start sending file contents to socket
                #self.idlequeue.set_read_timeout(self.fd, STALLED_TIMEOUT)
                #self.idlequeue.plug_idle(self, True, False)
                self.idlequeue.plug_idle(self, False, False)
            else:
                # receiving file contents from socket
                self.idlequeue.plug_idle(self, False, True)
            self.file_props.continue_cb = self.continue_paused_transfer
            # we have set up the connection, next - retrieve file
            self.state = 6
        if self.state < 5:
            self.idlequeue.plug_idle(self, True, False)
            self.state += 1
            return None

    def pollin(self):
        self.idlequeue.remove_timeout(self.fd)
        if self.connected:
            if self.file_props.paused:
                self.idlequeue.plug_idle(self, False, False)
                return
            if self.state < 5:
                self.idlequeue.set_read_timeout(self.fd, CONNECT_TIMEOUT)
                self.main(0)
            elif self.state == 5: # wait for proxy reply
                pass
            elif self.file_props.type_ == 'r':
                self.idlequeue.set_read_timeout(self.fd, STALLED_TIMEOUT)
                result = self.start_transfer() # receive
                self.queue.process_result(result, self)
        else:
            self.disconnect()

    def pollout(self):
        self.idlequeue.remove_timeout(self.fd)
        if self.state == 0:
            self.do_connect()
            return
        if self.state == 1: # send initially: version and auth types
            self.send_raw(self._get_auth_buff())
        elif self.state == 3: # send 'connect' request
            self.send_raw(self._get_request_buff(self._get_sha1_auth()))
        elif self.file_props.type_ != 'r':
            if self.file_props.paused:
                self.idlequeue.plug_idle(self, False, False)
                return
            result = self.start_transfer() # send
            self.queue.process_result(result, self)
            return

        self.state += 1
        # unplug and plug for reading
        self.idlequeue.plug_idle(self, False, True)
        self.idlequeue.set_read_timeout(self.fd, CONNECT_TIMEOUT)

    def pollend(self):
        if self.state >= 5:
            # error during transfer
            self.disconnect()
            self.file_props.error = -1
            self.queue.process_result(-1, self)
        else:
            self.queue.reconnect_client(self, self.streamhost)


class Socks5SenderClient(Socks5Client, Socks5Sender):

    def __init__(self, idlequeue, sock_hash, parent, _sock, host=None,
    port=None, connected=True, file_props=None,
    initiator=None, target=None):
        Socks5Client.__init__(self, idlequeue, host, port, initiator, target,
            file_props.transport_sid)
        Socks5Sender.__init__(self, idlequeue, sock_hash, parent, _sock,
            host, port, connected, file_props)


class Socks5SenderServer(Socks5Server, Socks5Sender):

    def __init__(self, idlequeue, sock_hash, parent, _sock, host=None,
    port=None, connected=True, file_props=None):
        Socks5Server.__init__(self, idlequeue, host, port, None, None,
            file_props.transport_sid)
        Socks5Sender.__init__(self, idlequeue, sock_hash, parent, _sock,
            host, port, connected, file_props)


class Socks5ReceiverClient(Socks5Client, Socks5Receiver):
    def __init__(self, idlequeue, streamhost, transport_sid, file_props=None):
        Socks5Client.__init__(self, idlequeue, streamhost['host'],
            int(streamhost['port']), streamhost['initiator'],
            streamhost['target'], transport_sid)
        Socks5Receiver.__init__(self, idlequeue, streamhost, transport_sid,
            file_props)


class Socks5ReceiverServer(Socks5Server, Socks5Receiver):

    def __init__(self, idlequeue, streamhost, transport_sid, file_props=None):
        Socks5Server.__init__(self, idlequeue, streamhost['host'],
            int(streamhost['port']), streamhost['initiator'],
            streamhost['target'], transport_sid)
        Socks5Receiver.__init__(self, idlequeue, streamhost, transport_sid,
            file_props)


class Socks5Listener(IdleObject):
    def __init__(self, idlequeue, port, fp):
        """
        Handle all incoming connections on (0.0.0.0, port)

        This class implements IdleObject, but we will expect
        only pollin events though
        """
        IdleObject.__init__(self)
        self.port = port
        self.ais = socket.getaddrinfo(None, port, socket.AF_UNSPEC,
            socket.SOCK_STREAM, socket.SOL_TCP, socket.AI_PASSIVE)
        self.ais.sort(reverse=True) # Try IPv6 first
        self.queue_idx = -1
        self.idlequeue = idlequeue
        self.queue = None
        self.started = False
        self._sock = None
        self.fd = -1
        self.file_props = fp
        self.connections = []

    def bind(self):
        for ai in self.ais:
            # try the different possibilities (ipv6, ipv4, etc.)
            try:
                self._serv = socket.socket(*ai[:3])
            except socket.error as e:
                if e.errno == EAFNOSUPPORT:
                    self.ai = None
                    continue
                raise
            self._serv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._serv.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            self._serv.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            # Under windows Vista, we need that to listen on ipv6 AND ipv4
            # Doesn't work under windows XP
            if os.name == 'nt':
                if sys.getwindowsversion().major >= 6:  # Win Vista +
                    # 47 is socket.IPPROTO_IPV6
                    # 27 is socket.IPV6_V6ONLY under windows, but not defined ...
                    self._serv.setsockopt(41, 27, 0)
            # will fail when port as busy, or we don't have rights to bind
            try:
                self._serv.bind(ai[4])
                self.ai = ai
                break
            except Exception:
                self.ai = None
                continue
        if not self.ai:
            log.error('unable to bind to port %s', str(self.port))
            return None
        self._serv.listen(socket.SOMAXCONN)
        self._serv.setblocking(False)
        self.fd = self._serv.fileno()
        self.idlequeue.plug_idle(self, False, True)
        self.started = True

    def pollend(self):
        """
        Called when we stop listening on (host, port)
        """
        self.disconnect()

    def pollin(self):
        """
        Accept a new incoming connection and notify queue
        """
        sock = self.accept_conn()
        self.queue.on_connection_accepted(sock, self)

    def disconnect(self):
        """
        Free all resources, we are not listening anymore
        """
        self.idlequeue.remove_timeout(self.fd)
        self.idlequeue.unplug_idle(self.fd)
        self.fd = -1
        self.state = -1
        self.started = False
        try:
            self._serv.close()
        except Exception:
            pass

    def accept_conn(self):
        """
        Accept a new incoming connection
        """
        _sock = self._serv.accept()
        _sock[0].setblocking(False)
        self.connections.append(_sock[0])
        return _sock
