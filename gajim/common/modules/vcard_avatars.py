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

from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler
from nbxmpp.const import AvatarState
from nbxmpp.modules.util import is_error

from gajim.common import app
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import as_task


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

        self.avatar_conversion_available = False

    def pass_disco(self, info):
        is_available = Namespace.VCARD_CONVERSION in info.features
        self.avatar_conversion_available = is_available
        self._log.info('Discovered Avatar Conversion')

    @as_task
    def _request_vcard(self, jid, expected_sha, type_):
        _task = yield

        vcard = yield self._con.get_module('VCardTemp').request_vcard(jid=jid)

        if is_error(vcard):
            self._log.warning(vcard)
            return

        avatar, avatar_sha = vcard.get_avatar()
        if avatar is None:
            self._log.warning('Avatar missing: %s %s', jid, expected_sha)
            return

        if expected_sha != avatar_sha:
            self._log.warning('Avatar mismatch: %s %s != %s',
                              jid,
                              expected_sha,
                              avatar_sha)
            return

        self._log.info('Received: %s %s', jid, avatar_sha)
        app.interface.save_avatar(avatar)

        if type_ == 'contact':
            self._con.get_module('Roster').set_avatar_sha(jid, avatar_sha)
            app.contacts.set_avatar(self._account, jid, avatar_sha)
            app.interface.update_avatar(self._account, jid)

        elif type_ == 'muc':
            app.storage.cache.set_muc_avatar_sha(jid, avatar_sha)
            app.contacts.set_avatar(self._account, jid, avatar_sha)
            app.interface.update_avatar(self._account, jid, room_avatar=True)

        elif type_ == 'muc-user':
            contact = app.contacts.get_gc_contact(self._account,
                                                  jid.bare,
                                                  jid.resource)
            if contact is not None:
                contact.avatar_sha = avatar_sha
                app.interface.update_avatar(contact=contact)

    def _presence_received(self, _con, _stanza, properties):
        if not properties.type.is_available:
            return

        if properties.avatar_state in (AvatarState.IGNORE,
                                       AvatarState.NOT_READY):
            return

        if self._con.get_own_jid().bare_match(properties.jid):
            return

        if properties.from_muc:
            self._gc_update_received(properties)
        else:
            # Check if presence is from a MUC service
            contact = app.contacts.get_groupchat_contact(self._account,
                                                         str(properties.jid))
            self._update_received(properties, room=contact is not None)

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
        self._process_update(properties.jid.bare,
                             properties.avatar_state,
                             properties.avatar_sha,
                             room)

    def _process_update(self, jid, state, avatar_sha, room):
        if state == AvatarState.EMPTY:
            # Empty <photo/> tag, means no avatar is advertised
            self._log.info('%s has no avatar published', jid)
            app.contacts.set_avatar(self._account, jid, None)

            if room:
                app.storage.cache.set_muc_avatar_sha(jid, None)
            else:
                self._con.get_module('Roster').set_avatar_sha(jid, None)
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
                    app.storage.cache.set_muc_avatar_sha(jid, avatar_sha)
                else:
                    self._con.get_module('Roster').set_avatar_sha(jid,
                                                                  avatar_sha)
                app.contacts.set_avatar(self._account, jid, avatar_sha)
                app.interface.update_avatar(
                    self._account, jid, room_avatar=room)
                return

            if avatar_sha not in self._requested_shas:
                self._requested_shas.append(avatar_sha)
                if room:
                    self._request_vcard(jid, avatar_sha, 'muc')
                else:
                    self._request_vcard(jid, avatar_sha, 'contact')

    def _gc_update_received(self, properties):
        nick = properties.jid.resource

        gc_contact = app.contacts.get_gc_contact(
            self._account, properties.jid.bare, nick)

        if gc_contact is None:
            self._log.error('no gc contact found: %s', nick)
            return

        if properties.avatar_state == AvatarState.EMPTY:
            # Empty <photo/> tag, means no avatar is advertised
            self._log.info('%s has no avatar published', nick)
            gc_contact.avatar_sha = None
            app.interface.update_avatar(contact=gc_contact)
        else:
            self._log.info('Update: %s %s', nick, properties.avatar_sha)
            if not app.interface.avatar_exists(properties.avatar_sha):
                if properties.avatar_sha not in self._requested_shas:
                    app.log('avatar').info('Request: %s', nick)
                    self._requested_shas.append(properties.avatar_sha)
                    self._request_vcard(properties.jid,
                                        properties.avatar_sha,
                                        'muc-user')
                return

            if gc_contact.avatar_sha != properties.avatar_sha:
                self._log.info('%s changed their Avatar: %s',
                               nick, properties.avatar_sha)
                gc_contact.avatar_sha = properties.avatar_sha
                app.interface.update_avatar(contact=gc_contact)
            else:
                self._log.info('Avatar already known: %s', nick)


def get_instance(*args, **kwargs):
    return VCardAvatars(*args, **kwargs), 'VCardAvatars'
