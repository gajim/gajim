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

# All XEPs that dont need their own module

import logging

import nbxmpp

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.modules.date_and_time import parse_datetime

log = logging.getLogger('gajim.c.m.misc')


# XEP-0380: Explicit Message Encryption

_eme_namespaces = {
    'urn:xmpp:otr:0':
        _('This message was encrypted with OTR '
          'and could not be decrypted.'),
    'jabber:x:encrypted':
        _('This message was encrypted with Legacy '
          'OpenPGP and could not be decrypted. You can install '
          'the PGP plugin to handle those messages.'),
    'urn:xmpp:openpgp:0':
        _('This message was encrypted with '
          'OpenPGP for XMPP and could not be decrypted.'),
    'fallback':
        _('This message was encrypted with %s '
          'and could not be decrypted.')
}


def parse_eme(stanza):
    enc_tag = stanza.getTag('encryption', namespace=nbxmpp.NS_EME)
    if enc_tag is None:
        return

    ns = enc_tag.getAttr('namespace')
    if ns is None:
        log.warning('No namespace on EME message')
        return

    if ns in _eme_namespaces:
        log.info('Found not decrypted message: %s', ns)
        return _eme_namespaces.get(ns)

    enc_name = enc_tag.getAttr('name')
    log.info('Found not decrypted message: %s', enc_name or ns)
    return _eme_namespaces.get('fallback') % enc_name or ns


# XEP-0203: Delayed Delivery

def parse_delay(stanza, epoch=True, convert='utc', from_=None, not_from=None):
    '''
    Returns the first valid delay timestamp that matches

    :param epoch:      Returns the timestamp as epoch

    :param convert:    Converts the timestamp to either utc or local

    :param from_:      Matches only delays that have the according
                       from attr set

    :param not_from:   Matches only delays that have the according
                       from attr not set
    '''
    delays = stanza.getTags('delay', namespace=nbxmpp.NS_DELAY2)

    for delay in delays:
        stamp = delay.getAttr('stamp')
        if stamp is None:
            log.warning('Invalid timestamp received: %s', stamp)
            log.warning(stanza)
            continue

        delay_from = delay.getAttr('from')
        if from_ is not None:
            if delay_from != from_:
                continue
        if not_from is not None:
            if delay_from in not_from:
                continue

        timestamp = parse_datetime(stamp, check_utc=True,
                                   epoch=epoch, convert=convert)
        if timestamp is None:
            log.warning('Invalid timestamp received: %s', stamp)
            log.warning(stanza)
            continue

        return timestamp


# XEP-0066: Out of Band Data

def parse_oob(event):
    oob_node = event.stanza.getTag('x', namespace=nbxmpp.NS_X_OOB)
    if oob_node is None:
        return

    url = oob_node.getTagData('url')
    if url is not None:
        event.additional_data.set_value('gajim', 'oob_url', url)

    desc = oob_node.getTagData('desc')
    if desc is not None:
        event.additional_data.set_value('gajim', 'oob_desc', desc)


# XEP-0308: Last Message Correction

def parse_correction(stanza):
    replace = stanza.getTag('replace', namespace=nbxmpp.NS_CORRECT)
    if replace is not None:
        id_ = replace.getAttr('id')
        if id_ is not None:
            return id_
        log.warning('No id attr found: %s', stanza)


# XEP-0224: Attention

def parse_attention(stanza):
    attention = stanza.getTag('attention', namespace=nbxmpp.NS_ATTENTION)
    if attention is None:
        return False
    delayed = stanza.getTag('x', namespace=nbxmpp.NS_DELAY2)
    if delayed is not None:
        return False
    return True


# XEP-0004: Data Forms

def parse_form(stanza):
    return stanza.getTag('x', namespace=nbxmpp.NS_DATA)


# XEP-0071: XHTML-IM

def parse_xhtml(stanza):
    if app.config.get('ignore_incoming_xhtml'):
        return None
    return stanza.getXHTML()
