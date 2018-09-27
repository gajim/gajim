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

import nbxmpp

log = logging.getLogger('gajim.c.m.bob')


class BitsOfBinary:
    def __init__(self, con):
        self._con = con
        self._account = con.name

        self.handlers = [
            ('iq', self._answer_bob_request, 'get', nbxmpp.NS_BOB)
        ]

        # Used to track which cids are in-flight.
        self.awaiting_cids = {}

    def _answer_bob_request(self, _con, stanza):
        log.info('Request from %s for BoB data', stanza.getFrom())
        iq = stanza.buildReply('error')
        err = nbxmpp.ErrorNode(nbxmpp.ERR_ITEM_NOT_FOUND)
        iq.addChild(node=err)
        log.info('Sending item-not-found')
        self._con.connection.send(iq)
        raise nbxmpp.NodeProcessed

    def _on_bob_received(self, _con, result, cid):
        """
        Called when we receive BoB data
        """
        if cid not in self.awaiting_cids:
            return

        if result.getType() == 'result':
            data = result.getTags('data', namespace=nbxmpp.NS_BOB)
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

        # An error occured, call callback without modifying data.
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
        iq.addChild(name='data', attrs={'cid': cid}, namespace=nbxmpp.NS_BOB)
        self._con.connection.SendAndCallForResponse(
            iq, self._on_bob_received, {'cid': cid})


def get_instance(*args, **kwargs):
    return BitsOfBinary(*args, **kwargs), 'BitsOfBinary'
