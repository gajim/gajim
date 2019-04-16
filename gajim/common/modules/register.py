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

        self.agent_registrations = {}

    def change_password(self, password, success_cb, error_cb):
        if not app.account_is_connected(self._account):
            return
        hostname = app.config.get_per('accounts', self._account, 'hostname')
        username = app.config.get_per('accounts', self._account, 'name')
        iq = nbxmpp.Iq(typ='set', to=hostname)
        query = iq.setTag(nbxmpp.NS_REGISTER + ' query')
        query.setTagData('username', username)
        query.setTagData('password', password)

        weak_success_cb = weakref.WeakMethod(success_cb)
        weak_error_cb = weakref.WeakMethod(error_cb)
        log.info('Send password change')
        self._con.connection.SendAndCallForResponse(
            iq, self._change_password_response, {'success_cb': weak_success_cb,
                                                 'error_cb': weak_error_cb})

    @staticmethod
    def _change_password_response(_con, stanza, success_cb, error_cb):
        if not nbxmpp.isResultNode(stanza):
            error = stanza.getErrorMsg()
            log.info('Error: %s', error)
            if error_cb() is not None:
                error_cb()(error)
        else:
            log.info('Password changed')
            if success_cb() is not None:
                success_cb()()

    def register_agent(self, agent, form, is_form, success_cb, error_cb):
        if not app.account_is_connected(self._account):
            return

        weak_success_cb = weakref.WeakMethod(success_cb)
        weak_error_cb = weakref.WeakMethod(error_cb)

        iq = nbxmpp.Iq('set', nbxmpp.NS_REGISTER, to=agent)
        if is_form:
            query = iq.setQuery()
            form.setAttr('type', 'submit')
            query.addChild(node=form)
        else:
            for field in form.keys():
                iq.setTag('query').setTagData(field, form[field])

        self._con.connection.SendAndCallForResponse(
            iq, self._register_agent_response, {'agent': agent,
                                                'success_cb': weak_success_cb,
                                                'error_cb': weak_error_cb})

        self.agent_registrations[agent] = {'roster_push': False,
                                           'sub_received': False}

    def _register_agent_response(self, _con, stanza, agent,
                                 success_cb, error_cb):
        if not nbxmpp.isResultNode(stanza):
            error = stanza.getErrorMsg()
            log.info('Error: %s', error)
            if error_cb() is not None:
                form = is_form = None
                if stanza.getTagAttr('error', 'type') == 'modify':
                    form, is_form = self._get_register_form(stanza)
                error_cb()(error, form, is_form)
            return

        self._con.get_module('Presence').subscribe(agent, auto_auth=True)

        self.agent_registrations[agent]['roster_push'] = True
        if self.agent_registrations[agent]['sub_received']:
            self._con.get_module('Presence').subscribed(agent)

        if success_cb() is not None:
            success_cb()()

    def get_register_form(self, jid, success_cb, error_cb):
        if not app.account_is_connected(self._account):
            return

        weak_success_cb = weakref.WeakMethod(success_cb)
        weak_error_cb = weakref.WeakMethod(error_cb)

        iq = nbxmpp.Iq('get', nbxmpp.NS_REGISTER, to=jid)
        self._con.connection.SendAndCallForResponse(
            iq, self._register_info_response, {'success_cb': weak_success_cb,
                                               'error_cb': weak_error_cb})

    def _register_info_response(self, _con, stanza, success_cb, error_cb):
        if not nbxmpp.isResultNode(stanza):
            error = stanza.getErrorMsg()
            log.info('Error: %s', error)
            if error_cb() is not None:
                error_cb()(error)
        else:
            log.info('Register form received')

            if success_cb() is not None:
                form, is_form = self._get_register_form(stanza)
                success_cb()(form, is_form)

    @staticmethod
    def _get_register_form(stanza):
        query = stanza.getTag('query')
        if not query:
            return None, False

        form = query.getTag('x', namespace=nbxmpp.NS_DATA)
        is_form = form is not None
        if not is_form:
            form = {}
            for field in query.getPayload():
                if not isinstance(field, nbxmpp.Node):
                    continue
                form[field.getName()] = field.getData()

        return form, is_form


def get_instance(*args, **kwargs):
    return Register(*args, **kwargs), 'Register'
