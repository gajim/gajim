# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

# XEP-0045: Multi-User Chat
# XEP-0249: Direct MUC Invitations

import logging

import nbxmpp

from gajim.common import i18n
from gajim.common.modules import dataforms
from gajim.common import app
from gajim.common import helpers
from gajim.common.nec import NetworkIncomingEvent

log = logging.getLogger('gajim.c.m.muc')


class MUC:
    def __init__(self, con):
        self._con = con
        self._account = con.name

        self.handlers = [
            ('message', self._mediated_invite, '', nbxmpp.NS_MUC_USER),
            ('message', self._direct_invite, '', nbxmpp.NS_CONFERENCE),
        ]

    def pass_disco(self, from_, identities, features, data, node):
        for identity in identities:
            if identity.get('category') != 'conference':
                continue
            if identity.get('type') != 'text':
                continue
            if nbxmpp.NS_MUC in features:
                log.info('Discovered MUC: %s', from_)
                # TODO: make this nicer
                self._con.muc_jid['jabber'] = from_
                raise nbxmpp.NodeProcessed

    def set_subject(self, room_jid, subject):
        if not app.account_is_connected(self._account):
            return
        message = nbxmpp.Message(room_jid, typ='groupchat', subject=subject)
        log.info('Set subject for %s', room_jid)
        self._con.connection.send(message)

    def request_config(self, room_jid):
        if not app.account_is_connected(self._account):
            return
        iq = nbxmpp.Iq(typ='get',
                       queryNS=nbxmpp.NS_MUC_OWNER,
                       to=room_jid)
        iq.setAttr('xml:lang', i18n.LANG)
        log.info('Request config for %s', room_jid)
        self._con.connection.SendAndCallForResponse(
            iq, self._config_received)

    def _config_received(self, stanza):
        if not nbxmpp.isResultNode(stanza):
            log.info('Error: %s', stanza.getError())
            return

        room_jid = stanza.getFrom().getStripped()
        payload = stanza.getQueryPayload()

        for form in payload:
            if form.getNamespace() == nbxmpp.NS_DATA:
                dataform = dataforms.ExtendForm(node=form)
                log.info('Config form received for %s', room_jid)
                app.nec.push_incoming_event(MucOwnerReceivedEvent(
                    None,
                    conn=self._con,
                    form_node=form,
                    dataform=dataform,
                    jid=room_jid))
                break

    def cancel_config(self, room_jid):
        if not app.account_is_connected(self._account):
            return
        cancel = nbxmpp.Node(tag='x', attrs={'xmlns': nbxmpp.NS_DATA,
                                             'type': 'cancel'})
        iq = nbxmpp.Iq(typ='set',
                       queryNS=nbxmpp.NS_MUC_OWNER,
                       payload=cancel,
                       to=room_jid)
        log.info('Cancel config for %s', room_jid)
        self._con.connection.SendAndCallForResponse(
            iq, self._default_response, {})

    def destroy(self, room_jid, reason='', jid=''):
        if not app.account_is_connected(self._account):
            return
        iq = nbxmpp.Iq(typ='set',
                       queryNS=nbxmpp.NS_MUC_OWNER,
                       to=room_jid)
        destroy = iq.setQuery().setTag('destroy')
        if reason:
            destroy.setTagData('reason', reason)
        if jid:
            destroy.setAttr('jid', jid)
        log.info('Destroy room: %s, reason: %s, alternate: %s',
                 room_jid, reason, jid)
        self._con.connection.SendAndCallForResponse(
            iq, self._default_response, {})

    def set_config(self, room_jid, form):
        if not app.account_is_connected(self._account):
            return
        iq = nbxmpp.Iq(typ='set', to=room_jid, queryNS=nbxmpp.NS_MUC_OWNER)
        query = iq.setQuery()
        form.setAttr('type', 'submit')
        query.addChild(node=form)
        log.info('Set config for %s', room_jid)
        self._con.connection.SendAndCallForResponse(
            iq, self._default_response, {})

    def set_affiliation(self, room_jid, users_dict):
        if not app.account_is_connected(self._account):
            return
        iq = nbxmpp.Iq(typ='set', to=room_jid, queryNS=nbxmpp.NS_MUC_ADMIN)
        item = iq.setQuery()
        for jid in users_dict:
            affiliation = users_dict[jid].get('affiliation')
            reason = users_dict[jid].get('reason') or None
            item_tag = item.addChild('item', {'jid': jid,
                                              'affiliation': affiliation})
            if reason is not None:
                item_tag.setTagData('reason', reason)
        log.info('Set affiliation for %s: %s', room_jid, users_dict)
        self._con.connection.SendAndCallForResponse(
            iq, self._default_response, {})

    def get_affiliation(self, room_jid, affiliation):
        if not app.account_is_connected(self._account):
            return
        iq = nbxmpp.Iq(typ='get', to=room_jid, queryNS=nbxmpp.NS_MUC_ADMIN)
        item = iq.setQuery().setTag('item')
        item.setAttr('affiliation', affiliation)
        log.info('Get affiliation %s for %s', affiliation, room_jid)
        self._con.connection.SendAndCallForResponse(
            iq, self._affiliation_received)

    def _affiliation_received(self, stanza):
        if not nbxmpp.isResultNode(stanza):
            log.info('Error: %s', stanza.getError())
            return

        room_jid = stanza.getFrom().getStripped()
        query = stanza.getTag('query', namespace=nbxmpp.NS_MUC_ADMIN)
        items = query.getTags('item')
        users_dict = {}
        for item in items:
            try:
                jid = helpers.parse_jid(item.getAttr('jid'))
            except helpers.InvalidFormat:
                log.warning('Invalid JID: %s, ignoring it',
                            item.getAttr('jid'))
                continue
            affiliation = item.getAttr('affiliation')
            users_dict[jid] = {'affiliation': affiliation}
            if item.has_attr('nick'):
                users_dict[jid]['nick'] = item.getAttr('nick')
            if item.has_attr('role'):
                users_dict[jid]['role'] = item.getAttr('role')
            reason = item.getTagData('reason')
            if reason:
                users_dict[jid]['reason'] = reason
        log.info('Affiliations received from %s: %s', room_jid, users_dict)
        app.nec.push_incoming_event(MucAdminReceivedEvent(
            None, conn=self._con, room_jid=room_jid, users_dict=users_dict))

    def set_role(self, room_jid, nick, role, reason=''):
        if not app.account_is_connected(self._account):
            return
        iq = nbxmpp.Iq(typ='set', to=room_jid, queryNS=nbxmpp.NS_MUC_ADMIN)
        item = iq.setQuery().setTag('item')
        item.setAttr('nick', nick)
        item.setAttr('role', role)
        if reason:
            item.addChild(name='reason', payload=reason)
        log.info('Set role for %s: %s %s %s', room_jid, nick, role, reason)
        self._con.connection.SendAndCallForResponse(
            iq, self._default_response, {})

    def _mediated_invite(self, con, stanza):
        muc_user = stanza.getTag('x', namespace=nbxmpp.NS_MUC_USER)
        if muc_user is None:
            return

        decline = muc_user.getTag('decline')
        if decline is not None:

            room_jid = stanza.getFrom().getStripped()
            from_ = self._get_from(room_jid, decline)

            reason = decline.getTagData('reason')
            log.info('Invite declined: %s, %s', reason, from_)
            app.nec.push_incoming_event(
                GcDeclineReceived(None,
                                  account=self._account,
                                  from_=from_,
                                  room_jid=room_jid,
                                  reason=reason))
            raise nbxmpp.NodeProcessed

        invite = muc_user.getTag('invite')
        if invite is not None:

            room_jid = stanza.getFrom().getStripped()
            from_ = self._get_from(room_jid, invite)

            reason = invite.getTagData('reason')
            password = muc_user.getTagData('password')
            is_continued = invite.getTag('continue') is not None
            log.info('Mediated invite: continued: %s, reason: %s, from: %s',
                     is_continued, reason, from_)
            if room_jid in app.gc_connected[self._account] and \
                    app.gc_connected[self._account][room_jid]:
                # We are already in groupchat. Ignore invitation
                log.info('We are already in this room')
                raise nbxmpp.NodeProcessed

            app.nec.push_incoming_event(
                GcInvitationReceived(None,
                                     account=self._account,
                                     from_=from_,
                                     room_jid=room_jid,
                                     reason=reason,
                                     password=password,
                                     is_continued=is_continued))
            raise nbxmpp.NodeProcessed

    def _get_from(self, room_jid, stanza):
        try:
            from_ = nbxmpp.JID(helpers.parse_jid(stanza.getAttr('from')))
        except helpers.InvalidFormat:
            log.warning('Invalid JID on invite: %s, ignoring it',
                        stanza.getAttr('from'))
            raise nbxmpp.NodeProcessed

        known_contact = app.contacts.get_contacts(self._account, room_jid)
        ignore = app.config.get_per(
            'accounts', self._account, 'ignore_unknown_contacts')
        if ignore and not known_contact:
            log.info('Ignore invite from unknown contact %s', from_)
            raise nbxmpp.NodeProcessed

        return from_

    def _direct_invite(self, con, stanza):
        direct = stanza.getTag('x', namespace=nbxmpp.NS_CONFERENCE)
        if direct is None:
            return

        from_ = stanza.getFrom()

        try:
            room_jid = helpers.parse_jid(direct.getAttr('jid'))
        except helpers.InvalidFormat:
            log.warning('Invalid JID on invite: %s, ignoring it',
                        direct.getAttr('jid'))
            raise nbxmpp.NodeProcessed

        reason = direct.getAttr('reason')
        password = direct.getAttr('password')
        is_continued = direct.getAttr('continue') == 'true'

        log.info('Direct invite: continued: %s, reason: %s, from: %s',
                 is_continued, reason, from_)

        app.nec.push_incoming_event(
            GcInvitationReceived(None,
                                 account=self._account,
                                 from_=from_,
                                 room_jid=room_jid,
                                 reason=reason,
                                 password=password,
                                 is_continued=is_continued))
        raise nbxmpp.NodeProcessed

    def invite(self, room, to, reason=None, continue_=False):
        if not app.account_is_connected(self._account):
            return
        contact = app.contacts.get_contact_from_full_jid(self._account, to)
        if contact and contact.supports(nbxmpp.NS_CONFERENCE):
            invite = self._build_direct_invite(room, to, reason, continue_)
        else:
            invite = self._build_mediated_invite(room, to, reason, continue_)
        self._con.connection.send(invite)

    def _build_direct_invite(self, room, to, reason, continue_):
        message = nbxmpp.Message(to=to)
        attrs = {'jid': room}
        if reason:
            attrs['reason'] = reason
        if continue_:
            attrs['continue'] = 'true'
        password = app.gc_passwords.get(room, None)
        if password:
            attrs['password'] = password
        message = message.addChild(name='x', attrs=attrs,
                                   namespace=nbxmpp.NS_CONFERENCE)
        return message

    def _build_mediated_invite(self, room, to, reason, continue_):
        message = nbxmpp.Message(to=room)
        muc_user = message.addChild('x', namespace=nbxmpp.NS_MUC_USER)
        invite = muc_user.addChild('invite', attrs={'to': to})
        if continue_:
            invite.addChild(name='continue')
        if reason:
            invite.setTagData('reason', reason)
        password = app.gc_passwords.get(room, None)
        if password:
            muc_user.setTagData('password', password)
        return message

    def decline(self, room, to, reason=None):
        if not app.account_is_connected(self._account):
            return
        message = nbxmpp.Message(to=room)
        muc_user = message.addChild('x', namespace=nbxmpp.NS_MUC_USER)
        decline = muc_user.addChild('decline', attrs={'to': to})
        if reason:
            decline.setTagData('reason', reason)
        self._con.connection.send(message)

    def request_voice(self, room):
        if not app.account_is_connected(self._account):
            return
        message = nbxmpp.Message(to=room)
        x = nbxmpp.DataForm(typ='submit')
        x.addChild(node=nbxmpp.DataField(name='FORM_TYPE',
                                         value=nbxmpp.NS_MUC + '#request'))
        x.addChild(node=nbxmpp.DataField(name='muc#role',
                                         value='participant',
                                         typ='text-single'))
        message.addChild(node=x)
        self._con.connection.send(message)

    def _default_response(self, conn, stanza, **kwargs):
        if not nbxmpp.isResultNode(stanza):
            log.info('Error: %s', stanza.getError())


class GcInvitationReceived(NetworkIncomingEvent):
    name = 'gc-invitation-received'


class GcDeclineReceived(NetworkIncomingEvent):
    name = 'gc-decline-received'


class MucAdminReceivedEvent(NetworkIncomingEvent):
    name = 'muc-admin-received'


class MucOwnerReceivedEvent(NetworkIncomingEvent):
    name = 'muc-owner-received'


def get_instance(*args, **kwargs):
    return MUC(*args, **kwargs), 'MUC'
