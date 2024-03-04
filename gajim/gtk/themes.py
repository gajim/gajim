# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast
from typing import NamedTuple

from enum import IntEnum

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.const import StyleAttr
from gajim.common.events import StyleChanged
from gajim.common.events import ThemeUpdate
from gajim.common.i18n import _

from gajim.gtk.builder import get_builder
from gajim.gtk.dialogs import ConfirmationDialog
from gajim.gtk.dialogs import DialogButton
from gajim.gtk.dialogs import ErrorDialog
from gajim.gtk.preferences import Preferences
from gajim.gtk.util import get_app_window


class StyleOption(NamedTuple):
    label: str
    selector: str
    attr: StyleAttr


CSS_STYLE_OPTIONS: list[StyleOption] = [
    StyleOption(_('Conversation: Text Font'),
                '.gajim-conversation-text',
                StyleAttr.FONT),

    StyleOption(_('Conversation: Text Color'),
                '.gajim-conversation-text',
                StyleAttr.COLOR),

    StyleOption(_('Conversation: URL Color'),
                '.gajim-url',
                StyleAttr.COLOR),

    StyleOption(_('Conversation: Nickname Color (Incoming)'),
                '.gajim-incoming-nickname',
                StyleAttr.COLOR),

    StyleOption(_('Conversation: Nickname Color (Outgoing)'),
                '.gajim-outgoing-nickname',
                StyleAttr.COLOR),

    StyleOption(_('Mention: Message Background Color'),
                '.gajim-mention-highlight',
                StyleAttr.BACKGROUND),

    StyleOption(_('Status Message: Text Color'),
                '.gajim-status-message',
                StyleAttr.COLOR),

    StyleOption(_('Status Message: Text Font'),
                '.gajim-status-message',
                StyleAttr.FONT),

    StyleOption(_('Message Correction: Background Color'),
                '.gajim-msg-correcting text',
                StyleAttr.BACKGROUND),

    StyleOption(_('Chat Banner: Foreground Color'),
                '.gajim-banner',
                StyleAttr.COLOR),

    StyleOption(_('Chat Banner: Background Color'),
                '.gajim-banner',
                StyleAttr.BACKGROUND),

    StyleOption(_('Chat Banner: Text Font'),
                '.gajim-banner',
                StyleAttr.FONT),

    StyleOption(_('Contact List: Group Foreground Color'),
                '.gajim-group-row',
                StyleAttr.COLOR),

    StyleOption(_('Contact List: Group Background Color'),
                '.gajim-group-row',
                StyleAttr.BACKGROUND),

    StyleOption(_('Contact List: Group Font'),
                '.gajim-group-row',
                StyleAttr.FONT),

    StyleOption(_('Contact List: Contact Foreground Color'),
                '.gajim-contact-row',
                StyleAttr.COLOR),

    StyleOption(_('Contact List: Contact Background Color'),
                '.gajim-contact-row',
                StyleAttr.BACKGROUND),

    StyleOption(_('Contact List: Contact Font'),
                '.gajim-contact-row',
                StyleAttr.FONT),

    StyleOption(_('Status: Online Color'),
                '.gajim-status-online',
                StyleAttr.COLOR),

    StyleOption(_('Status: Away Color'),
                '.gajim-status-away',
                StyleAttr.COLOR),

    StyleOption(_('Status: DND Color'),
                '.gajim-status-dnd',
                StyleAttr.COLOR),

    StyleOption(_('Status: Offline Color'),
                '.gajim-status-offline',
                StyleAttr.COLOR),
]


class Column(IntEnum):
    THEME = 0


class Themes(Gtk.ApplicationWindow):
    def __init__(self, transient: Gtk.Window) -> None:
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_title(_('Gajim Themes'))
        self.set_name('ThemesWindow')
        self.set_show_menubar(False)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_transient_for(transient)
        self.set_resizable(True)
        self.set_default_size(600, 400)
        self.set_modal(True)

        self._ui = get_builder('themes_window.ui')
        self.add(self._ui.theme_grid)

        self._get_themes()
        self._ui.option_listbox.set_placeholder(self._ui.placeholder)

        self._ui.connect_signals(self)
        self.connect_after('key-press-event', self._on_key_press)

        self.show_all()

        self._fill_choose_listbox()

    def _on_key_press(self,
                      _widget: Gtk.Widget,
                      event: Gdk.EventKey
                      ) -> None:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _get_themes(self) -> None:
        current_theme = app.settings.get('roster_theme')
        for theme in app.css_config.themes:
            if theme == current_theme:
                self._ui.theme_store.prepend([theme])
                continue
            self._ui.theme_store.append([theme])

    def _on_theme_name_edit(self,
                            _renderer: Gtk.CellRendererText,
                            path: str,
                            new_name: str) -> None:
        iter_ = self._ui.theme_store.get_iter(path)
        old_name = self._ui.theme_store[iter_][Column.THEME]

        if new_name == 'default':
            ErrorDialog(
                _('Invalid Name'),
                _('Name <b>default</b> is not allowed'),
                secondary_use_markup=True)
            return

        if ' ' in new_name:
            ErrorDialog(
                _('Invalid Name'),
                _('Spaces are not allowed'))
            return

        if new_name == '':
            return

        result = app.css_config.rename_theme(old_name, new_name)
        if result is False:
            return

        app.settings.set('roster_theme', new_name)
        self._ui.theme_store.set_value(iter_, Column.THEME, new_name)

    def _select_theme_row(self, iter_: Gtk.TreeIter) -> None:
        self._ui.theme_treeview.get_selection().select_iter(iter_)

    def _on_theme_selected(self, tree_selection: Gtk.TreeSelection) -> None:
        store, iter_ = tree_selection.get_selected()
        if iter_ is None:
            self._clear_options()
            return
        theme = store[iter_][Column.THEME]
        app.css_config.change_preload_theme(theme)

        self._ui.remove_theme_button.set_sensitive(True)
        self._load_options()
        self._apply_theme(theme)
        app.ged.raise_event(StyleChanged())

    def _load_options(self) -> None:
        self._ui.option_listbox.foreach(self._remove_option)
        for option in CSS_STYLE_OPTIONS:
            value = app.css_config.get_value(
                option.selector, option.attr, pre=True)

            if value is None:
                continue

            row = Option(option, value)
            self._ui.option_listbox.add(row)

    def _add_option(self, _listbox: Gtk.ListBox, row: Option) -> None:
        # Add theme if there is none
        store, _ = self._ui.theme_treeview.get_selection().get_selected()
        first = store.get_iter_first()
        if first is None:
            self._on_add_new_theme()

        # Don't add an option twice
        for option in self._ui.option_listbox.get_children():
            if option == row:
                return

        # Get default value if it exists
        value = app.css_config.get_value(
            row.option.selector, row.option.attr)

        row = Option(row.option, value)
        self._ui.option_listbox.add(row)
        self._ui.option_popover.popdown()

    def _clear_options(self) -> None:
        self._ui.option_listbox.foreach(self._remove_option)

    def _fill_choose_listbox(self) -> None:
        for option in CSS_STYLE_OPTIONS:
            self._ui.choose_option_listbox.add(ChooseOption(option))

    def _remove_option(self, row: Gtk.ListBoxRow) -> None:
        self._ui.option_listbox.remove(row)
        row.destroy()

    def _on_add_new_theme(self, *args: Any) -> None:
        name = self._create_theme_name()
        if not app.css_config.add_new_theme(name):
            return

        self._update_preferences_window()

        self._ui.remove_theme_button.set_sensitive(True)
        iter_ = self._ui.theme_store.append([name])
        self._select_theme_row(iter_)
        self._apply_theme(name)

    def reload_roster_theme(self) -> None:
        tree_selection = self._ui.theme_treeview.get_selection()
        store, iter_ = tree_selection.get_selected()
        if iter_ is None:
            return
        theme = store[iter_][Column.THEME]
        self._apply_theme(theme)

    @staticmethod
    def _apply_theme(theme: str) -> None:
        app.settings.set('roster_theme', theme)
        app.css_config.change_theme(theme)
        app.ged.raise_event(ThemeUpdate())

    @staticmethod
    def _update_preferences_window() -> None:
        window = cast(Preferences | None, get_app_window('Preferences'))
        if window is not None:
            window.update_theme_list()

    @staticmethod
    def _create_theme_name() -> str:
        index = 0
        while f'newtheme{index}' in app.css_config.themes:
            index += 1
        return f'newtheme{index}'

    def _on_remove_theme(self, *args: Any) -> None:
        store, iter_ = self._ui.theme_treeview.get_selection().get_selected()
        if iter_ is None:
            return

        theme = store[iter_][Column.THEME]

        def _remove_theme():
            if theme == app.settings.get('roster_theme'):
                self._apply_theme('default')
                app.ged.raise_event(StyleChanged())

            app.css_config.remove_theme(theme)
            self._update_preferences_window()
            assert isinstance(store, Gtk.ListStore)
            assert iter_ is not None
            store.remove(iter_)

            first = store.get_iter_first()
            if first is None:
                self._ui.remove_theme_button.set_sensitive(False)
                self._clear_options()

        text = _('Do you want to delete this theme?')
        if theme == app.settings.get('roster_theme'):
            text = _('This is the theme you are currently using.\n'
                     'Do you want to delete this theme?')

        ConfirmationDialog(
            _('Delete'),
            _('Delete Theme'),
            text,
            [DialogButton.make('Cancel'),
             DialogButton.make('Delete',
                               callback=_remove_theme)],
            transient_for=self).show()


class Option(Gtk.ListBoxRow):
    def __init__(self,
                 option: StyleOption,
                 value: str | Pango.FontDescription | None
                 ) -> None:
        Gtk.ListBoxRow.__init__(self)
        self.option = option
        self._box = Gtk.Box(spacing=12)

        label = Gtk.Label()
        label.set_text(option.label)
        label.set_hexpand(True)
        label.set_halign(Gtk.Align.START)
        self._box.add(label)

        if option.attr in (StyleAttr.COLOR, StyleAttr.BACKGROUND):
            assert not isinstance(value, Pango.FontDescription)
            self._init_color(value)
        elif option.attr == StyleAttr.FONT:
            assert not isinstance(value, str)
            self._init_font(value)

        remove_button = Gtk.Button.new_from_icon_name(
            'list-remove-symbolic', Gtk.IconSize.MENU)
        remove_button.set_tooltip_text(_('Remove Setting'))
        remove_button.get_style_context().add_class('theme_remove_button')
        remove_button.connect('clicked', self._on_remove)
        self._box.add(remove_button)

        self.add(self._box)
        self.show_all()

    def _init_color(self, color: str | None) -> None:
        color_button = Gtk.ColorButton()
        if color is not None:
            rgba = Gdk.RGBA()
            rgba.parse(color)
            color_button.set_rgba(rgba)
        color_button.set_halign(Gtk.Align.END)
        color_button.connect('color-set', self._on_color_set)
        self._box.add(color_button)

    def _init_font(self, desc: Pango.FontDescription | None) -> None:
        font_button = Gtk.FontButton()
        if desc is not None:
            font_button.set_font_desc(desc)
        font_button.set_halign(Gtk.Align.END)
        font_button.connect('font-set', self._on_font_set)
        self._box.add(font_button)

    def _on_color_set(self, color_button: Gtk.ColorButton) -> None:
        color = color_button.get_rgba()
        color_string = color.to_string()
        app.css_config.set_value(
            self.option.selector, self.option.attr, color_string, pre=True)
        app.ged.raise_event(StyleChanged())
        themes_win = cast(Themes, self.get_toplevel())
        themes_win.reload_roster_theme()

    def _on_font_set(self, font_button: Gtk.FontButton) -> None:
        desc = font_button.get_font_desc()
        if desc is None:
            return
        app.css_config.set_font(self.option.selector, desc, pre=True)
        app.ged.raise_event(StyleChanged())
        themes_win = cast(Themes, self.get_toplevel())
        themes_win.reload_roster_theme()

    def _on_remove(self, *args: Any) -> None:
        listbox = cast(Gtk.ListBox, self.get_parent())
        listbox.remove(self)
        app.css_config.remove_value(
            self.option.selector, self.option.attr, pre=True)
        app.ged.raise_event(StyleChanged())
        self.destroy()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ChooseOption):
            raise NotImplementedError
        return other.option == self.option


class ChooseOption(Gtk.ListBoxRow):
    def __init__(self, option: StyleOption) -> None:
        Gtk.ListBoxRow.__init__(self)
        self.option = option
        label = Gtk.Label(label=option.label)
        label.set_xalign(0)
        self.add(label)
        self.show_all()
