# Copyright (C) 2018 Emmanuel Gil Peyrot <linkmauve AT linkmauve.fr>
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

import logging
import hashlib
from base64 import b64decode
from pathlib import Path

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common import configpaths
from gajim.common.modules.base import BaseModule

log = logging.getLogger('gajim.c.m.bob')


class BitsOfBinary(BaseModule):
    def __init__(self, con):
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self._answer_bob_request,
                          typ='get',
                          ns=Namespace.BOB),
        ]

        # Used to track which cids are in-flight.
        self.awaiting_cids = {}

    def _answer_bob_request(self, _con, stanza, _properties):
        self._log.info('Request from %s for BoB data', stanza.getFrom())
        iq = stanza.buildReply('error')
        err = nbxmpp.ErrorNode(nbxmpp.ERR_ITEM_NOT_FOUND)
        iq.addChild(node=err)
        self._log.info('Sending item-not-found')
        self._con.connection.send(iq)
        raise nbxmpp.NodeProcessed

    def _on_bob_received(self, _nbxmpp_client, result, cid):
        """
        Called when we receive BoB data
        """
        if cid not in self.awaiting_cids:
            return

        if result.getType() == 'result':
            data = result.getTags('data', namespace=Namespace.BOB)
            if data.getAttr('cid') == cid:
                for func in self.awaiting_cids[cid]:
                    cb = func[0]
                    args = func[1]
                    pos = func[2]
                    bob_data = data.getData()
                    def recurs(node, cid, data):
                        if node.getData() == 'cid:' + cid:
                            node.setData(data)
                        else:
                            for child in node.getChildren():
                                recurs(child, cid, data)
                    recurs(args[pos], cid, bob_data)
                    cb(*args)
                del self.awaiting_cids[cid]
                return

        # An error occurred, call callback without modifying data.
        for func in self.awaiting_cids[cid]:
            cb = func[0]
            args = func[1]
            cb(*args)
        del self.awaiting_cids[cid]

    def get_bob_data(self, cid, to, callback, args, position):
        """
        Request for BoB (XEP-0231) and when data will arrive, call callback
        with given args, after having replaced cid by it's data in
        args[position]
        """
        if cid in self.awaiting_cids:
            self.awaiting_cids[cid].appends((callback, args, position))
        else:
            self.awaiting_cids[cid] = [(callback, args, position)]
        iq = nbxmpp.Iq(to=to, typ='get')
        iq.addChild(name='data', attrs={'cid': cid}, namespace=Namespace.BOB)
        self._con.connection.SendAndCallForResponse(
            iq, self._on_bob_received, {'cid': cid})


def parse_bob_data(stanza):
    data_node = stanza.getTag('data', namespace=Namespace.BOB)
    if data_node is None:
        return None

    cid = data_node.getAttr('cid')
    type_ = data_node.getAttr('type')
    max_age = data_node.getAttr('max-age')
    if max_age is not None:
        try:
            max_age = int(max_age)
        except Exception:
            log.exception(stanza)
            return None

    if cid is None or type_ is None:
        log.warning('Invalid data node (no cid or type attr): %s', stanza)
        return None

    try:
        algo_hash = cid.split('@')[0]
        algo, hash_ = algo_hash.split('+')
    except Exception:
        log.exception('Invalid cid: %s', stanza)
        return None

    bob_data = data_node.getData()
    if not bob_data:
        log.warning('No data found: %s', stanza)
        return None

    filepath = Path(configpaths.get('BOB')) / algo_hash
    if algo_hash in app.bob_cache or filepath.exists():
        log.info('BoB data already cached')
        return None

    try:
        bob_data = b64decode(bob_data)
    except Exception:
        log.warning('Unable to decode data')
        log.exception(stanza)
        return None

    if len(bob_data) > 10000:
        log.warning('%s: data > 10000 bytes', stanza.getFrom())
        return None

    try:
        sha = hashlib.new(algo)
    except ValueError as error:
        log.warning(stanza)
        log.warning(error)
        return None

    sha.update(bob_data)
    if sha.hexdigest() != hash_:
        log.warning('Invalid hash: %s', stanza)
        return None

    if max_age == 0:
        app.bob_cache[algo_hash] = bob_data
    else:
        try:
            with open(str(filepath), 'w+b') as file:
                file.write(bob_data)
        except Exception:
            log.warning('Unable to save data')
            log.exception(stanza)
            return None

    log.info('BoB data stored: %s', algo_hash)
    return filepath


def store_bob_data(bob_data):
    if bob_data is None:
        return None

    algo_hash = '%s+%s' % (bob_data.algo, bob_data.hash_)

    filepath = Path(configpaths.get('BOB')) / algo_hash
    if algo_hash in app.bob_cache or filepath.exists():
        log.info('BoB data already cached')
        return None

    if bob_data.max_age == 0:
        app.bob_cache[algo_hash] = bob_data.data
    else:
        try:
            with open(str(filepath), 'w+b') as file:
                file.write(bob_data.data)
        except Exception:
            log.exception('Unable to save data')
            return None

    log.info('BoB data stored: %s', algo_hash)
    return filepath


def get_instance(*args, **kwargs):
    return BitsOfBinary(*args, **kwargs), 'BitsOfBinary'
