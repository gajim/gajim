# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only


from nbxmpp.http import HTTPRequest
from nbxmpp.http import HTTPSession
from nbxmpp.structs import ProxyData

from gajim.common import app
from gajim.common.helpers import determine_proxy
from gajim.common.helpers import get_account_proxy


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
