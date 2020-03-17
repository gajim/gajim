# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
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

from collections import namedtuple
from enum import IntEnum

from gi.repository import Gtk
from gi.repository import Gdk

from gajim.common import app
from gajim.common.nec import NetworkEvent
from gajim.common.i18n import _
from gajim.common.const import StyleAttr

from gajim.gtk.dialogs import ErrorDialog
from gajim.gtk.dialogs import DialogButton
from gajim.gtk.dialogs import NewConfirmationDialog
from gajim.gtk.util import get_builder
from gajim.gtk.util import get_app_window

StyleOption = namedtuple('StyleOption', 'label selector attr')

CSS_STYLE_OPTIONS = [
    StyleOption(_('Chatstate Composing'),
                '.gajim-state-composing',
                StyleAttr.COLOR),

    StyleOption(_('Chatstate Inactive'),
                '.gajim-state-inactive',
                StyleAttr.COLOR),

    StyleOption(_('Chatstate Gone'),
                '.gajim-state-gone',
                StyleAttr.COLOR),

    StyleOption(_('Chatstate Paused'),
                '.gajim-state-paused',
                StyleAttr.COLOR),

    StyleOption(_('Group Chat Tab New Directed Message'),
                '.gajim-state-tab-muc-directed-msg',
                StyleAttr.COLOR),

    StyleOption(_('Group Chat Tab New Message'),
                '.gajim-state-tab-muc-msg',
                StyleAttr.COLOR),

    StyleOption(_('Banner Foreground Color'),
                '.gajim-banner',
                StyleAttr.COLOR),

    StyleOption(_('Banner Background Color'),
                '.gajim-banner',
                StyleAttr.BACKGROUND),

    StyleOption(_('Banner Font'),
                '.gajim-banner',
                StyleAttr.FONT),

    StyleOption(_('Account Row Foreground Color'),
                '.gajim-account-row',
                StyleAttr.COLOR),

    StyleOption(_('Account Row Background Color'),
                '.gajim-account-row',
                StyleAttr.BACKGROUND),

    StyleOption(_('Account Row Font'),
                '.gajim-account-row',
                StyleAttr.FONT),

    StyleOption(_('Group Row Foreground Color'),
                '.gajim-group-row',
                StyleAttr.COLOR),

    StyleOption(_('Group Row Background Color'),
                '.gajim-group-row',
                StyleAttr.BACKGROUND),

    StyleOption(_('Group Row Font'),
                '.gajim-group-row',
                StyleAttr.FONT),

    StyleOption(_('Contact Row Foreground Color'),
                '.gajim-contact-row',
                StyleAttr.COLOR),

    StyleOption(_('Contact Row Background Color'),
                '.gajim-contact-row',
                StyleAttr.BACKGROUND),

    StyleOption(_('Contact Row Font'),
                '.gajim-contact-row',
                StyleAttr.FONT),

    StyleOption(_('Conversation Font'),
                '.gajim-conversation-font',
                StyleAttr.FONT),

    StyleOption(_('Incoming Nickname Color'),
                '.gajim-incoming-nickname',
                StyleAttr.COLOR),

    StyleOption(_('Outgoing Nickname Color'),
                '.gajim-outgoing-nickname',
                StyleAttr.COLOR),

    StyleOption(_('Incoming Message Text Color'),
                '.gajim-incoming-message-text',
                StyleAttr.COLOR),

    StyleOption(_('Incoming Message Text Font'),
                '.gajim-incoming-message-text',
                StyleAttr.FONT),

    StyleOption(_('Outgoing Message Text Color'),
                '.gajim-outgoing-message-text',
                StyleAttr.COLOR),

    StyleOption(_('Outgoing Message Text Font'),
                '.gajim-outgoing-message-text',
                StyleAttr.FONT),

    StyleOption(_('Status Message Color'),
                '.gajim-status-message',
                StyleAttr.COLOR),

    StyleOption(_('Status Message Font'),
                '.gajim-status-message',
                StyleAttr.FONT),

    StyleOption(_('URL Color'),
                '.gajim-url',
                StyleAttr.COLOR),

    StyleOption(_('Highlight Message Color'),
                '.gajim-highlight-message',
                StyleAttr.COLOR),

    StyleOption(_('Message Correcting'),
                '.gajim-msg-correcting text',
                StyleAttr.BACKGROUND),

    StyleOption(_('Contact Disconnected Background'),
                '.gajim-roster-disconnected',
                StyleAttr.BACKGROUND),

    StyleOption(_('Contact Connected Background '),
                '.gajim-roster-connected',
                StyleAttr.BACKGROUND),
    StyleOption(_('Status Online Color'),
                '.gajim-status-online',
                StyleAttr.COLOR),
    StyleOption(_('Status Away Color'),
                '.gajim-status-away',
                StyleAttr.COLOR),
    StyleOption(_('Status DND Color'),
                '.gajim-status-dnd',
                StyleAttr.COLOR),
    StyleOption(_('Status Offline Color'),
                '.gajim-status-offline',
                StyleAttr.COLOR),
]


class Column(IntEnum):
    THEME = 0


class Themes(Gtk.ApplicationWindow):
    def __init__(self, transient):
        Gtk.Window.__init__(self)
        self.set_application(app.app)
        self.set_title(_('Gajim Themes'))
        self.set_name('ThemesWindow')
        self.set_show_menubar(False)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_transient_for(transient)
        self.set_resizable(True)
        self.set_default_size(600, 400)

        self._ui = get_builder('themes_window.ui')
        self.add(self._ui.theme_grid)

        self._get_themes()
        self._ui.option_listbox.set_placeholder(self._ui.placeholder)

        self._ui.connect_signals(self)
        self.connect('destroy', self._on_destroy)
        self.show_all()

        self._fill_choose_listbox()

    def _get_themes(self):
        for theme in app.css_config.themes:
            self._ui.theme_store.append([theme])

    def _on_theme_name_edit(self, _renderer, path, new_name):
        iter_ = self._ui.theme_store.get_iter(path)
        old_name = self._ui.theme_store[iter_][Column.THEME]

        if new_name == 'default':
            ErrorDialog(
                _('Invalid Name'),
                _('Name <b>default</b> is not allowed'),
                transient_for=self)
            return

        if ' ' in new_name:
            ErrorDialog(
                _('Invalid Name'),
                _('Spaces are not allowed'),
                transient_for=self)
            return

        if new_name == '':
            return

        result = app.css_config.rename_theme(old_name, new_name)
        if result is False:
            return

        self._ui.theme_store.set_value(iter_, Column.THEME, new_name)

    def _select_theme_row(self, iter_):
        self._ui.theme_treeview.get_selection().select_iter(iter_)

    def _on_theme_selected(self, tree_selection):
        store, iter_ = tree_selection.get_selected()
        if iter_ is None:
            self._clear_options()
            return
        theme = store[iter_][Column.THEME]
        app.css_config.change_preload_theme(theme)

        self._ui.remove_theme_button.set_sensitive(True)
        self._load_options()

    def _load_options(self):
        self._ui.option_listbox.foreach(self._remove_option)
        for option in CSS_STYLE_OPTIONS:
            value = app.css_config.get_value(
                option.selector, option.attr, pre=True)

            if value is None:
                continue

            row = Option(option, value)
            self._ui.option_listbox.add(row)

    def _add_option(self, _listbox, row):
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

    def _clear_options(self):
        self._ui.option_listbox.foreach(self._remove_option)

    def _fill_choose_listbox(self):
        for option in CSS_STYLE_OPTIONS:
            self._ui.choose_option_listbox.add(ChooseOption(option))

    def _remove_option(self, row):
        self._ui.option_listbox.remove(row)
        row.destroy()

    def _on_add_new_theme(self, *args):
        name = self._create_theme_name()
        if not app.css_config.add_new_theme(name):
            return

        self._ui.remove_theme_button.set_sensitive(True)
        iter_ = self._ui.theme_store.append([name])
        self._select_theme_row(iter_)
        self._apply_theme(name)

    @staticmethod
    def _apply_theme(theme):
        app.config.set('roster_theme', theme)
        app.css_config.change_theme(theme)
        app.nec.push_incoming_event(NetworkEvent('theme-update'))

        # Begin repainting themed widgets throughout
        app.interface.roster.repaint_themed_widgets()
        app.interface.roster.change_roster_style(None)

        # Update Preferences theme combobox
        window = get_app_window('Preferences')
        if window is not None:
            window.update_theme_list()

    @staticmethod
    def _create_theme_name():
        i = 0
        while 'newtheme%s' % i in app.css_config.themes:
            i += 1
        return 'newtheme%s' % i

    def _on_remove_theme(self, *args):
        store, iter_ = self._ui.theme_treeview.get_selection().get_selected()
        if iter_ is None:
            return

        theme = store[iter_][Column.THEME]

        def _remove_theme():
            if theme == app.config.get('roster_theme'):
                self._apply_theme('default')

            app.css_config.remove_theme(theme)
            store.remove(iter_)

            first = store.get_iter_first()
            if first is None:
                self._ui.remove_theme_button.set_sensitive(False)
                self._clear_options()

        text = _('Do you want to delete this theme?')
        if theme == app.config.get('roster_theme'):
            text = _('This is the theme you are currently using.\n'
                     'Do you want to delete this theme?')

        NewConfirmationDialog(
            _('Delete'),
            _('Delete Theme'),
            text,
            [DialogButton.make('Cancel'),
             DialogButton.make('Delete',
                               callback=_remove_theme)],
            transient_for=self).show()

    @staticmethod
    def _on_destroy(*args):
        window = get_app_window('Preferences')
        if window is not None:
            window.update_theme_list()


class Option(Gtk.ListBoxRow):
    def __init__(self, option, value):
        Gtk.ListBoxRow.__init__(self)
        self.option = option
        self._box = Gtk.Box(spacing=12)

        label = Gtk.Label()
        label.set_text(option.label)
        label.set_hexpand(True)
        label.set_halign(Gtk.Align.START)
        self._box.add(label)

        if option.attr in (StyleAttr.COLOR, StyleAttr.BACKGROUND):
            self._init_color(value)
        elif option.attr == StyleAttr.FONT:
            self._init_font(value)

        remove_button = Gtk.Button.new_from_icon_name(
            'list-remove-symbolic', Gtk.IconSize.MENU)
        remove_button.set_tooltip_text(_('Remove Setting'))
        remove_button.get_style_context().add_class('theme_remove_button')
        remove_button.connect('clicked', self._on_remove)
        self._box.add(remove_button)

        self.add(self._box)
        self.show_all()

    def _init_color(self, color):
        color_button = Gtk.ColorButton()
        if color is not None:
            rgba = Gdk.RGBA()
            rgba.parse(color)
            color_button.set_rgba(rgba)
        color_button.set_halign(Gtk.Align.END)
        color_button.connect('color-set', self._on_color_set)
        self._box.add(color_button)

    def _init_font(self, desc):
        font_button = Gtk.FontButton()
        if desc is not None:
            font_button.set_font_desc(desc)
        font_button.set_halign(Gtk.Align.END)
        font_button.connect('font-set', self._on_font_set)
        self._box.add(font_button)

    def _on_color_set(self, color_button):
        color = color_button.get_rgba()
        color_string = color.to_string()
        app.css_config.set_value(
            self.option.selector, self.option.attr, color_string, pre=True)
        app.nec.push_incoming_event(NetworkEvent('style-changed'))

    def _on_font_set(self, font_button):
        desc = font_button.get_font_desc()
        app.css_config.set_font(self.option.selector, desc, pre=True)
        app.nec.push_incoming_event(NetworkEvent('style-changed'))

    def _on_remove(self, *args):
        self.get_parent().remove(self)
        app.css_config.remove_value(
            self.option.selector, self.option.attr, pre=True)
        app.nec.push_incoming_event(NetworkEvent('style-changed'))
        self.destroy()

    def __eq__(self, other):
        if isinstance(other, ChooseOption):
            return other.option == self.option
        return other.option == self.option


class ChooseOption(Gtk.ListBoxRow):
    def __init__(self, option):
        Gtk.ListBoxRow.__init__(self)
        self.option = option
        label = Gtk.Label(label=option.label)
        label.set_xalign(0)
        self.add(label)
        self.show_all()
