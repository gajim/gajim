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


class GcInvitationReceived(NetworkIncomingEvent):
    name = 'gc-invitation-received'


class GcDeclineReceived(NetworkIncomingEvent):
    name = 'gc-decline-received'


def get_instance(*args, **kwargs):
    return MUC(*args, **kwargs), 'MUC'
