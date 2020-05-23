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

from pathlib import Path

from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler
from nbxmpp.const import AvatarState

from gajim.common import app
from gajim.common import configpaths
from gajim.common.const import RequestAvatar
from gajim.common.modules.base import BaseModule


class VCardAvatars(BaseModule):
    def __init__(self, con):
        BaseModule.__init__(self, con)
        self._requested_shas = []

        self.handlers = [
            StanzaHandler(name='presence',
                          callback=self._presence_received,
                          ns=Namespace.VCARD_UPDATE,
                          priority=51),
        ]

        self.avatar_advertised = False
        self._find_own_avatar()

    def _find_own_avatar(self):
        sha = app.config.get_per('accounts', self._account, 'avatar_sha')
        if not sha:
            return
        path = Path(configpaths.get('AVATAR')) / sha
        if not path.exists():
            self._log.info('Missing own avatar, reset sha')
            app.config.set_per('accounts', self._account, 'avatar_sha', '')

    def _presence_received(self, _con, _stanza, properties):
        if not properties.type.is_available:
            return

        if properties.avatar_state in (AvatarState.IGNORE,
                                       AvatarState.NOT_READY):
            return

        if self._con.get_own_jid().bareMatch(properties.jid):
            if self._con.get_own_jid() == properties.jid:
                # Initial presence reflection
                if self._con.avatar_conversion:
                    # XEP-0398: Tells us the current avatar sha on the
                    # initial presence reflection
                    self._self_update_received(properties)
            else:
                # Presence from another resource of ours
                self._self_update_received(properties)
            return

        if properties.from_muc:
            self._gc_update_received(properties)
        else:
            # Check if presence is from a MUC service
            contact = app.contacts.get_groupchat_contact(self._account,
                                                         str(properties.jid))
            self._update_received(properties, room=contact is not None)

    def _self_update_received(self, properties):
        jid = properties.jid.getBare()
        if properties.avatar_state == AvatarState.EMPTY:
            # Empty <photo/> tag, means no avatar is advertised
            self._log.info('%s has no avatar published', properties.jid)
            app.config.set_per('accounts', self._account, 'avatar_sha', '')
            app.contacts.set_avatar(self._account, jid, None)
            app.interface.update_avatar(self._account, jid)
            return

        self._log.info('Update: %s %s', jid, properties.avatar_sha)
        current_sha = app.config.get_per(
            'accounts', self._account, 'avatar_sha')

        if properties.avatar_sha != current_sha:
            path = Path(configpaths.get('AVATAR')) / properties.avatar_sha
            if path.exists():
                app.config.set_per('accounts', self._account,
                                   'avatar_sha', properties.avatar_sha)
                app.contacts.set_avatar(self._account,
                                        jid,
                                        properties.avatar_sha)
                app.interface.update_avatar(self._account, jid)
            else:
                self._log.info('Request : %s', jid)
                self._con.get_module('VCardTemp').request_vcard(
                    RequestAvatar.SELF)
        else:
            self._log.info('Avatar already known: %s %s',
                           jid, properties.avatar_sha)

    def muc_disco_info_update(self, disco_info):
        if not disco_info.supports(Namespace.VCARD):
            return

        field_var = '{http://modules.prosody.im/mod_vcard_muc}avatar#sha1'
        if not disco_info.has_field(Namespace.MUC_INFO, field_var):
            # Workaround so we don’t delete the avatar for servers that don’t
            # support sha in disco info. Once there is a accepted XEP this
            # can be removed
            return

        avatar_sha = disco_info.get_field_value(Namespace.MUC_INFO, field_var)
        state = AvatarState.EMPTY if not avatar_sha else AvatarState.ADVERTISED
        self._process_update(str(disco_info.jid), state, avatar_sha, True)

    def _update_received(self, properties, room=False):
        self._process_update(properties.jid.getBare(),
                             properties.avatar_state,
                             properties.avatar_sha,
                             room)

    def _process_update(self, jid, state, avatar_sha, room):
        acc_jid = self._con.get_own_jid().getStripped()
        if state == AvatarState.EMPTY:
            # Empty <photo/> tag, means no avatar is advertised
            self._log.info('%s has no avatar published', jid)

            # Remove avatar
            self._log.debug('Remove: %s', jid)
            app.contacts.set_avatar(self._account, jid, None)

            if room:
                app.logger.set_muc_avatar_sha(jid, None)
            else:
                app.logger.set_avatar_sha(acc_jid, jid, None)
            app.interface.update_avatar(self._account, jid, room_avatar=room)
        else:
            self._log.info('Update: %s %s', jid, avatar_sha)
            current_sha = app.contacts.get_avatar_sha(self._account, jid)

            if avatar_sha == current_sha:
                self._log.info('Avatar already known: %s %s', jid, avatar_sha)
                return

            if app.interface.avatar_exists(avatar_sha):
                # Check if the avatar is already in storage
                self._log.info('Found avatar in storage')
                if room:
                    app.logger.set_muc_avatar_sha(jid, avatar_sha)
                else:
                    app.logger.set_avatar_sha(acc_jid, jid, avatar_sha)
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

    def _gc_update_received(self, properties):
        nick = properties.jid.getResource()

        gc_contact = app.contacts.get_gc_contact(
            self._account, properties.jid.getBare(), nick)

        if gc_contact is None:
            self._log.error('no gc contact found: %s', nick)
            return

        if properties.avatar_state == AvatarState.EMPTY:
            # Empty <photo/> tag, means no avatar is advertised, remove avatar
            self._log.info('%s has no avatar published', nick)
            self._log.debug('Remove: %s', nick)
            gc_contact.avatar_sha = None
            app.interface.update_avatar(contact=gc_contact)
        else:
            self._log.info('Update: %s %s', nick, properties.avatar_sha)
            if not app.interface.avatar_exists(properties.avatar_sha):
                if properties.avatar_sha not in self._requested_shas:
                    app.log('avatar').info('Request: %s', nick)
                    self._requested_shas.append(properties.avatar_sha)
                    self._con.get_module('VCardTemp').request_vcard(
                        RequestAvatar.USER, str(properties.jid),
                        room=True, sha=properties.avatar_sha)
                return

            if gc_contact.avatar_sha != properties.avatar_sha:
                self._log.info('%s changed their Avatar: %s',
                               nick, properties.avatar_sha)
                gc_contact.avatar_sha = properties.avatar_sha
                app.interface.update_avatar(contact=gc_contact)
            else:
                self._log.info('Avatar already known: %s', nick)

    def send_avatar_presence(self, force=False, after_publish=False):
        if self._con.avatar_conversion:
            if not after_publish:
                # XEP-0398: We only resend presence after we publish a
                # new avatar
                return
        else:
            if self.avatar_advertised and not force:
                self._log.debug('Avatar already advertised')
                return

        self._con.update_presence()
        self.avatar_advertised = True

    def add_update_node(self, node):
        update = node.setTag('x', namespace=Namespace.VCARD_UPDATE)
        if self._con.get_module('VCardTemp').own_vcard_received:
            sha = app.config.get_per('accounts', self._account, 'avatar_sha')
            own_jid = self._con.get_own_jid()
            self._log.info('Send avatar presence to: %s %s',
                           node.getTo() or own_jid, sha or 'no sha advertised')
            update.setTagData('photo', sha)


def get_instance(*args, **kwargs):
    return VCardAvatars(*args, **kwargs), 'VCardAvatars'
