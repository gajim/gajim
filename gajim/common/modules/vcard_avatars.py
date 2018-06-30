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

# XEP-0153: vCard-Based Avatars

import os
import logging

import nbxmpp

from gajim.common import app
from gajim.common import helpers
from gajim.common import configpaths
from gajim.common.const import RequestAvatar

log = logging.getLogger('gajim.c.m.vcard.avatars')


class VCardAvatars:
    def __init__(self, con):
        self._con = con
        self._account = con.name
        self._requested_shas = []

        self.handlers = [
            ('presence', self._presence_received, '', nbxmpp.NS_VCARD_UPDATE),
        ]

        self.avatar_advertised = False

    def _presence_received(self, con, stanza):
        update = stanza.getTag('x', namespace=nbxmpp.NS_VCARD_UPDATE)
        if update is None:
            return

        jid = stanza.getFrom()

        avatar_sha = update.getTagData('photo')
        if avatar_sha is None:
            log.info('%s is not ready to promote an avatar', jid)
            # Empty update element, ignore
            return

        if self._con.get_own_jid().bareMatch(jid):
            if self._con.get_own_jid() == jid:
                # Reflection of our own presence
                return
            self._self_update_received(jid, avatar_sha)
            return

        # Check if presence is from a MUC service
        contact = app.contacts.get_groupchat_contact(self._account, str(jid))
        if contact is not None:
            self._update_received(jid, avatar_sha)
        elif stanza.getTag('x', namespace=nbxmpp.NS_MUC_USER):
            show = stanza.getShow()
            type_ = stanza.getType()
            self._gc_update_received(jid, avatar_sha, show, type_)
        else:
            self._update_received(jid, avatar_sha)

    def _self_update_received(self, jid, avatar_sha):
        jid = jid.getStripped()
        full_jid = jid
        if avatar_sha == '':
            # Empty <photo/> tag, means no avatar is advertised
            log.info('%s has no avatar published', full_jid)
            return

        log.info('Update: %s %s', jid, avatar_sha)
        current_sha = app.config.get_per(
            'accounts', self._account, 'avatar_sha')

        if avatar_sha != current_sha:
            log.info('Request : %s', jid)
            self._con.get_module('VCardTemp').request_vcard(RequestAvatar.SELF)
        else:
            log.info('Avatar already known: %s %s',
                     jid, avatar_sha)

    def _update_received(self, jid, avatar_sha, room=False):
        jid = jid.getStripped()
        full_jid = jid
        if avatar_sha == '':
            # Empty <photo/> tag, means no avatar is advertised
            log.info('%s has no avatar published', full_jid)

            # Remove avatar
            log.debug('Remove: %s', jid)
            app.contacts.set_avatar(self._account, jid, None)
            acc_jid = self._con.get_own_jid().getStripped()
            if not room:
                app.logger.set_avatar_sha(acc_jid, jid, None)
            app.interface.update_avatar(
                self._account, jid, room_avatar=room)
        else:
            log.info('Update: %s %s', full_jid, avatar_sha)
            current_sha = app.contacts.get_avatar_sha(self._account, jid)

            if avatar_sha == current_sha:
                log.info('Avatar already known: %s %s', jid, avatar_sha)
                return

            if room:
                # We dont save the room avatar hash in our DB, so check
                # if we previously downloaded it
                if app.interface.avatar_exists(avatar_sha):
                    app.contacts.set_avatar(self._account, jid, avatar_sha)
                    app.interface.update_avatar(
                        self._account, jid, room_avatar=room)
                return

            if avatar_sha not in self._requested_shas:
                self._requested_shas.append(avatar_sha)
                if room:
                    self._con.get_module('VCardTemp').request_vcard(
                        RequestAvatar.ROOM, jid, sha=avatar_sha)
                else:
                    self._con.get_module('VCardTemp').request_vcard(
                        RequestAvatar.USER, jid, sha=avatar_sha)

    def _gc_update_received(self, jid, avatar_sha, show, type_):
        if show == 'offline' or type_ == 'unavailable':
            return

        nick = jid.getResource()

        gc_contact = app.contacts.get_gc_contact(
            self._account, jid.getStripped(), nick)

        if gc_contact is None:
            log.error('no gc contact found: %s', nick)
            return

        if avatar_sha == '':
            # Empty <photo/> tag, means no avatar is advertised, remove avatar
            log.info('%s has no avatar published', nick)
            log.debug('Remove: %s', nick)
            gc_contact.avatar_sha = None
            app.interface.update_avatar(contact=gc_contact)
        else:
            log.info('Update: %s %s', nick, avatar_sha)
            path = os.path.join(configpaths.get('AVATAR'), avatar_sha)
            if not os.path.isfile(path):
                if avatar_sha not in self._requested_shas:
                    app.log('avatar').info('Request: %s', nick)
                    self._requested_shas.append(avatar_sha)
                    self._con.get_module('VCardTemp').request_vcard(
                        RequestAvatar.USER, str(jid),
                        room=True, sha=avatar_sha)
                return

            if gc_contact.avatar_sha != avatar_sha:
                log.info('%s changed his Avatar: %s', nick, avatar_sha)
                gc_contact.avatar_sha = avatar_sha
                app.interface.update_avatar(contact=gc_contact)
            else:
                log.info('Avatar already known: %s', nick)

    def send_avatar_presence(self, force=False):
        if self.avatar_advertised and not force:
            log.debug('Avatar already advertised')
            return
        show = helpers.get_xmpp_show(app.SHOW_LIST[self._con.connected])
        pres = nbxmpp.Presence(typ=None, priority=self._con.priority,
                               show=show, status=self._con.status)
        pres = self._con.add_sha(pres)
        self._con.connection.send(pres)
        self.avatar_advertised = True
        app.interface.update_avatar(self._account,
                                    self._con.get_own_jid().getStripped())

    def add_update_node(self, node):
        update = node.setTag('x', namespace=nbxmpp.NS_VCARD_UPDATE)
        if self._con.get_module('VCardTemp').own_vcard_received:
            sha = app.config.get_per('accounts', self._account, 'avatar_sha')
            own_jid = self._con.get_own_jid()
            log.info('Send avatar presence to: %s %s',
                     node.getTo() or own_jid, sha or 'no sha advertised')
            update.setTagData('photo', sha)
        return node
