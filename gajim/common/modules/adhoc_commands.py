# Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2006-2007 Tomasz Melcer <liori AT exroot.org>
# Copyright (C) 2007 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
#                    Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
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

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler
from nbxmpp.modules import dataforms
from nbxmpp.util import generate_id

from gajim.common import app
from gajim.common import helpers
from gajim.common.i18n import _
from gajim.common.nec import NetworkIncomingEvent
from gajim.common.modules.base import BaseModule


class AdHocCommand:
    commandnode = 'command'
    commandname = 'The Command'
    commandfeatures = (Namespace.DATA,)

    @staticmethod
    def is_visible_for(_samejid):
        """
        This returns True if that command should be visible and invocable for
        others

        samejid - True when command is invoked by an entity with the same bare
        jid.
        """
        return True

    def __init__(self, conn, jid, sessionid):
        self.connection = conn
        self.jid = jid
        self.sessionid = sessionid

    def build_response(self, request, status='executing', defaultaction=None,
                       actions=None):
        assert status in ('executing', 'completed', 'canceled')

        response = request.buildReply('result')
        cmd = response.getTag('command', namespace=Namespace.COMMANDS)
        cmd.setAttr('sessionid', self.sessionid)
        cmd.setAttr('node', self.commandnode)
        cmd.setAttr('status', status)
        if defaultaction is not None or actions is not None:
            if defaultaction is not None:
                assert defaultaction in ('cancel', 'execute', 'prev', 'next',
                                         'complete')
                attrs = {'action': defaultaction}
            else:
                attrs = {}

            cmd.addChild('actions', attrs, actions)
        return response, cmd

    def bad_request(self, stanza):
        self.connection.connection.send(
            nbxmpp.Error(stanza, Namespace.STANZAS + ' bad-request'))

    def cancel(self, request):
        response = self.build_response(request, status='canceled')[0]
        self.connection.connection.send(response)
        return False    # finish the session


class ChangeStatusCommand(AdHocCommand):
    commandnode = 'change-status'
    commandname = _('Change status information')

    def __init__(self, conn, jid, sessionid):
        AdHocCommand.__init__(self, conn, jid, sessionid)
        self._callback = self.first_step

    @staticmethod
    def is_visible_for(samejid):
        """
        Change status is visible only if the entity has the same bare jid
        """
        return samejid

    def execute(self, request):
        return self._callback(request)

    def first_step(self, request):
        # first query...
        response, cmd = self.build_response(request,
                                            defaultaction='execute',
                                            actions=['execute'])

        cmd.addChild(
            node=dataforms.SimpleDataForm(
                title=_('Change status'),
                instructions=_('Set the presence type and description'),
                fields=[
                    dataforms.create_field(
                        'list-single',
                        var='presence-type',
                        label='Type of presence:',
                        options=[
                            ('chat', _('Free for chat')),
                            ('online', _('Online')),
                            ('away', _('Away')),
                            ('xa', _('Extended away')),
                            ('dnd', _('Do not disturb')),
                            ('offline', _('Offline - disconnect'))],
                        value='online',
                        required=True),
                    dataforms.create_field(
                        'text-multi',
                        var='presence-desc',
                        label=_('Presence description:'))
                ]
            )
        )

        self.connection.connection.send(response)

        # for next invocation
        self._callback = self.second_step

        return True     # keep the session

    def second_step(self, request):
        # check if the data is correct
        try:
            form = dataforms.SimpleDataForm(
                extend=request.getTag('command').getTag('x'))
        except Exception:
            self.bad_request(request)
            return False

        try:
            presencetype = form['presence-type'].value
            if presencetype not in ('chat', 'online', 'away',
                                    'xa', 'dnd', 'offline'):
                self.bad_request(request)
                return False
        except Exception:
            # KeyError if there's no presence-type field in form or
            # AttributeError if that field is of wrong type
            self.bad_request(request)
            return False

        try:
            presencedesc = form['presence-desc'].value
        except Exception:       # same exceptions as in last comment
            presencedesc = ''

        response, cmd = self.build_response(request, status='completed')
        cmd.addChild('note', {}, _('The status has been changed.'))

        # if going offline, we need to push response so it won't go into
        # queue and disappear
        self.connection.connection.send(response,
                                        now=presencetype == 'offline')

        # send new status
        app.get_client(self.connection.name).change_status(
            presencetype, presencedesc)

        return False    # finish the session


class AdHocCommands(BaseModule):

    _nbxmpp_extends = 'AdHoc'
    _nbxmpp_methods = [
        'request_command_list',
        'execute_command',
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self._execute_command_received,
                          typ='set',
                          ns=Namespace.COMMANDS),
        ]

        # a list of all commands exposed: node -> command class
        self._commands = {}
        if app.settings.get('remote_commands'):
            for cmdobj in (ChangeStatusCommand,):
                self._commands[cmdobj.commandnode] = cmdobj

        # a list of sessions; keys are tuples (jid, sessionid, node)
        self._sessions = {}

    def get_own_bare_jid(self):
        return self._con.get_own_jid().bare

    def is_same_jid(self, jid):
        """
        Test if the bare jid given is the same as our bare jid
        """
        return nbxmpp.JID.from_string(jid).bare == self.get_own_bare_jid()

    def command_list_query(self, stanza):
        iq = stanza.buildReply('result')
        jid = helpers.get_full_jid_from_iq(stanza)
        query = iq.getTag('query')
        # buildReply don't copy the node attribute. Re-add it
        query.setAttr('node', Namespace.COMMANDS)

        for node, cmd in self._commands.items():
            if cmd.is_visible_for(self.is_same_jid(jid)):
                query.addChild('item', {
                    # TODO: find the jid
                    'jid': str(self._con.get_own_jid()),
                    'node': node,
                    'name': cmd.commandname})

        self._con.connection.send(iq)

    def command_info_query(self, stanza):
        """
        Send disco#info result for query for command (XEP-0050, example 6.).
        Return True if the result was sent, False if not
        """
        try:
            jid = helpers.get_full_jid_from_iq(stanza)
        except helpers.InvalidFormat:
            self._log.warning('Invalid JID: %s, ignoring it', stanza.getFrom())
            return False

        node = stanza.getTagAttr('query', 'node')

        if node not in self._commands:
            return False

        cmd = self._commands[node]
        if cmd.is_visible_for(self.is_same_jid(jid)):
            iq = stanza.buildReply('result')
            query = iq.getTag('query')
            query.addChild('identity',
                           attrs={'type': 'command-node',
                                  'category': 'automation',
                                  'name': cmd.commandname})
            query.addChild('feature', attrs={'var': Namespace.COMMANDS})
            for feature in cmd.commandfeatures:
                query.addChild('feature', attrs={'var': feature})

            self._con.connection.send(iq)
            return True

        return False

    def command_items_query(self, stanza):
        """
        Send disco#items result for query for command.
        Return True if the result was sent, False if not.
        """
        jid = helpers.get_full_jid_from_iq(stanza)
        node = stanza.getTagAttr('query', 'node')

        if node not in self._commands:
            return False

        cmd = self._commands[node]
        if cmd.is_visible_for(self.is_same_jid(jid)):
            iq = stanza.buildReply('result')
            self._con.connection.send(iq)
            return True

        return False

    def _execute_command_received(self, _con, stanza, _properties):
        jid = helpers.get_full_jid_from_iq(stanza)

        cmd = stanza.getTag('command')
        if cmd is None:
            self._log.error('Malformed stanza (no command node) %s', stanza)
            raise nbxmpp.NodeProcessed

        node = cmd.getAttr('node')
        if node is None:
            self._log.error('Malformed stanza (no node attr) %s', stanza)
            raise nbxmpp.NodeProcessed

        sessionid = cmd.getAttr('sessionid')
        if sessionid is None:
            # we start a new command session
            # only if we are visible for the jid and command exist
            if node not in self._commands:
                self._con.connection.send(
                    nbxmpp.Error(
                        stanza, Namespace.STANZAS + ' item-not-found'))
                self._log.warning('Comand %s does not exist: %s', node, jid)
                raise nbxmpp.NodeProcessed

            newcmd = self._commands[node]
            if not newcmd.is_visible_for(self.is_same_jid(jid)):
                self._log.warning('Command not visible for jid: %s', jid)
                raise nbxmpp.NodeProcessed

            # generate new sessionid
            sessionid = generate_id()

            # create new instance and run it
            obj = newcmd(conn=self, jid=jid, sessionid=sessionid)
            rc = obj.execute(stanza)
            if rc:
                self._sessions[(jid, sessionid, node)] = obj
            self._log.info('Comand %s executed: %s', node, jid)
            raise nbxmpp.NodeProcessed

        # the command is already running, check for it
        magictuple = (jid, sessionid, node)
        if magictuple not in self._sessions:
            # we don't have this session... ha!
            self._log.warning('Invalid session %s', magictuple)
            raise nbxmpp.NodeProcessed

        action = cmd.getAttr('action')
        obj = self._sessions[magictuple]

        try:
            if action == 'cancel':
                rc = obj.cancel(stanza)
            elif action == 'prev':
                rc = obj.prev(stanza)
            elif action == 'next':
                rc = obj.next(stanza)
            elif action == 'execute' or action is None:
                rc = obj.execute(stanza)
            elif action == 'complete':
                rc = obj.complete(stanza)
            else:
                # action is wrong. stop the session, send error
                raise AttributeError
        except AttributeError as error:
            # the command probably doesn't handle invoked action...
            # stop the session, return error
            del self._sessions[magictuple]
            self._log.warning('Wrong action %s %s', node, jid)
            raise nbxmpp.NodeProcessed from error

        # delete the session if rc is False
        if not rc:
            del self._sessions[magictuple]

        raise nbxmpp.NodeProcessed

    def send_command(self, jid, node, session_id,
                     form, action='execute'):
        """
        Send the command with data form. Wait for reply
        """
        self._log.info('Send Command: %s %s %s %s',
                       jid, node, session_id, action)
        stanza = nbxmpp.Iq(typ='set', to=jid)
        cmdnode = stanza.addChild('command',
                                  namespace=Namespace.COMMANDS,
                                  attrs={'node': node,
                                         'action': action})

        if session_id:
            cmdnode.setAttr('sessionid', session_id)

        if form:
            cmdnode.addChild(node=form.get_purged())

        self._con.connection.SendAndCallForResponse(
            stanza, self._action_response_received)

    def _action_response_received(self, _nbxmpp_client, stanza):
        if not nbxmpp.isResultNode(stanza):
            self._log.info('Error: %s', stanza.getError())

            app.nec.push_incoming_event(
                AdHocCommandError(None, conn=self._con,
                                  error=stanza.getError()))
            return
        self._log.info('Received action response')
        command = stanza.getTag('command')
        app.nec.push_incoming_event(
            AdHocCommandActionResponse(
                None, conn=self._con, command=command))

    def send_cancel(self, jid, node, session_id):
        """
        Send the command with action='cancel'
        """
        self._log.info('Cancel: %s %s %s', jid, node, session_id)
        stanza = nbxmpp.Iq(typ='set', to=jid)
        stanza.addChild('command', namespace=Namespace.COMMANDS,
                        attrs={
                            'node': node,
                            'sessionid': session_id,
                            'action': 'cancel'
                        })

        self._con.connection.SendAndCallForResponse(
            stanza, self._cancel_result_received)

    def _cancel_result_received(self, _nbxmpp_client, stanza):
        if not nbxmpp.isResultNode(stanza):
            self._log.warning('Error: %s', stanza.getError())
        else:
            self._log.info('Cancel successful')


class AdHocCommandError(NetworkIncomingEvent):
    name = 'adhoc-command-error'


class AdHocCommandActionResponse(NetworkIncomingEvent):
    name = 'adhoc-command-action-response'


def get_instance(*args, **kwargs):
    return AdHocCommands(*args, **kwargs), 'AdHocCommands'
