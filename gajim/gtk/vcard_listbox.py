#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast
from typing import Union

import datetime as dt
import logging

from gi.repository import Adw
from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
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
from gajim.common.iana.time_zones import ZONES
from gajim.common.util.text import escape_iri_path_segment
from gajim.common.util.uri import InvalidUri
from gajim.common.util.uri import parse_uri
from gajim.common.util.user_strings import get_time_zone_string

from gajim.gtk.dropdown import GajimDropDown
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import check_finalize
from gajim.gtk.util.misc import iterate_widget_tree
from gajim.gtk.util.misc import open_uri
from gajim.gtk.vcard_grid import ADR_FIELDS
from gajim.gtk.vcard_grid import ADR_PLACEHOLDER_TEXT
from gajim.gtk.vcard_grid import DEFAULT_KWARGS
from gajim.gtk.vcard_grid import FIELD_TOOLTIPS
from gajim.gtk.vcard_grid import LABEL_DICT
from gajim.gtk.vcard_grid import ORDER
from gajim.gtk.vcard_grid import PROPERTIES_WITH_TYPE
from gajim.gtk.vcard_grid import SEX_VALUES
from gajim.gtk.vcard_grid import SupportedProperties
from gajim.gtk.vcard_grid import SupportedPropertiesT
from gajim.gtk.vcard_grid import TextEntryPropertiesT
from gajim.gtk.vcard_grid import TypeDropDown

VCardRowsT = Union[
    "AddressRow",
    "GenderRow",
    "TimezoneRow",
    "TextViewRow",
    "BirthdayRow",
    "TextRow",
    "ReadOnlyRow",
]

log = logging.getLogger("gajim.gtk.vcard_listbox")


def format_property_value(prop: SupportedPropertiesT) -> str:
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
    return prop.value


def add_remove_button(row: VCardRowsT) -> Gtk.Button:
    button = Gtk.Button(
        icon_name="lucide-trash-symbolic",
        tooltip_text=_("Remove this profile field"),
        valign=Gtk.Align.CENTER,
    )
    button.add_css_class("flat")
    button.connect("clicked", lambda *args: row.emit("removed"))
    row.add_prefix(button)
    return button


class GVCardProp(GObject.Object):
    __gtype_name__ = "GVCardProp"

    def __init__(self, prop: SupportedPropertiesT) -> None:
        GObject.Object.__init__(self)
        self._prop = prop

    def get_prop(self) -> SupportedPropertiesT:
        return self._prop


class VCardListBox(Gtk.ListBox):
    __gtype_name__ = "VCardListBox"

    def __init__(self) -> None:
        Gtk.ListBox.__init__(self, selection_mode=Gtk.SelectionMode.NONE)

        self.add_css_class("boxed-list")
        self._vcard = VCard()
        self._edit_mode = False

        self._class_mapping = {
            "fn": TextRow,
            "bday": BirthdayRow,
            "gender": GenderRow,
            "pronouns": TextRow,
            "adr": AddressRow,
            "tel": TextRow,
            "email": TextRow,
            "impp": TextRow,
            "title": TextRow,
            "role": TextRow,
            "org": TextRow,
            "url": TextRow,
            "key": TextViewRow,
            "note": TextViewRow,
            "tz": TimezoneRow,
        }

        self._model: Gio.ListStore[GVCardProp] = Gio.ListStore(item_type=GVCardProp)
        self.bind_model(self._model, self._create_widget_func)

    def run_destroy(self) -> None:
        self._model.remove_all()
        self.bind_model(None, None)
        app.check_finalize(self)

    def load(self, vcard: VCard, *, edit_mode: bool) -> None:
        self._model.remove_all()
        self._vcard = vcard.copy()
        self._edit_mode = edit_mode

        for prop in vcard.get_properties():
            if isinstance(prop, SupportedProperties):
                self._append_property(prop)

    def get_vcard(self) -> VCard:
        return self._vcard.copy()

    def in_edit_mode(self) -> bool:
        return self._edit_mode

    def add_field(self, name: str) -> Gtk.ListBoxRow:
        prop = cast(
            SupportedPropertiesT,
            self._vcard.add_property(name, **DEFAULT_KWARGS[name]),
        )
        return self._append_property(prop)

    def _create_widget_func(self, item: GVCardProp) -> VCardRowsT:
        prop = item.get_prop()
        if self._edit_mode:
            row_cls = self._class_mapping[prop.name]
            row = row_cls(prop)  # type: ignore
            row.connect("removed", self._on_remove_clicked)
        else:
            row = ReadOnlyRow(prop)
        return row

    @staticmethod
    def _sort_func(prop1: GVCardProp, prop2: GVCardProp, *_user_data: Any) -> int:
        pos1 = ORDER.index(prop1.get_prop().name)
        pos2 = ORDER.index(prop2.get_prop().name)

        if pos1 == pos2:
            return 0
        return 1 if pos2 < pos1 else -1

    def _append_property(self, prop: SupportedPropertiesT) -> Gtk.ListBoxRow:
        pos = cast(int, self._model.insert_sorted(GVCardProp(prop), self._sort_func))
        row = self.get_row_at_index(pos)
        assert row is not None
        row.grab_focus()
        return row

    def _remove_property(self, pos: int) -> None:
        row = cast(VCardRowsT, self.get_row_at_index(pos))
        assert row is not None
        self._model.remove(pos)
        row.run_destroy()

    def _on_remove_clicked(self, row: VCardRowsT) -> None:
        self._remove_property(row.get_index())


class BaseRow(SignalManager):
    def __init__(self, prop: SupportedPropertiesT) -> None:
        SignalManager.__init__(self)
        self._prop = prop

    def get_prop(self) -> SupportedPropertiesT:
        return self._prop


class AddressRow(Adw.ExpanderRow, BaseRow):
    __gsignals__ = {
        "removed": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, prop: AdrProperty) -> None:
        Adw.ExpanderRow.__init__(self, title=LABEL_DICT[prop.name])
        BaseRow.__init__(self, prop)

        for field in ADR_FIELDS:
            values = getattr(prop, field)
            entry = Adw.EntryRow(
                title=ADR_PLACEHOLDER_TEXT[field], text=values[0] if values else ""
            )
            entry.connect("notify::text", self._on_entry_changed, prop, field)
            self.add_row(entry)

        self._dropdown = TypeDropDown(prop.parameters)
        self.add_suffix(self._dropdown)

        add_remove_button(self)

    def run_destroy(self):
        self._disconnect_all()
        self._dropdown.run_destroy()
        check_finalize(self)

    @staticmethod
    def _on_entry_changed(
        row: Adw.EntryRow,
        _param: GObject.ParamSpec,
        prop: AdrProperty,
        attribute: str,
    ) -> None:
        text = row.get_text()
        setattr(prop, attribute, [text] if text else [])


class GenderRow(Adw.ExpanderRow, BaseRow):
    __gsignals__ = {
        "removed": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, prop: GenderProperty) -> None:
        Adw.ExpanderRow.__init__(self, title=LABEL_DICT[prop.name])
        BaseRow.__init__(self, prop)

        dropdown: GajimDropDown[str] = GajimDropDown()
        data = {"-": "-"}
        data.update(SEX_VALUES)
        dropdown.set_data(data)
        dropdown.select_key(prop.sex or "-")
        dropdown.set_valign(Gtk.Align.CENTER)
        dropdown.connect("notify::selected", self._on_dropdown_changed, prop)

        sex_row = Adw.ActionRow(title=_("Gender"))
        sex_row.add_suffix(dropdown)
        self.add_row(sex_row)

        entry = Adw.EntryRow(title=_("Gender Identity"), text=prop.identity or "")
        entry.connect("notify::text", self._on_entry_changed, prop)
        self.add_row(entry)

        add_remove_button(self)

    def run_destroy(self):
        self._disconnect_all()
        check_finalize(self)

    @staticmethod
    def _on_dropdown_changed(
        dropdown: GajimDropDown[str],
        _param: GObject.ParamSpec,
        prop: GenderProperty,
    ) -> None:
        value = dropdown.get_selected_key()
        prop.sex = None if value == "-" else value

    @staticmethod
    def _on_entry_changed(
        row: Adw.EntryRow,
        _param: GObject.ParamSpec,
        prop: GenderProperty,
    ) -> None:
        prop.identity = row.get_text() or None


class TextViewRow(Adw.ExpanderRow, BaseRow):
    __gsignals__ = {
        "removed": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, prop: NoteProperty | KeyProperty) -> None:
        Adw.ExpanderRow.__init__(self, title=LABEL_DICT[prop.name])
        BaseRow.__init__(self, prop)

        text_view = Gtk.TextView(
            wrap_mode=Gtk.WrapMode.WORD_CHAR,
            hexpand=True,
            valign=Gtk.Align.FILL,
            left_margin=8,
            right_margin=8,
            top_margin=8,
            bottom_margin=8,
        )

        text_buffer = text_view.get_buffer()
        text_buffer.set_text(prop.value)
        self._connect(text_buffer, "notify::text", self._on_multiline_changed, prop)

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
        self.add_row(content_row)

        self._dropdown = None
        if isinstance(prop, KeyProperty):
            self._dropdown = TypeDropDown(prop.parameters)
            self.add_suffix(self._dropdown)

        add_remove_button(self)

    def run_destroy(self):
        self._disconnect_all()
        if self._dropdown is not None:
            self._dropdown.run_destroy()
        check_finalize(self)

    def _on_multiline_changed(
        self,
        buffer: Gtk.TextBuffer,
        _param: GObject.ParamSpec,
        prop: NoteProperty | KeyProperty,
    ) -> None:
        start, end = buffer.get_bounds()
        prop.value = buffer.get_text(start, end, False)


class TimezoneRow(Adw.ActionRow, BaseRow):
    __gsignals__ = {
        "removed": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, prop: TzProperty) -> None:
        Adw.ActionRow.__init__(self, title=LABEL_DICT[prop.name])
        BaseRow.__init__(self, prop)

        self._dropdown: GajimDropDown[str] = GajimDropDown()
        self._dropdown.set_data(ZONES)
        self._dropdown.set_enable_search(True)
        self._dropdown.select_key(prop.value)
        self._dropdown.set_valign(Gtk.Align.CENTER)
        self._dropdown.connect("notify::selected", self._on_dropdown_changed, prop)
        self.add_suffix(self._dropdown)

        add_remove_button(self)

    def run_destroy(self):
        self._disconnect_all()
        self._dropdown.run_destroy()
        check_finalize(self)

    @staticmethod
    def _on_dropdown_changed(
        dropdown: GajimDropDown[str],
        _param: GObject.ParamSpec,
        prop: TzProperty,
    ) -> None:
        item = dropdown.get_selected_item()
        if item is None:
            return
        prop.value = item.key
        prop.value_type = "text"


class BirthdayRow(Adw.EntryRow, BaseRow):
    __gsignals__ = {
        "removed": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, prop: BDayProperty) -> None:
        Adw.EntryRow.__init__(
            self,
            title=LABEL_DICT[prop.name],
            text=prop.value,
            input_purpose=Gtk.InputPurpose.FREE_FORM,
        )
        BaseRow.__init__(self, prop)

        self._connect(self, "notify::text", self._on_entry_changed, prop)

        calendar = Gtk.Calendar(year=1980, month=5, day=15)
        self._connect(calendar, "day-selected", self._on_calendar_day_selected)

        popover = Gtk.Popover(child=calendar)
        self._menu_button = Gtk.MenuButton(
            icon_name="lucide-calendar-symbolic",
            popover=popover,
            tooltip_text=_("Select a date"),
            valign=Gtk.Align.CENTER,
        )
        self.add_suffix(self._menu_button)

        add_remove_button(self)

    def run_destroy(self):
        self._disconnect_all()
        check_finalize(self)

    @staticmethod
    def _on_entry_changed(
        row: Adw.EntryRow,
        _param: GObject.ParamSpec,
        prop: BDayProperty,
    ) -> None:
        prop.value = row.get_text()

    def _on_calendar_day_selected(self, calendar: Gtk.Calendar) -> None:
        date_time = calendar.get_date()
        self.set_text(dt.date(*date_time.get_ymd()).isoformat())
        self._menu_button.popdown()


class TextRow(Adw.EntryRow, BaseRow):
    __gsignals__ = {
        "removed": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, prop: TextEntryPropertiesT) -> None:
        BaseRow.__init__(self, prop)
        if isinstance(prop, OrgProperty):
            value = prop.values[0] if prop.values else ""
        else:
            value = prop.value
        Adw.EntryRow.__init__(self, title=LABEL_DICT[prop.name], text=value)

        self.set_tooltip_text(FIELD_TOOLTIPS.get(prop.name, ""))
        self._connect(self, "notify::text", self._on_entry_changed, prop)

        self._dropdown = None
        if prop.name in PROPERTIES_WITH_TYPE:
            self._dropdown = TypeDropDown(prop.parameters)
            self.add_suffix(self._dropdown)

        add_remove_button(self)

    def run_destroy(self):
        self._disconnect_all()
        if self._dropdown is not None:
            self._dropdown.run_destroy()
        check_finalize(self)

    @staticmethod
    def _on_entry_changed(
        row: Adw.EntryRow,
        _param: GObject.ParamSpec,
        prop: TextEntryPropertiesT,
    ) -> None:
        text = row.get_text()
        if isinstance(prop, OrgProperty):
            prop.values = [text] if text else []
        else:
            prop.value = text


class ReadOnlyRow(Adw.ActionRow, BaseRow):
    def __init__(self, prop: SupportedPropertiesT) -> None:
        Adw.ActionRow.__init__(
            self, title=LABEL_DICT[prop.name], subtitle_selectable=True
        )
        BaseRow.__init__(self, prop)
        self.add_css_class("property")

        value = format_property_value(prop)

        match prop.name:
            case "email":
                # EMAIL https://rfc-editor.org/rfc/rfc6350#section-6.4.2
                uri = "mailto:" + escape_iri_path_segment(value)
                self.set_value_with_uri(uri)

            case "tel" | "impp" | "url" | "key":
                # TEL       https://rfc-editor.org/rfc/rfc6350#section-6.4.1
                # IMPP      https://rfc-editor.org/rfc/rfc6350#section-6.4.3
                # URL       https://rfc-editor.org/rfc/rfc6350#section-6.7.8
                # KEY       https://rfc-editor.org/rfc/rfc6350#section-6.8.1
                self.set_value_with_uri(value)

            case _:
                self.set_subtitle(value)

    def run_destroy(self):
        self._disconnect_all()
        check_finalize(self)

    def set_value_with_uri(self, value: str) -> None:
        uri = parse_uri(value)
        if isinstance(uri, InvalidUri):
            self.set_subtitle(value)
            return

        self.set_subtitle(
            '<a href="{}">{}</a>'.format(  # noqa: UP032
                GLib.markup_escape_text(value), GLib.markup_escape_text(value)
            )
        )
        self._override_link_handler()

    def _override_link_handler(self) -> Gtk.Label | None:
        # Find subtitle label and override link handler. open_uri() works on all platforms
        # and handles xmpp uris internally
        for widget, _parent in iterate_widget_tree(self, only_children=True):
            if (
                isinstance(widget, Gtk.Label)
                and widget.get_buildable_id() == "subtitle"
            ):
                widget.connect("activate-link", self._on_activate_link)
                return

        log.warning("Unable to override link handler")

    @staticmethod
    def _on_activate_link(_label: Gtk.Label, uri: str) -> int:
        open_uri(uri)
        return Gdk.EVENT_STOP
