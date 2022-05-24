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

import logging

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk

from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common import ged
from gajim.common.ged import EventHelper
from gajim.common.const import AvatarSize
from gajim.common.const import CallType
from gajim.common.const import JingleState
from gajim.common.events import CallUpdated
from gajim.common.i18n import _

from .builder import get_builder
from .gstreamer import create_gtk_widget

log = logging.getLogger('gajim.gui.call_window')


class CallWindow(Gtk.ApplicationWindow, EventHelper):
    def __init__(self, account: str, resource_jid: JID) -> None:
        Gtk.ApplicationWindow.__init__(self)
        EventHelper.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_resizable(True)
        self.set_default_size(700, 600)
        self.set_name('CallWindow')

        self._account = account
        self._client = app.get_client(account)

        contacts_module = self._client.get_module('Contacts')
        self._contact = contacts_module.get_contact(resource_jid.bare)
        self._resource_contact = contacts_module.get_contact(resource_jid)
        self.set_title(_('Call with %s') % self._contact.name)

        self._video_widget_other = None
        self._video_widget_self = None

        self._ui = get_builder('call_window.ui')
        self.add(self._ui.av_box)

        self._ui.avatar_image.set_from_surface(
            self._contact.get_avatar(AvatarSize.CALL_BIG,
                                     self.get_scale_factor(),
                                     add_show=False))

        self.connect('destroy', self._on_destroy)
        self._ui.connect_signals(self)
        self.show_all()

        self.register_events([
            ('call-updated', ged.GUI2, self._on_call_updated),
        ])

    def _on_destroy(self, *args: Any) -> None:
        app.call_manager.stop_call(
            self._account,
            self._resource_contact)

        self.unregister_events()
        self._ui.dtmf_popover.destroy()
        app.check_finalize(self)

    def _close_with_timeout(self, timeout: int = 3) -> None:
        self._ui.av_box.set_sensitive(False)
        GLib.timeout_add_seconds(timeout, self.destroy)

    def _on_upgrade_to_video_clicked(self, button: Gtk.Button) -> None:
        app.call_manager.upgrade_to_video_call()
        button.hide()

    def _on_end_call_clicked(self, button: Gtk.Button) -> None:
        button.set_sensitive(False)
        app.call_manager.stop_call(
            self._account,
            self._resource_contact)
        self._close_with_timeout(timeout=1)

    def _on_enable_video_clicked(self, _button: Gtk.Button) -> None:
        app.call_manager.start_call(
            self._account, self._contact.jid, CallType.VIDEO)

    def _on_num_button_press(self,
                             button: Gtk.Button,
                             _event: Gdk.EventButton
                             ) -> None:
        button_id = Gtk.Buildable.get_name(button)
        key = button_id.split('_')[1]
        app.call_manager.start_dtmf(
            self._account, self._resource_contact.jid, key)

    def _on_num_button_release(self,
                               _button: Gtk.Button,
                               _event: Gdk.EventButton
                               ) -> None:
        app.call_manager.stop_dtmf(
            self._account, self._resource_contact.jid)

    def _on_mic_volume_changed(self,
                               _button: Gtk.VolumeButton,
                               value: float
                               ) -> None:
        app.call_manager.mic_volume_changed(
            self._account, self._resource_contact.jid, int(value))

    def _on_output_volume_changed(self,
                                  _button: Gtk.VolumeButton,
                                  value: float
                                  ) -> None:
        app.call_manager.output_volume_changed(
            self._account, self._resource_contact.jid, int(value))

    def _on_call_updated(self, event: CallUpdated) -> None:
        if event.jingle_type == 'audio':
            self._update_audio(event)
        else:
            self._update_video(event)

    def _update_audio(self, event: CallUpdated) -> None:
        if self._contact.supports_video:
            self._ui.av_cam_button.set_sensitive(
                event.video_state not in (
                    JingleState.CONNECTING,
                    JingleState.CONNECTED))

        if event.audio_state == JingleState.NULL:
            self._ui.audio_buttons_box.set_sensitive(False)
            self._ui.jingle_audio_state.set_no_show_all(True)
            self._ui.jingle_audio_state.hide()
            self._ui.jingle_connection_state.set_text('')
            self._ui.jingle_connection_spinner.stop()
            self._ui.jingle_connection_spinner.hide()

            if event.video_state == JingleState.NULL:
                self._ui.jingle_connection_state.set_text(_('Call ended'))
                self._close_with_timeout()
        else:
            self._ui.jingle_connection_spinner.show()
            self._ui.jingle_connection_spinner.start()

        if event.audio_state == JingleState.CONNECTING:
            self._ui.jingle_connection_state.set_text(_('Calling…'))
            self._ui.av_cam_button.set_sensitive(False)

        elif event.audio_state == JingleState.CONNECTION_RECEIVED:
            self._ui.jingle_connection_state.set_text(_('Incoming Call'))

        elif event.audio_state == JingleState.CONNECTED:
            self._ui.jingle_audio_state.set_no_show_all(False)
            self._ui.jingle_audio_state.show()
            self._ui.jingle_connection_state.set_text('')
            self._ui.jingle_connection_spinner.stop()
            self._ui.jingle_connection_spinner.hide()
            if self._contact.supports_video:
                self._ui.av_cam_button.set_sensitive(True)

            input_vol = app.settings.get('audio_input_volume')
            output_vol = app.settings.get('audio_output_volume')
            self._ui.mic_hscale.set_value(max(min(input_vol, 100), 0))
            self._ui.sound_hscale.set_value(max(min(output_vol, 100), 0))
            self._ui.audio_buttons_box.set_sensitive(True)

        elif event.audio_state == JingleState.ERROR:
            self._ui.jingle_audio_state.hide()
            self._ui.jingle_connection_state.set_text(
                _('Connection Error'))
            self._ui.jingle_connection_spinner.stop()
            self._ui.jingle_connection_spinner.hide()

        if not event.audio_sid:
            self._ui.audio_buttons_box.set_sensitive(False)

    def _update_video(self, event: CallUpdated) -> None:
        if event.video_state == JingleState.NULL:
            self._ui.avatar_image.show()
            self._ui.video_box.set_no_show_all(True)
            self._ui.video_box.hide()
            self._ui.outgoing_viewport.set_no_show_all(True)
            self._ui.outgoing_viewport.hide()
            if self._video_widget_other:
                self._video_widget_other.destroy()
            if self._video_widget_self:
                self._video_widget_self.destroy()

            if event.audio_state != JingleState.CONNECTED:
                self._ui.jingle_connection_state.set_text('')
            self._ui.jingle_connection_spinner.stop()
            self._ui.jingle_connection_spinner.hide()
            self._ui.av_cam_button.set_sensitive(True)
            self._ui.av_cam_button.set_tooltip_text(_('Turn Camera on'))
            self._ui.av_cam_image.set_from_icon_name(
                'feather-camera-symbolic', Gtk.IconSize.BUTTON)
            if event.audio_state == JingleState.NULL:
                self._ui.jingle_connection_state.set_text(_('Call ended'))
                self._close_with_timeout()
        else:
            self._ui.jingle_connection_spinner.show()
            self._ui.jingle_connection_spinner.start()

        if event.video_state == JingleState.CONNECTING:
            self._ui.jingle_connection_state.set_text(_('Calling (Video)…'))
            self._ui.av_cam_button.set_sensitive(False)
            self._ui.av_cam_button.set_tooltip_text(_('Turn Camera off'))
            self._ui.av_cam_image.set_from_icon_name(
                'feather-camera-off-symbolic', Gtk.IconSize.BUTTON)

        elif event.video_state == JingleState.CONNECTION_RECEIVED:
            self._ui.jingle_connection_state.set_text(
                _('Incoming Call (Video)'))
            self._ui.answer_video_button.show()
            self._ui.av_cam_button.set_sensitive(False)
            self._ui.av_cam_button.set_tooltip_text(_('Turn Camera off'))
            self._ui.av_cam_image.set_from_icon_name(
                'feather-camera-off-symbolic', Gtk.IconSize.BUTTON)

        elif event.video_state == JingleState.CONNECTED:
            self._ui.avatar_image.hide()
            self._ui.video_box.set_no_show_all(False)
            self._ui.video_box.show_all()
            self._ui.answer_video_button.hide()
            if app.settings.get('video_see_self'):
                self._ui.outgoing_viewport.set_no_show_all(False)
                self._ui.outgoing_viewport.show()
            else:
                self._ui.outgoing_viewport.set_no_show_all(True)
                self._ui.outgoing_viewport.hide()

            other_gtk_widget = create_gtk_widget()
            self_gtk_widget = create_gtk_widget()
            if other_gtk_widget is None or self_gtk_widget is None:
                log.warning('Could not create GStreamer widgets')
                return

            sink_other, self._video_widget_other, _name = other_gtk_widget
            sink_self, self._video_widget_self, _name = self_gtk_widget
            self._ui.incoming_viewport.add(self._video_widget_other)
            self._ui.outgoing_viewport.add(self._video_widget_self)

            session = self._client.get_module('Jingle').get_jingle_session(
                str(self._resource_contact.jid), event.video_sid)
            content = session.get_content('video')
            content.do_setup(sink_self, sink_other)

            self._ui.jingle_connection_state.set_text('')
            self._ui.jingle_connection_spinner.stop()
            self._ui.jingle_connection_spinner.hide()

            self._ui.av_cam_button.set_sensitive(True)
            self._ui.av_cam_button.set_tooltip_text(_('Turn Camera off'))
            self._ui.av_cam_image.set_from_icon_name(
                'feather-camera-off-symbolic', Gtk.IconSize.BUTTON)

        elif event.video_state == JingleState.ERROR:
            self._ui.jingle_connection_state.set_text(
                _('Connection Error'))
            self._ui.jingle_connection_spinner.stop()
            self._ui.jingle_connection_spinner.hide()
