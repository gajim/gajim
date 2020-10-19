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

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import Gio
from gi.repository import GObject

from gajim.gtk.util import get_builder
from gajim.gtk.util import EventHelper


class Assistant(Gtk.ApplicationWindow, EventHelper):

    __gsignals__ = dict(
        button_clicked=(
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            (str, )
        ),
        page_changed=(
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            (str, )
        ))

    def __init__(self,
                 transient_for=None,
                 width=550,
                 height=400,
                 transition_duration=200):
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

        self._pages = {}
        self._buttons = {}
        self._button_visible_func = None

        self._ui = get_builder('assistant.ui')
        self.add(self._ui.main_grid)

        self._ui.stack.set_transition_duration(transition_duration)

        self.connect('key-press-event', self._on_key_press_event)
        self.connect('destroy', self.__on_destroy)
        self._ui.connect_signals(self)

    def show_all(self):
        page_name = self._ui.stack.get_visible_child_name()
        buttons = self._button_visible_func(self, page_name)
        self._set_buttons_visible(buttons)
        self.update_page_complete()
        self.emit('page-changed', page_name)
        Gtk.ApplicationWindow.show_all(self)

    def _on_key_press_event(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def update_page_complete(self):
        page_widget = self._ui.stack.get_visible_child()
        for button, complete in self._buttons.values():
            if complete:
                button.set_sensitive(page_widget.complete)

    def update_title(self):
        self.set_title(self._ui.stack.get_visible_child().title)

    def set_button_visible_func(self, func):
        self._button_visible_func = func

    def set_default_button(self, button_name):
        button, _ = self._buttons[button_name]
        button.grab_default()

    def add_button(self, name, label, css_class=None, complete=False):
        button = Gtk.Button(label=label,
                            can_default=True,
                            no_show_all=True)
        button.connect('clicked', self.__on_button_clicked)
        if css_class is not None:
            button.get_style_context().add_class(css_class)
        self._buttons[name] = (button, complete)
        self._ui.action_area.pack_end(button, False, False, 0)

    def add_pages(self, pages):
        self._pages = pages
        for name, widget in pages.items():
            self._ui.stack.add_named(widget, name)

    def add_default_page(self, name):
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

    def get_current_page(self):
        return self._ui.stack.get_visible_child_name()

    def show_page(self, name, transition=Gtk.StackTransitionType.NONE):
        buttons = self._button_visible_func(self, name)
        self._set_buttons_visible(buttons)
        self._ui.stack.set_visible_child_full(name, transition)

    def get_page(self, name):
        return self._pages[name]

    def _set_buttons_visible(self, buttons):
        for button, _ in self._buttons.values():
            button.hide()

        if buttons is None:
            return

        for button_name in buttons:
            button, _ = self._buttons[button_name]
            button.show()

    def _on_visible_child_name(self, stack, _param):
        self.update_title()
        self.update_page_complete()
        self.emit('page-changed', stack.get_visible_child_name())

    def __on_button_clicked(self, button):
        for button_name, button_data in self._buttons.items():
            button_ = button_data[0]
            if button_ == button:
                self.emit('button-clicked', button_name)
                return

    def __on_destroy(self, *args):
        self._pages.clear()
        self._buttons.clear()


class Page(Gtk.Box):
    def __init__(self):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(18)
        self.set_valign(Gtk.Align.CENTER)

        self.title = ''
        self.complete = True


class DefaultPage(Page):
    def __init__(self, icon_name, icon_css_class):
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

    def set_heading(self, heading):
        self._heading.set_text(heading)

    def set_text(self, text):
        self._label.set_text(text)

    def set_title(self, title):
        self.title = title


class ErrorPage(DefaultPage):
    def __init__(self):
        DefaultPage.__init__(self,
                             icon_name='dialog-error-symbolic',
                             icon_css_class='error-color')


class SuccessPage(DefaultPage):
    def __init__(self):
        DefaultPage.__init__(self,
                             icon_name='object-select-symbolic',
                             icon_css_class='success-color')


class ProgressPage(Page):
    def __init__(self):
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

    def set_text(self, text):
        self._label.set_text(text)

    def set_title(self, title):
        self.title = title
