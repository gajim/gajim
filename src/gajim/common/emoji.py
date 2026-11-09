# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass

from gi.repository import Gio
from gi.repository import GLib

from gajim.common.i18n import get_default_lang
from gajim.common.i18n import get_short_lang_code

log = logging.getLogger("gajim.c.emoji")

EMOJI_DATA_ENTRY_T = tuple[list[int], str, str, list[str], list[str], int]
FALLBACK_LOCALE = "en"

SKIN_TONE_MODIFIERS = (0x1F3FB, 0x1F3FC, 0x1F3FD, 0x1F3FE, 0x1F3FF)


@dataclass
class EmojiSequenceData:
    short_name: str
    trans_short_name: str
    keywords: list[str]
    trans_keywords: list[str]
    skin_tone_variations: list[str]


def get_locale_fallbacks(desired: str) -> list[str]:
    """
    Returns full list of locales to try loading emoji data in, in the order of
    decreasing preference and specificity.  E.g., ['de', 'en']
    for desired == 'de'.
    """
    result = [desired]
    if FALLBACK_LOCALE not in result:
        result.append(FALLBACK_LOCALE)

    return result


def generate_unicode_sequence(c_sequence: list[int]) -> tuple[bool, str]:
    """
    Generates a unicode sequence from a list of codepoints
    """
    has_skin_tone_variation = False
    u_sequence = ""
    for codepoint in c_sequence:
        if codepoint == 0:
            has_skin_tone_variation = True
            codepoint = 0xFE0F

        if codepoint == 0x1F3FB:
            has_skin_tone_variation = True
            continue

        u_sequence += chr(codepoint)
    return has_skin_tone_variation, u_sequence


def generate_skin_tone_sequence(c_sequence: list[int], modifier: int) -> str:
    """
    Replaces GTKs placeholder '0' for skin tone modifiers
    with a given modifier
    """
    u_sequence = ""
    for codepoint in c_sequence:
        if codepoint in (0, 0x1F3FB):
            codepoint = modifier
        u_sequence += chr(codepoint)
    return u_sequence


def _load_gtk_emoji_resource(lang: str) -> list[EMOJI_DATA_ENTRY_T] | None:
    # Sources of emoji data can be found at:
    # https://gitlab.gnome.org/GNOME/gtk/-/tree/main/gtk/emoji
    emoji_data_resource = f"/org/gtk/libgtk/emoji/{lang}.data"

    # some distribution do not register locale emoji resources, so let's do it
    try:
        res = Gio.resource_load(f"/usr/share/gtk-4.0/emoji/{lang}.gresource")
    except GLib.Error:
        pass
    else:
        Gio.resources_register(res)

    try:
        bytes_ = Gio.resources_lookup_data(
            emoji_data_resource, Gio.ResourceLookupFlags.NONE
        )
        assert bytes_ is not None
        log.info("Loaded emoji data resource for locale %s", lang)

        variant = GLib.Variant.new_from_bytes(
            # Reference for the data format:
            # https://gitlab.gnome.org/GNOME/gtk/-/blob/main/gtk/emoji/convert-emoji.c#L25
            GLib.VariantType("a(aussasasu)"),
            bytes_,
            True,
        )

        return variant.unpack()
    except GLib.Error as error:
        log.info("Loading emoji data resource for locale %s failed: %s", lang, error)
        return None


def _load_gtk_emoji_data(
    languages: list[str],
) -> tuple[dict[str, str | EmojiSequenceData], set[str]]:
    log.debug("Trying locales %s", languages)
    for lang in languages:
        emoji_data = _load_gtk_emoji_resource(lang)
        if emoji_data:
            break
    else:
        raise RuntimeError(f"No resource could be loaded; tried {languages}")

    codepoints: set[str] = set()
    emojis: dict[str, str | EmojiSequenceData] = {}

    for (
        c_sequence,
        short_name,
        trans_short_name,
        keywords,
        trans_keywords,
        _group,
    ) in emoji_data:
        # Example item:
        # (
        #     [128515],
        #     'grinning face with big eyes',
        #     'grinsendes Gesicht mit großen Augen',
        #     ['face', 'mouth', 'open', 'smile'],
        #     ['gesicht', 'grinsendes gesicht mit großen augen', 'lol', 'lustig', 'lächeln'],  # noqa: E501
        #     1
        # )
        # If '0' is in c_sequence its a placeholder for skin tone modifiers

        has_skin_variation, u_sequence = generate_unicode_sequence(c_sequence)
        var_sequences: list[str] = []

        if has_skin_variation:
            for modifier in SKIN_TONE_MODIFIERS:
                var_sequence = generate_skin_tone_sequence(c_sequence, modifier)
                var_sequences.append(var_sequence)
                emojis[var_sequence] = u_sequence
                codepoints.update(var_sequence)

        emojis[u_sequence] = EmojiSequenceData(
            short_name=short_name,
            trans_short_name=trans_short_name,
            keywords=keywords,
            trans_keywords=trans_keywords,
            skin_tone_variations=var_sequences,
        )
        codepoints.update(u_sequence)

    return emojis, codepoints


def _load_emoji_data() -> tuple[dict[str, str | EmojiSequenceData], set[str]]:
    app_locale = get_default_lang()
    log.info("Loading emoji data, application locale is %s", app_locale)
    short_locale = get_short_lang_code(app_locale)
    languages = get_locale_fallbacks(short_locale)
    try:
        return _load_gtk_emoji_data(languages)
    except Exception as err:
        log.critical("Unable to load emoji data: %s", err)
        return {}, set()


class _EmojiData:
    def __init__(self) -> None:
        self._emoji_data: dict[str, str | EmojiSequenceData] = {}

    def init(self) -> None:
        self._emoji_data, self._emoji_codepoints = _load_emoji_data()
        if not self._emoji_data:
            raise RuntimeError("Unable to load emoji data")

        log.info("Loaded %s emojis", len(self._emoji_data))

    def is_emoji(self, string: str) -> bool:
        if not string:
            return False
        res = self._emoji_data.get(string)
        if res is None:
            res = self._emoji_data.get(f"{string}\ufe0f")
        return res is not None

    def contains_only_emojis(self, string: str, max_chars: int = -1) -> bool:
        if not string:
            return False
        if max_chars > 0 and len(string) > max_chars:
            return False
        return set(string).issubset(self._emoji_codepoints)

    def __iter__(self) -> Iterator[tuple[str, str | EmojiSequenceData]]:
        yield from self._emoji_data.items()

    def iter_sequences(self) -> Iterator[str]:
        for seq, _ in self:
            yield " ".join("%08x" % ord(c) for c in seq)


EmojiData = _EmojiData()
