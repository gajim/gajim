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

def parse_delay(stanza, epoch=True, convert='utc'):
    timestamp = None
    delay = stanza.getTagAttr(
        'delay', 'stamp', namespace=nbxmpp.NS_DELAY2)
    if delay is not None:
        timestamp = parse_datetime(delay, check_utc=True,
                                   epoch=epoch, convert=convert)
        if timestamp is None:
            log.warning('Invalid timestamp received: %s', delay)
            log.warning(stanza)

    return timestamp


# XEP-0066: Out of Band Data

def parse_oob(stanza, dict_=None, key='Gajim'):
    oob_node = stanza.getTag('x', namespace=nbxmpp.NS_X_OOB)
    if oob_node is None:
        return
    result = {}
    url = oob_node.getTagData('url')
    if url is not None:
        result['oob_url'] = url
    desc = oob_node.getTagData('desc')
    if desc is not None:
        result['oob_desc'] = desc

    if dict_ is None:
        return result

    if key in dict_:
        dict_[key] += result
    else:
        dict_[key] = result

    return dict_


# XEP-0308: Last Message Correction

def parse_correction(stanza):
    replace = stanza.getTag('replace', namespace=nbxmpp.NS_CORRECT)
    if replace is not None:
        id_ = replace.getAttr('id')
        if id_ is not None:
            return id_
        log.warning('No id attr found: %s' % stanza)


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
