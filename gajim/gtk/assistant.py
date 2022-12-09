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
from typing import Callable
from typing import cast
from typing import Literal
from typing import Optional
from typing import overload

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import Gio
from gi.repository import GObject

from .builder import get_builder
from .util import EventHelper


class Assistant(Gtk.ApplicationWindow, EventHelper):

    __gsignals__ = {
        'button-clicked': (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            (str, )
        ),
        'page-changed': (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            (str, )
        )}

    def __init__(self,
                 transient_for: Optional[Gtk.Window] = None,
                 width: int = 550,
                 height: int = 400,
                 transition_duration: int = 200) -> None:
        Gtk.ApplicationWindow.__init__(self)
        EventHelper.__init__(self)
        self.set_application(Gio.Application.get_default())
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_name('Assistant')
        self.set_default_size(width, height)
        self.set_resizable(True)
        self.set_transient_for(transient_for)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)

        self._pages: dict[str, Page] = {}
        self._buttons: dict[str, tuple[Gtk.Button, bool]] = {}
        self._button_visible_func = None

        self._ui = get_builder('assistant.ui')
        self.add(self._ui.main_grid)

        self._ui.stack.set_transition_duration(transition_duration)

        self.connect('key-press-event', self._on_key_press_event)
        self.connect('destroy', self.__on_destroy)
        self._ui.connect_signals(self)

    def show_all(self) -> None:
        page_name = self._ui.stack.get_visible_child_name()
        self.emit('page-changed', page_name)
        Gtk.ApplicationWindow.show_all(self)

    def _on_key_press_event(self,
                            _widget: Gtk.Widget,
                            event: Gdk.EventKey
                            ) -> None:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _update_page_complete(self, *args: Any) -> None:
        page_widget = cast(Page, self._ui.stack.get_visible_child())
        for button, complete in self._buttons.values():
            if complete:
                button.set_sensitive(page_widget.complete)

    def update_title(self) -> None:
        page_widget = cast(Page, self._ui.stack.get_visible_child())
        self.set_title(page_widget.title)

    def _hide_buttons(self) -> None:
        for button, _ in self._buttons.values():
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
            button, _ = self._buttons[button_name]
            button.show()

    def set_button_visible_func(self, func: Callable[..., list[str]]) -> None:
        self._button_visible_func = func

    def set_default_button(self, button_name: str) -> None:
        button, _ = self._buttons[button_name]
        button.grab_default()

    def add_button(self,
                   name: str,
                   label: str,
                   css_class: Optional[str] = None,
                   complete: bool = False
                   ) -> None:
        button = Gtk.Button(label=label,
                            can_default=True,
                            no_show_all=True)
        button.connect('clicked', self.__on_button_clicked)
        if css_class is not None:
            button.get_style_context().add_class(css_class)
        self._buttons[name] = (button, complete)
        self._ui.action_area.pack_end(button, False, False, 0)

    def add_pages(self, pages: dict[str, Page]):
        for name, widget in pages.items():
            self._pages[name] = widget
            widget.connect('update-page-complete', self._update_page_complete)
            self._ui.stack.add_named(widget, name)

    @overload
    def add_default_page(self, name: Literal['success']) -> SuccessPage: ...

    @overload
    def add_default_page(self, name: Literal['error']) -> ErrorPage: ...

    @overload
    def add_default_page(self, name: Literal['progress']) -> ProgressPage: ...

    def add_default_page(self, name: str) -> Page:
        if name == 'success':
            page = SuccessPage()
        elif name == 'error':
            page = ErrorPage()
        elif name == 'progress':
            page = ProgressPage()
        else:
            raise ValueError('Unknown page: %s' % name)

        self._pages[name] = page
        self._ui.stack.add_named(page, name)
        return page

    def get_current_page(self) -> str:
        name = self._ui.stack.get_visible_child_name()
        assert name is not None
        return name

    def show_page(self,
                  name: str,
                  transition: Gtk.StackTransitionType =
                  Gtk.StackTransitionType.NONE) -> None:

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
        self.emit('page-changed', stack.get_visible_child_name())

    def __on_button_clicked(self, button: Gtk.Button) -> None:
        for button_name, button_data in self._buttons.items():
            button_ = button_data[0]
            if button_ == button:
                self.emit('button-clicked', button_name)
                return

    def __on_destroy(self, *args: Any) -> None:
        self._pages.clear()
        self._buttons.clear()


class Page(Gtk.Box):

    __gsignals__ = {
        'update-page-complete': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(18)
        self.set_valign(Gtk.Align.CENTER)

        self.title: str = ''
        self.complete: bool = True

    def get_visible_buttons(self) -> Optional[list[str]]:
        return None

    def get_default_button(self) -> Optional[str]:
        return None

    def update_page_complete(self) -> None:
        self.emit('update-page-complete')


class DefaultPage(Page):
    def __init__(self, icon_name: str, icon_css_class: str) -> None:
        Page.__init__(self)

        self._heading = Gtk.Label()
        self._heading.get_style_context().add_class('large-header')
        self._heading.set_max_width_chars(30)
        self._heading.set_line_wrap(True)
        self._heading.set_halign(Gtk.Align.CENTER)
        self._heading.set_justify(Gtk.Justification.CENTER)

        icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.DIALOG)
        icon.get_style_context().add_class(icon_css_class)

        self._label = Gtk.Label()
        self._label.set_max_width_chars(50)
        self._label.set_line_wrap(True)
        self._label.set_halign(Gtk.Align.CENTER)
        self._label.set_justify(Gtk.Justification.CENTER)

        self.pack_start(self._heading, False, True, 0)
        self.pack_start(icon, False, True, 0)
        self.pack_start(self._label, False, True, 0)
        self.show_all()

    def set_heading(self, heading: str) -> None:
        self._heading.set_text(heading)

    def set_text(self, text: str) -> None:
        self._label.set_text(text)

    def set_title(self, title: str) -> None:
        self.title = title


class ErrorPage(DefaultPage):
    def __init__(self) -> None:
        DefaultPage.__init__(self,
                             icon_name='dialog-error-symbolic',
                             icon_css_class='error-color')


class SuccessPage(DefaultPage):
    def __init__(self) -> None:
        DefaultPage.__init__(self,
                             icon_name='object-select-symbolic',
                             icon_css_class='success-color')


class ProgressPage(Page):
    def __init__(self) -> None:
        Page.__init__(self)

        self._label = Gtk.Label()
        self._label.set_max_width_chars(50)
        self._label.set_line_wrap(True)
        self._label.set_halign(Gtk.Align.CENTER)
        self._label.set_justify(Gtk.Justification.CENTER)

        spinner = Gtk.Spinner()
        spinner.start()

        self.pack_start(spinner, True, True, 0)
        self.pack_start(self._label, False, True, 0)

        self.show_all()

    def set_text(self, text: str) -> None:
        self._label.set_text(text)

    def set_title(self, title: str) -> None:
        self.title = title
