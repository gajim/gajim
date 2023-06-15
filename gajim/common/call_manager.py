from __future__ import annotations

import logging
import time

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common import events
from gajim.common import ged
from gajim.common import sound
from gajim.common import types
from gajim.common.const import CallType
from gajim.common.const import JingleState
from gajim.common.const import KindConstant
from gajim.common.ged import EventHelper
from gajim.common.helpers import AdditionalDataDict
from gajim.common.helpers import play_sound
from gajim.common.i18n import _
from gajim.common.jingle_rtp import JingleAudio
from gajim.common.jingle_session import JingleSession
from gajim.common.modules.contacts import BareContact

log = logging.getLogger('gajim.c.call_manager')


class CallManager(EventHelper):
    def __init__(self) -> None:
        EventHelper.__init__(self)
        self._account: str | None = None
        self._resource_jid: JID | None = None

        self._jingle_audio_sid: str | None = None
        self._jingle_video_sid: str | None = None

        self._jingle_audio_state: JingleState = JingleState.NULL
        self._jingle_video_state: JingleState = JingleState.NULL

        # Helper for upgrading voice call to voice + video without
        # having to show a new call row
        self._incoming_video_event: events.JingleRequestReceived | None = None

        # pylint: disable=line-too-long
        self.register_events([
            ('jingle-request-received', ged.GUI2, self._on_jingle_request),
            ('jingle-connected-received', ged.GUI2, self._on_jingle_connected),
            ('jingle-disconnected-received', ged.GUI2,
             self._on_jingle_disconnected),
            ('jingle-error-received', ged.GUI2, self._on_jingle_error),
        ])
        # pylint: enable=line-too-long

    def _on_jingle_request(self, event: events.JingleRequestReceived) -> None:
        content_types: list[str] = []
        for item in event.contents:
            content_types.append(item.media)
        if not any(item in ('audio', 'video') for item in content_types):
            return

        if self._resource_jid is not None:
            if str(self._resource_jid) != event.fjid:
                log.info('Received jingle request while in active call: '
                         '%s, %s',
                         event.account, event.jid)
                return

        self._account = event.account
        self._resource_jid = JID.from_string(event.fjid)

        if 'audio' in content_types:
            self._set_jingle_state(
                'audio',
                JingleState.CONNECTION_RECEIVED,
                event.sid)
        if 'video' in content_types:
            self._set_jingle_state(
                'video',
                JingleState.CONNECTION_RECEIVED,
                event.sid)

        if self._jingle_audio_state in (
                JingleState.CONNECTED,
                JingleState.CONNECTING) and 'video' in content_types:
            self._incoming_video_event = event
        else:
            # There is no voice call running running yet
            play_sound('incoming-call-sound', event.account, loop=True)

            client = app.get_client(event.account)
            contact = client.get_module('Contacts').get_contact(event.jid)
            assert isinstance(contact, BareContact)
            app.ged.raise_event(
                events.Notification(account=event.account,
                                    jid=event.jid,
                                    type='incoming-call',
                                    title=_('Incoming Call'),
                                    text=_('%s is calling') % contact.name))

    def _on_jingle_connected(self,
                             event: events.JingleConnectedReceived
                             ) -> None:
        client = app.get_client(event.account)
        session = client.get_module('Jingle').get_jingle_session(
            event.fjid, event.sid)
        if session is None:
            return

        if event.media == 'audio':
            self._set_jingle_state(
                'audio',
                JingleState.CONNECTED,
                event.sid)
        if event.media == 'video':
            self._set_jingle_state(
                'video',
                JingleState.CONNECTED,
                event.sid)

        if not session.accepted:
            session.approve_session()
        for content in event.media:
            session.approve_content(content)
        sound.stop()

    def _on_jingle_disconnected(self,
                                event: events.JingleDisconnectedReceived
                                ) -> None:
        if event.media is None:
            self._stop_jingle(
                event.account,
                JID.from_string(event.fjid),
                sid=event.sid,
                reason=event.reason)
        if event.media == 'audio':
            self._set_jingle_state(
                'audio',
                JingleState.NULL,
                sid=event.sid,
                reason=event.reason)
        if event.media == 'video':
            self._set_jingle_state(
                'video',
                JingleState.NULL,
                sid=event.sid,
                reason=event.reason)
        sound.stop()

    def _on_jingle_error(self, event: events.JingleErrorReceived) -> None:
        if event.sid == self._jingle_audio_sid:
            self._set_jingle_state(
                'audio',
                JingleState.ERROR,
                reason=event.reason)
        sound.stop()

    def _set_jingle_state(self,
                          jingle_type: str,
                          state: JingleState,
                          sid: str | None = None,
                          reason: str | None = None
                          ) -> None:
        if state in (
                JingleState.CONNECTING,
                JingleState.CONNECTED,
                JingleState.NULL,
                JingleState.ERROR) and reason:
            log.info('%s state: %s, reason: %s', jingle_type, state, reason)

        if state == JingleState.ERROR:
            return

        if jingle_type == 'audio':
            if state == self._jingle_audio_state:
                return
            if (state == JingleState.NULL and self._jingle_audio_sid not
                    in (None, sid)):
                return
        else:
            if state == self._jingle_video_state:
                return
            if (state == JingleState.NULL and self._jingle_video_sid not
                    in (None, sid)):
                return

        new_sid = None
        if state == JingleState.NULL:
            new_sid = None
        if state in (
                JingleState.CONNECTION_RECEIVED,
                JingleState.CONNECTING,
                JingleState.CONNECTED):
            new_sid = sid

        if jingle_type == 'audio':
            self._jingle_audio_state = state
            self._jingle_audio_sid = new_sid
        else:
            self._jingle_video_state = state
            self._jingle_video_sid = new_sid

        app.ged.raise_event(
            events.CallUpdated(jingle_type=jingle_type,
                               audio_state=self._jingle_audio_state,
                               video_state=self._jingle_video_state,
                               audio_sid=self._jingle_audio_sid,
                               video_sid=self._jingle_video_sid))

        if (self._jingle_audio_state == JingleState.NULL and
                self._jingle_video_state == JingleState.NULL):
            assert self._account is not None
            assert self._resource_jid is not None
            app.ged.raise_event(events.CallStopped(
                self._account,
                JID.from_string(self._resource_jid.bare)))

    def _stop_jingle(self,
                     account: str,
                     full_jid: JID,
                     sid: str | None = None,
                     reason: str | None = None
                     ) -> None:
        if self._jingle_audio_sid and sid in (self._jingle_audio_sid, None):
            self._close_jingle_content(account, full_jid, 'audio')
        if self._jingle_video_sid and sid in (self._jingle_video_sid, None):
            self._close_jingle_content(account, full_jid, 'video')
        if reason is not None:
            log.info('Stopping Jingle: %s', reason)

        self._account = None
        self._resource_jid = None

    def _close_jingle_content(self,
                              account: str,
                              full_jid: JID,
                              jingle_type: str,
                              shutdown: bool | None = False
                              ) -> None:
        if jingle_type == 'audio':
            if self._jingle_audio_sid is None:
                return
        else:
            if self._jingle_video_sid is None:
                return

        client = app.get_client(account)
        if jingle_type == 'audio':
            session = client.get_module('Jingle').get_jingle_session(
                str(full_jid), self._jingle_audio_sid)
        else:
            session = client.get_module('Jingle').get_jingle_session(
                str(full_jid), self._jingle_video_sid)

        if session is not None:
            content = session.get_content(jingle_type)
            if content is not None:
                assert content.creator is not None
                assert content.name is not None
                session.remove_content(content.creator, content.name)

        if not shutdown:
            if jingle_type == 'audio':
                self._jingle_audio_sid = None
                self._jingle_audio_state = JingleState.NULL
            else:
                self._jingle_video_sid = None
                self._jingle_video_state = JingleState.NULL

        app.ged.raise_event(
            events.CallUpdated(jingle_type=jingle_type,
                               audio_state=self._jingle_audio_state,
                               video_state=self._jingle_video_state,
                               audio_sid=self._jingle_audio_sid,
                               video_sid=self._jingle_video_sid))

    def _get_audio_content(self,
                           account: str,
                           jid: JID
                           ) -> JingleAudio | None:
        client = app.get_client(account)
        session = client.get_module('Jingle').get_jingle_session(
            str(jid), self._jingle_audio_sid)
        if session is None:
            return None

        content = session.get_content('audio')
        if content is None:
            return None

        assert isinstance(content, JingleAudio)
        return content

    def start_call(self,
                   account: str,
                   jid: JID,
                   call_type: CallType
                   ) -> None:
        client = app.get_client(account)
        contact = client.get_module('Contacts').get_contact(jid)
        assert isinstance(contact, BareContact)
        call_resources = self._get_call_resources(contact)
        if not call_resources:
            return

        # TODO: Resource priority
        self._account = account
        self._resource_jid = call_resources[0].jid

        if self._jingle_audio_sid is None:
            app.ged.raise_event(
                events.CallStarted(self._account, self._resource_jid))

        if call_type == CallType.VIDEO:
            sid = client.get_module('Jingle').start_audio_video(
                str(self._resource_jid))
            self._set_jingle_state('audio', JingleState.CONNECTING, sid)
            self._set_jingle_state('video', JingleState.CONNECTING, sid)
            self._store_outgoing_call(account, jid, sid)
            return

        if self._jingle_audio_state != JingleState.NULL:
            self._close_jingle_content(account, self._resource_jid, 'audio')
        else:
            sid = client.get_module('Jingle').start_audio(
                str(self._resource_jid))
            self._set_jingle_state('audio', JingleState.CONNECTING, sid)
            self._store_outgoing_call(account, jid, sid)

    def stop_call(self, account: str, contact: types.ResourceContact) -> None:
        self._close_jingle_content(
            account, contact.jid, 'audio', shutdown=True)
        self._close_jingle_content(
            account, contact.jid, 'video', shutdown=True)

        self._account = None
        self._resource_jid = None

    def upgrade_to_video_call(self) -> None:
        assert self._incoming_video_event is not None
        self.accept_call(self._incoming_video_event.jingle_session)
        self._incoming_video_event = None

    def accept_call(self, session: JingleSession) -> None:
        if self._jingle_video_sid is None:
            assert self._account is not None
            assert self._resource_jid is not None
            app.ged.raise_event(
                events.CallStarted(self._account, self._resource_jid))

        sound.stop()

        audio = session.get_content('audio')
        video = session.get_content('video')

        if audio and not audio.negotiated:
            self._set_jingle_state(
                'audio', JingleState.CONNECTING, session.sid)
        if video and not video.negotiated:
            self._set_jingle_state(
                'video', JingleState.CONNECTING, session.sid)

        if not session.accepted:
            session.approve_session()

        if audio is not None:
            session.approve_content('audio')
        if video is not None:
            session.approve_content('video')

    def get_active_call_jid(self) -> JID | None:
        return self._resource_jid

    @staticmethod
    def decline_call(session: JingleSession) -> None:
        sound.stop()

        audio = session.get_content('audio')
        video = session.get_content('video')

        if not session.accepted:
            session.decline_session()
        else:
            if audio is not None:
                session.reject_content('audio')
            if video is not None:
                session.reject_content('video')

    def start_dtmf(self, account: str, jid: JID, key: str) -> None:
        content = self._get_audio_content(account, jid)
        if content is not None:
            content.start_dtmf(key)

    def stop_dtmf(self, account: str, jid: JID) -> None:
        content = self._get_audio_content(account, jid)
        if content is not None:
            content.stop_dtmf()

    def mic_volume_changed(self, account: str, jid: JID, value: int) -> None:
        content = self._get_audio_content(account, jid)
        if content is not None:
            content.set_mic_volume(value / 100)
            app.settings.set('audio_input_volume', value)

    def output_volume_changed(self, account: str, jid: JID, value: int) -> None:
        content = self._get_audio_content(account, jid)
        if content is not None:
            content.set_out_volume(value / 100)
            app.settings.set('audio_output_volume', value)

    @staticmethod
    def _get_call_resources(contact: types.BareContact
                            ) -> list[types.ResourceContact]:
        resource_list: list[types.ResourceContact] = []
        for resource_contact in contact.iter_resources():
            if resource_contact.supports(Namespace.JINGLE_RTP):
                resource_list.append(resource_contact)
        return resource_list

    @staticmethod
    def _store_outgoing_call(account: str, jid: JID, sid: str) -> None:
        additional_data = AdditionalDataDict()
        additional_data.set_value('gajim', 'sid', sid)
        app.storage.archive.insert_into_logs(
            account,
            jid,
            time.time(),
            KindConstant.CALL_OUTGOING,
            additional_data=additional_data)
