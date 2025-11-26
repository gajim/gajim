# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import Any
from typing import cast

import hashlib
import logging
from urllib.parse import urlparse

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common import configpaths
from gajim.common.const import ALL_MIME_TYPES
from gajim.common.enum import FTState
from gajim.common.enum import PreviewState
from gajim.common.file_transfer_manager import FileTransfer
from gajim.common.helpers import determine_proxy
from gajim.common.i18n import _
from gajim.common.multiprocess.http import CancelledError
from gajim.common.multiprocess.http import ContentTypeNotAllowed
from gajim.common.multiprocess.http import HTTPStatusError
from gajim.common.multiprocess.http import MaxContentLengthExceeded
from gajim.common.util.preview import contains_audio_streams
from gajim.common.util.preview import get_icon_for_mime_type
from gajim.common.util.preview import get_image_paths
from gajim.common.util.preview import get_size_and_mime_type
from gajim.common.util.preview import is_audio
from gajim.common.util.preview import is_image
from gajim.common.util.preview import is_video
from gajim.common.util.preview import UrlPreview

from gajim.gtk.menus import get_preview_menu
from gajim.gtk.preview.audio import AudioPreviewWidget
from gajim.gtk.preview.file_control_buttons import FileControlButtons
from gajim.gtk.preview.image import ImagePreviewWidget
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import get_ui_string
from gajim.gtk.widgets import GajimPopover

log = logging.getLogger("gajim.gtk.preview")


@Gtk.Template.from_string(string=get_ui_string("preview/preview.ui"))
class PreviewWidget(Gtk.Box, SignalManager):
    """Process Diagram

    flowchart TD

    %% Nodes
        A[Start]
        B{File Available}
        C[Downloading]
        D{Error?}
        E{Download Error?}
        F[Offer Download]
        G[Error]
        H[Downloaded]
        I{Previewable?}
        K[Display]
        L[Do Nothing]

    %% Defining the styles
        classDef Green fill:#50C878;

    %% Assigning styles to nodes
        class C,F,G,H,J,K Green;

    %% Links
        A --> B
        B -->|No| C
        B -->|Yes| H
        C --> D
        D --> |Yes| E
        E --> |No| F
        E --> |Yes| G
        F --> C
        D --> |No| H
        H --> I
        I --> |No| L
        I --> |Yes| K
    """

    __gtype_name__ = "PreviewWidget"

    _stack: Gtk.Stack = Gtk.Template.Child()
    _icon_button: Gtk.Button = Gtk.Template.Child()
    _mime_image: Gtk.Image = Gtk.Template.Child()
    _right_box: Gtk.Box = Gtk.Template.Child()
    _progress_box: Gtk.Box = Gtk.Template.Child()
    _progressbar: Gtk.ProgressBar = Gtk.Template.Child()
    _progress_text: Gtk.Label = Gtk.Template.Child()
    _cancel_download_button: Gtk.Button = Gtk.Template.Child()
    _content_box: Gtk.Box = Gtk.Template.Child()
    _link_button: Gtk.LinkButton = Gtk.Template.Child()
    _info_message_label: Gtk.Label = Gtk.Template.Child()
    _file_control_buttons: FileControlButtons = Gtk.Template.Child()
    _download_button: Gtk.Button = Gtk.Template.Child()

    def __init__(
        self, account: str, preview: UrlPreview, from_us: bool, context: str | None
    ) -> None:
        Gtk.Box.__init__(self)
        SignalManager.__init__(self)

        self._account = account
        self._from_us = from_us
        self._uri = preview.uri
        self._file_size = 0
        self._preview_id = hashlib.sha256(self._uri.encode()).hexdigest()
        self._preview_id_short = self._preview_id[:10]
        self._info_message = None
        self._http_obj = None
        self._state = PreviewState.INIT

        self._connect(
            self._cancel_download_button, "clicked", self._on_cancel_download_clicked
        )
        self._connect(self._download_button, "clicked", self._on_download_clicked)
        self._connect(self._icon_button, "clicked", self._on_icon_clicked)

        pointer_cursor = Gdk.Cursor.new_from_name("pointer")
        self._icon_button.set_cursor(pointer_cursor)
        self._cancel_download_button.set_cursor(pointer_cursor)
        self._download_button.set_cursor(pointer_cursor)

        self._menu_popover = GajimPopover(None)
        self.append(self._menu_popover)

        gesture_secondary_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        self._connect(gesture_secondary_click, "pressed", self._on_preview_clicked)
        self.add_controller(gesture_secondary_click)

        # Set initial file attributes, guessed based on the uri
        self._filename = preview.file_name
        self._mime_type = preview.mime_type

        self._file_control_buttons.set_file_name(self._filename)
        self._mime_image.set_from_gicon(get_icon_for_mime_type(self._mime_type))

        self._orig_dir = configpaths.get("DOWNLOADS")
        self._thumb_dir = configpaths.get("DOWNLOADS_THUMB")

        self._urlparts = urlparse(self._uri)
        thumbnail_size = app.settings.get("preview_size")

        self._orig_path, self._thumb_path = get_image_paths(
            self._uri, self._urlparts, thumbnail_size, self._orig_dir, self._thumb_dir
        )

        self._link_button.set_uri(self._uri)
        self._link_button.set_tooltip_text(self._uri)
        self._link_button.set_label(self._uri)
        label = cast(Gtk.Label, self._link_button.get_child())
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_max_width_chars(32)

        if ftobj := app.ftm.get_transfer(self._preview_id):
            log.info(
                "Bind to existing transfer: %s %s", self._preview_id_short, self._uri
            )
            self._connect_to_ftobj(ftobj)
            return

        if self._orig_path.exists():
            self._mime_type, self._file_size = get_size_and_mime_type(self._orig_path)
            self._set_widget_state(PreviewState.DOWNLOADED)
            self._set_widget_state(PreviewState.DISPLAY)
            return

        max_content_length = app.settings.get("preview_max_file_size")
        if max_content_length > 0 and self._should_auto_preview(context):
            self._download_content(max_content_length, ALL_MIME_TYPES)

        else:
            self._info_message = _("Automatic preview disabled")
            self._set_widget_state(PreviewState.OFFER_DOWNLOAD)

    def do_unroot(self) -> None:
        self._disconnect_all()
        del self._menu_popover
        del self._http_obj
        Gtk.Box.do_unroot(self)
        app.check_finalize(self)

    def get_text(self) -> str:
        return self._uri

    def _should_auto_preview(self, context: str | None) -> bool:
        if self._from_us:
            return True

        return context != "public" or app.settings.get("preview_anonymous_muc")

    def _reset_progress(self) -> None:
        self._progress_text.set_label("0 %")
        self._progressbar.set_fraction(0)

    def _set_display_widget(self, widget: Gtk.Widget) -> None:
        self._stack.add_named(widget, "widget")
        self._stack.set_visible_child_name("widget")

    def _set_widget_state(self, state: PreviewState) -> None:
        log.info("Set widget state %s %s", self._preview_id_short, state.name)
        self._state = state

        # Handle PreviewState.DISPLAY state first, so if no fitting widget is found
        # all other widget states remain as in PreviewState.DOWNLOADED
        if state == PreviewState.DISPLAY:

            widget = None
            if is_image(self._mime_type) or is_video(self._mime_type):
                assert self._mime_type is not None
                widget = ImagePreviewWidget(
                    self._filename,
                    self._file_size,
                    self._mime_type,
                    self._orig_path,
                    self._thumb_path,
                )

            elif is_audio(self._mime_type):
                if (
                    app.audio_player is not None
                    and app.is_installed("GST")
                    and contains_audio_streams(self._orig_path)
                ):
                    widget = AudioPreviewWidget(
                        self._filename, self._file_size, self._orig_path
                    )

            if widget is not None:
                self._connect(widget, "display-error", self._on_display_error)
                self._set_display_widget(widget)

            return

        self._download_button.set_visible(state == PreviewState.OFFER_DOWNLOAD)
        self._download_button.set_sensitive(state == PreviewState.OFFER_DOWNLOAD)

        self._file_control_buttons.set_file_name(self._filename)
        self._file_control_buttons.set_file_size(self._file_size)

        self._cancel_download_button.set_visible(state == PreviewState.DOWNLOADING)
        self._cancel_download_button.set_sensitive(state == PreviewState.DOWNLOADING)

        self._progress_box.set_visible(state == PreviewState.DOWNLOADING)

        self._mime_image.set_from_gicon(get_icon_for_mime_type(self._mime_type))
        self._link_button.set_visible(state == PreviewState.ERROR)

        self._info_message_label.set_text(self._info_message or "")
        self._info_message_label.set_tooltip_text(self._info_message or "")
        self._info_message_label.set_visible(self._info_message is not None)

        if state == PreviewState.DOWNLOADING:
            self._reset_progress()

        elif state == PreviewState.DOWNLOADED:
            self._file_control_buttons.set_path(self._orig_path)

    def _on_display_error(self, _widget: Any) -> None:
        self._stack.set_visible_child_name("preview")

    def _on_download_clicked(self, button: Gtk.Button) -> None:
        button.set_sensitive(False)
        self._download_content()

    def _on_icon_clicked(self, button: Gtk.Button) -> None:
        if self._state == PreviewState.OFFER_DOWNLOAD:
            self._download_button.emit("clicked")

        elif self._state == PreviewState.DISPLAY:
            app.app.activate_action(
                "open-file", GLib.Variant("s", str(self._orig_path))
            )

    def _on_cancel_download_clicked(self, button: Gtk.Button) -> None:
        button.set_sensitive(False)
        assert self._http_obj is not None
        self._http_obj.cancel()

    def _on_preview_clicked(
        self,
        _gesture_click: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
    ) -> None:

        encrypted = self._uri.startswith("aesgcm://")
        menu = get_preview_menu(self._uri, encrypted=encrypted)
        self._menu_popover.set_menu_model(menu)
        self._menu_popover.set_pointing_to_coord(x, y)
        self._menu_popover.popup()

    def _download_content(
        self,
        max_content_length: int = -1,
        allowed_content_types: set[str] | None = None,
    ) -> None:

        log.info("Start downloading: %s %s", self._preview_id_short, self._uri)

        obj = app.ftm.http_request(
            "GET",
            self._uri,
            self._preview_id,
            output=self._orig_path,
            with_progress=True,
            max_content_length=max_content_length,
            allowed_content_types=allowed_content_types,
            proxy=determine_proxy(self._account),
        )

        if obj is None:
            return

        self._connect_to_ftobj(obj)

    def _connect_to_ftobj(self, obj: FileTransfer) -> None:
        self._connect(obj, "finished", self._on_download_finished)
        self._connect(obj, "notify::progress", self._on_download_progress)
        self._http_obj = obj
        self._info_message = None

        if obj.state <= FTState.IN_PROGRESS:
            self._set_widget_state(PreviewState.DOWNLOADING)

    def _on_download_progress(
        self, ftobj: FileTransfer, _param: GObject.ParamSpec
    ) -> None:

        progress = ftobj.get_property("progress")
        total = ftobj.get_total()
        if total is None:
            self._progressbar.set_pulse_step(0.1)
            self._progressbar.pulse()
            return

        fraction = progress / total
        self._progress_text.set_label(f"{int(fraction * 100)} %")
        self._progressbar.set_fraction(fraction)

    def _on_download_finished(
        self,
        ftobj: FileTransfer,
    ) -> None:

        self._disconnect_object(ftobj)
        assert self._orig_path is not None
        self._info_message = None
        next_state = PreviewState.DOWNLOADED

        try:
            ftobj.raise_for_error()
        except ContentTypeNotAllowed as error:
            log.info("Not an allowed content type: %s, %s", error, self._uri)
            next_state = PreviewState.OFFER_DOWNLOAD

        except MaxContentLengthExceeded as error:
            log.info('File size (%s) too big for URL: "%s"', error, self._uri)
            self._info_message = _("Automatic preview disabled (file too big)")
            next_state = PreviewState.OFFER_DOWNLOAD

        except HTTPStatusError as error:
            log.info("Status error for %s: %s", self._uri, error)
            self._info_message = str(error)
            next_state = PreviewState.ERROR

        except OverflowError as error:
            log.info("Content-Length overflow for %s: %s", self._uri, error)
            next_state = PreviewState.ERROR

        except CancelledError:
            log.info("Download cancelled for %s", self._uri)
            next_state = PreviewState.OFFER_DOWNLOAD

        except Exception:
            log.exception("Unknown error for: %s", self._uri)
            self._info_message = _("Unknown Error")
            next_state = PreviewState.ERROR

        finally:
            if metadata := ftobj.get_metadata():
                if self._orig_path.exists():
                    self._mime_type, self._file_size = get_size_and_mime_type(
                        self._orig_path
                    )

                else:
                    self._mime_type = metadata.content_type or ""
                    self._file_size = metadata.content_length or -1

        self._set_widget_state(next_state)

        if ftobj.state != FTState.FINISHED:
            return

        log.info("File stored: %s %s", self._preview_id_short, self._orig_path.name)

        self._set_widget_state(PreviewState.DISPLAY)
