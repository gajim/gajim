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
