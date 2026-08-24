#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast

import datetime as dt
import re
from collections.abc import Iterable
from dataclasses import dataclass

from gi.repository import Adw
from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp.modules.vcard4 import AdrProperty
from nbxmpp.modules.vcard4 import BDayProperty
from nbxmpp.modules.vcard4 import GenderProperty
from nbxmpp.modules.vcard4 import KeyProperty
from nbxmpp.modules.vcard4 import NoteProperty
from nbxmpp.modules.vcard4 import OrgProperty
from nbxmpp.modules.vcard4 import TzProperty
from nbxmpp.modules.vcard4 import VCard

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.util.uri import InvalidUri
from gajim.common.util.uri import parse_uri
from gajim.common.util.user_strings import get_time_zone_string

from gajim.gtk.dropdown import GajimDropDown
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import convert_py_to_glib_datetime
from gajim.gtk.vcard_grid import ADR_FIELDS
from gajim.gtk.vcard_grid import ADR_PLACEHOLDER_TEXT
from gajim.gtk.vcard_grid import DEFAULT_KWARGS
from gajim.gtk.vcard_grid import FIELD_TOOLTIPS
from gajim.gtk.vcard_grid import LABEL_DICT
from gajim.gtk.vcard_grid import ORDER
from gajim.gtk.vcard_grid import PROPERTIES_WITH_TYPE
from gajim.gtk.vcard_grid import SEX_VALUES
from gajim.gtk.vcard_grid import SupportedPropertiesT
from gajim.gtk.vcard_grid import TextEntryPropertiesT
from gajim.gtk.vcard_grid import TypeDropDown

ADDABLE_FIELDS = {name: LABEL_DICT[name] for name in DEFAULT_KWARGS}
_EMAIL_PATTERN = re.compile(r"[^@:/?#]+@[^@:/?#]+")
_TEL_PATTERN = re.compile(r"tel:[+0-9A-Za-z*#().,;=\-]+")
_IMPP_SCHEMES = ("matrix", "sip", "sips", "xmpp")

type EditableRow = Adw.ActionRow | Adw.EntryRow | Adw.ExpanderRow


def copy_vcard(vcard: VCard) -> VCard:
    return VCard.from_node(vcard.to_node())


def format_profile_property(prop: SupportedPropertiesT) -> str:
    if isinstance(prop, OrgProperty):
        return ", ".join(value for value in prop.values if value)
    if isinstance(prop, AdrProperty):
        return ", ".join(
            value for field in ADR_FIELDS for value in getattr(prop, field) if value
        )
    if isinstance(prop, GenderProperty):
        sex = SEX_VALUES.get(prop.sex, prop.sex) if prop.sex else ""
        return ", ".join(value for value in (sex, prop.identity) if value)
    if isinstance(prop, TzProperty):
        return get_time_zone_string(prop) or prop.value
    return getattr(prop, "value", "")


def build_profile_property_uri(prop: SupportedPropertiesT) -> str | None:
    value = format_profile_property(prop)
    if (
        not value
        or value != value.strip()
        or any(ord(character) < 32 for character in value)
    ):
        return None

    allowed_schemes: tuple[str, ...]
    if prop.name == "email":
        scheme, separator, payload = value.partition(":")
        address = payload if separator and scheme.casefold() == "mailto" else value
        if any(character.isspace() for character in address):
            return None
        if _EMAIL_PATTERN.fullmatch(address) is None:
            return None
        uri = f"mailto:{address}"
        allowed_schemes = ("mailto",)
    elif prop.name == "tel":
        scheme, separator, payload = value.partition(":")
        number = payload if separator and scheme.casefold() == "tel" else value
        number = "".join(number.split())
        uri = f"tel:{number}"
        if _TEL_PATTERN.fullmatch(uri) is None:
            return None
        allowed_schemes = ("tel",)
    elif prop.name == "impp":
        uri = value
        allowed_schemes = _IMPP_SCHEMES
    elif prop.name == "url":
        uri = value
        allowed_schemes = ("http", "https")
    else:
        return None

    scheme, separator, payload = uri.partition(":")
    scheme = scheme.casefold()
    if not separator or not payload or scheme not in allowed_schemes:
        return None
    try:
        parsed = parse_uri(uri)
    except Exception:
        return None
    return (
        None
        if isinstance(parsed, InvalidUri)
        or parsed.scheme.casefold() not in allowed_schemes
        else uri
    )


def get_supported_properties(vcard: VCard) -> list[SupportedPropertiesT]:
    return cast(
        list[SupportedPropertiesT],
        [prop for prop in vcard.get_properties() if prop.name in ORDER],
    )


class _PropertyBaselines:
    def __init__(self, vcard: VCard) -> None:
        self._baseline_vcard = VCard()
        self._values: dict[int, str | None] = {}
        self._removed: set[int] = set()
        self.acknowledge(vcard)

    def acknowledge(self, vcard: VCard) -> None:
        self._baseline_vcard = copy_vcard(vcard)
        properties = get_supported_properties(vcard)
        originals = get_supported_properties(self._baseline_vcard)
        pairs = list(zip(properties, originals, strict=True))
        if any(prop.name != original.name for prop, original in pairs):
            raise ValueError("Copied vCard property order changed")
        self._values = {id(prop): str(original.to_node()) for prop, original in pairs}
        self._removed.clear()

    def add(self, prop: SupportedPropertiesT) -> None:
        self._values[id(prop)] = None

    def remove(self, prop: SupportedPropertiesT) -> str | None:
        original = self._values.pop(id(prop))
        if original is not None:
            self._removed.add(id(prop))
        return original

    def restore(self, prop: SupportedPropertiesT, original: str | None) -> None:
        self._values[id(prop)] = original
        self._removed.discard(id(prop))

    def is_property_dirty(self, prop: SupportedPropertiesT) -> bool:
        original = self._values[id(prop)]
        return original is None or original != str(prop.to_node())

    def is_dirty(self, properties: Iterable[SupportedPropertiesT]) -> bool:
        return bool(self._removed) or any(
            self.is_property_dirty(prop) for prop in properties
        )


@dataclass(frozen=True, slots=True)
class VCardRemoval:
    prop: SupportedPropertiesT
    original: str | None

    @property
    def label(self) -> str:
        return LABEL_DICT[self.prop.name]


class VCardEditor(Gtk.ListBox, SignalManager):
    __gtype_name__ = "VCardEditor"
    __gsignals__ = {
        "changed": (GObject.SignalFlags.RUN_LAST, None, ()),
        "properties-changed": (GObject.SignalFlags.RUN_LAST, None, ()),
        "property-removed": (GObject.SignalFlags.RUN_LAST, None, (object,)),
    }

    def __init__(self) -> None:
        Gtk.ListBox.__init__(self, selection_mode=Gtk.SelectionMode.NONE)
        SignalManager.__init__(self)

        self.add_css_class("boxed-list")
        self._nickname = ""
        self._nickname_original = ""
        self._nickname_dirty = False
        self._nickname_row: Adw.EntryRow | None = None
        self._vcard = VCard()
        self._baselines = _PropertyBaselines(self._vcard)
        self._rows: list[tuple[Gtk.ListBoxRow, SupportedPropertiesT]] = []
        self._pending_removals: dict[int, VCardRemoval] = {}
        self._row_signal_data: dict[int, list[tuple[GObject.Object, int]]] = {}
        self._building_row_signals: list[tuple[GObject.Object, int]] = []

    def do_unroot(self) -> None:
        self._disconnect_all()
        Gtk.ListBox.do_unroot(self)
        app.check_finalize(self)

    def load(self, vcard: VCard, nickname: str) -> None:
        self._disconnect_all()
        self._clear_rows()
        self._nickname = nickname
        self._nickname_original = nickname
        self._nickname_dirty = False
        self._vcard = copy_vcard(vcard)
        self._baselines = _PropertyBaselines(self._vcard)
        self._append_nickname_row()

        properties = sorted(
            get_supported_properties(self._vcard),
            key=lambda prop: ORDER.index(prop.name),
        )
        for prop in properties:
            self._append_property(prop)
        self.emit("changed")
        self.emit("properties-changed")

    def get_vcard(self) -> VCard:
        return copy_vcard(self._vcard)

    def get_nickname(self) -> str:
        return self._nickname

    def get_dirty_state(self) -> tuple[bool, bool]:
        vcard_dirty = self._baselines.is_dirty(prop for _row, prop in self._rows)
        return vcard_dirty, self._nickname_dirty

    def acknowledge_saved(self, vcard: bool, nickname: bool) -> None:
        if vcard:
            self._baselines.acknowledge(self._vcard)
            for row, _prop in self._rows:
                row.remove_css_class("unsaved")
        if nickname:
            self._nickname_dirty = False
            self._nickname_original = self._nickname
            if self._nickname_row is not None:
                self._nickname_row.remove_css_class("unsaved")
        self.emit("changed")

    def add_field(self, name: str) -> Gtk.ListBoxRow:
        prop = cast(
            SupportedPropertiesT,
            self._vcard.add_property(name, **DEFAULT_KWARGS[name]),
        )
        self._baselines.add(prop)
        row = self._append_property(prop)
        self._update_property_style(prop)
        row.grab_focus()
        self.emit("changed")
        self.emit("properties-changed")
        return row

    def get_present_field_names(self) -> set[str]:
        names = {prop.name for _row, prop in self._rows}
        names.update(removal.prop.name for removal in self._pending_removals.values())
        return names

    def undo_removal(self, removal: VCardRemoval) -> bool:
        pending = self._pending_removals.pop(id(removal), None)
        if pending is not removal:
            return False

        self._baselines.restore(removal.prop, removal.original)
        row = self._append_property(removal.prop)
        self._update_property_style(removal.prop)
        row.grab_focus()
        self.emit("properties-changed")
        return True

    def finalize_removal(self, removal: VCardRemoval) -> bool:
        pending = self._pending_removals.pop(id(removal), None)
        if pending is not removal:
            return False

        self._vcard.remove_property(removal.prop)
        self.emit("properties-changed")
        return True

    def validate(self) -> None:
        for removal in list(self._pending_removals.values()):
            self.finalize_removal(removal)
        for row, prop in list(self._rows):
            if prop.is_empty:
                self._remove_property(row, prop)

    def _clear_rows(self) -> None:
        while child := self.get_first_child():
            self.remove(child)
        self._rows.clear()
        self._pending_removals.clear()
        self._row_signal_data.clear()
        self._building_row_signals = []
        self._nickname_row = None

    def _append_nickname_row(self) -> None:
        self._nickname_row = self._create_entry_row(_("Name"), self._nickname)
        self._nickname_row.set_tooltip_text(
            _(
                "Enter your nickname. This is how your name is displayed to your contacts."
            )
        )
        self._connect(
            self._nickname_row,
            "notify::text",
            self._on_nickname_changed,
        )
        self.append(self._nickname_row)

    def _append_property(self, prop: SupportedPropertiesT) -> Gtk.ListBoxRow:
        self._building_row_signals = []
        if isinstance(prop, AdrProperty):
            row = self._create_address_row(prop)
        elif isinstance(prop, GenderProperty):
            row = self._create_gender_row(prop)
        elif isinstance(prop, TzProperty):
            row = self._create_timezone_row(prop)
        elif isinstance(prop, (NoteProperty, KeyProperty)):
            row = self._create_multiline_row(prop)
        elif isinstance(prop, BDayProperty):
            row = self._create_birthday_row(prop)
        else:
            row = self._create_text_row(cast(TextEntryPropertiesT, prop))

        self._add_common_controls(row, prop)
        self._row_signal_data[id(row)] = self._building_row_signals
        order_index = ORDER.index(prop.name)
        position = len(self._rows)
        for index, (_existing_row, existing_prop) in enumerate(self._rows):
            if ORDER.index(existing_prop.name) > order_index:
                position = index
                break
        self.insert(row, position + 1)
        self._rows.insert(position, (row, prop))
        return row

    def _connect_row(
        self,
        obj: GObject.Object,
        signal_name: str,
        callback: Any,
        *args: Any,
    ) -> None:
        signal_id = self._connect(obj, signal_name, callback, *args)
        self._building_row_signals.append((obj, signal_id))

    def _create_text_row(self, prop: TextEntryPropertiesT) -> Adw.EntryRow:
        if isinstance(prop, OrgProperty):
            values = prop.values
            attribute = "values"
            tail = values[1:]
        else:
            values = [prop.value]
            attribute = "value"
            tail = None
        row = self._create_entry_row(LABEL_DICT[prop.name], values[0] if values else "")
        row.set_tooltip_text(FIELD_TOOLTIPS.get(prop.name, ""))
        self._bind_entry(row, prop, attribute, tail)
        return row

    def _create_birthday_row(self, prop: BDayProperty) -> Adw.EntryRow:
        row = self._create_entry_row(LABEL_DICT[prop.name], prop.value)
        row.set_input_purpose(Gtk.InputPurpose.FREE_FORM)
        self._bind_entry(row, prop)

        calendar = Gtk.Calendar(year=1980, month=5, day=15)
        self._connect_row(calendar, "day-selected", self._on_calendar_day_selected, row)

        popover = Gtk.Popover(child=calendar)
        button = Gtk.MenuButton(
            icon_name="lucide-calendar-symbolic",
            popover=popover,
            tooltip_text=_("Select a date"),
            valign=Gtk.Align.CENTER,
        )
        self._connect_row(
            button,
            "notify::active",
            self._on_calendar_button_active,
            row,
            calendar,
        )
        row.add_suffix(button)
        return row

    def _create_gender_row(self, prop: GenderProperty) -> Adw.ExpanderRow:
        row = Adw.ExpanderRow(title=LABEL_DICT[prop.name])

        sex_row = Adw.ActionRow(title=_("Gender"))
        dropdown: GajimDropDown[str] = GajimDropDown()
        data = {"-": "-"}
        data.update(SEX_VALUES)
        dropdown.set_data(data)
        dropdown.select_key(prop.sex or "-")
        dropdown.set_valign(Gtk.Align.CENTER)
        self._connect_row(dropdown, "notify::selected", self._on_dropdown_changed, prop)
        sex_row.add_suffix(dropdown)
        row.add_row(sex_row)

        identity_row = self._create_entry_row(_("Gender Identity"), prop.identity or "")
        self._bind_entry(identity_row, prop, "identity")
        row.add_row(identity_row)
        return row

    def _create_address_row(self, prop: AdrProperty) -> Adw.ExpanderRow:
        row = Adw.ExpanderRow(title=LABEL_DICT[prop.name])
        for field in ADR_FIELDS:
            values = getattr(prop, field)
            entry = self._create_entry_row(
                ADR_PLACEHOLDER_TEXT[field], values[0] if values else ""
            )
            self._bind_entry(entry, prop, field, values[1:])
            row.add_row(entry)
        return row

    @staticmethod
    def _create_entry_row(title: str, text: str) -> Adw.EntryRow:
        return Adw.EntryRow(title=title, text=text)

    def _bind_entry(
        self,
        row: Adw.EntryRow,
        prop: SupportedPropertiesT,
        attribute: str = "value",
        tail: list[str] | None = None,
    ) -> None:
        self._connect_row(
            row, "notify::text", self._on_entry_changed, prop, attribute, tail
        )

    def _create_timezone_row(self, prop: TzProperty) -> Adw.ActionRow:
        row = Adw.ActionRow(title=LABEL_DICT[prop.name])
        dropdown: GajimDropDown[str] = GajimDropDown()
        from gajim.common.iana.time_zones import ZONES

        dropdown.set_data(ZONES)
        dropdown.set_enable_search(True)
        dropdown.select_key(prop.value)
        dropdown.set_valign(Gtk.Align.CENTER)
        self._connect_row(dropdown, "notify::selected", self._on_dropdown_changed, prop)
        row.add_suffix(dropdown)
        return row

    def _create_multiline_row(
        self, prop: NoteProperty | KeyProperty
    ) -> Adw.ExpanderRow:
        row = Adw.ExpanderRow(title=LABEL_DICT[prop.name])

        text_view = Gtk.TextView(
            wrap_mode=Gtk.WrapMode.WORD_CHAR, hexpand=True, valign=Gtk.Align.FILL
        )
        text_view.props.left_margin = text_view.props.right_margin = 8
        text_view.props.top_margin = text_view.props.bottom_margin = 8
        text_view.get_buffer().set_text(prop.value)
        text_view.set_visible(True)
        self._connect_row(
            text_view.get_buffer(),
            "notify::text",
            self._on_multiline_changed,
            prop,
        )

        scrolled = Gtk.ScrolledWindow(
            child=text_view,
            height_request=120 if isinstance(prop, NoteProperty) else 180,
            hexpand=True,
            has_frame=False,
            propagate_natural_width=True,
        )
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        content_row = Adw.ActionRow()
        content_row.add_suffix(scrolled)
        row.add_row(content_row)
        return row

    def _add_common_controls(
        self, row: EditableRow, prop: SupportedPropertiesT
    ) -> None:
        if prop.name in PROPERTIES_WITH_TYPE:
            dropdown = TypeDropDown(prop.parameters)
            self._connect_row(
                dropdown,
                "notify::selected",
                self._on_dropdown_changed,
                prop,
            )
            row.add_suffix(dropdown)

        remove_button = Gtk.Button(
            icon_name="lucide-trash-symbolic",
            tooltip_text=_("Remove this profile field"),
            valign=Gtk.Align.CENTER,
        )
        remove_button.add_css_class("flat")
        self._connect_row(
            remove_button,
            "clicked",
            self._on_remove_clicked,
            row,
            prop,
        )
        row.add_suffix(remove_button)

    def _remove_property(self, row: Gtk.ListBoxRow, prop: SupportedPropertiesT) -> None:
        self._baselines.remove(prop)
        self._vcard.remove_property(prop)
        self._rows.remove((row, prop))
        self._disconnect_row(row)
        self.remove(row)
        self.emit("changed")
        self.emit("properties-changed")

    def _defer_property_removal(
        self, row: Gtk.ListBoxRow, prop: SupportedPropertiesT
    ) -> VCardRemoval:
        removal = VCardRemoval(prop, self._baselines.remove(prop))
        self._pending_removals[id(removal)] = removal
        self._rows.remove((row, prop))
        self._disconnect_row(row)
        self.remove(row)
        self.emit("changed")
        self.emit("property-removed", removal)
        return removal

    def _disconnect_row(self, row: Gtk.ListBoxRow) -> None:
        for obj, signal_id in self._row_signal_data.pop(id(row)):
            obj.disconnect(signal_id)
            self._signal_data.remove((obj, signal_id))

    def _on_remove_clicked(
        self,
        _button: Gtk.Button,
        row: Gtk.ListBoxRow,
        prop: SupportedPropertiesT,
    ) -> None:
        self._defer_property_removal(row, prop)

    def _on_nickname_changed(
        self, row: Adw.EntryRow, _param: GObject.ParamSpec
    ) -> None:
        self._nickname = row.get_text()
        self._nickname_dirty = self._nickname != self._nickname_original
        row.remove_css_class("unsaved")
        if self._nickname_dirty:
            row.add_css_class("unsaved")
        self.emit("changed")

    def _on_entry_changed(
        self,
        row: Adw.EntryRow,
        _param: GObject.ParamSpec,
        prop: SupportedPropertiesT,
        attribute: str,
        tail: list[str] | None,
    ) -> None:
        text = row.get_text()
        value: str | list[str] = [text, *(tail or [])] if tail is not None else text
        setattr(prop, attribute, value if text else ([] if tail is not None else ""))
        self._update_property_style(prop)

    def _on_dropdown_changed(
        self,
        dropdown: GajimDropDown[Any],
        _param: GObject.ParamSpec,
        prop: SupportedPropertiesT,
    ) -> None:
        if isinstance(prop, GenderProperty):
            value = dropdown.get_selected_key()
            prop.sex = None if value == "-" else value
        elif isinstance(prop, TzProperty):
            item = dropdown.get_selected_item()
            if item is None:
                return
            prop.value = item.key
            prop.value_type = "text"
        self._update_property_style(prop)

    def _on_multiline_changed(
        self,
        buffer: Gtk.TextBuffer,
        _param: GObject.ParamSpec,
        prop: NoteProperty | KeyProperty,
    ) -> None:
        start, end = buffer.get_bounds()
        prop.value = buffer.get_text(start, end, False)
        self._update_property_style(prop)

    def _update_property_style(self, prop: SupportedPropertiesT) -> None:
        changed = self._baselines.is_property_dirty(prop)
        row = next(row for row, row_prop in self._rows if row_prop is prop)
        row.remove_css_class("unsaved")
        if changed:
            row.add_css_class("unsaved")
        self.emit("changed")

    @staticmethod
    def _on_calendar_button_active(
        button: Gtk.MenuButton,
        _param: GObject.ParamSpec,
        row: Adw.EntryRow,
        calendar: Gtk.Calendar,
    ) -> None:
        if not button.get_active():
            return
        try:
            date = dt.date.fromisoformat(row.get_text())
        except ValueError:
            return
        calendar.select_day(convert_py_to_glib_datetime(date))

    @staticmethod
    def _on_calendar_day_selected(calendar: Gtk.Calendar, row: Adw.EntryRow) -> None:
        date_time = calendar.get_date()
        row.set_text(dt.date(*date_time.get_ymd()).isoformat())
