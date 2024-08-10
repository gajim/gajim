# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from nbxmpp.protocol import InvalidJid
from nbxmpp.protocol import Iq
from nbxmpp.protocol import JID

from gajim.common import app


class InvalidFormat(Exception):
    pass


def parse_jid(jidstring: str) -> str:
    try:
        return str(validate_jid(jidstring))
    except Exception as error:
        raise InvalidFormat(error)


def parse_resource(resource: str) -> str | None:
    '''
    Perform stringprep on resource and return it
    '''
    if not resource:
        return None

    try:
        return resource.encode('OpaqueString').decode('utf-8')
    except UnicodeError:
        raise InvalidFormat('Invalid character in resource.')


def get_full_jid_from_iq(iq_obj: Iq) -> str | None:
    '''
    Return the full jid (with resource) from an iq
    '''
    jid = iq_obj.getFrom()
    if jid is None:
        return None
    return parse_jid(str(iq_obj.getFrom()))


def get_jid_from_iq(iq_obj: Iq) -> str | None:
    '''
    Return the jid (without resource) from an iq
    '''
    jid = get_full_jid_from_iq(iq_obj)
    if jid is None:
        return None
    return app.get_jid_without_resource(jid)


def validate_jid(jid: str | JID, type_: str | None = None) -> JID:
    try:
        jid = JID.from_string(str(jid))
    except InvalidJid as error:
        raise ValueError(error)

    if type_ is None:
        return jid
    if type_ == 'bare' and jid.is_bare:
        return jid
    if type_ == 'full' and jid.is_full:
        return jid
    if type_ == 'domain' and jid.is_domain:
        return jid

    raise ValueError(f'Not a {type_} JID')
