# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of Gajim.
#
# Gajim is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

import os
import math
import logging

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Pango
import css_parser

from gajim.common import app
from gajim.common import configpaths
from gajim.common.const import StyleAttr, CSSPriority

from gajim.gtk.const import Theme

log = logging.getLogger('gajim.gtk.css')
settings = Gtk.Settings.get_default()


class CSSConfig():
    def __init__(self):
        """
        CSSConfig handles loading and storing of all relevant Gajim style files

        The order in which CSSConfig loads the styles

        1. gajim.css
        2. gajim-dark.css (Only if gtk-application-prefer-dark-theme = True)
        3. default.css or default-dark.css (from gajim/data/style)
        4. user-theme.css (from ~/.config/Gajim/theme)

        # gajim.css:

        This is the main style and the application default

        # gajim-dark.css

        Has only entries which we want to override in gajim.css

        # default.css or default-dark.css

        Has all the values that are changeable via UI (see themes.py).
        Depending on `gtk-application-prefer-dark-theme` either default.css or
        default-dark.css gets loaded

        # user-theme.css

        These are the themes the Themes Dialog stores. Because they are
        loaded at last they overwrite everything else. Users should add custom
        css here."""

        # Delete empty rules
        css_parser.ser.prefs.keepEmptyRules = False

        # Holds the currently selected theme in the Theme Editor
        self._pre_css = None
        self._pre_css_path = None

        # Holds the default theme, its used if values are not found
        # in the selected theme
        self._default_css = None
        self._default_css_path = None

        # Holds the currently selected theme
        self._css = None
        self._css_path = None

        # User Theme CSS Provider
        self._provider = Gtk.CssProvider()

        # Cache of recently requested values
        self._cache = {}

        # Holds all currently available themes
        self.themes = []

        self.set_dark_theme()
        self._load_css()
        self._gather_available_themes()
        self._load_default()
        self._load_selected()
        self._activate_theme()
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            self._provider,
            CSSPriority.USER_THEME)

    @property
    def prefer_dark(self):
        setting = app.config.get('dark_theme')
        if setting == Theme.SYSTEM:
            if settings is None:
                return False
            return settings.get_property('gtk-application-prefer-dark-theme')
        return setting == Theme.DARK

    @staticmethod
    def set_dark_theme(value=None):
        if value is None:
            value = app.config.get('dark_theme')
        else:
            app.config.set('dark_theme', value)

        if settings is None:
            return
        if value == Theme.SYSTEM:
            settings.reset_property('gtk-application-prefer-dark-theme')
            return
        settings.set_property('gtk-application-prefer-dark-theme', bool(value))

    def _load_css(self):
        self._load_css_from_file('gajim.css', CSSPriority.APPLICATION)
        if self.prefer_dark:
            self._load_css_from_file('gajim-dark.css',
                                     CSSPriority.APPLICATION_DARK)

        self._load_css_from_file('default.css', CSSPriority.DEFAULT_THEME)
        if self.prefer_dark:
            self._load_css_from_file('default-dark.css',
                                     CSSPriority.DEFAULT_THEME_DARK)

    def _load_css_from_file(self, filename, priority):
        path = os.path.join(configpaths.get('STYLE'), filename)
        try:
            with open(path, "r") as file_:
                css = file_.read()
        except Exception as exc:
            log.error('Error loading css: %s', exc)
            return
        self._activate_css(css, priority)

    @staticmethod
    def _activate_css(css, priority):
        try:
            provider = Gtk.CssProvider()
            provider.load_from_data(bytes(css.encode('utf-8')))
            Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),
                                                     provider,
                                                     priority)
        except Exception:
            log.exception('Error loading application css')

    @staticmethod
    def _pango_to_css_weight(number):
        # Pango allows for weight values between 100 and 1000
        # CSS allows only full hundred numbers like 100, 200 ..
        number = int(number)
        if number < 100:
            return 100
        if number > 900:
            return 900
        return int(math.ceil(number / 100.0)) * 100

    def _gather_available_themes(self):
        files = os.listdir(configpaths.get('MY_THEME'))
        self.themes = [file[:-4] for file in files if file.endswith('.css')]
        if 'default' in self.themes:
            # Ignore user created themes that are named 'default'
            self.themes.remove('default')

    def get_theme_path(self, theme, user=True):
        if theme == 'default' and self.prefer_dark:
            theme = 'default-dark'

        if user:
            return os.path.join(configpaths.get('MY_THEME'), '%s.css' % theme)
        return os.path.join(configpaths.get('STYLE'), '%s.css' % theme)

    def _determine_theme_path(self):
        # Gets the path of the currently active theme.
        # If it does not exist, it falls back to the default theme
        theme = app.config.get('roster_theme')
        if theme == 'default':
            return self.get_theme_path(theme, user=False)

        theme_path = self.get_theme_path(theme)
        if not theme or not os.path.exists(theme_path):
            log.warning('Theme %s not found, fallback to default', theme)
            app.config.set('roster_theme', 'default')
            log.info('Use Theme: default')
            return self.get_theme_path('default', user=False)
        log.info('Use Theme: %s', theme)
        return theme_path

    def _load_selected(self, new_path=None):
        if new_path is None:
            self._css_path = self._determine_theme_path()
        else:
            self._css_path = new_path
        self._css = css_parser.parseFile(self._css_path)

    def _load_default(self):
        self._default_css_path = self.get_theme_path('default', user=False)
        self._default_css = css_parser.parseFile(self._default_css_path)

    def _load_pre(self, theme):
        log.info('Preload theme %s', theme)
        self._pre_css_path = self.get_theme_path(theme)
        self._pre_css = css_parser.parseFile(self._pre_css_path)

    def _write(self, pre):
        path = self._css_path
        css = self._css
        if pre:
            path = self._pre_css_path
            css = self._pre_css
        with open(path, 'w', encoding='utf-8') as file:
            file.write(css.cssText.decode('utf-8'))

        active = self._pre_css_path == self._css_path
        if not pre or active:
            self._load_selected()
            self._activate_theme()

    def set_value(self, selector, attr, value, pre=False):
        if attr == StyleAttr.FONT:
            # forward to set_font() for convenience
            return self.set_font(selector, value, pre)

        if isinstance(attr, StyleAttr):
            attr = attr.value

        css = self._css
        if pre:
            css = self._pre_css
        for rule in css:
            if rule.type != rule.STYLE_RULE:
                continue
            if rule.selectorText == selector:
                log.info('Set %s %s %s', selector, attr, value)
                rule.style[attr] = value
                if not pre:
                    self._add_to_cache(selector, attr, value)
                self._write(pre)
                return None

        # The rule was not found, so we add it to this theme
        log.info('Set %s %s %s', selector, attr, value)
        rule = css_parser.css.CSSStyleRule(selectorText=selector)
        rule.style[attr] = value
        css.add(rule)
        self._write(pre)
        return None

    def set_font(self, selector, description, pre=False):
        css = self._css
        if pre:
            css = self._pre_css
        family, size, style, weight = self._get_attr_from_description(
            description)
        for rule in css:
            if rule.type != rule.STYLE_RULE:
                continue
            if rule.selectorText == selector:
                log.info('Set Font for: %s %s %s %s %s',
                         selector, family, size, style, weight)
                rule.style['font-family'] = family
                rule.style['font-style'] = style
                rule.style['font-size'] = '%spt' % size
                rule.style['font-weight'] = weight

                if not pre:
                    self._add_to_cache(
                        selector, 'fontdescription', description)
                self._write(pre)
                return

        # The rule was not found, so we add it to this theme
        log.info('Set Font for: %s %s %s %s %s',
                 selector, family, size, style, weight)
        rule = css_parser.css.CSSStyleRule(selectorText=selector)
        rule.style['font-family'] = family
        rule.style['font-style'] = style
        rule.style['font-size'] = '%spt' % size
        rule.style['font-weight'] = weight
        css.add(rule)
        self._write(pre)

    def _get_attr_from_description(self, description):
        size = description.get_size() / Pango.SCALE
        style = self._get_string_from_pango_style(description.get_style())
        weight = self._pango_to_css_weight(int(description.get_weight()))
        family = description.get_family()
        return family, size, style, weight

    def _get_default_rule(self, selector, _attr):
        for rule in self._default_css:
            if rule.type != rule.STYLE_RULE:
                continue
            if rule.selectorText == selector:
                log.info('Get Default Rule %s', selector)
                return rule
        return None

    def get_font(self, selector, pre=False):
        if pre:
            css = self._pre_css
        else:
            css = self._css
            try:
                return self._get_from_cache(selector, 'fontdescription')
            except KeyError:
                pass

        if css is None:
            return None

        for rule in css:
            if rule.type != rule.STYLE_RULE:
                continue
            if rule.selectorText == selector:
                log.info('Get Font for: %s', selector)
                style = rule.style.getPropertyValue('font-style') or None
                size = rule.style.getPropertyValue('font-size') or None
                weight = rule.style.getPropertyValue('font-weight') or None
                family = rule.style.getPropertyValue('font-family') or None

                desc = self._get_description_from_css(
                    family, size, style, weight)
                if not pre:
                    self._add_to_cache(selector, 'fontdescription', desc)
                return desc

        self._add_to_cache(selector, 'fontdescription', None)
        return None

    def _get_description_from_css(self, family, size, style, weight):
        if family is None:
            return None
        desc = Pango.FontDescription()
        desc.set_family(family)
        if weight is not None:
            desc.set_weight(Pango.Weight(int(weight)))
        if style is not None:
            desc.set_style(self._get_pango_style_from_string(style))
        if size is not None:
            desc.set_size(int(size[:-2]) * Pango.SCALE)
        return desc

    @staticmethod
    def _get_pango_style_from_string(style: str) -> int:
        if style == 'normal':
            return Pango.Style(0)
        if style == 'oblique':
            return Pango.Style(1)
        # Pango.Style.ITALIC:
        return Pango.Style(2)

    @staticmethod
    def _get_string_from_pango_style(style: Pango.Style) -> str:
        if style == Pango.Style.NORMAL:
            return 'normal'
        if style == Pango.Style.ITALIC:
            return 'italic'
        # Pango.Style.OBLIQUE:
        return 'oblique'

    def get_value(self, selector, attr, pre=False):
        if attr == StyleAttr.FONT:
            # forward to get_font() for convenience
            return self.get_font(selector, pre)

        if isinstance(attr, StyleAttr):
            attr = attr.value

        if pre:
            css = self._pre_css
        else:
            css = self._css
            try:
                return self._get_from_cache(selector, attr)
            except KeyError:
                pass

        if css is not None:
            for rule in css:
                if rule.type != rule.STYLE_RULE:
                    continue
                if rule.selectorText == selector:
                    log.info('Get %s %s: %s',
                             selector, attr, rule.style[attr] or None)
                    value = rule.style.getPropertyValue(attr) or None
                    if not pre:
                        self._add_to_cache(selector, attr, value)
                    return value

        # We didnt find the selector in the selected theme
        # search in default theme
        if not pre:
            rule = self._get_default_rule(selector, attr)
            value = rule if rule is None else rule.style[attr]
            self._add_to_cache(selector, attr, value)
            return value
        return None

    def remove_value(self, selector, attr, pre=False):
        if attr == StyleAttr.FONT:
            # forward to remove_font() for convenience
            return self.remove_font(selector, pre)

        if isinstance(attr, StyleAttr):
            attr = attr.value

        css = self._css
        if pre:
            css = self._pre_css
        for rule in css:
            if rule.type != rule.STYLE_RULE:
                continue
            if rule.selectorText == selector:
                log.info('Remove %s %s', selector, attr)
                rule.style.removeProperty(attr)
                break
        self._write(pre)
        return None

    def remove_font(self, selector, pre=False):
        css = self._css
        if pre:
            css = self._pre_css

        for rule in css:
            if rule.type != rule.STYLE_RULE:
                continue
            if rule.selectorText == selector:
                log.info('Remove Font from: %s', selector)
                rule.style.removeProperty('font-family')
                rule.style.removeProperty('font-size')
                rule.style.removeProperty('font-style')
                rule.style.removeProperty('font-weight')
                break
        self._write(pre)

    def change_theme(self, theme):
        user = not theme == 'default'
        theme_path = self.get_theme_path(theme, user=user)
        if not os.path.exists(theme_path):
            log.error('Change Theme: Theme %s does not exist', theme_path)
            return False
        self._load_selected(theme_path)
        self._activate_theme()
        app.config.set('roster_theme', theme)
        log.info('Change Theme: Successful switched to %s', theme)
        return True

    def change_preload_theme(self, theme):
        theme_path = self.get_theme_path(theme)
        if not os.path.exists(theme_path):
            log.error('Change Preload Theme: Theme %s does not exist',
                      theme_path)
            return False
        self._load_pre(theme)
        log.info('Successful switched to %s', theme)
        return True

    def rename_theme(self, old_theme, new_theme):
        if old_theme not in self.themes:
            log.error('Rename Theme: Old theme %s not found', old_theme)
            return False

        if new_theme in self.themes:
            log.error('Rename Theme: New theme %s exists already', new_theme)
            return False

        old_theme_path = self.get_theme_path(old_theme)
        new_theme_path = self.get_theme_path(new_theme)
        os.rename(old_theme_path, new_theme_path)
        self.themes.remove(old_theme)
        self.themes.append(new_theme)
        self._load_pre(new_theme)
        log.info('Rename Theme: Successful renamed theme from %s to %s',
                 old_theme, new_theme)
        return True

    def _activate_theme(self):
        log.info('Activate theme')
        self._invalidate_cache()
        self._provider.load_from_data(self._css.cssText)

    def add_new_theme(self, theme):
        theme_path = self.get_theme_path(theme)
        if os.path.exists(theme_path):
            log.error('Add Theme: %s exists already', theme_path)
            return False
        with open(theme_path, 'w', encoding='utf8'):
            pass
        self.themes.append(theme)
        log.info('Add Theme: Successful added theme %s', theme)
        return True

    def remove_theme(self, theme):
        theme_path = self.get_theme_path(theme)
        if os.path.exists(theme_path):
            os.remove(theme_path)
            self.themes.remove(theme)
        log.info('Remove Theme: Successful removed theme %s', theme)

    def _add_to_cache(self, selector, attr, value):
        self._cache[selector + attr] = value

    def _get_from_cache(self, selector, attr):
        return self._cache[selector + attr]

    def _invalidate_cache(self):
        self._cache = {}
