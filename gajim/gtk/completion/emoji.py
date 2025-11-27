# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast
from typing import Final

import locale
import logging

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.i18n import get_default_lang
from gajim.common.i18n import get_short_lang_code

from gajim.gtk.completion.base import BaseCompletionListItem
from gajim.gtk.completion.base import BaseCompletionProvider
from gajim.gtk.completion.base import BaseCompletionViewItem
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import get_ui_string

log = logging.getLogger("gajim.gtk.completion.emoji")

EMOJI_DATA_ENTRY_T = tuple[list[int], str, str, list[str], list[str], int]
MAX_COMPLETION_ENTRIES = 8
FALLBACK_LOCALE = "en"

SKIN_TONE_MODIFIERS = (0x1F3FB, 0x1F3FC, 0x1F3FD, 0x1F3FE, 0x1F3FF)


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


def try_load_raw_emoji_data(locale: str) -> GLib.Bytes | None:
    # Sources of emoji data can be found at:
    # https://gitlab.gnome.org/GNOME/gtk/-/tree/main/gtk/emoji
    emoji_data_resource = f"/org/gtk/libgtk/emoji/{locale}.data"

    # some distribution do not register locale emoji resources, so let's do it
    try:
        res = Gio.resource_load(f"/usr/share/gtk-4.0/emoji/{locale}.gresource")
    except GLib.Error:
        pass
    else:
        Gio.resources_register(res)

    try:
        bytes_ = Gio.resources_lookup_data(
            emoji_data_resource, Gio.ResourceLookupFlags.NONE
        )
        assert bytes_ is not None
        log.info("Loaded emoji data resource for locale %s", locale)
        return bytes_
    except GLib.Error as error:
        log.info("Loading emoji data resource for locale %s failed: %s", locale, error)
        return None


def parse_emoji_data(bytes_data: GLib.Bytes, loc: str) -> Gio.ListStore:

    variant = GLib.Variant.new_from_bytes(
        # Reference for the data format:
        # https://gitlab.gnome.org/GNOME/gtk/-/blob/main/gtk/emoji/convert-emoji.c#L25
        GLib.VariantType("a(aussasasu)"),
        bytes_data,
        True,
    )

    iterable: list[EMOJI_DATA_ENTRY_T] = variant.unpack()

    store = Gio.ListStore(item_type=EmojiCompletionListItem)
    for (
        c_sequence,
        _short_name,
        trans_short_name,
        _keywords,
        trans_keywords,
        _group,
    ) in iterable:
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
        keywords_string = ", ".join(trans_keywords)

        u_mod_sequences: dict[str, str] = {}
        if has_skin_variation:
            for index, modifier in enumerate(SKIN_TONE_MODIFIERS, start=1):
                u_mod_sequences[f"var{index}"] = generate_skin_tone_sequence(
                    c_sequence, modifier
                )

        item = EmojiCompletionListItem(
            emoji=u_sequence,
            short_name=trans_short_name,
            keywords=f"[ {keywords_string} ]",
            search=f'{trans_short_name}|{"|".join(trans_keywords)}',
            has_skin_variation=has_skin_variation,
            **u_mod_sequences,
        )
        store.append(item)

    store.sort(_sort_short_name)
    return store


@staticmethod
def _sort_short_name(
    item1: EmojiCompletionListItem, item2: EmojiCompletionListItem
) -> int:
    return locale.strcoll(item1.short_name, item2.short_name)


class EmojiCompletionListItem(BaseCompletionListItem, GObject.Object):
    __gtype_name__ = "EmojiCompletionListItem"

    emoji = GObject.Property(type=str)
    short_name = GObject.Property(type=str)
    keywords = GObject.Property(type=str)
    search = GObject.Property(type=str)
    has_skin_variation = GObject.Property(type=bool, default=False)
    var1 = GObject.Property(type=str, default="")
    var2 = GObject.Property(type=str, default="")
    var3 = GObject.Property(type=str, default="")
    var4 = GObject.Property(type=str, default="")
    var5 = GObject.Property(type=str, default="")

    def get_text(self) -> str:
        return self.emoji


@Gtk.Template(string=get_ui_string("emoji_completion_view_item.ui"))
class EmojiCompletionViewItem(
    BaseCompletionViewItem[EmojiCompletionListItem], Gtk.Stack, SignalManager
):
    __gtype_name__ = "EmojiCompletionViewItem"
    css_class = "emoji-completion"

    _emoji_label: Gtk.Label = Gtk.Template.Child()
    _short_name_label: Gtk.Label = Gtk.Template.Child()
    _keywords_label: Gtk.Label = Gtk.Template.Child()
    _var1_button: Gtk.Button = Gtk.Template.Child()
    _var2_button: Gtk.Button = Gtk.Template.Child()
    _var3_button: Gtk.Button = Gtk.Template.Child()
    _var4_button: Gtk.Button = Gtk.Template.Child()
    _var5_button: Gtk.Button = Gtk.Template.Child()

    has_skin_variation = GObject.Property(type=bool, default=False)

    def __init__(self) -> None:
        super().__init__()
        Gtk.Stack.__init__(self)
        SignalManager.__init__(self)

        controller = Gtk.GestureClick(
            button=Gdk.BUTTON_SECONDARY, propagation_phase=Gtk.PropagationPhase.CAPTURE
        )
        self._connect(controller, "pressed", self._on_button_press)
        self.add_controller(controller)

        self._connect(self._var1_button, "clicked", self._on_var_button_clicked)
        self._connect(self._var2_button, "clicked", self._on_var_button_clicked)
        self._connect(self._var3_button, "clicked", self._on_var_button_clicked)
        self._connect(self._var4_button, "clicked", self._on_var_button_clicked)
        self._connect(self._var5_button, "clicked", self._on_var_button_clicked)

    def _on_button_press(
        self,
        _gesture_click: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
    ) -> int:

        if not self.props.has_skin_variation:  # pyright: ignore
            return Gdk.EVENT_PROPAGATE

        self.set_visible_child_name("variations")
        return Gdk.EVENT_STOP

    def _on_var_button_clicked(self, button: Gtk.Button) -> None:
        emoji = button.get_label()
        view = cast(Gtk.Widget, self.get_parent().get_parent())  # pyright: ignore
        view.emit("extended-activate", emoji)

    def bind(self, obj: EmojiCompletionListItem) -> None:
        bind_spec = [
            ("has_skin_variation", self, "has_skin_variation"),
            ("emoji", self._emoji_label, "label"),
            ("short_name", self._short_name_label, "label"),
            ("keywords", self._keywords_label, "label"),
            ("var1", self._var1_button, "label"),
            ("var2", self._var2_button, "label"),
            ("var3", self._var3_button, "label"),
            ("var4", self._var4_button, "label"),
            ("var5", self._var5_button, "label"),
        ]

        for source_prop, widget, target_prop in bind_spec:
            bind = obj.bind_property(
                source_prop, widget, target_prop, GObject.BindingFlags.SYNC_CREATE
            )
            self._bindings.append(bind)

    def unbind(self) -> None:
        self.set_visible_child_name("emoji")
        for bind in self._bindings:
            bind.unbind()
        self._bindings.clear()

    def do_unroot(self) -> None:
        self._disconnect_all()
        Gtk.Stack.do_unroot(self)
        app.check_finalize(self)


class EmojiCompletionProvider(BaseCompletionProvider):

    trigger_char: Final = ":"
    name = _("Emojis")

    def __init__(self) -> None:
        self._load_complete = False

        expression = Gtk.PropertyExpression.new(EmojiCompletionListItem, None, "search")
        self._string_filter = Gtk.StringFilter(expression=expression)

        self._filter_model = Gtk.FilterListModel(filter=self._string_filter)
        self._model = Gtk.SliceListModel(
            model=self._filter_model, size=MAX_COMPLETION_ENTRIES
        )

    def get_model(self) -> tuple[Gio.ListModel, type[EmojiCompletionViewItem]]:
        return self._model, EmojiCompletionViewItem

    @staticmethod
    def _load_emoji_data() -> Gio.ListStore:
        app_locale = get_default_lang()
        log.info("Loading emoji data; application locale is %s", app_locale)
        short_locale = get_short_lang_code(app_locale)
        locales = get_locale_fallbacks(short_locale)
        try:
            log.debug("Trying locales %s", locales)
            raw_emoji_data: GLib.Bytes | None = None
            for loc in locales:
                raw_emoji_data = try_load_raw_emoji_data(loc)
                if raw_emoji_data:
                    break
            else:
                raise RuntimeError(f"No resource could be loaded; tried {locales}")

            return parse_emoji_data(raw_emoji_data, loc)
        except Exception as err:
            log.warning("Unable to load emoji data: %s", err)
            return Gio.ListStore(item_type=EmojiCompletionListItem)

    def check(self, candidate: str, start_iter: Gtk.TextIter) -> bool:
        return candidate.startswith(self.trigger_char)

    def populate(self, candidate: str, contact: Any) -> bool:
        candidate = candidate.lstrip(self.trigger_char)
        if not candidate or not len(candidate) > 1:
            # Don't activate until a sufficient # of chars have been typed,
            # which is chosen to be > 1 to not interfere with ASCII smilies
            # consisting of a colon and 1 single other char.
            return False

        if not app.settings.get("enable_emoji_shortcodes"):
            return False

        if not self._load_complete:
            model = self._load_emoji_data()
            self._filter_model.set_model(model)
            self._load_complete = True

        self._string_filter.set_search(candidate)
        return self._model.get_n_items() > 0
