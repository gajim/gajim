# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only


import binascii
import logging

from nbxmpp.http import HTTPRequest
from nbxmpp.http import HTTPSession
from nbxmpp.structs import ProxyData

from gajim.common import app
from gajim.common.aes import AESKeyData
from gajim.common.helpers import determine_proxy
from gajim.common.helpers import get_account_proxy

log = logging.getLogger("gajim.c.util.http")


def create_http_session(account: str | None = None,
                        proxy: ProxyData | None = None
                        ) -> HTTPSession:

    session = HTTPSession(user_agent=f'Gajim {app.version}')

    if proxy is None:
        if account is not None:
            proxy = get_account_proxy(account)
        else:
            proxy = determine_proxy()

    if proxy is not None:
        session.set_proxy_resolver(proxy.get_resolver())

    return session


def create_http_request(account: str | None = None) -> HTTPRequest:
    session = create_http_session(account)
    return session.create_request()


def get_aes_key_data(fragment_string: str) -> AESKeyData:
    if not fragment_string:
        raise ValueError('Invalid fragment')

    fragment = binascii.unhexlify(fragment_string)
    size = len(fragment)
    # Clients started out with using a 16 byte IV but long term
    # want to switch to the more performant 12 byte IV
    # We have to support both
    if size == 48:
        key = fragment[16:]
        iv = fragment[:16]
    elif size == 44:
        key = fragment[12:]
        iv = fragment[:12]
    else:
        raise ValueError('Invalid fragment size: %s' % size)

    return AESKeyData(key, iv)
