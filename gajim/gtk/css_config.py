# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
import math
import sys
from pathlib import Path

import css_parser
from css_parser.css import CSSStyleRule
from css_parser.css import CSSStyleSheet
from gi.repository import Adw
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common import configpaths
from gajim.common.const import CSSPriority
from gajim.common.const import StyleAttr

if sys.platform == "win32":
    from gajim.common.winapi.system_style import SystemStyleListener
else:
    from gajim.common.dbus.system_style import SystemStyleListener

from gajim.gtk.const import Theme

log = logging.getLogger("gajim.gtk.css")


class CSSConfig:
    def __init__(self) -> None:
        """
        CSSConfig handles loading and storing of all relevant Gajim style files

        The order in which CSSConfig loads the styles

        1. gajim.css
        2. gajim-dark.css (Only if Adw.StyleManager.get_dark() = True)
        3. default.css or default-dark.css (from gajim/data/style)
        4. user-theme.css (from ~/.config/Gajim/theme)

        # gajim.css:

        This is the main style and the application default

        # gajim-dark.css

        Has only entries which we want to override in gajim.css

        # default.css or default-dark.css

        Has all the values that are changeable via UI (see themes.py).
        Depending on `Adw.StyleManager.get_dark()` either default.css or
        default-dark.css gets loaded

        # user-theme.css

        These are the themes the Themes Dialog stores. Because they are
        loaded at last they overwrite everything else. Users should add custom
        css here."""

        # Delete empty rules
        css_parser.ser.prefs.keepEmptyRules = False
        css_parser.ser.prefs.omitLastSemicolon = False

        # Holds the currently selected theme in the Theme Editor
        self._pre_css: CSSStyleSheet | None = None
        self._pre_css_path: Path | None = None

        # Holds the default theme, its used if values are not found
        # in the selected theme
        self._default_css: CSSStyleSheet | None = None
        self._default_css_path: Path | None = None

        # Holds the currently selected theme
        self._css: CSSStyleSheet | None = None
        self._css_path: Path | None = None

        # User Theme CSS Provider
        self._provider = Gtk.CssProvider()

        # Used for dynamic classes like account colors
        self._dynamic_provider = Gtk.CssProvider()
        self._dynamic_dict: dict[str, str] = {}
        self.refresh()

        display = Gdk.Display.get_default()
        assert display is not None
        Gtk.StyleContext.add_provider_for_display(
            display, self._dynamic_provider, CSSPriority.APPLICATION
        )

        # Font size provider for GUI font size
        self._app_font_size_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            display, self._app_font_size_provider, CSSPriority.PRE_THEME
        )

        # Cache of recently requested values
        self._cache: dict[str, str | Pango.FontDescription | None] = {}

        # Holds all currently available themes
        self.themes: list[str] = []

        self._system_style = SystemStyleListener(callback=self.set_dark_theme)

        self.set_dark_theme()
        self._load_css()
        self._gather_available_themes()
        self._load_default()
        self._load_selected()
        self._activate_theme()

        Gtk.StyleContext.add_provider_for_display(
            display, self._provider, CSSPriority.USER_THEME
        )

        self.apply_app_font_size()

        if sys.platform == "win32":
            self._apply_windows_css()

    @property
    def prefer_dark(self) -> bool:
        setting = app.settings.get("dark_theme")
        if setting == Theme.SYSTEM:
            if self._system_style.prefer_dark is not None:
                return self._system_style.prefer_dark

            adw_style_manager = Adw.StyleManager.get_default()
            return adw_style_manager.get_dark()

        return setting == Theme.DARK

    def set_dark_theme(self, value: int | None = None) -> None:
        if value is None:
            value = app.settings.get("dark_theme")
        else:
            app.settings.set("dark_theme", value)

        adw_style_manager = Adw.StyleManager.get_default()
        if value == Theme.SYSTEM:
            if self._system_style.prefer_dark is None:
                adw_style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)
                return

            value = self._system_style.prefer_dark

        if value:
            adw_style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        else:
            adw_style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)

    def reload_css(self) -> None:
        self._load_css()

    def _load_css(self) -> None:
        self._load_css_from_file("gajim.css", CSSPriority.APPLICATION)
        if self.prefer_dark:
            self._load_css_from_file("gajim-dark.css", CSSPriority.APPLICATION_DARK)

        self._load_css_from_file("default.css", CSSPriority.DEFAULT_THEME)
        if self.prefer_dark:
            self._load_css_from_file("default-dark.css", CSSPriority.DEFAULT_THEME_DARK)

    def _load_css_from_file(self, filename: str, priority: CSSPriority) -> None:
        path = configpaths.get("STYLE") / filename
        try:
            with open(path, encoding="utf8") as file_:
                css = file_.read()
        except Exception as exc:
            log.error("Error loading css: %s", exc)
            return
        self._activate_css(css, priority)

    def _activate_css(self, css: str, priority: CSSPriority) -> None:
        try:
            provider = Gtk.CssProvider()
            provider.load_from_bytes(GLib.Bytes.new(css.encode("utf-8")))
            display = Gdk.Display.get_default()
            assert display is not None
            Gtk.StyleContext.add_provider_for_display(display, provider, priority)
            self._load_selected()
            self._activate_theme()

        except Exception:
            log.exception("Error loading application css")

    def apply_app_font_size(self) -> None:
        app_font_size = app.settings.get("app_font_size")
        css = f"""
        * {{
            font-size: {app_font_size}rem;
        }}
        """
        self._app_font_size_provider.load_from_bytes(
            GLib.Bytes.new(css.encode("utf-8"))
        )

    def _apply_windows_css(self) -> None:
        """Apply extra CSS on Windows to fix issues, see:
        https://gitlab.gnome.org/GNOME/libadwaita/-/issues/1053
        """
        self._load_css_from_file("windows.css", CSSPriority.APPLICATION)

    @staticmethod
    def _pango_to_css_weight(number: int) -> int:
        # Pango allows for weight values between 100 and 1000
        # CSS allows only full hundred numbers like 100, 200 ..
        if number < 100:
            return 100
        if number > 900:
            return 900
        return int(math.ceil(number / 100.0)) * 100

    def _gather_available_themes(self) -> None:
        files = configpaths.get("MY_THEME").iterdir()
        self.themes = [file.stem for file in files if file.suffix == ".css"]
        if "default" in self.themes:
            # Ignore user created themes that are named 'default'
            self.themes.remove("default")

    def get_theme_path(self, theme: str, user: bool = True) -> Path:
        if theme == "default" and self.prefer_dark:
            theme = "default-dark"

        if user:
            return configpaths.get("MY_THEME") / f"{theme}.css"
        return configpaths.get("STYLE") / f"{theme}.css"

    def _determine_theme_path(self) -> Path:
        # Gets the path of the currently active theme.
        # If it does not exist, it falls back to the default theme
        theme = app.settings.get("roster_theme")
        if theme == "default":
            return self.get_theme_path(theme, user=False)

        theme_path = self.get_theme_path(theme)
        if not theme or not theme_path.exists():
            log.warning("Theme %s not found, fallback to default", theme)
            app.settings.set("roster_theme", "default")
            log.info("Use Theme: default")
            return self.get_theme_path("default", user=False)
        log.info("Use Theme: %s", theme)
        return theme_path

    def _load_selected(self, new_path: Path | None = None) -> None:
        if new_path is None:
            self._css_path = self._determine_theme_path()
        else:
            self._css_path = new_path
        self._css = css_parser.parseFile(self._css_path)

    def _load_default(self) -> None:
        self._default_css_path = self.get_theme_path("default", user=False)
        self._default_css = css_parser.parseFile(self._default_css_path)

    def _load_pre(self, theme: str) -> None:
        log.info("Preload theme %s", theme)
        self._pre_css_path = self.get_theme_path(theme)
        self._pre_css = css_parser.parseFile(self._pre_css_path)

    def _write(self, pre: bool) -> None:
        path = self._css_path
        css = self._css
        if pre:
            path = self._pre_css_path
            css = self._pre_css

        assert path is not None
        assert css is not None
        with open(path, "w", encoding="utf-8") as file:
            file.write(css.cssText.decode("utf-8"))

        active = self._pre_css_path == self._css_path
        if not pre or active:
            self._load_selected()
            self._activate_theme()

    def set_value(
        self,
        selector: str,
        attr: str | StyleAttr,
        value: str | Pango.FontDescription,
        pre: bool = False,
    ) -> None:

        if attr == StyleAttr.FONT:
            # forward to set_font() for convenience
            assert isinstance(value, Pango.FontDescription)
            self.set_font(selector, value, pre)
            return

        if isinstance(attr, StyleAttr):
            attr = attr.value

        css = self._css
        if pre:
            css = self._pre_css

        assert css is not None
        for rule in css:
            if rule.type != rule.STYLE_RULE:
                continue
            if rule.selectorText == selector:
                log.info("Set %s %s %s", selector, attr, value)
                rule.style[attr] = value
                if not pre:
                    self._add_to_cache(selector, attr, value)
                self._write(pre)
                return

        # The rule was not found, so we add it to this theme
        log.info("Set %s %s %s", selector, attr, value)
        rule = CSSStyleRule(selectorText=selector)
        rule.style[attr] = value
        css.add(rule)
        self._write(pre)

    def set_font(
        self, selector: str, description: Pango.FontDescription, pre: bool = False
    ) -> None:
        css = self._css
        if pre:
            css = self._pre_css
        family, size, style, weight = self._get_attr_from_description(description)
        assert css is not None
        for rule in css:
            if rule.type != rule.STYLE_RULE:
                continue
            if rule.selectorText == selector:
                log.info(
                    "Set Font for: %s %s %s %s %s",
                    selector,
                    family,
                    size,
                    style,
                    weight,
                )
                # Quote font-family in order to avoid unquoted font-families
                # (this is a bug in css_parser)
                rule.style["font-family"] = f'"{family}"'
                rule.style["font-style"] = style
                rule.style["font-size"] = f"{size}pt"
                rule.style["font-weight"] = weight

                if not pre:
                    self._add_to_cache(selector, "fontdescription", description)
                self._write(pre)
                return

        # The rule was not found, so we add it to this theme
        log.info("Set Font for: %s %s %s %s %s", selector, family, size, style, weight)
        rule = CSSStyleRule(selectorText=selector)
        # Quote font-family in order to avoid unquoted font-families
        # (this is a bug in css_parser)
        rule.style["font-family"] = f'"{family}"'
        rule.style["font-style"] = style
        rule.style["font-size"] = f"{size}pt"
        rule.style["font-weight"] = weight
        css.add(rule)
        self._write(pre)

    def _get_attr_from_description(
        self, description: Pango.FontDescription
    ) -> tuple[str | None, float, str, int]:

        size = description.get_size() / Pango.SCALE
        style = self._get_string_from_pango_style(description.get_style())
        weight = self._pango_to_css_weight(int(description.get_weight()))
        family = description.get_family()
        return family, size, style, weight

    def _get_default_rule(self, selector: str, _attr: str) -> CSSStyleRule | None:

        assert self._default_css is not None
        for rule in self._default_css:
            if rule.type != rule.STYLE_RULE:
                continue
            if rule.selectorText == selector:
                log.info("Get Default Rule %s", selector)
                return rule
        return None

    def get_font(
        self, selector: str, pre: bool = False
    ) -> Pango.FontDescription | None:
        if pre:
            css = self._pre_css
        else:
            css = self._css
            try:
                font_desc = self._get_from_cache(selector, "fontdescription")
                if isinstance(font_desc, Pango.FontDescription):
                    return font_desc
            except KeyError:
                pass

        if css is None:
            return None

        for rule in css:
            if rule.type != rule.STYLE_RULE:
                continue
            if rule.selectorText == selector:
                log.info("Get Font for: %s", selector)
                style = rule.style.getPropertyValue("font-style") or None
                size = rule.style.getPropertyValue("font-size") or None
                weight = rule.style.getPropertyValue("font-weight") or None
                family = rule.style.getPropertyValue("font-family") or None

                if family is not None:
                    # Unquote previously quoted font-family
                    # (this is a bug in css_parser)
                    family = family.strip('"')

                desc = self._get_description_from_css(family, size, style, weight)
                if not pre:
                    self._add_to_cache(selector, "fontdescription", desc)
                return desc

        self._add_to_cache(selector, "fontdescription", None)
        return None

    def _get_description_from_css(
        self,
        family: str | None,
        size: str | None,
        style: str | None,
        weight: str | None,
    ) -> Pango.FontDescription | None:

        if family is None:
            return None
        desc = Pango.FontDescription()
        desc.set_family(family)
        if weight is not None:
            desc.set_weight(Pango.Weight(int(weight)))
        if style is not None:
            desc.set_style(self._get_pango_style_from_string(style))
        if size is not None:
            desc.set_size(int(float(size[:-2])) * Pango.SCALE)
        return desc

    @staticmethod
    def _get_pango_style_from_string(style: str) -> Pango.Style:
        if style == "normal":
            return Pango.Style(0)
        if style == "oblique":
            return Pango.Style(1)
        # Pango.Style.ITALIC:
        return Pango.Style(2)

    @staticmethod
    def _get_string_from_pango_style(style: Pango.Style) -> str:
        if style == Pango.Style.NORMAL:
            return "normal"
        if style == Pango.Style.ITALIC:
            return "italic"
        # Pango.Style.OBLIQUE:
        return "oblique"

    def get_value(
        self, selector: str, attr: str | StyleAttr, pre: bool = False
    ) -> str | Pango.FontDescription | None:

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
                    log.info("Get %s %s: %s", selector, attr, rule.style[attr] or None)
                    value = rule.style.getPropertyValue(attr) or None
                    if not pre:
                        self._add_to_cache(selector, attr, value)
                    return value

        # We didn’t find the selector in the selected theme
        # search in default theme
        if not pre:
            rule = self._get_default_rule(selector, attr)
            value = rule if rule is None else rule.style[attr]
            self._add_to_cache(selector, attr, value)
            return value
        return None

    def remove_value(
        self, selector: str, attr: str | StyleAttr, pre: bool = False
    ) -> None:

        if attr == StyleAttr.FONT:
            # forward to remove_font() for convenience
            self.remove_font(selector, pre)
            return

        if isinstance(attr, StyleAttr):
            attr = attr.value

        css = self._css
        if pre:
            css = self._pre_css

        assert css is not None
        for rule in css:
            if rule.type != rule.STYLE_RULE:
                continue
            if rule.selectorText == selector:
                log.info("Remove %s %s", selector, attr)
                rule.style.removeProperty(attr)
                break
        self._write(pre)

    def remove_font(self, selector: str, pre: bool = False) -> None:
        css = self._css
        if pre:
            css = self._pre_css

        assert css is not None
        for rule in css:
            if rule.type != rule.STYLE_RULE:
                continue
            if rule.selectorText == selector:
                log.info("Remove Font from: %s", selector)
                rule.style.removeProperty("font-family")
                rule.style.removeProperty("font-size")
                rule.style.removeProperty("font-style")
                rule.style.removeProperty("font-weight")
                break
        self._write(pre)

    def change_theme(self, theme: str) -> bool:
        user = not theme == "default"
        theme_path = self.get_theme_path(theme, user=user)
        if not theme_path.exists():
            log.error("Change Theme: Theme %s does not exist", theme_path)
            return False
        self._load_selected(theme_path)
        self._activate_theme()
        app.settings.set("roster_theme", theme)
        log.info("Change Theme: Successful switched to %s", theme)
        return True

    def change_preload_theme(self, theme: str) -> bool:
        theme_path = self.get_theme_path(theme)
        if not theme_path.exists():
            log.error("Change Preload Theme: Theme %s does not exist", theme_path)
            return False
        self._load_pre(theme)
        log.info("Successful switched to %s", theme)
        return True

    def rename_theme(self, old_theme: str, new_theme: str) -> bool:
        if old_theme not in self.themes:
            log.error("Rename Theme: Old theme %s not found", old_theme)
            return False

        if new_theme in self.themes:
            log.error("Rename Theme: New theme %s exists already", new_theme)
            return False

        old_theme_path = self.get_theme_path(old_theme)
        new_theme_path = self.get_theme_path(new_theme)
        old_theme_path.rename(new_theme_path)
        self.themes.remove(old_theme)
        self.themes.append(new_theme)
        self._load_pre(new_theme)
        log.info(
            "Rename Theme: Successful renamed theme from %s to %s", old_theme, new_theme
        )
        return True

    def _activate_theme(self) -> None:
        log.info("Activate theme")
        self._invalidate_cache()
        assert self._css is not None
        self._provider.load_from_bytes(GLib.Bytes.new(self._css.cssText))

    def add_new_theme(self, theme: str) -> bool:
        theme_path = self.get_theme_path(theme)
        if theme_path.exists():
            log.error("Add Theme: %s exists already", theme_path)
            return False
        with open(theme_path, "w", encoding="utf8"):
            pass
        self.themes.append(theme)
        log.info("Add Theme: Successful added theme %s", theme)
        return True

    def remove_theme(self, theme: str) -> None:
        theme_path = self.get_theme_path(theme)
        if theme_path.exists():
            theme_path.unlink()
            self.themes.remove(theme)
        log.info("Remove Theme: Successful removed theme %s", theme)

    def _add_to_cache(
        self, selector: str, attr: str, value: str | Pango.FontDescription | None
    ) -> None:

        self._cache[selector + attr] = value

    def _get_from_cache(
        self, selector: str, attr: str
    ) -> str | Pango.FontDescription | None:

        return self._cache[selector + attr]

    def _invalidate_cache(self) -> None:
        self._cache = {}

    def refresh(self) -> None:
        css = ""
        accounts = app.settings.get_accounts()
        for index, account in enumerate(accounts):
            color = app.settings.get_account_setting(account, "account_color")
            css_class = f"gajim_class_{index}"
            css += f".{css_class} {{ background-color: {color}; }}\n"
            self._dynamic_dict[account] = css_class

        self._dynamic_provider.load_from_bytes(GLib.Bytes.new(css.encode()))

    def get_dynamic_class(self, name: str) -> str:
        return self._dynamic_dict[name]
