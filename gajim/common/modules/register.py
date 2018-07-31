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
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

# XEP-0077: In-Band Registration

import logging
import weakref

import nbxmpp

from gajim.common import app

log = logging.getLogger('gajim.c.m.register')


class Register:
    def __init__(self, con):
        self._con = con
        self._account = con.name

        self.handlers = []

    def change_password(self, password, success_cb, error_cb):
        if not app.account_is_connected(self._account):
            return
        hostname = app.config.get_per('accounts', self._account, 'hostname')
        username = app.config.get_per('accounts', self._account, 'name')
        iq = nbxmpp.Iq(typ='set', to=hostname)
        q = iq.setTag(nbxmpp.NS_REGISTER + ' query')
        q.setTagData('username', username)
        q.setTagData('password', password)

        weak_success_cb = weakref.WeakMethod(success_cb)
        weak_error_cb = weakref.WeakMethod(error_cb)
        log.info('Send password change')
        self._con.connection.SendAndCallForResponse(
            iq, self._change_password_response, {'success_cb': weak_success_cb,
                                                 'error_cb': weak_error_cb})

    def _change_password_response(self, con, stanza, success_cb, error_cb):
        if not nbxmpp.isResultNode(stanza):
            error = stanza.getErrorMsg()
            log.info('Error: %s', error)
            error_cb()(error)
        else:
            log.info('Password changed')
            success_cb()()


def get_instance(*args, **kwargs):
    return Register(*args, **kwargs), 'Register'
