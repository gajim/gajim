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

log = logging.getLogger('gajim.c.m.misc')


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
