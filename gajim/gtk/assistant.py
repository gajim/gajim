# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast
from typing import Literal
from typing import overload

from collections.abc import Callable

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.ged import EventHelper

from gajim.gtk.builder import get_builder
from gajim.gtk.util import SignalManager
from gajim.gtk.widgets import GajimAppWindow


class Assistant(GObject.Object, GajimAppWindow, EventHelper):

    __gsignals__ = {
        "button-clicked": (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            (str,),
        ),
        "page-changed": (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            (str,),
        ),
    }

    def __init__(
        self,
        name: str = "Assistant",
        transient_for: Gtk.Window | None = None,
        width: int = 550,
        height: int = 400,
        transition_duration: int = 200,
    ) -> None:
        GObject.Object.__init__(self)
        GajimAppWindow.__init__(
            self,
            name=name,
            transient_for=transient_for,
            default_width=width,
            default_height=height,
        )

        EventHelper.__init__(self)

        self._pages: dict[str, Page] = {}
        self._buttons: dict[str, tuple[Gtk.Button, bool]] = {}
        self._button_visible_func = None

        self._ui = get_builder("assistant.ui")
        self.set_child(self._ui.main_grid)

        self._ui.stack.set_transition_duration(transition_duration)

        self._connect(
            self._ui.stack, "notify::visible-child-name", self._on_visible_child_name
        )

    def show_all(self) -> None:
        page_name = self._ui.stack.get_visible_child_name()
        self.emit("page-changed", page_name)
        self.window.show()

    def _update_page_complete(self, *args: Any) -> None:
        page_widget = cast(Page, self._ui.stack.get_visible_child())
        for button, complete in self._buttons.values():
            if complete:
                button.set_sensitive(page_widget.complete)

    def update_title(self) -> None:
        page_widget = cast(Page, self._ui.stack.get_visible_child())
        self.window.set_title(page_widget.title)

    def _hide_buttons(self) -> None:
        for button, _complete in self._buttons.values():
            button.hide()

    def _set_buttons_visible(self) -> None:
        page_name = self._ui.stack.get_visible_child_name()
        assert page_name is not None
        if self._button_visible_func is None:
            buttons = self.get_page(page_name).get_visible_buttons()
            if buttons is not None:
                if len(buttons) == 1:
                    default = buttons[0]
                else:
                    default = self.get_page(page_name).get_default_button()
                if default is not None:
                    self.set_default_button(default)
        else:
            buttons = self._button_visible_func(self, page_name)

        self._update_page_complete()

        if buttons is None:
            return

        for button_name in buttons:
            button, _complete = self._buttons[button_name]
            button.show()

    def set_button_visible_func(self, func: Callable[..., list[str]]) -> None:
        self._button_visible_func = func

    def set_default_button(self, button_name: str) -> None:
        button, _complete = self._buttons[button_name]
        self.window.set_default_widget(button)

    def add_button(
        self,
        name: str,
        label: str,
        css_class: str | None = None,
        complete: bool = False,
    ) -> None:
        button = Gtk.Button(label=label, visible=False)
        button.connect("clicked", self.__on_button_clicked)
        if css_class is not None:
            button.add_css_class(css_class)
        self._buttons[name] = (button, complete)
        self._ui.action_area.append(button)

    def add_pages(self, pages: dict[str, Page]):
        for name, widget in pages.items():
            self._pages[name] = widget
            self._connect(widget, "update-page-complete", self._update_page_complete)
            self._ui.stack.add_named(widget, name)

    @overload
    def add_default_page(self, name: Literal["success"]) -> SuccessPage: ...

    @overload
    def add_default_page(self, name: Literal["error"]) -> ErrorPage: ...

    @overload
    def add_default_page(self, name: Literal["progress"]) -> ProgressPage: ...

    def add_default_page(self, name: str) -> Page:
        if name == "success":
            page = SuccessPage()
        elif name == "error":
            page = ErrorPage()
        elif name == "progress":
            page = ProgressPage()
        else:
            raise ValueError("Unknown page: %s" % name)

        self._pages[name] = page
        self._ui.stack.add_named(page, name)
        return page

    def get_current_page(self) -> str:
        name = self._ui.stack.get_visible_child_name()
        assert name is not None
        return name

    def show_page(
        self,
        name: str,
        transition: Gtk.StackTransitionType = Gtk.StackTransitionType.NONE,
    ) -> None:

        if self._ui.stack.get_visible_child_name() == name:
            return
        self._hide_buttons()
        self._ui.stack.set_visible_child_full(name, transition)

    def get_page(self, name: str) -> Page:
        return self._pages[name]

    def _on_visible_child_name(self, stack: Gtk.Stack, _param: str) -> None:
        if stack.get_visible_child_name() is None:
            # Happens for some reason when adding the first page
            return
        self.update_title()
        self._set_buttons_visible()
        self.emit("page-changed", stack.get_visible_child_name())

    def __on_button_clicked(self, button: Gtk.Button) -> None:
        for button_name, button_data in self._buttons.items():
            button_ = button_data[0]
            if button_ == button:
                self.emit("button-clicked", button_name)
                return

    def _cleanup(self) -> None:
        self.unregister_events()
        self._pages.clear()
        del self._pages
        self._buttons.clear()
        del self._buttons
        del self._button_visible_func
        self.run_dispose()


class Page(Gtk.Box, SignalManager):

    __gsignals__ = {
        "update-page-complete": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self) -> None:
        Gtk.Box.__init__(
            self,
            orientation=Gtk.Orientation.VERTICAL,
            spacing=18,
            valign=Gtk.Align.CENTER,
        )
        SignalManager.__init__(self)

        self.title: str = ""
        self.complete: bool = True

    def do_unroot(self) -> None:
        Gtk.Box.do_unroot(self)
        self._disconnect_all()
        app.check_finalize(self)

    def get_visible_buttons(self) -> list[str] | None:
        return None

    def get_default_button(self) -> str | None:
        return None

    def update_page_complete(self) -> None:
        self.emit("update-page-complete")


class DefaultPage(Page):
    def __init__(self, icon_name: str, icon_css_class: str) -> None:
        Page.__init__(self)

        self._heading = Gtk.Label()
        self._heading.add_css_class("large-header")
        self._heading.set_max_width_chars(30)
        self._heading.set_wrap(True)
        self._heading.set_wrap_mode(Pango.WrapMode.WORD)
        self._heading.set_halign(Gtk.Align.CENTER)
        self._heading.set_justify(Gtk.Justification.CENTER)

        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(64)
        icon.add_css_class(icon_css_class)

        self._label = Gtk.Label()
        self._label.set_max_width_chars(50)
        self._label.set_wrap(True)
        self._label.set_wrap_mode(Pango.WrapMode.WORD)
        self._label.set_halign(Gtk.Align.CENTER)
        self._label.set_justify(Gtk.Justification.CENTER)

        self.append(self._heading)
        self.append(icon)
        self.append(self._label)

    def set_heading(self, heading: str) -> None:
        self._heading.set_text(heading)

    def set_text(self, text: str) -> None:
        self._label.set_text(text)

    def set_title(self, title: str) -> None:
        self.title = title


class ErrorPage(DefaultPage):
    def __init__(self) -> None:
        DefaultPage.__init__(
            self, icon_name="dialog-error-symbolic", icon_css_class="error-color"
        )


class SuccessPage(DefaultPage):
    def __init__(self) -> None:
        DefaultPage.__init__(
            self, icon_name="object-select-symbolic", icon_css_class="success-color"
        )


class ProgressPage(Page):
    def __init__(self) -> None:
        Page.__init__(self)

        self._label = Gtk.Label()
        self._label.set_max_width_chars(50)
        self._label.set_wrap(True)
        self._label.set_wrap_mode(Pango.WrapMode.WORD)
        self._label.set_halign(Gtk.Align.CENTER)
        self._label.set_justify(Gtk.Justification.CENTER)

        spinner = Gtk.Spinner()
        spinner.start()

        self.append(spinner)
        self.append(self._label)

    def set_text(self, text: str) -> None:
        self._label.set_text(text)

    def set_title(self, title: str) -> None:
        self.title = title
