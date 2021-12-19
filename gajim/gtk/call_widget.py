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

from __future__ import annotations
from typing import Any
from typing import List
from typing import Optional

import logging
import time

from gi.repository import GObject
from gi.repository import Gdk
from gi.repository import Gtk

from nbxmpp.namespaces import Namespace

from gajim.common import app
from gajim.common import types
from gajim.common.const import JingleState
from gajim.common.const import KindConstant
from gajim.common.helpers import AdditionalDataDict
from gajim.common.i18n import _
from gajim.common.jingle_rtp import JingleAudio
from gajim.common.nec import NetworkEvent

from .gstreamer import create_gtk_widget
from .builder import get_builder

log = logging.getLogger('gajim.gui.call_widget')


class CallWidget(Gtk.Box):

    __gsignals__ = {
        'incoming-call': (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            (object, )
        ),
        'call-ended': (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            ()
        ),
    }

    def __init__(self, account: str, contact: types.BareContact) -> None:
        Gtk.Box.__init__(self)
        self.set_no_show_all(True)

        self._account = account
        self._client = app.get_client(account)
        self._contact = contact

        # Helper for upgrading voice call to voice + video without
        # having to show a new call row
        self._incoming_video_event = None

        self._jingle: dict(str, JingleObject) = {
            'audio': JingleObject(
                JingleState.NULL,
                self._update_audio),
            'video': JingleObject(
                JingleState.NULL,
                self._update_video),
        }
        self._video_widget_other = None
        self._video_widget_self = None

        self._ui = get_builder('call_widget.ui')
        self.add(self._ui.av_box)
        self.connect('destroy', self._on_destroy)

        dtmf: list(str) = [
            '1', '2', '3', '4', '5', '6', '7', '8', '9', '*', '0', '#']
        for key in dtmf:
            button = self._ui.get_object(key + '_button')
            button.connect(
                'button-press-event', self._on_num_button_press, key)
            button.connect('button-release-event', self._on_num_button_release)

        self._ui.connect_signals(self)

    def _on_destroy(self, *args: Any) -> None:
        for jingle_type in ('audio', 'video'):
            self._close_jingle_content(jingle_type, shutdown=True)
        self._jingle.clear()

    def detect_av(self) -> None:
        if (self._contact.supports(Namespace.JINGLE_ICE_UDP) and
                app.is_installed('FARSTREAM')):
            self._jingle['audio'].available = self._contact.supports(
                Namespace.JINGLE_RTP_AUDIO)
            self._jingle['video'].available = self._contact.supports(
                Namespace.JINGLE_RTP_VIDEO)
        else:
            if (self._jingle['audio'].available or
                    self._jingle['video'].available):
                self._stop_jingle()
            self._jingle['audio'].available = False
            self._jingle['video'].available = False

    def get_jingle_available(self, content_type: str) -> bool:
        return self._jingle[content_type].available

    def _on_call_with_mic(self, _button: Gtk.Button) -> None:
        self._on_jingle_button_toggled(['audio'])
        self._ui.av_start_box.hide()

    def _on_call_with_mic_and_cam(self, _button: Gtk.Button) -> None:
        self._on_jingle_button_toggled(['audio', 'video'])
        self._ui.av_start_box.hide()

    def _on_answer_video_clicked(self, button: Gtk.Button) -> None:
        self.accept_call(self._incoming_video_event)
        self._incoming_video_event = None
        button.hide()

    def _on_end_call_clicked(self, _button: Gtk.Button) -> None:
        self._close_jingle_content('audio')
        self._close_jingle_content('video')
        self._ui.jingle_audio_state.set_no_show_all(True)
        self._ui.jingle_audio_state.hide()
        self.set_no_show_all(True)
        self.hide()
        self.emit('call-ended')

    def _on_video(self, _button: Gtk.Button) -> None:
        self._on_jingle_button_toggled(['video'])

    def _on_jingle_button_toggled(self, jingle_types: List[str]) -> None:
        if all(item in jingle_types for item in ['audio', 'video']):
            # Both 'audio' and 'video' in jingle_types
            sid = self._client.get_module('Jingle').start_audio_video(
                self._contact.jid)
            self._set_jingle_state('audio', JingleState.CONNECTING, sid)
            self._set_jingle_state('video', JingleState.CONNECTING, sid)
            self._store_outgoing_call(sid)
            return

        if 'audio' in jingle_types:
            if self._jingle['audio'].state != JingleState.NULL:
                self._close_jingle_content('audio')
            else:
                sid = self._client.get_module('Jingle').start_audio(
                    self._contact.jid)
                self._set_jingle_state('audio', JingleState.CONNECTING, sid)
                self._store_outgoing_call(sid)

        if 'video' in jingle_types:
            if self._jingle['video'].state != JingleState.NULL:
                self._close_jingle_content('video')
            else:
                sid = self._client.get_module('Jingle').start_video(
                    self._contact.jid)
                self._set_jingle_state('video', JingleState.CONNECTING, sid)
                self._store_outgoing_call(sid)

    def _store_outgoing_call(self, sid: str) -> None:
        additional_data = AdditionalDataDict()
        additional_data.set_value('gajim', 'sid', sid)
        app.storage.archive.insert_into_logs(
            self._account,
            self._contact.jid.bare,
            time.time(),
            KindConstant.CALL_OUTGOING,
            additional_data=additional_data)

    def _on_num_button_press(self,
                             _button: Gtk.Button,
                             _event: Gdk.EventButton,
                             num: int
                             ) -> None:
        self._get_audio_content().start_dtmf(num)

    def _on_num_button_release(self,
                               _button: Gtk.Button,
                               _event: Gdk.EventButton
                               ) -> None:
        self._get_audio_content().stop_dtmf()

    def _on_mic_volume_changed(self,
                               _button: Gtk.VolumeButton,
                               value: float
                               ) -> None:
        self._get_audio_content().set_mic_volume(value / 100)
        app.settings.set('audio_input_volume', int(value))

    def _on_output_volume_changed(self,
                                  _button: Gtk.VolumeButton,
                                  value: float
                                  ) -> None:
        self._get_audio_content().set_out_volume(value / 100)
        app.settings.set('audio_output_volume', int(value))

    def process_event(self, event):
        if event.name == 'jingle-request-received':
            self._on_jingle_request(event)
        if event.name == 'jingle-connected-received':
            self._on_jingle_connected(event)
        if event.name == 'jingle-disconnected-received':
            self._on_jingle_disconnected(event)
        if event.name == 'jingle-error':
            self._on_jingle_error(event)

    def _on_jingle_request(self, event):
        content_types: list(str) = []
        for item in event.contents:
            content_types.append(item.media)
        if not any(item in ('audio', 'video') for item in content_types):
            return

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

        if self._jingle['audio'].state in (
                JingleState.CONNECTED,
                JingleState.CONNECTING) and 'video' in content_types:
            self._incoming_video_event = event
        else:
            # There is no voice call running running yet
            self.emit('incoming-call', event)

            app.nec.push_incoming_event(
                NetworkEvent('notification',
                             account=self._account,
                             jid=self._contact.jid,
                             notif_type='incoming-call',
                             title=_('Incoming Call'),
                             text=_('%s is calling') % self._contact.name))

    def _on_jingle_connected(self, event):
        session = self._client.get_module('Jingle').get_jingle_session(
            event.fjid, event.sid)

        if event.media == 'audio':
            content = session.get_content('audio')
            self._set_jingle_state(
                'audio',
                JingleState.CONNECTED,
                event.sid)
        if event.media == 'video':
            content = session.get_content('video')
            self._set_jingle_state(
                'video',
                JingleState.CONNECTED,
                event.sid)

        if not session.accepted:
            session.approve_session()
        for content in event.media:
            session.approve_content(content)

    def _on_jingle_disconnected(self, event):
        if event.media is None:
            self._stop_jingle(sid=event.sid, reason=event.reason)
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

    def _on_jingle_error(self, event):
        if event.sid == self._jingle['audio'].sid:
            self._set_jingle_state(
                'audio',
                JingleState.ERROR,
                reason=event.reason)

    def start_call(self) -> None:
        audio_state = self._jingle['audio'].state
        video_state = self._jingle['video'].state
        if audio_state == JingleState.NULL and video_state == JingleState.NULL:
            self.set_no_show_all(False)
            self.show_all()
            self._ui.jingle_audio_state.hide()
            self._ui.av_start_box.show()
            self._ui.av_start_mic_cam_button.set_sensitive(
                self._jingle['video'].available)
            self._ui.av_cam_button.set_sensitive(False)

    def accept_call(self, session):
        if not session:
            return

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

    @staticmethod
    def decline_call(session):
        if not session:
            return

        audio = session.get_content('audio')
        video = session.get_content('video')

        if not session.accepted:
            session.decline_session()
        else:
            if audio is not None:
                session.reject_content('audio')
            if video is not None:
                session.reject_content('video')

    def _update_audio(self) -> None:
        audio_state = self._jingle['audio'].state
        video_state = self._jingle['video'].state
        if self._jingle['video'].available:
            self._ui.av_cam_button.set_sensitive(
                video_state not in (
                    JingleState.CONNECTING,
                    JingleState.CONNECTED))

        if audio_state == JingleState.NULL:
            self._ui.audio_buttons_box.set_sensitive(False)
            self._ui.jingle_audio_state.set_no_show_all(True)
            self._ui.jingle_audio_state.hide()
            self._ui.jingle_connection_state.set_text('')
            self._ui.jingle_connection_spinner.stop()
            self._ui.jingle_connection_spinner.hide()

            if video_state == JingleState.NULL:
                self.set_no_show_all(True)
                self.hide()
                self.emit('call-ended')
        else:
            self._ui.jingle_connection_spinner.show()
            self._ui.jingle_connection_spinner.start()

        if audio_state == JingleState.CONNECTING:
            self.set_no_show_all(False)
            self.show_all()
            self._ui.jingle_connection_state.set_text(_('Calling…'))
            self._ui.av_cam_button.set_sensitive(False)

        elif audio_state == JingleState.CONNECTION_RECEIVED:
            self._ui.jingle_connection_state.set_text(_('Incoming Call'))

        elif audio_state == JingleState.CONNECTED:
            self._ui.jingle_audio_state.set_no_show_all(False)
            self._ui.jingle_audio_state.show()
            self._ui.jingle_connection_state.set_text('')
            self._ui.jingle_connection_spinner.stop()
            self._ui.jingle_connection_spinner.hide()
            if self._jingle['video'].available:
                self._ui.av_cam_button.set_sensitive(True)

            input_vol = app.settings.get('audio_input_volume')
            output_vol = app.settings.get('audio_output_volume')
            self._ui.mic_hscale.set_value(max(min(input_vol, 100), 0))
            self._ui.sound_hscale.set_value(max(min(output_vol, 100), 0))
            self._ui.audio_buttons_box.set_sensitive(True)

        elif audio_state == JingleState.ERROR:
            self._ui.jingle_audio_state.hide()
            self._ui.jingle_connection_state.set_text(
                _('Connection Error'))
            self._ui.jingle_connection_spinner.stop()
            self._ui.jingle_connection_spinner.hide()

        if not self._jingle['audio'].sid:
            self._ui.audio_buttons_box.set_sensitive(False)

    def _update_video(self) -> None:
        audio_state = self._jingle['audio'].state
        video_state = self._jingle['video'].state

        if video_state == JingleState.NULL:
            self._ui.video_box.set_no_show_all(True)
            self._ui.video_box.hide()
            self._ui.outgoing_viewport.set_no_show_all(True)
            self._ui.outgoing_viewport.hide()
            if self._video_widget_other:
                self._video_widget_other.destroy()
            if self._video_widget_self:
                self._video_widget_self.destroy()

            if audio_state != JingleState.CONNECTED:
                self._ui.jingle_connection_state.set_text('')
            self._ui.jingle_connection_spinner.stop()
            self._ui.jingle_connection_spinner.hide()
            self._ui.av_cam_button.set_sensitive(True)
            self._ui.av_cam_button.set_tooltip_text(_('Turn Camera on'))
            self._ui.av_cam_image.set_from_icon_name(
                'feather-camera-symbolic', Gtk.IconSize.BUTTON)
            if audio_state == JingleState.NULL:
                self.set_no_show_all(True)
                self.hide()
                self.emit('call-ended')
        else:
            self._ui.jingle_connection_spinner.show()
            self._ui.jingle_connection_spinner.start()

        if video_state == JingleState.CONNECTING:
            self._ui.jingle_connection_state.set_text(_('Calling (Video)…'))
            self.set_no_show_all(False)
            self.show_all()
            self._ui.av_cam_button.set_sensitive(False)
            self._ui.av_cam_button.set_tooltip_text(_('Turn Camera off'))
            self._ui.av_cam_image.set_from_icon_name(
                'feather-camera-off-symbolic', Gtk.IconSize.BUTTON)

        elif video_state == JingleState.CONNECTION_RECEIVED:
            self._ui.jingle_connection_state.set_text(
                _('Incoming Call (Video)'))
            self._ui.answer_video_button.show()
            self._ui.av_cam_button.set_sensitive(False)
            self._ui.av_cam_button.set_tooltip_text(_('Turn Camera off'))
            self._ui.av_cam_image.set_from_icon_name(
                'feather-camera-off-symbolic', Gtk.IconSize.BUTTON)

        elif video_state == JingleState.CONNECTED:
            self._ui.video_box.set_no_show_all(False)
            self._ui.video_box.show_all()
            self._ui.answer_video_button.hide()
            if app.settings.get('video_see_self'):
                self._ui.outgoing_viewport.set_no_show_all(False)
                self._ui.outgoing_viewport.show()
            else:
                self._ui.outgoing_viewport.set_no_show_all(True)
                self._ui.outgoing_viewport.hide()

            sink_other, self._video_widget_other, _name = create_gtk_widget()
            sink_self, self._video_widget_self, _name = create_gtk_widget()
            self._ui.incoming_viewport.add(self._video_widget_other)
            self._ui.outgoing_viewport.add(self._video_widget_self)

            session = self._client.get_module('Jingle').get_jingle_session(
                self._contact.jid, self._jingle['video'].sid)
            content = session.get_content('video')
            content.do_setup(sink_self, sink_other)

            self._ui.jingle_connection_state.set_text('')
            self._ui.jingle_connection_spinner.stop()
            self._ui.jingle_connection_spinner.hide()

            self._ui.av_cam_button.set_sensitive(True)
            self._ui.av_cam_button.set_tooltip_text(_('Turn Camera off'))
            self._ui.av_cam_image.set_from_icon_name(
                'feather-camera-off-symbolic', Gtk.IconSize.BUTTON)

        elif video_state == JingleState.ERROR:
            self._ui.jingle_connection_state.set_text(
                _('Connection Error'))
            self._ui.jingle_connection_spinner.stop()
            self._ui.jingle_connection_spinner.hide()

    def _set_jingle_state(self, jingle_type: str, state: str, sid: str = None,
                          reason: str = None) -> None:
        jingle = self._jingle[jingle_type]
        if state in (
                JingleState.CONNECTING,
                JingleState.CONNECTED,
                JingleState.NULL,
                JingleState.ERROR) and reason:
            log.info('%s state: %s, reason: %s', jingle_type, state, reason)

        if state in (jingle.state, JingleState.ERROR):
            return

        if (state == JingleState.NULL and jingle.sid not in (None, sid)):
            return

        new_sid = None
        if state == JingleState.NULL:
            new_sid = None
        if state in (
                JingleState.CONNECTION_RECEIVED,
                JingleState.CONNECTING,
                JingleState.CONNECTED):
            new_sid = sid

        jingle.state = state
        jingle.sid = new_sid
        jingle.update()

    def _stop_jingle(self,
                     sid: Optional[str] = None,
                     reason: Optional[str] = None
                     ) -> None:
        audio_sid = self._jingle['audio'].sid
        video_sid = self._jingle['video'].sid
        if audio_sid and sid in (audio_sid, None):
            self._close_jingle_content('audio')
        if video_sid and sid in (video_sid, None):
            self._close_jingle_content('video')

    def _close_jingle_content(self,
                              jingle_type: str,
                              shutdown: Optional[bool] = False
                              ) -> None:
        jingle = self._jingle[jingle_type]
        if not jingle.sid:
            return

        session = self._client.get_module('Jingle').get_jingle_session(
            self._contact.jid, jingle.sid)
        if session:
            content = session.get_content(jingle_type)
            if content:
                session.remove_content(content.creator, content.name)

        if not shutdown:
            jingle.sid = None
            jingle.state = JingleState.NULL
            jingle.update()

    def _get_audio_content(self) -> Optional[JingleAudio]:
        session = self._client.get_module('Jingle').get_jingle_session(
            self._contact.jid, self._jingle['audio'].sid)
        return session.get_content('audio')


class JingleObject:
    __slots__ = ('sid', 'state', 'available', 'update')

    def __init__(self, state, update):
        self.sid = None
        self.state = state
        self.available = False
        self.update = update
