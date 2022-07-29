# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
#                    Alex Mauer <hawke AT hawkesnest.net>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
#                         Travis Shirk <travis AT pobox.com>
# Copyright (C) 2007-2008 Julien Pivotto <roidelapluie AT gmail.com>
#                         Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
#                    Jonathan Schleifer <js-gajim AT webkeks.org>
# Copyright (C) 2018 Marcin Mielniczuk <marmistrz dot dev at zoho dot eu>
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

from typing import Any
from typing import Optional

import logging

from nbxmpp import JID
from nbxmpp.const import StatusCode
from nbxmpp.modules.security_labels import Displaymarking
from nbxmpp.structs import PresenceProperties
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import MucSubject

from gi.repository import Gtk

from gajim.common import app
from gajim.common import events
from gajim.common import helpers
from gajim.common.helpers import AdditionalDataDict
from gajim.common.helpers import event_filter
from gajim.common.helpers import to_user_string

from gajim.common.i18n import _
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant

from gajim.gui.controls.base import BaseControl

from gajim.command_system.implementation.hosts import GroupChatCommands

from gajim.gui.const import ControlType
from gajim.gui.dialogs import DialogButton
from gajim.gui.dialogs import ConfirmationDialog
from gajim.gui.groupchat_roster import GroupchatRoster
from gajim.gui.groupchat_state import GroupchatState

log = logging.getLogger('gajim.gui.controls.groupchat')


class GroupchatControl(BaseControl):

    _type = ControlType.GROUPCHAT

    # Set a command host to bound to. Every command given through a group chat
    # will be processed with this command host.
    COMMAND_HOST = GroupChatCommands

    def __init__(self, account: str, jid: JID) -> None:
        BaseControl.__init__(self,
                             'groupchat_control',
                             account,
                             jid)

        self.is_anonymous: bool = True

        self.room_jid = str(self.contact.jid)

        self._groupchat_state = GroupchatState(self.contact)
        self.xml.conv_view_overlay.add_overlay(self._groupchat_state)

        self.roster = GroupchatRoster(self.account, self.room_jid, self)
        self.roster.connect('row-activated', self._on_roster_row_activated)

        show_roster = app.settings.get('hide_groupchat_occupants_list')
        self._roster_revealer = Gtk.Revealer(no_show_all=not show_roster)
        self._roster_revealer.add(self.roster)
        self._roster_revealer.set_reveal_child(show_roster)
        self.xml.conv_view_box.add(self._roster_revealer)

        app.settings.connect_signal(
            'hide_groupchat_occupants_list', self._show_roster)

        self._subject_text = ''

        self._set_control_inactive()

        self.widget.show_all()

        # PluginSystem: adding GUI extension point for this GroupchatControl
        # instance object
        app.plugin_manager.gui_extension_point('groupchat_control', self)

    def _connect_contact_signals(self) -> None:
        self.contact.multi_connect({
            'state-changed': self._on_muc_state_changed,
            'user-joined': self._on_user_joined,
            'user-left': self._on_user_left,
            'user-affiliation-changed': self._on_user_affiliation_changed,
            'user-role-changed': self._on_user_role_changed,
            'user-status-show-changed': self._on_user_status_show_changed,
            'user-nickname-changed': self._on_user_nickname_changed,
            'room-kicked': self._on_room_kicked,
            'room-destroyed': self._on_room_destroyed,
            'room-config-finished': self._on_room_config_finished,
            'room-config-changed': self._on_room_config_changed,
            'room-presence-error': self._on_room_presence_error,
            'room-voice-request': self._on_room_voice_request,
            'room-subject': self._on_room_subject,
        })

    def _on_muc_state_changed(self,
                              _contact: GroupchatContact,
                              _signal_name: str
                              ) -> None:
        if self.contact.is_joined:
            self._set_control_active()

        elif self.contact.is_not_joined:
            self._set_control_inactive()

    def _on_muc_disco_update(self, event: events.MucDiscoUpdate) -> None:
        pass

    # Actions
    def invite(self, invited_jid: JID) -> None:
        # TODO: Remove, used by command system
        self._client.get_module('MUC').invite(
            self.contact.jid, invited_jid)
        invited_contact = self._client.get_module('Contacts').get_contact(
            invited_jid)
        self.add_info_message(
            _('%s has been invited to this group chat') % invited_contact.name)

    def _show_roster(self, show_roster: bool, *args: Any) -> None:
        transition = Gtk.RevealerTransitionType.SLIDE_RIGHT
        if show_roster:
            self._roster_revealer.set_no_show_all(False)
            self._roster_revealer.show_all()
            transition = Gtk.RevealerTransitionType.SLIDE_LEFT
        self._roster_revealer.set_transition_type(transition)
        self._roster_revealer.set_reveal_child(show_roster)

    def _on_roster_row_activated(self,
                                 _roster: GroupchatRoster,
                                 nick: str
                                 ) -> None:
        muc_prefer_direct_msg = app.settings.get('muc_prefer_direct_msg')
        if not self.is_anonymous and muc_prefer_direct_msg:
            participant = self.contact.get_resource(nick)
            app.window.add_chat(self.account,
                                participant.real_jid,
                                'contact',
                                select=True,
                                workspace='current')
        else:
            contact = self.contact.get_resource(nick)
            app.window.add_private_chat(self.account, contact.jid, select=True)

    def _on_room_voice_request(self,
                               _contact: GroupchatContact,
                               _signal_name: str,
                               properties: MessageProperties
                               ) -> None:
        voice_request = properties.voice_request
        assert voice_request is not None

        def on_approve() -> None:
            self._client.get_module('MUC').approve_voice_request(
                self.room_jid, voice_request)

        ConfirmationDialog(
            _('Voice Request'),
            _('Voice Request'),
            _('<b>%(nick)s</b> from <b>%(room_name)s</b> requests voice') % {
                'nick': voice_request.nick, 'room_name': self.contact.name},
            [DialogButton.make('Cancel'),
             DialogButton.make('Accept',
                               text=_('_Approve'),
                               callback=on_approve)],
            modal=False).show()

    def _on_mam_message_received(self,
                                 event: events.MamMessageReceived
                                 ) -> None:
        if not event.properties.type.is_groupchat:
            return
        if event.archive_jid != self.room_jid:
            return
        self.add_message(event.msgtxt,
                         contact=event.properties.muc_nickname,
                         tim=event.properties.mam.timestamp,
                         message_id=event.properties.id,
                         stanza_id=event.stanza_id,
                         additional_data=event.additional_data,
                         notify=False)

    def _on_gc_message_received(self, event: events.GcMessageReceived) -> None:
        if event.properties.muc_nickname is None:
            # message from server
            self.add_message(event.msgtxt,
                             tim=event.properties.timestamp,
                             displaymarking=event.displaymarking,
                             additional_data=event.additional_data)
        else:
            self.add_message(event.msgtxt,
                             contact=event.properties.muc_nickname,
                             tim=event.properties.timestamp,
                             displaymarking=event.displaymarking,
                             message_id=event.properties.id,
                             stanza_id=event.stanza_id,
                             additional_data=event.additional_data)

    def add_message(self,
                    text: str,
                    contact: str = '',
                    tim: Optional[float] = None,
                    displaymarking: Optional[Displaymarking] = None,
                    message_id: Optional[str] = None,
                    stanza_id: Optional[str] = None,
                    additional_data: Optional[AdditionalDataDict] = None,
                    notify: bool = True
                    ) -> None:

        if contact == self.contact.nickname:
            kind = 'outgoing'
        else:
            kind = 'incoming'
            # muc-specific chatstate

        BaseControl.add_message(self,
                                text,
                                kind,
                                contact,
                                tim,
                                notify,
                                displaymarking=displaymarking,
                                message_id=message_id,
                                stanza_id=stanza_id,
                                additional_data=additional_data)

    def _on_room_subject(self,
                         _contact: GroupchatContact,
                         _signal_name: str,
                         subject: Optional[MucSubject]
                         ) -> None:

        if subject is None:
            return

        if self._subject_text == subject.text:
            # Probably a rejoin, we already showed that subject
            return

        self._subject_text = subject.text

        if (app.settings.get('show_subject_on_join') or
                not self.contact.is_joining):
            self.conversation_view.add_muc_subject(subject)

    def _on_room_config_changed(self,
                                _contact: GroupchatContact,
                                _signal_name: str,
                                properties: MessageProperties
                                ) -> None:
        # http://www.xmpp.org/extensions/xep-0045.html#roomconfig-notify

        status_codes = properties.muc_status_codes
        assert status_codes is not None

        changes: list[str] = []
        if StatusCode.SHOWING_UNAVAILABLE in status_codes:
            changes.append(_('Group chat now shows unavailable members'))

        if StatusCode.NOT_SHOWING_UNAVAILABLE in status_codes:
            changes.append(_('Group chat now does not show '
                             'unavailable members'))

        if StatusCode.CONFIG_NON_PRIVACY_RELATED in status_codes:
            changes.append(_('A setting not related to privacy has been '
                             'changed'))
            self._client.get_module('Discovery').disco_muc(self.room_jid)

        if StatusCode.CONFIG_ROOM_LOGGING in status_codes:
            # Can be a presence (see chg_contact_status in groupchat_control.py)
            changes.append(_('Conversations are stored on the server'))

        if StatusCode.CONFIG_NO_ROOM_LOGGING in status_codes:
            changes.append(_('Conversations are not stored on the server'))

        if StatusCode.CONFIG_NON_ANONYMOUS in status_codes:
            changes.append(_('Group chat is now non-anonymous'))
            self.is_anonymous = False

        if StatusCode.CONFIG_SEMI_ANONYMOUS in status_codes:
            changes.append(_('Group chat is now semi-anonymous'))
            self.is_anonymous = True

        if StatusCode.CONFIG_FULL_ANONYMOUS in status_codes:
            changes.append(_('Group chat is now fully anonymous'))
            self.is_anonymous = True

        for change in changes:
            self.add_info_message(change)

    @event_filter(['account'])
    def _on_ping_event(self, event: events.PingEventT) -> None:
        if not event.contact.is_groupchat:
            return

        if self.contact.jid != event.contact.room_jid:
            return

        nick = event.contact.name
        if isinstance(event, events.PingSent):
            self.add_info_message(_('Ping? (%s)') % nick)
        elif isinstance(event, events.PingReply):
            self.add_info_message(_('Pong! (%(nick)s %(delay)s s.)') % {
                'nick': nick,
                'delay': event.seconds})
        else:
            self.add_info_message(event.error)

    def _set_control_active(self) -> None:
        assert self.roster is not None
        self.roster.initial_draw()
        self.conversation_view.update_avatars()

    def _set_control_inactive(self) -> None:
        assert self.roster is not None
        self.roster.enable_sort(False)
        self.roster.clear()

        self._client.get_module('Chatstate').remove_delay_timeout(self.contact)

    def rejoin(self) -> None:
        self._client.get_module('MUC').join(self.room_jid)

    def _on_user_joined(self,
                        _contact: GroupchatContact,
                        _signal_name: str,
                        user_contact: GroupchatParticipant,
                        properties: PresenceProperties
                        ) -> None:
        nick = user_contact.name
        if not properties.is_muc_self_presence:
            if self.contact.is_joined:
                self.conversation_view.add_muc_user_joined(nick)
            return

        status_codes = properties.muc_status_codes or []

        if not self.contact.is_joined:
            # We just joined the room
            self.add_info_message(_('You (%s) joined the group chat') % nick)

        if StatusCode.NON_ANONYMOUS in status_codes:
            self.add_info_message(
                _('Any participant is allowed to see your full XMPP Address'))
            self.is_anonymous = False

        if StatusCode.CONFIG_ROOM_LOGGING in status_codes:
            self.add_info_message(_('Conversations are stored on the server'))

        if StatusCode.NICKNAME_MODIFIED in status_codes:
            self.add_info_message(
                _('The server has assigned or modified your nickname in this '
                  'group chat'))

    def _on_room_config_finished(self,
                                 _contact: GroupchatContact,
                                 _signal_name: str
                                 ) -> None:
        self.add_info_message(_('A new group chat has been created'))

    def _on_user_nickname_changed(self,
                                  _contact: GroupchatContact,
                                  _signal_name: str,
                                  user_contact: GroupchatParticipant,
                                  properties: MessageProperties
                                  ) -> None:
        nick = user_contact.name

        assert properties.muc_user is not None
        new_nick = properties.muc_user.nick
        if properties.is_muc_self_presence:
            message = _('You are now known as %s') % new_nick
        else:
            message = _('{nick} is now known '
                        'as {new_nick}').format(nick=nick, new_nick=new_nick)

        self.add_info_message(message)

    def _on_user_status_show_changed(self,
                                     contact: GroupchatContact,
                                     _signal_name: str,
                                     user_contact: GroupchatParticipant,
                                     properties: MessageProperties
                                     ) -> None:
        if not contact.settings.get('print_status'):
            return

        self.conversation_view.add_user_status(user_contact.name,
                                               user_contact.show.value,
                                               user_contact.status)

    def _on_user_affiliation_changed(self,
                                     _contact: GroupchatContact,
                                     _signal_name: str,
                                     user_contact: GroupchatParticipant,
                                     properties: PresenceProperties
                                     ) -> None:
        affiliation = helpers.get_uf_affiliation(user_contact.affiliation)
        nick = user_contact.name

        assert properties.muc_user is not None
        reason = properties.muc_user.reason
        reason = '' if reason is None else f': {reason}'

        actor = properties.muc_user.actor
        # Group Chat: You have been kicked by Alice
        actor = '' if actor is None else _(' by {actor}').format(actor=actor)

        if properties.is_muc_self_presence:
            message = _('** Your Affiliation has been set to '
                        '{affiliation}{actor}{reason}').format(
                            affiliation=affiliation,
                            actor=actor,
                            reason=reason)
        else:
            message = _('** Affiliation of {nick} has been set to '
                        '{affiliation}{actor}{reason}').format(
                            nick=nick,
                            affiliation=affiliation,
                            actor=actor,
                            reason=reason)

        self.add_info_message(message)

    def _on_user_role_changed(self,
                              _contact: GroupchatContact,
                              _signal_name: str,
                              user_contact: GroupchatParticipant,
                              properties: PresenceProperties
                              ) -> None:
        role = helpers.get_uf_role(user_contact.role)
        nick = user_contact.name

        assert properties.muc_user is not None
        reason = properties.muc_user.reason
        reason = '' if reason is None else f': {reason}'

        actor = properties.muc_user.actor
        # Group Chat: You have been kicked by Alice
        actor = '' if actor is None else _(' by {actor}').format(actor=actor)

        if properties.is_muc_self_presence:
            message = _('** Your Role has been set to '
                        '{role}{actor}{reason}').format(role=role,
                                                        actor=actor,
                                                        reason=reason)
        else:
            message = _('** Role of {nick} has been set to '
                        '{role}{actor}{reason}').format(nick=nick,
                                                        role=role,
                                                        actor=actor,
                                                        reason=reason)

        self.add_info_message(message)

    def _on_room_kicked(self,
                        _contact: GroupchatContact,
                        _signal_name: str,
                        properties: MessageProperties
                        ) -> None:
        status_codes = properties.muc_status_codes or []

        assert properties.muc_user is not None
        reason = properties.muc_user.reason
        reason = '' if reason is None else f': {reason}'

        actor = properties.muc_user.actor
        # Group Chat: You have been kicked by Alice
        actor = '' if actor is None else _(' by {actor}').format(actor=actor)

        # Group Chat: We have been removed from the room by Alice: reason
        message = _('You have been removed from the group chat{actor}{reason}')

        if StatusCode.REMOVED_ERROR in status_codes:
            # Handle 333 before 307, some MUCs add both
            # Group Chat: Server kicked us because of an server error
            message = _('You have left due '
                        'to an error{reason}').format(reason=reason)
            self.add_info_message(message)

        elif StatusCode.REMOVED_KICKED in status_codes:
            # Group Chat: We have been kicked by Alice: reason
            message = _('You have been '
                        'kicked{actor}{reason}').format(actor=actor,
                                                        reason=reason)
            self.add_info_message(message)

        elif StatusCode.REMOVED_BANNED in status_codes:
            # Group Chat: We have been banned by Alice: reason
            message = _('You have been '
                        'banned{actor}{reason}').format(actor=actor,
                                                        reason=reason)
            self.add_info_message(message)

        elif StatusCode.REMOVED_AFFILIATION_CHANGE in status_codes:
            # Group Chat: We were removed because of an affiliation change
            reason = _(': Affiliation changed')
            message = message.format(actor=actor, reason=reason)
            self.add_info_message(message)

        elif StatusCode.REMOVED_NONMEMBER_IN_MEMBERS_ONLY in status_codes:
            # Group Chat: Room configuration changed
            reason = _(': Group chat configuration changed to members-only')
            message = message.format(actor=actor, reason=reason)
            self.add_info_message(message)

        elif StatusCode.REMOVED_SERVICE_SHUTDOWN in status_codes:
            # Group Chat: Kicked because of server shutdown
            reason = ': System shutdown'
            message = message.format(actor=actor, reason=reason)
            self.add_info_message(message)

    def _on_user_left(self,
                      _contact: GroupchatContact,
                      _signal_name: str,
                      user_contact: GroupchatParticipant,
                      properties: MessageProperties
                      ) -> None:
        status_codes = properties.muc_status_codes or []
        nick = user_contact.name

        assert properties.muc_user is not None
        reason = properties.muc_user.reason
        reason = '' if reason is None else f': {reason}'

        actor = properties.muc_user.actor
        # Group Chat: You have been kicked by Alice
        actor = '' if actor is None else _(' by {actor}').format(actor=actor)

        # Group Chat: We have been removed from the room
        message = _('{nick} has been removed from the group chat{by}{reason}')

        if StatusCode.REMOVED_ERROR in status_codes:
            # Handle 333 before 307, some MUCs add both
            self.conversation_view.add_muc_user_left(
                nick, properties.muc_user.reason, error=True)

        elif StatusCode.REMOVED_KICKED in status_codes:
            # Group Chat: User was kicked by Alice: reason
            message = _('{nick} has been '
                        'kicked{actor}{reason}').format(nick=nick,
                                                        actor=actor,
                                                        reason=reason)
            self.add_info_message(message)

        elif StatusCode.REMOVED_BANNED in status_codes:
            # Group Chat: User was banned by Alice: reason
            message = _('{nick} has been '
                        'banned{actor}{reason}').format(nick=nick,
                                                        actor=actor,
                                                        reason=reason)
            self.add_info_message(message)

        elif StatusCode.REMOVED_AFFILIATION_CHANGE in status_codes:
            reason = _(': Affiliation changed')
            message = message.format(nick=nick, by=actor, reason=reason)
            self.add_info_message(message)

        elif StatusCode.REMOVED_NONMEMBER_IN_MEMBERS_ONLY in status_codes:
            reason = _(': Group chat configuration changed to members-only')
            message = message.format(nick=nick, by=actor, reason=reason)
            self.add_info_message(message)

        else:
            self.conversation_view.add_muc_user_left(
                nick, properties.muc_user.reason)

    def _on_room_presence_error(self,
                                _contact: GroupchatContact,
                                _signal_name: str,
                                properties: MessageProperties
                                ) -> None:
        error_message = to_user_string(properties.error)
        self.add_info_message(_('Error: %s') % error_message)

    def _on_room_destroyed(self,
                           _contact: GroupchatContact,
                           _signal_name: str,
                           properties: MessageProperties
                           ) -> None:
        destroyed = properties.muc_destroyed

        reason = destroyed.reason
        reason = '' if reason is None else f': {reason}'

        message = _('Group chat has been destroyed')
        self.add_info_message(message)

        alternate = destroyed.alternate
        if alternate is not None:
            join_message = _('You can join this group chat '
                             'instead: xmpp:%s?join') % str(alternate)
            self.add_info_message(join_message)

    def shutdown(self, reason: Optional[str] = None) -> None:
        app.settings.disconnect_signals(self)
        self.contact.disconnect(self)

        # PluginSystem: removing GUI extension points connected with
        # GrouphatControl instance object
        app.plugin_manager.remove_gui_extension_point(
            'groupchat_control', self)

        self.roster.destroy()
        self.roster = None

        super(GroupchatControl, self).shutdown()
        app.check_finalize(self)
