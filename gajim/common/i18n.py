# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2004 Vincent Hanquez <tab AT snarc.org>
# Copyright (C) 2005-2006 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2009 Benjamin Richter <br AT waldteufel-online.net>
# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import cast

import gettext
import importlib.resources
import locale
import os
import sys
import unicodedata
from pathlib import Path

DOMAIN = 'gajim'


def init() -> None:
    _trans.init()


def get_default_lang() -> str:
    return _trans.get_default_lang()


def get_short_lang_code(lang: str | None = None) -> str:
    if lang is None:
        lang = _trans.get_default_lang()
    return lang[:2]


def is_rtl_text(text: str) -> bool:
    '''
    Determine paragraph writing direction according to
    http://www.unicode.org/reports/tr9/#The_Paragraph_Level
    '''
    for char in text:
        bidi = unicodedata.bidirectional(char)
        if bidi == 'L':
            return False
        if bidi in ('AL', 'R'):
            return True

    return False


def ngettext(s_sing: str, s_plural: str, n: int) -> str:
    return _trans.translation.ngettext(s_sing, s_plural, n)


class Translation:
    def __init__(self) -> None:
        self.translation = gettext.NullTranslations()
        self._default_lang = None

        self.install()

    def get_default_lang(self) -> str:
        assert self._default_lang is not None
        return self._default_lang

    @staticmethod
    def _get_win32_default_lang() -> str:
        import ctypes
        windll = ctypes.windll.kernel32
        return locale.windows_locale[windll.GetUserDefaultUILanguage()]

    @staticmethod
    def _get_darwin_default_lang() -> str:
        from AppKit import NSLocale

        # FIXME: This returns a two letter language code (en, de, fr)
        # We need a way to get en_US, de_DE etc.
        return NSLocale.currentLocale().languageCode()

    def _get_default_lang(self) -> str:
        if sys.platform == 'win32':
            return self._get_win32_default_lang()

        if sys.platform == 'darwin':
            return self._get_darwin_default_lang()

        return locale.getlocale()[0] or 'en'

    def init(self) -> None:
        try:
            locale.setlocale(locale.LC_ALL, '')
        except locale.Error as error:
            print(error, file=sys.stderr)

        self._default_lang = self._get_default_lang()
        if sys.platform == 'win32':
            # Set the env var on Windows because gettext.find() uses it to
            # find the translation
            # Use LANGUAGE instead of LANG, LANG sets LC_ALL and thus
            # doesn't retain other region settings like LC_TIME
            os.environ['LANGUAGE'] = self._default_lang

        package_dir = cast(Path, importlib.resources.files('gajim'))
        locale_dir = package_dir / 'data' / 'locale'

        try:
            self.translation = gettext.translation(DOMAIN, locale_dir)
            if hasattr(locale, 'bindtextdomain'):
                locale.bindtextdomain(DOMAIN, locale_dir)
                locale.textdomain(DOMAIN)
        except OSError:
            pass

        self.install()

    def install(self) -> None:
        global _, g_, p_
        _ = self.translation.gettext
        g_ = self.translation.gettext
        p_ = self.translation.pgettext


_trans = Translation()
