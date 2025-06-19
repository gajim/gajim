# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast
from typing import Literal
from typing import overload

from collections.abc import Callable
from dataclasses import dataclass

from gi.repository import Adw
from gi.repository import Gtk

from gajim.common import app
from gajim.common.i18n import _

AppearanceT = Literal["default", "suggested", "destructive"]


@dataclass
class DialogResponse:
    response_id: str
    label: str
    appearance: AppearanceT = "default"
    is_default: bool = False


@dataclass
class CancelDialogResponse(DialogResponse):
    response_id: str = "cancel"
    label: str = _("_Cancel")
    appearance: AppearanceT = "default"
    is_default: bool = True


class DialogEntry(Gtk.Entry):
    def __init__(self, text: str = ""):
        Gtk.Entry.__init__(self, margin_start=50, margin_end=50)
        self.set_text(text)

    def get_value(self) -> str:
        return self.get_text()


class DialogCheckButton(Gtk.Box):
    def __init__(self, label: str):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)

        label_widget = Gtk.Label(
            wrap=True,
            max_width_chars=50,
            halign=Gtk.Align.START,
            margin_start=10,
        )
        label_widget.set_text_with_mnemonic(label)

        self._checkbutton = Gtk.CheckButton(
            child=label_widget,
            can_focus=False,
            margin_start=30,
            margin_end=30,
        )

        self.append(self._checkbutton)

    def get_value(self) -> bool:
        return self._checkbutton.get_active()


ExtraWidgetT = DialogEntry | DialogCheckButton | None


class _BaseAlertDialog(Adw.AlertDialog):
    def __init__(
        self,
        heading: str,
        body: str,
        *,
        body_use_markup: bool = False,
        responses: list[DialogResponse] | None = None,
        close_response: str = "close",
        emit_responses: list[str] | None = None,
        extra_widget: ExtraWidgetT = None,
        callback: Callable[..., None] | None = None,
        parent: Gtk.Window | None = None,
    ) -> None:
        if parent is None:
            parent = app.app.get_active_window()

        if responses is None:
            responses = []

        self._callback = callback
        self._emit_responses = emit_responses

        Adw.AlertDialog.__init__(
            self,
            heading=heading,
            body=body,
            body_use_markup=body_use_markup,
            prefer_wide_layout=True,
            close_response=close_response,
        )

        for response in responses:
            self.add_response(response.response_id, response.label)
            match response.appearance:
                case "suggested":
                    self.set_response_appearance(
                        response.response_id, Adw.ResponseAppearance.SUGGESTED
                    )
                case "destructive":
                    self.set_response_appearance(
                        response.response_id, Adw.ResponseAppearance.DESTRUCTIVE
                    )
                case _:
                    pass

            if response.is_default:
                self.set_default_response(response.response_id)

        self.set_extra_child(extra_widget)

        self.connect("response", self._on_response)
        self.present(parent)

        if extra_widget is not None:
            extra_widget.grab_focus()

    def _emit_response(self, response_id: str) -> None:
        if self._callback is None:
            return

        if self._emit_responses is not None and response_id not in self._emit_responses:
            return

        widget = cast(ExtraWidgetT, self.get_extra_child())

        args: list[Any] = []
        # Add the response_id as callback arg only if we emit more than one response
        if self._emit_responses is None or len(self._emit_responses) != 1:
            args.append(response_id)

        if widget is not None:
            args.append(widget.get_value())

        self._callback(*args)

    def _on_response(self, _dialog: Adw.AlertDialog, response_id: str) -> None:
        self._emit_response(response_id)


class AlertDialog(_BaseAlertDialog):
    pass


class InformationAlertDialog(_BaseAlertDialog):
    def __init__(
        self,
        heading: str,
        body: str,
        *,
        body_use_markup: bool = False,
        callback: Callable[[], None] | None = None,
        parent: Gtk.Window | None = None,
    ) -> None:

        _BaseAlertDialog.__init__(
            self,
            heading,
            body,
            body_use_markup=body_use_markup,
            responses=[
                DialogResponse("ok", _("_OK"), is_default=True),
            ],
            callback=callback,
            parent=parent,
        )

    def _emit_response(self, response_id: str) -> None:
        if self._callback is None:
            return

        self._callback()


class ConfirmationAlertDialog(_BaseAlertDialog):
    @overload
    def __init__(
        self,
        heading: str,
        body: str,
        confirm_label: str,
        *,
        body_use_markup: bool = ...,
        appearance: AppearanceT = ...,
        extra_widget: Literal[None] = ...,
        callback: Callable[[], None] | None = ...,
        parent: Gtk.Window | None = ...,
    ) -> None: ...

    @overload
    def __init__(
        self,
        heading: str,
        body: str,
        confirm_label: str,
        *,
        body_use_markup: bool = ...,
        appearance: AppearanceT = ...,
        extra_widget: DialogEntry = ...,
        callback: Callable[[str], None] | None = ...,
        parent: Gtk.Window | None = ...,
    ) -> None: ...

    def __init__(
        self,
        heading: str,
        body: str,
        confirm_label: str,
        *,
        body_use_markup: bool = False,
        appearance: AppearanceT = "default",
        extra_widget: ExtraWidgetT = None,
        callback: Callable[..., None] | None = None,
        parent: Gtk.Window | None = None,
    ) -> None:

        _BaseAlertDialog.__init__(
            self,
            heading,
            body,
            body_use_markup=body_use_markup,
            responses=[
                CancelDialogResponse(),
                DialogResponse("confirm", confirm_label, appearance=appearance),
            ],
            emit_responses=["confirm"],
            extra_widget=extra_widget,
            callback=callback,
            parent=parent,
        )
