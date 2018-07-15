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

# XEP-0280: Message Carbons

import logging

import nbxmpp

log = logging.getLogger('gajim.c.m.carbons')


def parse_carbon(con, stanza):
    carbon = stanza.getTag(
        'received', namespace=nbxmpp.NS_CARBONS, protocol=True)
    if carbon is None:
        carbon = stanza.getTag(
            'sent', namespace=nbxmpp.NS_CARBONS, protocol=True)
        if carbon is None:
            return stanza, False, False

    # Carbon must be from our bare jid
    own_jid = con.get_own_jid()
    if not stanza.getFrom().bareMatch(own_jid):
        log.warning('Ignore message because from is invalid %s',
                    stanza.getFrom())
        raise nbxmpp.NodeProcessed

    forwarded = carbon.getTag('forwarded',
                              namespace=nbxmpp.NS_FORWARD,
                              protocol=True)
    message = forwarded.getTag('message', protocol=True)

    type_ = carbon.getName()
    to = message.getTo()
    frm = message.getFrom()
    log.info('Received type: %s, from: %s, to: %s', type_, to, frm)

    if type_ == 'received':
        sent = False
        if message.getFrom().bareMatch(own_jid):
            # Drop 'received' Carbons from ourself, we already
            # got the message with the 'sent' Carbon or via the
            # message itself
            log.info('Drop "received"-Carbon from ourself: %s')
            raise nbxmpp.NodeProcessed
        if message.getTag('x', namespace=nbxmpp.NS_MUC_USER) is not None:
            # A MUC broadcasts messages sent to us to all resources
            # there is no need to process carbons for these messages
            log.info('Drop MUC-PM "received"-Carbon')
            raise nbxmpp.NodeProcessed

    elif type_ == 'sent':
        if frm is None:
            frm = own_jid.getStripped()
        message.setTo(frm)
        if to is None:
            to = own_jid.getStripped()
        message.setFrom(to)
        sent = True

    else:
        log.warning('Ignore invalid carbon: %s', stanza)
        raise nbxmpp.NodeProcessed

    return message, sent, True
