# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast
from typing import Literal

import logging
from collections.abc import Callable
from collections.abc import Collection
from collections.abc import Generator
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

from gi.repository import Adw
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp.errors import BaseError
from nbxmpp.errors import CancelledError
from nbxmpp.errors import StanzaError
from nbxmpp.errors import TimeoutStanzaError
from nbxmpp.modules.user_avatar import Avatar
from nbxmpp.modules.vcard4 import VCard
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.task import Task

from gajim.common import app
from gajim.common import ged
from gajim.common.client import Client
from gajim.common.const import AvatarSize
from gajim.common.events import VCard4Received
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.util.decorators import event_filter

from gajim.gtk.alert import ConfirmationAlertDialog
from gajim.gtk.alert import InformationAlertDialog
from gajim.gtk.filechoosers import AvatarFileChooserButton
from gajim.gtk.menus import get_account_menu
from gajim.gtk.profile import ProfileEditor
from gajim.gtk.status_message_row import StatusMessageSelectorRow
from gajim.gtk.status_selector import StatusSelector
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import get_ui_string
from gajim.gtk.vcard_editor import build_profile_property_uri
from gajim.gtk.vcard_editor import copy_vcard
from gajim.gtk.vcard_editor import format_profile_property
from gajim.gtk.vcard_editor import get_supported_properties
from gajim.gtk.vcard_grid import LABEL_DICT
from gajim.gtk.vcard_grid import ORDER
from gajim.gtk.vcard_grid import SupportedPropertiesT

log = logging.getLogger("gajim.gtk.account_page")

_LIGHTBOX_MAX_SIZE = 500
_LIGHTBOX_TOTAL_MARGIN = 60
_AVATAR_PUBLISH_STATUS_DELAY_MS = 200

type _TaskScope = Literal["profile", "avatar", "privacy-vcard", "privacy-avatar"]
type _TaskDone = Callable[[object | None, Exception | None], None]
type _TaskStep = tuple[object, tuple[object, ...], dict[str, object]]
type _TaskSequence = Generator[_TaskStep, str | None, None]
type _PrivacyKind = Literal["vcard", "avatar"]
type _ProfileComponent = Literal["vcard", "nickname"]
type _DeferredNavigation = tuple[str | None, bool] | Callable[[], None]

_PRIVACY_NODES: tuple[tuple[str, _PrivacyKind], ...] = (
    (Namespace.VCARD4_PUBSUB, "vcard"),
    (Namespace.AVATAR_METADATA, "avatar"),
    (Namespace.AVATAR_DATA, "avatar"),
    (Namespace.NICK, "avatar"),
)

GObject.type_ensure(Adw.ActionRow)
GObject.type_ensure(Adw.Breakpoint)
GObject.type_ensure(Adw.BreakpointBin)
GObject.type_ensure(Adw.Clamp)
GObject.type_ensure(Adw.PreferencesGroup)
GObject.type_ensure(Adw.ToastOverlay)
GObject.type_ensure(Adw.WrapBox)


@dataclass
class _ProfileSaveState:
    vcard: VCard
    nickname: str
    pending: set[str] = field(default_factory=set[str])
    errors: list[tuple[str, str]] = field(default_factory=list[tuple[str, str]])
    echoed: set[str] = field(default_factory=set[str])

    def complete(self, component: str, error: tuple[str, str] | None = None) -> None:
        self.pending.discard(component)
        if error is not None:
            self.errors.append(error)

    def record_echo(self, component: str) -> None:
        if component in self.pending:
            self.echoed.add(component)


@dataclass
class _PrivacyState:
    pending: int = 0
    public: dict[_PrivacyKind, bool | None] = field(
        default_factory=lambda: {"vcard": None, "avatar": None}
    )
    failed: set[_PrivacyKind] = field(default_factory=set[_PrivacyKind])
    avatar_nodes: bool = True

    def ready(self, kind: _PrivacyKind) -> bool:
        public = self.public[kind]
        return self.pending == 0 and kind not in self.failed and public is not None

    def refresh_needed(
        self, *, has_vcard: bool, vcard_failed: bool
    ) -> tuple[bool, bool]:
        return (
            not has_vcard or vcard_failed,
            bool(self.failed) or all(value is None for value in self.public.values()),
        )


@dataclass
class _AvatarSnapshot:
    paintable: Gdk.Paintable | None
    remove_visible: bool


@dataclass
class _AvatarPublishState:
    avatar: Avatar | None
    preview: _AvatarSnapshot
    previous: _AvatarSnapshot
    echo_received: bool = False

    def get_expected_sha(self) -> str | None:
        return None if self.avatar is None else self.avatar.metadata.default


def _external_update_action(
    *,
    matches_current: bool,
    matches_pending: bool,
    editing: bool,
    dirty: bool,
) -> Literal["current-echo", "pending-echo", "queue", "apply"]:
    if matches_pending:
        return "pending-echo"
    if matches_current:
        return "current-echo"
    if editing and dirty:
        return "queue"
    return "apply"


def _profile_controls_busy(
    scopes: Collection[_TaskScope | None],
) -> bool:
    return "profile" in scopes or "avatar" in scopes


class _AccountPageWrapLayout(Adw.WrapLayout):
    __gtype_name__ = "AccountPageWrapLayout"

    def do_allocate(
        self, widget: Gtk.Widget, width: int, height: int, baseline: int
    ) -> None:
        Adw.WrapLayout.do_allocate(self, widget, width, height, baseline)

        identity = widget.get_first_child()
        account = None if identity is None else identity.get_next_sibling()
        if identity is None or account is None:
            return

        identity_ok, identity_bounds = identity.compute_bounds(widget)
        account_ok, account_bounds = account.compute_bounds(widget)
        if not identity_ok or not account_ok:
            return

        # AdwWrapBox does not expose its line assignments. Once it has laid out
        # its children, non-overlapping vertical bounds mean that the account
        # group has moved onto the line below the identity box.
        wrapped = (
            account_bounds.get_y()
            >= identity_bounds.get_y() + identity_bounds.get_height()
        )
        margin_top = 12 if wrapped else 40
        if identity.get_margin_top() == margin_top:
            return

        identity.set_margin_top(margin_top)
        Adw.WrapLayout.do_allocate(self, widget, width, height, baseline)


class AccountPageWrapBox(Adw.WrapBox):
    __gtype_name__ = "AccountPageWrapBox"

    def __init__(self) -> None:
        Adw.WrapBox.__init__(self)
        self.set_layout_manager(_AccountPageWrapLayout())


@Gtk.Template(string=get_ui_string("avatar_lightbox.ui"))
class AvatarLightbox(Adw.Dialog):
    __gtype_name__ = "AvatarLightbox"

    _close_button: Gtk.Button = Gtk.Template.Child()
    _picture: Gtk.Picture = Gtk.Template.Child()

    def __init__(self, paintable: Gdk.Paintable) -> None:
        Adw.Dialog.__init__(self)
        self._picture.set_paintable(paintable)
        self._host: Gtk.Widget | None = None
        self._size_parent: Gtk.Widget | None = None
        self._tick_callback_id: int | None = None
        self._backdrop_click = Gtk.GestureClick()
        self._backdrop_click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self._close_button.connect("clicked", self._on_close_clicked)
        self._backdrop_click.connect("pressed", self._on_backdrop_pressed)
        self.connect("closed", self._on_closed)

    def present(self, parent: Gtk.Widget | None = None) -> None:
        self._size_parent = parent
        self._sync_content_size()
        Adw.Dialog.present(self, parent)
        self._host = self.get_parent()
        if self._host is not None:
            self._host.add_controller(self._backdrop_click)
        self._tick_callback_id = self.add_tick_callback(self._on_tick)

    def _sync_content_size(self) -> None:
        if self._size_parent is None:
            return

        width = self._size_parent.get_width() - _LIGHTBOX_TOTAL_MARGIN
        height = self._size_parent.get_height() - _LIGHTBOX_TOTAL_MARGIN
        if width <= 0 or height <= 0:
            return

        size = min(_LIGHTBOX_MAX_SIZE, width, height)
        if size == self.get_content_width():
            return
        self.set_content_width(size)
        self.set_content_height(size)

    def _on_tick(self, _widget: Gtk.Widget, _clock: Gdk.FrameClock) -> bool:
        self._sync_content_size()
        return True

    def _on_close_clicked(self, _button: Gtk.Button) -> None:
        self.close()

    def _on_backdrop_pressed(self, gesture: Gtk.GestureClick, *_args: object) -> None:
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        self.close()

    def _on_closed(self, _dialog: Adw.Dialog) -> None:
        if self._tick_callback_id is not None:
            self.remove_tick_callback(self._tick_callback_id)
            self._tick_callback_id = None
        self._size_parent = None
        if self._host is not None:
            self._host.remove_controller(self._backdrop_click)
            self._host = None


@Gtk.Template(string=get_ui_string("account_page.ui"))
class AccountPage(Gtk.Box, SignalManager):
    __gtype_name__ = "AccountPage"

    _toast_overlay: Adw.ToastOverlay = Gtk.Template.Child()
    _scrolled: Gtk.ScrolledWindow = Gtk.Template.Child()
    _content_box: Gtk.Box = Gtk.Template.Child()
    _avatar_editor_box: Gtk.Box = Gtk.Template.Child()
    _avatar_image: Gtk.Image = Gtk.Template.Child()
    _avatar_publish_status: Gtk.Box = Gtk.Template.Child()
    _avatar_edit_button: AvatarFileChooserButton = Gtk.Template.Child()
    _remove_avatar_button: Gtk.Button = Gtk.Template.Child()

    _settings_button: Gtk.Button = Gtk.Template.Child()
    _menu_button: Gtk.MenuButton = Gtk.Template.Child()

    _our_jid_row: Adw.ActionRow = Gtk.Template.Child()
    _account_label_row: Adw.ActionRow = Gtk.Template.Child()

    _status_selector: StatusSelector = Gtk.Template.Child()
    _status_message_row: StatusMessageSelectorRow = Gtk.Template.Child()

    _profile_button: Gtk.Button = Gtk.Template.Child()
    _profile_header_stack: Gtk.Stack = Gtk.Template.Child()
    _profile_editor_header_box: Gtk.Box = Gtk.Template.Child()
    _profile_content_stack: Gtk.Stack = Gtk.Template.Child()
    _profile_editor_box: Gtk.Box = Gtk.Template.Child()
    _profile_preview_list: Gtk.ListBox = Gtk.Template.Child()
    _profile_name_row: Adw.ActionRow = Gtk.Template.Child()
    _privacy_retry_button: Gtk.Button = Gtk.Template.Child()
    _avatar_nick_access: Gtk.Switch = Gtk.Template.Child()
    _avatar_nick_access_row: Adw.ActionRow = Gtk.Template.Child()
    _vcard_access: Gtk.Switch = Gtk.Template.Child()
    _vcard_access_row: Adw.ActionRow = Gtk.Template.Child()

    def __init__(self) -> None:
        Gtk.Box.__init__(self)
        SignalManager.__init__(self)

        self._destroyed = False
        self._account: str | None = None
        self._contact: BareContact | None = None
        self._vcard: VCard | None = None
        self._nickname = ""
        self._avatar_snapshot = _AvatarSnapshot(None, False)
        self._vcard_cache: dict[str, VCard] = {}
        self._nickname_cache: dict[str, str] = {}
        self._profile_editor: ProfileEditor | None = None
        self._profile_editing = False
        self._avatar_editing = False
        self._editor_snapshot_reload_pending = False
        self._pending_profile_edit = False
        self._pending_navigation: _DeferredNavigation | None = None
        self._refresh_on_drain = False
        self._session = 0
        self._tasks: dict[Task, _TaskScope | None] = {}
        self._profile_save: _ProfileSaveState | None = None
        self._avatar_publish: _AvatarPublishState | None = None
        self._avatar_publish_status_timeout_id: int | None = None
        self._pending_avatar_publish: tuple[Avatar | None, _AvatarSnapshot] | None = (
            None
        )
        self._queued_vcard: VCard | None = None
        self._queued_nickname: str | None = None
        self._queued_avatar: _AvatarSnapshot | None = None
        self._vcard_request: Callable[[JID, VCard | None], None] | None = None
        self._vcard_load_failed = False
        self._privacy = _PrivacyState()
        self._privacy_update_guard = False
        self._privacy_refresh_scheduled = False

        self._menu_button.set_create_popup_func(self._on_menu_popup)

        avatar_click = Gtk.GestureClick()
        self._connect(avatar_click, "released", self._on_avatar_clicked)
        self._avatar_image.add_controller(avatar_click)
        self._avatar_image.set_cursor_from_name("pointer")

        for widget, signal, callback in (
            (self._avatar_edit_button, "path-picked", self._on_avatar_path_picked),
            (self._remove_avatar_button, "clicked", self._on_remove_avatar_clicked),
            (
                self._avatar_nick_access,
                "notify::active",
                self._on_access_switch_toggled,
            ),
            (self._vcard_access, "notify::active", self._on_access_switch_toggled),
            (self._privacy_retry_button, "clicked", self._on_privacy_retry_clicked),
        ):
            self._connect(widget, signal, callback)

        app.ged.register_event_handler(
            "vcard4-received", ged.GUI2, self._on_vcard_received
        )

    def do_unroot(self) -> None:
        self._hide_avatar_publish_status()
        if not self._destroyed:
            self._destroyed = True
            self._session += 1
            self._vcard_request = None
            self._cancel_owned_tasks()
            self._disconnect_signals()
            self._disconnect_all()
            app.ged.remove_event_handler(
                "vcard4-received", ged.GUI2, self._on_vcard_received
            )
        Gtk.Box.do_unroot(self)
        app.check_finalize(self)

    def set_account(self, account: str | None, edit_profile: bool = False) -> None:
        if self._account == account:
            if edit_profile:
                if self._has_scoped_operations("profile", "avatar"):
                    self._pending_profile_edit = True
                else:
                    self.edit_profile()
            return

        self._navigate(
            (account, edit_profile),
            lambda: self._set_account(account, edit_profile),
        )

    def _set_account(self, account: str | None, edit_profile: bool = False) -> None:
        self._close_profile_editor()
        self._disconnect_signals()

        self._session += 1
        self._account = account
        self._contact = None
        self._vcard = None
        self._nickname = ""
        self._avatar_snapshot = _AvatarSnapshot(None, False)
        self._queued_vcard = None
        self._queued_nickname = None
        self._pending_avatar_publish = None
        self._privacy_refresh_scheduled = False
        self._vcard_request = None
        self._vcard_load_failed = False
        self._privacy = _PrivacyState()
        self._refresh_on_drain = False
        self._privacy_retry_button.set_visible(False)
        self._set_privacy_switch("avatar", False)
        self._set_privacy_switch("vcard", False)
        self._set_vcard_rows(None)

        if account is not None:
            client = app.get_client(account)
            jid = client.get_own_jid().bare
            contact = client.get_module("Contacts").get_contact(jid)
            assert isinstance(contact, BareContact)
            self._contact = contact

            self._settings_button.set_action_target_value(GLib.Variant("s", account))

            self._profile_button.set_action_target_value(GLib.Variant("s", account))
            self._profile_button.set_action_name(f"app.{account}-profile")

            vcard = self._vcard_cache.get(account)
            if vcard is None:
                vcard = client.get_module("VCard4").get_own_vcard()
            if vcard is not None:
                self._set_authoritative_vcard(vcard)

            self._nickname = self._nickname_cache.get(account, contact.name)
            self._nickname_cache[account] = self._nickname
            self._avatar_snapshot = self._get_contact_avatar_snapshot()

        self._connect_signals()
        self._update_page()

        if account is not None:
            self._create_profile_editor()
            client = app.get_client(account)
            if self._vcard is None:
                self._request_vcard(client)
            self._request_privacy_settings(client)
        self._sync_control_state()
        if edit_profile:
            self.edit_profile()

    def get_account(self) -> str | None:
        return self._account

    def confirm_navigation(self, callback: Callable[[], None]) -> None:
        if self._has_operations():
            callback()
            return
        self._navigate(callback, callback)

    def _navigate(
        self, deferred: _DeferredNavigation, callback: Callable[[], None]
    ) -> None:
        if self._has_operations():
            self._pending_navigation = deferred
            return
        if (
            self._profile_editing
            and self._profile_editor is not None
            and self._profile_editor.has_unsaved_changes()
        ):
            self._confirm_discard(callback)
            return
        self._pending_profile_edit = False
        callback()

    def _confirm_discard(self, callback: Callable[[], None]) -> None:
        editor = self._profile_editor
        if editor is None:
            callback()
            return
        dialog = Adw.AlertDialog(
            heading=_("Discard Profile Changes?"),
            body=_("Your unsaved profile changes will be lost."),
            close_response="continue",
        )
        dialog.add_response("continue", _("Continue Editing"))
        dialog.add_response("discard", _("Discard"))
        dialog.set_default_response("continue")
        dialog.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)

        def on_response(_dialog: Adw.AlertDialog, response: str) -> None:
            if response != "discard":
                return
            if self._profile_editor is not editor:
                return
            self._discard_profile_changes()
            callback()

        dialog.connect("response", on_response)
        dialog.present(self)

    def edit_profile(self) -> None:
        if self._account is None:
            return

        self._create_profile_editor()
        assert self._profile_editor is not None
        if self._has_scoped_operations("profile", "avatar"):
            self._pending_profile_edit = True
            return
        if self._vcard is None:
            self._pending_profile_edit = True
            self._request_vcard(app.get_client(self._account))
            return

        self._profile_editor.load_snapshot(self._vcard, self._nickname)
        if not self._profile_editor.begin_edit():
            return
        self._pending_profile_edit = False
        self._profile_editing = True
        self._profile_header_stack.set_visible_child_name("edit")
        self._profile_content_stack.set_visible_child_name("edit")

    def _create_profile_editor(self) -> None:
        if self._account is None or self._profile_editor is not None:
            return

        self._profile_editor = ProfileEditor(self._scrolled, self._toast_overlay)
        for signal, callback in (
            ("save-requested", self._on_profile_save_requested),
            ("cancel-requested", self._discard_profile_changes),
            ("avatar-update-requested", self._on_avatar_update_requested),
            ("avatar-editing-changed", self._on_avatar_editing_changed),
            ("changed", self._on_profile_changed),
            ("error", self._on_profile_error),
        ):
            self._connect(self._profile_editor, signal, callback)
        if self._vcard is not None:
            self._profile_editor.load_snapshot(self._vcard, self._nickname)
        self._profile_editor_header_box.append(self._profile_editor.get_header())
        self._profile_editor_box.append(self._profile_editor)
        self._avatar_editor_box.append(self._profile_editor.get_avatar_editor())
        self._sync_control_state()

    def _connect_signals(self) -> None:
        if self._account is None:
            return

        assert self._contact is not None

        app.get_client(self._account).connect_signal(
            "state-changed", self._on_client_state_changed
        )
        self._contact.connect("avatar-update", self._on_avatar_update)
        self._contact.connect("nickname-update", self._on_nickname_update)
        app.settings.connect_signal(
            "account_label", self._update_account_label, self._account
        )

    def _disconnect_signals(self) -> None:
        if self._account is None:
            return

        app.get_client(self._account).disconnect_all_from_obj(self)
        if self._contact is not None:
            self._contact.disconnect_all_from_obj(self)
        app.settings.disconnect_signals(self)

    def _on_avatar_clicked(self, *_args: object) -> None:
        if self._account is None or self._contact is None:
            return

        client = app.get_client(self._account)
        if client.get_module("UserAvatar").refresh_avatar_if_invalid(self._contact):
            return

        paintable = self._avatar_image.get_paintable()
        if paintable is None:
            return

        AvatarLightbox(paintable).present(self)

    def _on_profile_changed(self, _editor: ProfileEditor) -> None:
        if (
            not self._profile_editing
            or self._profile_editor is None
            or self._profile_editor.has_unsaved_changes()
            or (self._queued_vcard is None and self._queued_nickname is None)
        ):
            self._sync_control_state()
            return

        self._apply_queued_profile(reload_editor=True)
        self._sync_control_state()

    def _on_profile_error(self, editor: ProfileEditor, title: str, text: str) -> None:
        if editor is self._profile_editor:
            InformationAlertDialog(title, text)

    def _on_profile_save_requested(
        self, editor: ProfileEditor, vcard: VCard, nickname: str
    ) -> None:
        if (
            editor is not self._profile_editor
            or self._account is None
            or self._vcard is None
            or self._has_operations()
        ):
            return
        if self._queued_vcard is not None or self._queued_nickname is not None:
            InformationAlertDialog(
                _("Profile changed on the server"),
                _("Cancel editing and reopen the profile before saving."),
            )
            return

        vcard_changed = not self._vcards_equal(vcard, self._vcard)
        nickname_changed = nickname != self._nickname
        if not vcard_changed and not nickname_changed:
            self._finish_profile_editing()
            return
        if not self._profile_save_status(vcard_changed, nickname_changed)[0]:
            self._sync_control_state()
            return

        client = app.get_client(self._account)
        state = _ProfileSaveState(copy_vcard(vcard), nickname)
        self._profile_save = state

        for component, changed in (
            ("vcard", vcard_changed),
            ("nickname", nickname_changed),
        ):
            if not changed:
                continue
            component = cast(_ProfileComponent, component)
            if component == "vcard":
                start = client.get_module("VCard4").set_vcard
                value = state.vcard
                public = self._privacy.public["vcard"]
            else:
                start = client.get_module("UserNickname").set_nickname
                value = nickname
                public = self._privacy.public["avatar"]
            state.pending.add(component)
            error = self._start_task(
                client,
                start,
                value,
                public=bool(public),
                scope="profile",
                done=lambda _result, task_error, component=component: (
                    self._on_profile_save_result(state, component, task_error)
                ),
            )
            if error is not None:
                state.complete(component, (self._profile_error_title(component), error))

        if not state.pending:
            self._finish_profile_save()
        self._sync_control_state()

    def _on_profile_save_result(
        self,
        state: _ProfileSaveState,
        component: _ProfileComponent,
        error: Exception | None,
    ) -> None:
        if self._profile_save is not state or component not in state.pending:
            return

        if error is not None and component not in state.echoed:
            state.complete(
                component,
                (self._profile_error_title(component), self._get_error_text(error)),
            )
        else:
            assert self._profile_editor is not None
            vcard_saved = component == "vcard"
            if vcard_saved:
                self._set_authoritative_vcard(state.vcard, update_editor=False)
            else:
                self._set_authoritative_nickname(state.nickname)
            self._profile_editor.acknowledge_saved(vcard_saved, not vcard_saved)
            state.complete(component)
        if not state.pending:
            self._finish_profile_save()

    @staticmethod
    def _profile_error_title(component: _ProfileComponent) -> str:
        return (
            _("Unable to save profile")
            if component == "vcard"
            else _("Unable to save name")
        )

    def _finish_profile_save(self) -> None:
        state = self._profile_save
        if state is None or state.pending:
            return
        self._profile_save = None
        if not state.errors:
            self._apply_queued_profile()
            self._finish_profile_editing()
            return

        assert self._profile_editor is not None
        if len(state.errors) == 1:
            title, text = state.errors[0]
        else:
            title = _("Unable to save profile")
            text = "\n".join(
                f"{error_title}: {error}" for error_title, error in state.errors
            )
        self._profile_editor.show_error(title, text)

    def _discard_profile_changes(self, *_args: object) -> None:
        if (
            self._has_operations()
            or self._profile_editor is None
            or self._vcard is None
        ):
            return
        self._apply_queued_profile()
        self._profile_editor.discard_changes(self._vcard, self._nickname)
        self._finish_profile_editing()

    def _apply_queued_profile(self, *, reload_editor: bool = False) -> None:
        queued_vcard, queued_nickname = self._queued_vcard, self._queued_nickname
        self._queued_vcard = None
        self._queued_nickname = None
        if queued_vcard is not None:
            self._set_authoritative_vcard(queued_vcard, update_editor=False)
        if queued_nickname is not None:
            self._set_authoritative_nickname(queued_nickname)
        if reload_editor:
            self._reload_editor_snapshot()

    def _finish_profile_editing(self) -> None:
        if self._profile_editor is not None:
            self._profile_editor.end_edit()
        self._profile_editing = False
        self._profile_header_stack.set_visible_child_name("preview")
        self._profile_content_stack.set_visible_child_name("preview")
        self._sync_control_state()

    def _set_authoritative_vcard(
        self, vcard: VCard, *, update_editor: bool = True
    ) -> None:
        assert self._account is not None
        copied_vcard = copy_vcard(vcard)
        self._vcard_cache[self._account] = copied_vcard
        self._vcard = copied_vcard
        self._vcard_load_failed = False
        self._set_vcard_rows(copied_vcard)
        if update_editor:
            self._reload_editor_snapshot()

    def _set_authoritative_nickname(self, nickname: str) -> None:
        assert self._account is not None
        self._nickname = nickname
        self._nickname_cache[self._account] = nickname
        self._profile_name_row.set_subtitle(nickname)

    def _reload_editor_snapshot(self) -> None:
        if self._profile_editor is None or self._vcard is None:
            return
        if self._avatar_editing:
            self._editor_snapshot_reload_pending = True
            return
        self._editor_snapshot_reload_pending = False
        editing = self._profile_editing
        self._profile_editor.load_snapshot(self._vcard, self._nickname)
        if editing:
            self._profile_editor.begin_edit()

    @staticmethod
    def _vcards_equal(first: VCard, second: VCard) -> bool:
        return str(first.to_node()) == str(second.to_node())

    def _close_profile_editor(self) -> None:
        if self._profile_editor is None:
            return

        self._profile_header_stack.set_visible_child_name("preview")
        self._profile_content_stack.set_visible_child_name("preview")
        self._disconnect_object(self._profile_editor)
        self._profile_editor_header_box.remove(self._profile_editor.get_header())
        self._avatar_editor_box.remove(self._profile_editor.get_avatar_editor())
        self._profile_editor_box.remove(self._profile_editor)
        self._profile_editor = None
        self._profile_editing = False
        self._pending_profile_edit = False
        self._editor_snapshot_reload_pending = False
        self._set_avatar_editing(False)

    def _on_avatar_editing_changed(self, _editor: ProfileEditor, editing: bool) -> None:
        self._set_avatar_editing(editing)

    def _set_avatar_editing(self, editing: bool) -> None:
        self._avatar_editing = editing
        self._content_box.set_visible(not editing)
        self._avatar_editor_box.set_visible(editing)
        if editing:
            self._scrolled.get_vadjustment().set_value(0)
        elif self._editor_snapshot_reload_pending:
            self._reload_editor_snapshot()
        self._sync_control_state()

    def _on_menu_popup(self, menu_button: Gtk.MenuButton) -> None:
        assert self._account is not None
        menu_button.set_menu_model(get_account_menu(self._account))

    def _on_avatar_path_picked(
        self, _button: AvatarFileChooserButton, paths: list[Path]
    ) -> None:
        if (
            not paths
            or self._profile_editor is None
            or self._has_scoped_operations("profile", "avatar")
        ):
            return
        self._profile_editor.start_avatar_edit(paths[0])

    def _on_remove_avatar_clicked(self, _button: Gtk.Button) -> None:
        if self._contact is None or self._has_scoped_operations("profile", "avatar"):
            return
        ConfirmationAlertDialog(
            _("Remove Profile Picture?"),
            _("Do you really want to remove your profile picture?"),
            confirm_label=_("_Remove"),
            appearance="destructive",
            callback=self._remove_avatar,
        )

    def _remove_avatar(self) -> None:
        if self._contact is None or self._has_scoped_operations("profile", "avatar"):
            return
        preview = self._get_contact_avatar_snapshot(default=True).paintable
        assert preview is not None
        self._publish_avatar(None, preview, removing=True)

    def _on_avatar_update_requested(
        self, editor: ProfileEditor, avatar: Avatar, preview: Gdk.Texture
    ) -> None:
        if editor is not self._profile_editor:
            return
        self._publish_avatar(avatar, preview, removing=False)

    def _publish_avatar(
        self, avatar: Avatar | None, preview: Gdk.Paintable, *, removing: bool
    ) -> bool:
        if self._account is None or self._has_scoped_operations("profile", "avatar"):
            return False
        preview_snapshot = _AvatarSnapshot(preview, not removing)
        if (
            self._has_scoped_operations("privacy-vcard", "privacy-avatar")
            or self._privacy.pending > 0
            or self._privacy_refresh_scheduled
        ):
            self._pending_avatar_publish = (avatar, preview_snapshot)
            return True
        client = app.get_client(self._account)
        if not client.is_available() or not self._privacy.ready("avatar"):
            text = (
                _("You are offline")
                if not client.is_available()
                else _("Privacy settings are unavailable")
            )
            InformationAlertDialog(_("Error while uploading avatar"), text)
            return False

        state = _AvatarPublishState(
            avatar=avatar,
            preview=preview_snapshot,
            previous=_AvatarSnapshot(
                self._avatar_image.get_paintable(),
                self._remove_avatar_button.get_visible(),
            ),
        )
        self._avatar_publish = state
        self._show_avatar_snapshot(preview_snapshot)

        error = self._start_task(
            client,
            client.get_module("UserAvatar").set_avatar,
            avatar,
            public=bool(self._privacy.public["avatar"]),
            scope="avatar",
            done=lambda _result, task_error: self._on_set_avatar_result(
                state, task_error
            ),
        )
        if error is not None:
            self._end_avatar_publish(state.previous)
            InformationAlertDialog(_("Error while uploading avatar"), error)
            return False
        self._schedule_avatar_publish_status(state)
        return True

    def _on_set_avatar_result(
        self, state: _AvatarPublishState, error: Exception | None
    ) -> None:
        if self._avatar_publish is not state:
            return

        error_text: str | None = None
        missing_removal = False
        if error is not None:
            missing_removal = (
                state.avatar is None
                and isinstance(error, StanzaError)
                and error.condition == "item-not-found"
            )
            if not missing_removal and not state.echo_received:
                if (
                    isinstance(error, StanzaError)
                    and error.condition == "not-acceptable"
                    and error.app_condition == "payload-too-big"
                ):
                    error_text = _("Avatar file size too big")
                else:
                    error_text = self._get_error_text(error)

        if error_text is None:
            assert self._account is not None
            self._end_avatar_publish(state.preview)
            if not missing_removal:
                self._privacy.avatar_nodes = True
            app.get_client(self._account).update_presence(include_muc=True)
        else:
            self._end_avatar_publish(state.previous)
            InformationAlertDialog(_("Error while uploading avatar"), error_text)

    def _end_avatar_publish(self, fallback: _AvatarSnapshot) -> None:
        self._hide_avatar_publish_status()
        self._show_avatar_snapshot(self._queued_avatar or fallback, store=True)
        self._avatar_publish = None
        self._queued_avatar = None
        self._sync_control_state()

    def _schedule_avatar_publish_status(self, state: _AvatarPublishState) -> None:
        self._hide_avatar_publish_status()
        self._avatar_publish_status_timeout_id = GLib.timeout_add(
            _AVATAR_PUBLISH_STATUS_DELAY_MS,
            self._show_avatar_publish_status,
            state,
        )

    def _show_avatar_publish_status(self, state: _AvatarPublishState) -> bool:
        self._avatar_publish_status_timeout_id = None
        if self._avatar_publish is state:
            self._avatar_publish_status.set_visible(True)
        return GLib.SOURCE_REMOVE

    def _hide_avatar_publish_status(self) -> None:
        if self._avatar_publish_status_timeout_id is not None:
            GLib.source_remove(self._avatar_publish_status_timeout_id)
            self._avatar_publish_status_timeout_id = None
        self._avatar_publish_status.set_visible(False)

    def _get_contact_avatar_snapshot(self, *, default: bool = False) -> _AvatarSnapshot:
        assert self._contact is not None
        return _AvatarSnapshot(
            self._contact.get_avatar(
                AvatarSize.PUBLISH,
                self.get_scale_factor(),
                add_show=False,
                default=default,
            ),
            self._contact.avatar_sha is not None,
        )

    def _show_avatar_snapshot(
        self, snapshot: _AvatarSnapshot, *, store: bool = False
    ) -> None:
        if store:
            self._avatar_snapshot = snapshot
        self._avatar_image.set_from_paintable(snapshot.paintable)
        self._remove_avatar_button.set_visible(snapshot.remove_visible)

    def _request_privacy_settings(self, client: Client) -> None:
        if self._account is None or self._privacy.pending:
            return
        state = _PrivacyState(pending=len(_PRIVACY_NODES))
        self._privacy = state
        self._privacy_retry_button.set_visible(False)
        self._set_privacy_subtitles(_("Loading…"))
        self._sync_control_state()

        if not client.is_available():
            self._set_privacy_request_failed(offline=True)
            return

        pubsub = client.get_module("PubSub")
        for namespace, kind in _PRIVACY_NODES:
            error = self._start_task(
                client,
                pubsub.get_access_model,
                namespace,
                scope=None,
                done=lambda result, task_error, namespace=namespace, kind=kind: (
                    self._on_access_model_received(
                        state, namespace, kind, result, task_error
                    )
                ),
            )
            if error is not None:
                self._set_privacy_request_failed(offline=not client.is_available())
                return

    def _set_privacy_request_failed(self, *, offline: bool) -> None:
        self._privacy.pending = 0
        self._privacy.failed.update(("vcard", "avatar"))
        self._set_privacy_subtitles(
            _("You are offline") if offline else _("Unavailable")
        )
        self._privacy_retry_button.set_visible(not offline)
        self._sync_control_state()

    def _on_access_model_received(
        self,
        state: _PrivacyState,
        namespace: str,
        kind: _PrivacyKind,
        result: object | None,
        error: Exception | None,
    ) -> None:
        if self._privacy is not state or state.pending == 0:
            return

        is_public: bool | None = None
        if error is not None:
            if isinstance(error, StanzaError) and error.condition == "item-not-found":
                is_public = False
                if namespace in (
                    Namespace.AVATAR_METADATA,
                    Namespace.AVATAR_DATA,
                ):
                    state.avatar_nodes = False
            else:
                log.warning("Unable to get access model for %s: %s", namespace, error)
                state.failed.add(kind)
        else:
            is_public = result == "open"

        if is_public is not None:
            current = state.public[kind]
            state.public[kind] = is_public if current is None else current or is_public

        state.pending -= 1
        if state.pending:
            return
        for privacy_kind in ("vcard", "avatar"):
            public = state.public[privacy_kind]
            if privacy_kind in state.failed:
                self._privacy_control(privacy_kind)[1].set_subtitle(_("Unavailable"))
            elif public is not None:
                self._set_privacy_switch(privacy_kind, public)
        self._privacy_retry_button.set_visible(bool(state.failed))

    def _on_privacy_retry_clicked(self, _button: Gtk.Button) -> None:
        if (
            self._account is None
            or self._has_operations()
            or None in self._tasks.values()
        ):
            return
        self._request_privacy_settings(app.get_client(self._account))

    def _privacy_control(self, kind: _PrivacyKind) -> tuple[Gtk.Switch, Adw.ActionRow]:
        if kind == "vcard":
            return self._vcard_access, self._vcard_access_row
        return self._avatar_nick_access, self._avatar_nick_access_row

    def _set_privacy_subtitles(self, subtitle: str) -> None:
        for kind in ("vcard", "avatar"):
            self._privacy_control(kind)[1].set_subtitle(subtitle)

    def _set_privacy_switch(self, kind: _PrivacyKind, state: bool) -> None:
        switch, row = self._privacy_control(kind)
        self._privacy_update_guard = True
        try:
            switch.set_active(state)
        finally:
            self._privacy_update_guard = False
        row.set_subtitle(
            _("Visible for Everyone") if state else _("Visible only for Contacts")
        )

    def _on_access_switch_toggled(self, switch: Gtk.Switch, *_args: object) -> None:
        if self._privacy_update_guard:
            return
        kind: _PrivacyKind = "vcard" if switch is self._vcard_access else "avatar"
        self._privacy_control(kind)[1].set_subtitle(
            _("Visible for Everyone")
            if switch.get_active()
            else _("Visible only for Contacts")
        )

        if not switch.get_sensitive():
            return
        if kind == "vcard":
            self._set_vcard_privacy(switch.get_active())
        else:
            self._set_avatar_nickname_privacy(switch.get_active())

    def _set_vcard_privacy(self, desired: bool) -> None:
        previous = self._privacy.public["vcard"]
        if (
            self._account is None
            or self._vcard is None
            or previous is None
            or self._has_scoped_operations("profile", "avatar", "privacy-vcard")
        ):
            self._set_privacy_switch("vcard", bool(previous))
            return
        client = app.get_client(self._account)
        if not client.is_available():
            self._set_privacy_switch("vcard", previous)
            return

        error = self._start_task(
            client,
            client.get_module("VCard4").set_vcard,
            self._vcard,
            public=desired,
            scope="privacy-vcard",
            done=lambda _result, task_error: self._finish_vcard_privacy(
                desired, previous, task_error
            ),
        )
        if error is not None:
            self._privacy_write_failed("vcard", previous, error, refresh=False)

    def _finish_vcard_privacy(
        self, desired: bool, previous: bool, error: Exception | None
    ) -> None:
        if error is None:
            self._privacy.public["vcard"] = desired
            self._set_privacy_switch("vcard", desired)
        else:
            self._privacy_write_failed("vcard", previous, self._get_error_text(error))

    def _set_avatar_nickname_privacy(self, desired: bool) -> None:
        previous = self._privacy.public["avatar"]
        if (
            self._account is None
            or previous is None
            or self._has_scoped_operations("profile", "avatar", "privacy-avatar")
        ):
            self._set_privacy_switch("avatar", bool(previous))
            return
        client = app.get_client(self._account)
        if not client.is_available():
            self._set_privacy_switch("avatar", previous)
            return

        avatar_access = client.get_module("UserAvatar").set_access_model
        nickname_access = client.get_module("UserNickname").set_access_model

        def transaction() -> _TaskSequence:
            avatar_changed = False
            if self._privacy.avatar_nodes:
                error = yield avatar_access, (desired,), {}
                if error is not None:
                    self._privacy_write_failed("avatar", previous, error)
                    return
                avatar_changed = True

            error = yield nickname_access, (desired,), {}
            if error is None:
                self._privacy.public["avatar"] = desired
                self._set_privacy_switch("avatar", desired)
                return
            if not avatar_changed:
                self._privacy_write_failed("avatar", previous, error)
                return

            rollback_error = yield avatar_access, (previous,), {}
            self._privacy_write_failed(
                "avatar",
                previous,
                error,
                rollback_error=rollback_error,
                restored=rollback_error is None,
            )

        self._run_task_sequence(client, "privacy-avatar", transaction())

    def _privacy_write_failed(
        self,
        kind: _PrivacyKind,
        previous: bool,
        error: str,
        *,
        rollback_error: str | None = None,
        restored: bool = True,
        refresh: bool = True,
    ) -> None:
        if restored:
            self._set_privacy_switch(kind, previous)
        if rollback_error is not None:
            error = _(
                "%(error)s The previous setting could not be restored: "
                "%(rollback_error)s"
            ) % {"error": error, "rollback_error": rollback_error}
        if refresh:
            self._mark_privacy_for_refresh(kind)
        InformationAlertDialog(_("Unable to save privacy setting"), error)
        self._sync_control_state()

    def _mark_privacy_for_refresh(self, kind: _PrivacyKind) -> None:
        self._privacy.failed.add(kind)
        self._privacy.public[kind] = None
        self._privacy_control(kind)[1].set_subtitle(_("Unavailable"))
        self._privacy_refresh_scheduled = True
        GLib.idle_add(self._refresh_privacy_if_idle)

    def _refresh_privacy_if_idle(self) -> bool:
        if self._has_operations():
            return GLib.SOURCE_REMOVE
        self._privacy_refresh_scheduled = False
        if self._account is not None:
            self._request_privacy_settings(app.get_client(self._account))
        self._drain_deferred_actions()
        return GLib.SOURCE_REMOVE

    def _request_vcard(self, client: Client) -> None:
        if (
            self._account is None
            or self._vcard_request is not None
            or not client.is_available()
        ):
            if not client.is_available():
                self._finish_vcard_request(None, failed=True)
            return

        request_vcard = client.get_module("VCard4").request_vcard
        if not callable(request_vcard):
            self._finish_vcard_request(None, failed=True)
            return

        account = self._account
        session = self._session
        self._vcard_load_failed = False

        def on_vcard_received(jid: JID, vcard: VCard | None) -> None:
            if (
                self._destroyed
                or session != self._session
                or account != self._account
                or self._vcard_request is not on_vcard_received
                or self._contact is None
                or jid != self._contact.jid
            ):
                return
            self._finish_vcard_request(vcard)

        self._vcard_request = on_vcard_received
        try:
            immediate = request_vcard(
                jid=client.get_own_jid().new_as_bare(),
                callback=on_vcard_received,
            )
        except Exception:  # noqa: BLE001
            if self._vcard_request is on_vcard_received:
                self._finish_vcard_request(None, failed=True)
            return
        if immediate is not None:
            on_vcard_received(client.get_own_jid().new_as_bare(), immediate)
        self._sync_control_state()

    def _finish_vcard_request(
        self, vcard: VCard | None, *, failed: bool = False
    ) -> None:
        self._vcard_request = None
        if vcard is not None:
            self._accept_external_vcard(vcard)
        unavailable = self._vcard is None
        if failed or unavailable:
            self._vcard_load_failed = True
        if self._pending_profile_edit:
            self._pending_profile_edit = False
            if unavailable:
                InformationAlertDialog(
                    _("Unable to load profile"),
                    _("The profile could not be retrieved from the server."),
                )
            else:
                self.edit_profile()
        self._sync_control_state()
        self._drain_deferred_actions()

    def _accept_external_vcard(self, vcard: VCard) -> None:
        self._accept_external_profile(
            "vcard",
            vcard,
            self._vcard is not None and self._vcards_equal(vcard, self._vcard),
            self._profile_save is not None
            and self._vcards_equal(vcard, self._profile_save.vcard),
        )

    def _accept_external_nickname(self, nickname: str) -> None:
        self._accept_external_profile(
            "nickname",
            nickname,
            nickname == self._nickname,
            self._profile_save is not None and nickname == self._profile_save.nickname,
        )

    def _accept_external_profile(
        self,
        component: _ProfileComponent,
        value: VCard | str,
        matches_current: bool,
        matches_pending: bool,
    ) -> None:
        action = _external_update_action(
            matches_current=matches_current,
            matches_pending=matches_pending,
            editing=self._profile_editing,
            dirty=(
                self._profile_editor is not None
                and self._profile_editor.has_unsaved_changes()
            ),
        )
        if component == "vcard":
            assert isinstance(value, VCard)
            self._queued_vcard = copy_vcard(value) if action == "queue" else None
        else:
            assert isinstance(value, str)
            self._queued_nickname = value if action == "queue" else None

        if action in ("current-echo", "queue"):
            return
        if action == "pending-echo":
            assert self._profile_save is not None
            self._profile_save.record_echo(component)
            return
        if component == "vcard":
            self._set_authoritative_vcard(cast(VCard, value))
        else:
            self._set_authoritative_nickname(cast(str, value))
            self._reload_editor_snapshot()
        self._sync_control_state()

    def _start_task(
        self,
        client: Client,
        start: object,
        *args: object,
        scope: _TaskScope | None,
        done: _TaskDone,
        **kwargs: object,
    ) -> str | None:
        if not callable(start):
            return self._request_start_error(client)
        session = self._session

        def callback(task: Task) -> None:
            if task not in self._tasks:
                return
            try:
                result: object | None = None
                error: Exception | None = None
                try:
                    result = task.finish()
                except Exception as task_error:  # noqa: BLE001
                    error = task_error
                if not self._destroyed and session == self._session:
                    done(result, error)
            finally:
                self._tasks.pop(task, None)
                if not self._destroyed:
                    self._sync_control_state()
                    self._drain_deferred_actions()

        try:
            task = cast(Task | None, start(*args, callback=None, **kwargs))
        except Exception as error:  # noqa: BLE001
            return self._get_error_text(error)
        if task is None:
            return self._request_start_error(client)
        try:
            task.add_done_callback(callback, weak=False)
        except Exception as error:  # noqa: BLE001
            task.cancel()
            return self._get_error_text(error)
        self._tasks[task] = scope
        self._sync_control_state()
        return None

    def _run_task_sequence(
        self, client: Client, scope: _TaskScope, sequence: _TaskSequence
    ) -> None:
        def advance(error: str | None = None) -> None:
            try:
                start, args, kwargs = sequence.send(error)
            except StopIteration:
                return
            start_error = self._start_task(
                client,
                start,
                *args,
                scope=scope,
                done=lambda _result, task_error: advance(
                    None if task_error is None else self._get_error_text(task_error)
                ),
                **kwargs,
            )
            if start_error is not None:
                advance(start_error)

        advance()

    def _has_operations(self) -> bool:
        return any(scope is not None for scope in self._tasks.values())

    def _has_scoped_operations(self, *scopes: _TaskScope) -> bool:
        return any(scope in scopes for scope in self._tasks.values())

    def _cancel_owned_tasks(self) -> None:
        for task in list(self._tasks):
            task.cancel()

    def _drain_deferred_actions(self) -> None:
        if self._has_operations():
            return
        pending_navigation = self._pending_navigation
        if isinstance(pending_navigation, tuple):
            self._pending_navigation = None
            self._pending_profile_edit = False
            account, edit_profile = cast(tuple[str | None, bool], pending_navigation)
            self.set_account(account, edit_profile)
            return
        if self._privacy_refresh_scheduled:
            self._privacy_refresh_scheduled = False
            if self._account is not None:
                self._request_privacy_settings(app.get_client(self._account))
                if self._privacy.pending:
                    return
        if self._pending_avatar_publish is not None:
            if self._privacy.pending > 0 or self._privacy_refresh_scheduled:
                return
            avatar, preview = self._pending_avatar_publish
            self._pending_avatar_publish = None
            assert preview.paintable is not None
            if self._publish_avatar(
                avatar,
                preview.paintable,
                removing=not preview.remove_visible,
            ):
                return
        if pending_navigation is not None:
            self._pending_navigation = None
            self.confirm_navigation(pending_navigation)
            return
        if (
            self._refresh_on_drain
            and self._account is not None
            and self._vcard_request is None
            and self._privacy.pending == 0
        ):
            self._refresh_on_drain = False
            self._refresh_profile_data(app.get_client(self._account))
            if self._has_operations():
                return
        if self._pending_profile_edit:
            self._pending_profile_edit = False
            self.edit_profile()

    def _refresh_profile_data(self, client: Client) -> None:
        refresh_vcard, refresh_privacy = self._privacy.refresh_needed(
            has_vcard=self._vcard is not None,
            vcard_failed=self._vcard_load_failed,
        )
        if refresh_vcard:
            self._request_vcard(client)
        if refresh_privacy:
            self._request_privacy_settings(client)

    def _profile_save_status(
        self, vcard_changed: bool, nickname_changed: bool
    ) -> tuple[bool, str]:
        if self._account is None or not app.get_client(self._account).is_available():
            return False, _("You are offline")
        if self._vcard is None:
            return False, _("The profile is unavailable")
        if self._privacy.pending:
            return False, _("Retrieving privacy settings…")
        if (vcard_changed and not self._privacy.ready("vcard")) or (
            nickname_changed and not self._privacy.ready("avatar")
        ):
            return False, _("Privacy settings are unavailable")
        return True, ""

    def _sync_control_state(self) -> None:
        if self._destroyed:
            return
        account = self._account
        available = account is not None and app.get_client(account).is_available()
        busy = _profile_controls_busy(self._tasks.values())
        privacy_busy = self._has_scoped_operations("privacy-vcard", "privacy-avatar")
        self._profile_button.set_sensitive(available and not busy)
        if account is not None and not available:
            profile_tooltip = _("You are offline")
        elif busy:
            profile_tooltip = _("Please wait for the profile update to finish")
        else:
            profile_tooltip = _("Edit Profile")
        self._profile_button.set_tooltip_text(profile_tooltip)

        editor = self._profile_editor
        if editor is not None:
            editor.set_busy(busy)
            vcard_changed = False
            nickname_changed = False
            if self._profile_editing and self._vcard is not None:
                vcard_changed, nickname_changed = editor.get_change_state()
            save_allowed, reason = self._profile_save_status(
                vcard_changed, nickname_changed
            )
            editor.set_save_available(
                not busy
                and not privacy_busy
                and self._profile_editing
                and save_allowed,
                reason,
            )

        avatar_editable = (
            available
            and not busy
            and not self._avatar_editing
            and self._privacy.ready("avatar")
        )
        self._avatar_edit_button.set_visible(account is not None)
        self._avatar_edit_button.set_sensitive(avatar_editable)
        shown_avatar = (
            self._avatar_publish.preview
            if self._avatar_publish is not None
            else self._avatar_snapshot
        )
        self._remove_avatar_button.set_visible(
            account is not None and shown_avatar.remove_visible
        )
        self._remove_avatar_button.set_sensitive(avatar_editable)

        privacy_editable = available and not busy
        for kind in ("vcard", "avatar"):
            scope: _TaskScope = "privacy-vcard" if kind == "vcard" else "privacy-avatar"
            self._privacy_control(kind)[0].set_sensitive(
                privacy_editable
                and not self._has_scoped_operations(scope)
                and self._privacy.ready(kind)
                and (kind != "vcard" or self._queued_vcard is None)
            )
        self._privacy_retry_button.set_sensitive(
            privacy_editable and not privacy_busy and None not in self._tasks.values()
        )
        self._status_selector.set_sensitive(account is not None)
        self._status_message_row.set_sensitive(available)

    @staticmethod
    def _request_start_error(client: Client) -> str:
        if not client.is_available():
            return _("You are offline")
        return _("The operation is unavailable.")

    @staticmethod
    def _get_error_text(error: Exception) -> str:
        if isinstance(error, TimeoutStanzaError):
            return _("The request timed out.")
        if isinstance(error, CancelledError):
            return _("The request was cancelled.")
        if isinstance(error, BaseError):
            return error.get_text()
        return str(error) or _("The operation failed.")

    def _on_client_state_changed(self, client: Client, *_args: object) -> None:
        if not client.is_available():
            self._cancel_owned_tasks()
            if self._vcard_request is not None:
                self._finish_vcard_request(None, failed=True)
        else:
            if (
                self._has_operations()
                or self._vcard_request is not None
                or self._privacy.pending > 0
            ):
                self._refresh_on_drain = True
            else:
                self._refresh_profile_data(client)
        self._sync_control_state()

    def _on_avatar_update(self, *args: Any) -> None:
        if self._contact is None:
            return
        if self._avatar_publish is not None:
            if self._contact.avatar_sha == self._avatar_publish.get_expected_sha():
                self._avatar_publish.echo_received = True
                self._queued_avatar = None
                return
            self._queued_avatar = self._get_contact_avatar_snapshot()
            return
        self._show_avatar_snapshot(self._get_contact_avatar_snapshot(), store=True)
        self._sync_control_state()

    def _on_nickname_update(self, *args: Any) -> None:
        if self._contact is not None:
            self._accept_external_nickname(self._contact.name)

    def _update_account_label(self, label: str, *_args: object) -> None:
        self._account_label_row.set_subtitle(label)

    @event_filter(["account"])
    def _on_vcard_received(self, event: VCard4Received) -> None:
        if event.vcard is None:
            return
        self._accept_external_vcard(event.vcard)

    def _set_vcard_rows(self, vcard: VCard | None) -> None:
        if vcard is None:
            vcard = VCard()

        child = self._profile_name_row.get_next_sibling()
        while child is not None:
            next_child = child.get_next_sibling()
            self._profile_preview_list.remove(child)
            child = next_child

        properties = get_supported_properties(vcard)
        properties.sort(key=lambda prop: ORDER.index(prop.name))
        for prop in properties:
            if not prop.is_empty:
                self._append_profile_preview_row(prop)

    def _append_profile_preview_row(self, prop: SupportedPropertiesT) -> None:
        value = format_profile_property(prop)
        if not value:
            return

        row = Adw.ActionRow(
            title=LABEL_DICT[prop.name],
            subtitle=value,
            subtitle_selectable=True,
        )
        row.add_css_class("property")

        uri = build_profile_property_uri(prop)
        if uri is not None:
            row.set_activatable(True)
            row.set_action_name("app.open-link")
            row.set_action_target_value(GLib.Variant("s", uri))

        self._profile_preview_list.append(row)

    def _update_page(self) -> None:
        account = self._account
        self._menu_button.set_sensitive(account is not None)
        self._status_selector.set_account(account)
        self._status_message_row.set_account(account)

        if account is None:
            self._our_jid_row.set_subtitle("")
            self._account_label_row.set_subtitle("")
            self._avatar_image.set_from_paintable(None)
            return

        assert self._contact is not None

        account_label = app.settings.get_account_setting(account, "account_label")

        self._show_avatar_snapshot(self._avatar_snapshot)
        self._update_account_label(account_label)

        self._our_jid_row.set_subtitle(str(self._contact.jid))
        self._profile_name_row.set_subtitle(self._nickname)
        self._sync_control_state()
