# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast
from typing import Literal
from typing import overload

from collections.abc import Callable

from gi.repository import Adw
from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common.ged import EventHelper

from gajim.gtk.builder import get_builder
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.window import GajimAppWindow


class Assistant(GajimAppWindow, EventHelper):
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
        GajimAppWindow.__init__(
            self,
            name=name,
            transient_for=transient_for,
            default_width=width,
            default_height=height,
        )

        EventHelper.__init__(self)

        self._pages: dict[str, AssistantPage] = {}
        self._buttons: dict[str, tuple[Gtk.Button, bool]] = {}
        self._button_visible_func = None

        self._ui = get_builder("assistant.ui")
        self._ui.main_box.add_css_class("window-padding")

        toolbar_view = Adw.ToolbarView(content=self._ui.main_box)
        toolbar_view.add_top_bar(Adw.HeaderBar())
        self.set_content(toolbar_view)

        self._ui.stack.set_transition_duration(transition_duration)

        self._connect(
            self._ui.stack, "notify::visible-child-name", self._on_visible_child_name
        )

    def show_first_page(self) -> None:
        page_name = self._ui.stack.get_visible_child_name()
        self.emit("page-changed", page_name)

    def _update_page_complete(self, *args: Any) -> None:
        page_widget = cast(AssistantPage, self._ui.stack.get_visible_child())
        for button, complete in self._buttons.values():
            if complete:
                button.set_sensitive(page_widget.complete)

    def update_title(self) -> None:
        page_widget = cast(AssistantPage, self._ui.stack.get_visible_child())
        self.set_title(page_widget.title)

    def _hide_buttons(self) -> None:
        for button, _complete in self._buttons.values():
            button.set_visible(False)

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
            button.set_visible(True)

    def set_button_visible_func(self, func: Callable[..., list[str]]) -> None:
        self._button_visible_func = func

    def set_default_button(self, button_name: str) -> None:
        button, _complete = self._buttons[button_name]
        self.set_default_widget(button)

    def add_button(
        self,
        name: str,
        label: str,
        css_class: str | None = None,
        complete: bool = False,
    ) -> None:
        button = Gtk.Button(label=label, visible=False)
        self._connect(button, "clicked", self.__on_button_clicked)
        if css_class is not None:
            button.add_css_class(css_class)
        self._buttons[name] = (button, complete)
        self._ui.action_area.append(button)

    def add_pages(self, pages: dict[str, AssistantPage]):
        for name, widget in pages.items():
            self._pages[name] = widget
            self._connect(widget, "update-page-complete", self._update_page_complete)
            self._ui.stack.add_named(widget, name)

    @overload
    def add_default_page(self, name: Literal["success"]) -> AssistantSuccessPage: ...

    @overload
    def add_default_page(self, name: Literal["error"]) -> AssistantErrorPage: ...

    @overload
    def add_default_page(self, name: Literal["progress"]) -> AssistantProgressPage: ...

    def add_default_page(self, name: str) -> AssistantPage:
        if name == "success":
            page = AssistantSuccessPage()
        elif name == "error":
            page = AssistantErrorPage()
        elif name == "progress":
            page = AssistantProgressPage()
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

    def get_page(self, name: str) -> AssistantPage:
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


class AssistantPage(Gtk.Box, SignalManager):
    __gtype_name__ = "AssistantPage"
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


class DefaultPage(AssistantPage):
    __gtype_name__ = "AssistantDefaultPage"

    def __init__(
        self, icon_name: str | None = None, icon_css_class: str | None = None
    ) -> None:
        AssistantPage.__init__(self)

        self._heading = Gtk.Label(
            max_width_chars=30,
            wrap=True,
            halign=Gtk.Align.CENTER,
            justify=Gtk.Justification.CENTER,
        )
        self._heading.add_css_class("title-1")
        self.append(self._heading)

        if icon_name is not None:
            icon = Gtk.Image.new_from_icon_name(icon_name)
            icon.set_pixel_size(64)
            if icon_css_class is not None:
                icon.add_css_class(icon_css_class)
            self.append(icon)

        self._label = Gtk.Label(
            wrap=True,
            max_width_chars=50,
            halign=Gtk.Align.CENTER,
            justify=Gtk.Justification.CENTER,
        )
        self.append(self._label)

    def set_heading(self, heading: str) -> None:
        self._heading.set_text(heading)

    def set_text(self, text: str) -> None:
        self._label.set_text(text)

    def set_title(self, title: str) -> None:
        self.title = title


class AssistantErrorPage(DefaultPage):
    __gtype_name__ = "AssistantErrorPage"

    def __init__(self) -> None:
        DefaultPage.__init__(
            self, icon_name="lucide-circle-x-symbolic", icon_css_class="error"
        )


class AssistantSuccessPage(DefaultPage):
    __gtype_name__ = "AssistantSuccessPage"

    def __init__(self) -> None:
        DefaultPage.__init__(
            self, icon_name="lucide-check-symbolic", icon_css_class="success"
        )


class AssistantProgressPage(AssistantPage):
    __gtype_name__ = "AssistantProgressPage"

    def __init__(self) -> None:
        AssistantPage.__init__(self)

        self._label = Gtk.Label(
            wrap=True,
            max_width_chars=50,
            halign=Gtk.Align.CENTER,
            justify=Gtk.Justification.CENTER,
        )

        spinner = Adw.Spinner()
        self.append(spinner)
        self.append(self._label)

    def set_text(self, text: str) -> None:
        self._label.set_text(text)

    def set_title(self, title: str) -> None:
        self.title = title
