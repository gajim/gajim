# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common import ged
from gajim.common.const import AvatarSize
from gajim.common.const import CallType
from gajim.common.const import JingleState
from gajim.common.events import CallUpdated
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.jingle_rtp import JingleVideo
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import ResourceContact

from gajim.gtk.builder import get_builder
from gajim.gtk.gstreamer import create_gtk_widget
from gajim.gtk.widgets import GajimAppWindow

log = logging.getLogger("gajim.gtk.call_window")


class CallWindow(GajimAppWindow, EventHelper):
    def __init__(self, account: str, resource_jid: JID) -> None:
        GajimAppWindow.__init__(
            self,
            name="CallWindow",
            default_width=700,
            default_height=600,
        )

        EventHelper.__init__(self)

        self._account = account
        self._client = app.get_client(account)

        contacts_module = self._client.get_module("Contacts")
        self._contact = contacts_module.get_contact(resource_jid.bare)
        assert isinstance(self._contact, BareContact)
        self._resource_contact = contacts_module.get_contact(resource_jid)
        assert isinstance(self._resource_contact, ResourceContact)
        self.window.set_title(_("Call with %s") % self._contact.name)

        self._video_widget_other = None
        self._video_widget_self = None

        self._ui = get_builder("call_window.ui")
        self.set_child(self._ui.av_box)

        buttons = [
            self._ui.button_0,
            self._ui.button_1,
            self._ui.button_2,
            self._ui.button_3,
            self._ui.button_3,
            self._ui.button_4,
            self._ui.button_5,
            self._ui.button_6,
            self._ui.button_7,
            self._ui.button_8,
            self._ui.button_9,
            self._ui.button_star,
            self._ui.button_pound,
        ]
        for button in buttons:
            gesture_primary_click = Gtk.GestureClick(
                button=Gdk.BUTTON_PRIMARY,
                propagation_phase=Gtk.PropagationPhase.CAPTURE,
            )
            self._connect(gesture_primary_click, "pressed", self._on_button_press)
            self._connect(gesture_primary_click, "released", self._on_button_release)
            button.add_controller(gesture_primary_click)

        self._connect(
            self._ui.answer_video_button, "clicked", self._on_upgrade_to_video_clicked
        )
        self._connect(self._ui.av_cam_button, "clicked", self._on_enable_video_clicked)
        self._connect(self._ui.end_call_button, "clicked", self._on_end_call_clicked)
        self._connect(self._ui.mic_hscale, "value-changed", self._on_mic_volume_changed)
        self._connect(
            self._ui.sound_hscale, "value-changed", self._on_output_volume_changed
        )

        self._ui.avatar_image.set_pixel_size(AvatarSize.CALL_BIG)
        self._ui.avatar_image.set_from_paintable(
            self._contact.get_avatar(
                AvatarSize.CALL_BIG, self.get_scale_factor(), add_show=False
            )
        )

        self.register_events(
            [
                ("call-updated", ged.GUI2, self._on_call_updated),
            ]
        )

    def _cleanup(self) -> None:
        assert isinstance(self._resource_contact, ResourceContact)
        app.call_manager.stop_call(self._account, self._resource_contact)

        self.unregister_events()
        app.check_finalize(self)

    def _close_with_timeout(self, timeout: int = 3) -> None:
        self._ui.av_box.set_sensitive(False)
        GLib.timeout_add_seconds(timeout, self.close)

    def _on_upgrade_to_video_clicked(self, button: Gtk.Button) -> None:
        app.call_manager.upgrade_to_video_call()
        button.hide()

    def _on_end_call_clicked(self, button: Gtk.Button) -> None:
        button.set_sensitive(False)
        assert isinstance(self._resource_contact, ResourceContact)
        app.call_manager.stop_call(self._account, self._resource_contact)
        self._close_with_timeout(timeout=1)

    def _on_enable_video_clicked(self, _button: Gtk.Button) -> None:
        app.call_manager.start_call(self._account, self._contact.jid, CallType.VIDEO)

    def _on_button_press(
        self,
        gesture_click: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
    ) -> None:
        button = gesture_click.get_widget()
        if button is None:
            return

        key = button.get_name()
        app.call_manager.start_dtmf(self._account, self._resource_contact.jid, key)

    def _on_button_release(
        self,
        gesture_click: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
    ) -> None:
        app.call_manager.stop_dtmf(self._account, self._resource_contact.jid)

    def _on_mic_volume_changed(self, _button: Gtk.VolumeButton, value: float) -> None:
        app.call_manager.mic_volume_changed(
            self._account, self._resource_contact.jid, int(value)
        )

    def _on_output_volume_changed(
        self, _button: Gtk.VolumeButton, value: float
    ) -> None:
        app.call_manager.output_volume_changed(
            self._account, self._resource_contact.jid, int(value)
        )

    def _on_call_updated(self, event: CallUpdated) -> None:
        if event.jingle_type == "audio":
            self._update_audio(event)
        else:
            self._update_video(event)

    def _update_audio(self, event: CallUpdated) -> None:
        assert isinstance(self._contact, BareContact)
        if self._contact.supports_video:
            self._ui.av_cam_button.set_sensitive(
                event.video_state not in (JingleState.CONNECTING, JingleState.CONNECTED)
            )

        if event.audio_state == JingleState.NULL:
            self._ui.audio_buttons_box.set_sensitive(False)
            self._ui.jingle_audio_state.set_visible(False)
            self._ui.jingle_audio_state.hide()
            self._ui.jingle_connection_state.set_text("")
            self._ui.jingle_connection_spinner.stop()
            self._ui.jingle_connection_spinner.hide()

            if event.video_state == JingleState.NULL:
                self._ui.jingle_connection_state.set_text(_("Call ended"))
                self._close_with_timeout()
        else:
            self._ui.jingle_connection_spinner.show()
            self._ui.jingle_connection_spinner.start()

        if event.audio_state == JingleState.CONNECTING:
            self._ui.jingle_connection_state.set_text(_("Calling…"))
            self._ui.av_cam_button.set_sensitive(False)

        elif event.audio_state == JingleState.CONNECTION_RECEIVED:
            self._ui.jingle_connection_state.set_text(_("Incoming Call"))

        elif event.audio_state == JingleState.CONNECTED:
            self._ui.jingle_audio_state.show()
            self._ui.jingle_connection_state.set_text("")
            self._ui.jingle_connection_spinner.stop()
            self._ui.jingle_connection_spinner.hide()
            if self._contact.supports_video:
                self._ui.av_cam_button.set_sensitive(True)

            input_vol = app.settings.get("audio_input_volume")
            output_vol = app.settings.get("audio_output_volume")
            self._ui.mic_hscale.set_value(max(min(input_vol, 100), 0))
            self._ui.sound_hscale.set_value(max(min(output_vol, 100), 0))
            self._ui.audio_buttons_box.set_sensitive(True)

        elif event.audio_state == JingleState.ERROR:
            self._ui.jingle_audio_state.hide()
            self._ui.jingle_connection_state.set_text(_("Connection Error"))
            self._ui.jingle_connection_spinner.stop()
            self._ui.jingle_connection_spinner.hide()

        if not event.audio_sid:
            self._ui.audio_buttons_box.set_sensitive(False)

    def _update_video(self, event: CallUpdated) -> None:
        if event.video_state == JingleState.NULL:
            self._ui.avatar_image.show()
            self._ui.video_box.set_visible(False)
            self._ui.video_box.hide()
            self._ui.outgoing_viewport.set_visible(False)
            self._ui.outgoing_viewport.hide()

            if self._video_widget_other:
                self._ui.incoming_viewport.set_child(None)
                self._video_widget_other = None

            if self._video_widget_self:
                self._ui.outgoing_viewport.set_child(None)
                self._video_widget_self = None

            if event.audio_state != JingleState.CONNECTED:
                self._ui.jingle_connection_state.set_text("")
            self._ui.jingle_connection_spinner.stop()
            self._ui.jingle_connection_spinner.hide()
            self._ui.av_cam_button.set_sensitive(True)
            self._ui.av_cam_button.set_tooltip_text(_("Turn Camera on"))
            self._ui.av_cam_image.set_from_icon_name("feather-camera-symbolic")
            if event.audio_state == JingleState.NULL:
                self._ui.jingle_connection_state.set_text(_("Call ended"))
                self._close_with_timeout()
        else:
            self._ui.jingle_connection_spinner.show()
            self._ui.jingle_connection_spinner.start()

        if event.video_state == JingleState.CONNECTING:
            self._ui.jingle_connection_state.set_text(_("Calling (Video)…"))
            self._ui.av_cam_button.set_sensitive(False)
            self._ui.av_cam_button.set_tooltip_text(_("Turn Camera off"))
            self._ui.av_cam_image.set_from_icon_name("feather-camera-off-symbolic")

        elif event.video_state == JingleState.CONNECTION_RECEIVED:
            self._ui.jingle_connection_state.set_text(_("Incoming Call (Video)"))
            self._ui.answer_video_button.show()
            self._ui.av_cam_button.set_sensitive(False)
            self._ui.av_cam_button.set_tooltip_text(_("Turn Camera off"))
            self._ui.av_cam_image.set_from_icon_name("feather-camera-off-symbolic")

        elif event.video_state == JingleState.CONNECTED:
            self._ui.avatar_image.hide()
            self._ui.answer_video_button.hide()
            if app.settings.get("video_see_self"):
                self._ui.outgoing_viewport.show()
            else:
                self._ui.outgoing_viewport.set_visible(False)
                self._ui.outgoing_viewport.hide()

            other_gtk_widget = create_gtk_widget()
            self_gtk_widget = create_gtk_widget()
            if other_gtk_widget is None or self_gtk_widget is None:
                log.warning("Could not create GStreamer widgets")
                return

            sink_other, self._video_widget_other, _name = other_gtk_widget
            sink_self, self._video_widget_self, _name = self_gtk_widget
            self._ui.incoming_viewport.set_child(self._video_widget_other)
            self._ui.outgoing_viewport.set_child(self._video_widget_self)

            session = self._client.get_module("Jingle").get_jingle_session(
                str(self._resource_contact.jid), event.video_sid
            )
            assert session is not None
            content = session.get_content("video")
            assert isinstance(content, JingleVideo)
            content.do_setup(sink_self, sink_other)

            self._ui.jingle_connection_state.set_text("")
            self._ui.jingle_connection_spinner.stop()
            self._ui.jingle_connection_spinner.hide()

            self._ui.av_cam_button.set_sensitive(True)
            self._ui.av_cam_button.set_tooltip_text(_("Turn Camera off"))
            self._ui.av_cam_image.set_from_icon_name("feather-camera-off-symbolic")

        elif event.video_state == JingleState.ERROR:
            self._ui.jingle_connection_state.set_text(_("Connection Error"))
            self._ui.jingle_connection_spinner.stop()
            self._ui.jingle_connection_spinner.hide()
