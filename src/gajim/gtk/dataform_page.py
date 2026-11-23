# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast

from gi.repository import Adw
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp.modules.dataforms import BooleanField
from nbxmpp.modules.dataforms import DataField
from nbxmpp.modules.dataforms import FieldT
from nbxmpp.modules.dataforms import JidMultiField
from nbxmpp.modules.dataforms import ListMultiField
from nbxmpp.modules.dataforms import ListSingleField
from nbxmpp.modules.dataforms import Media
from nbxmpp.modules.dataforms import SimpleDataForm
from nbxmpp.modules.dataforms import StringField
from nbxmpp.modules.dataforms import TextMultiField
from nbxmpp.modules.dataforms import Uri

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.util.image import load_image
from gajim.common.util.image import MAX_DATAFORM_PIXELS
from gajim.common.util.text import make_href_markup

from gajim.gtk.util.classes import SignalManager


class DataFormRow(SignalManager):
    def __init__(self) -> None:
        SignalManager.__init__(self)
        self._validation_icon = Gtk.Image(
            icon_name="lucide-circle-alert-symbolic",
            valign=Gtk.Align.CENTER,
            visible=False,
        )
        cast(Adw.ActionRow, self).add_suffix(self._validation_icon)

    def set_validation(self, is_valid: bool, error: str) -> None:
        # Fields without an error are invalid because they are required but empty
        self._validation_icon.set_visible(not is_valid)
        self._validation_icon.set_tooltip_text(error or _("Required"))
        self._validation_icon.set_css_classes(["error" if error else "warning"])

    def run_destroy(self) -> None:
        self._disconnect_all()
        app.check_finalize(self)


class BooleanRow(Adw.ActionRow, DataFormRow):
    __gsignals__ = {
        "field-changed": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, field: BooleanField) -> None:
        Adw.ActionRow.__init__(
            self, title=field.label, subtitle=field.description, use_markup=False
        )
        DataFormRow.__init__(self)
        self._field = field

        switch = Gtk.Switch(active=field.value, valign=Gtk.Align.CENTER)
        self.add_suffix(switch)
        self.set_activatable_widget(switch)
        self._connect(switch, "notify::active", self._on_active_changed)

    def _on_active_changed(self, switch: Gtk.Switch, _param: Any) -> None:
        self._field.value = switch.get_active()
        self.emit("field-changed")


class TextSingleRow(Adw.EntryRow, DataFormRow):
    __gsignals__ = {
        "field-changed": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, field: StringField) -> None:
        Adw.EntryRow.__init__(
            self,
            title=field.label,
            text=field.value,
            tooltip_text=field.description,
            use_markup=False,
        )
        DataFormRow.__init__(self)
        self._field = field
        self._connect(self, "notify::text", self._on_text_changed)

    def _on_text_changed(self, _row: Adw.EntryRow, _param: Any) -> None:
        self._field.value = self.get_text()
        self.emit("field-changed")


class TextPrivateRow(TextSingleRow):
    def __init__(self, field: StringField) -> None:
        TextSingleRow.__init__(self, field)
        self.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        cast(Gtk.Text, self.get_delegate()).set_visibility(False)


class ListSingleRow(Adw.ComboRow, DataFormRow):
    __gsignals__ = {
        "field-changed": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, field: ListSingleField) -> None:
        options = dict(field.iter_options())
        if not field.value and options:
            field.value = next(iter(options))
        elif field.value not in options:
            options = {field.value: field.value, **options}

        Adw.ComboRow.__init__(
            self,
            title=field.label,
            subtitle=field.description,
            model=Gtk.StringList.new(list(options.values())),
            use_markup=False,
        )
        DataFormRow.__init__(self)
        self._field = field
        self._values = list(options)
        self.set_selected(self._values.index(field.value))
        self._connect(self, "notify::selected", self._on_selected)

    def _on_selected(self, _row: Adw.ComboRow, _param: Any) -> None:
        self._field.value = self._values[self.get_selected()]
        self.emit("field-changed")


class ListSingleChoiceRow(Adw.ExpanderRow, DataFormRow):
    __gsignals__ = {
        "field-changed": (GObject.SignalFlags.RUN_LAST, None, ()),
        "option-activated": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, field: ListSingleField) -> None:
        Adw.ExpanderRow.__init__(
            self,
            title=field.label,
            subtitle=field.description,
            use_markup=False,
            expanded=True,
        )
        DataFormRow.__init__(self)
        self._field = field

        group: Gtk.CheckButton | None = None
        for value, label in field.iter_options():
            check = Gtk.CheckButton(active=value == field.value, group=group)
            group = group or check
            self._connect(check, "toggled", self._on_toggled, value)

            gesture = Gtk.GestureClick(propagation_phase=Gtk.PropagationPhase.CAPTURE)
            self._connect(gesture, "pressed", self._on_pressed)

            row = Adw.ActionRow(title=label, use_markup=False)
            row.add_prefix(check)
            row.set_activatable_widget(check)
            row.add_controller(gesture)
            self.add_row(row)

    def _on_toggled(self, check: Gtk.CheckButton, value: str) -> None:
        if check.get_active():
            self._field.value = value
            self.emit("field-changed")

    def _on_pressed(
        self, _gesture: Gtk.GestureClick, n_press: int, _x: float, _y: float
    ) -> None:
        if n_press == 2:
            self.emit("option-activated")


class ListMultiRow(Adw.ExpanderRow, DataFormRow):
    __gsignals__ = {
        "field-changed": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, field: ListMultiField) -> None:
        Adw.ExpanderRow.__init__(
            self,
            title=field.label,
            subtitle=field.description,
            use_markup=False,
            expanded=True,
        )
        DataFormRow.__init__(self)
        self._field = field

        selected = set(field.values)
        for value, label in field.iter_options():
            switch = Adw.SwitchRow(
                title=label, active=value in selected, use_markup=False
            )
            self._connect(switch, "notify::active", self._on_toggled, value)
            self.add_row(switch)

    def _on_toggled(self, switch: Adw.SwitchRow, _param: Any, value: str) -> None:
        values = [item for item in self._field.values if item != value]
        if switch.get_active():
            values.append(value)
        self._field.values = values
        self.emit("field-changed")


class JidMultiRow(Adw.ExpanderRow, DataFormRow):
    __gsignals__ = {
        "field-changed": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, field: JidMultiField) -> None:
        Adw.ExpanderRow.__init__(
            self,
            title=field.label,
            subtitle=field.description,
            use_markup=False,
            expanded=True,
        )
        DataFormRow.__init__(self)
        self._field = field
        self._entries: list[Adw.EntryRow] = []

        for value in field.values:
            self._add_entry(value)

        add_button = Gtk.Button(
            icon_name="lucide-plus-symbolic", valign=Gtk.Align.CENTER
        )
        self._connect(add_button, "clicked", self._on_add_clicked)
        self._add_button_row = Adw.ActionRow(title=_("Add Address"))
        self._add_button_row.add_suffix(add_button)
        self._add_button_row.set_activatable_widget(add_button)
        self.add_row(self._add_button_row)

    def _add_entry(self, text: str) -> None:
        entry = Adw.EntryRow(title=_("Address"), text=text)
        remove_button = Gtk.Button(
            icon_name="lucide-minus-symbolic", valign=Gtk.Align.CENTER
        )
        entry.add_suffix(remove_button)
        self._connect(entry, "notify::text", self._update_values)
        self._connect(remove_button, "clicked", self._on_remove_clicked, entry)
        self.add_row(entry)
        self._entries.append(entry)

    def _on_add_clicked(self, _button: Gtk.Button) -> None:
        self.remove(self._add_button_row)
        self._add_entry("")
        self.add_row(self._add_button_row)

    def _on_remove_clicked(self, button: Gtk.Button, entry: Adw.EntryRow) -> None:
        self._disconnect_object(button)
        self._disconnect_object(entry)
        self.remove(entry)
        self._entries.remove(entry)
        self._update_values()

    def _update_values(self, *_args: Any) -> None:
        self._field.values = [
            text for entry in self._entries if (text := entry.get_text().strip())
        ]
        self.emit("field-changed")


class TextMultiRow(Adw.ExpanderRow, DataFormRow):
    __gsignals__ = {
        "field-changed": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, field: TextMultiField) -> None:
        Adw.ExpanderRow.__init__(
            self,
            title=field.label,
            subtitle=field.description,
            use_markup=False,
            expanded=True,
        )
        DataFormRow.__init__(self)
        self._field = field

        text_view = Gtk.TextView(
            wrap_mode=Gtk.WrapMode.WORD_CHAR,
            left_margin=12,
            right_margin=12,
            top_margin=6,
            bottom_margin=6,
        )
        text_view.get_buffer().set_text(field.value)
        self._connect(text_view.get_buffer(), "changed", self._on_text_changed)

        scrolled = Gtk.ScrolledWindow(
            child=text_view,
            min_content_height=100,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
        )
        self.add_row(
            Gtk.ListBoxRow(child=scrolled, selectable=False, activatable=False)
        )

    def _on_text_changed(self, buffer: Gtk.TextBuffer) -> None:
        self._field.value = buffer.get_text(*buffer.get_bounds(), False)
        self.emit("field-changed")


class ReadOnlyRow(Adw.ActionRow):
    def __init__(self, field: FieldT) -> None:
        Adw.ActionRow.__init__(
            self,
            title=field.label,
            subtitle=self._get_value_text(field),
            subtitle_selectable=True,
            tooltip_text=field.description,
            use_markup=False,
        )
        self.add_css_class("property")

    @staticmethod
    def _get_value_text(field: FieldT) -> str:
        match field:
            case BooleanField():
                return _("Yes") if field.value else _("No")
            case ListMultiField():
                options = dict(field.iter_options())
                return "\n".join(options.get(value, value) for value in field.values)
            case ListSingleField():
                return dict(field.iter_options()).get(field.value, field.value)
            case _:
                return field.value


class ImageMediaRow(Adw.PreferencesRow):
    def __init__(self, uri: Uri) -> None:
        Adw.PreferencesRow.__init__(self, activatable=False)

        image = Gtk.Image(pixel_size=170, margin_top=12, margin_bottom=12)
        image.add_css_class("preview-image")
        cid = uri.uri_data.split(":")[1].split("@")[0]
        if (data := app.bob_cache.get(cid)) is not None:
            pixbuf = load_image(data, size=170, max_image_pixels=MAX_DATAFORM_PIXELS)
            if pixbuf is not None:
                image.set_from_paintable(Gdk.Texture.new_for_pixbuf(pixbuf))
        self.set_child(image)


DataFormRowsT = (
    BooleanRow
    | TextSingleRow
    | ListSingleRow
    | ListSingleChoiceRow
    | ListMultiRow
    | JidMultiRow
    | TextMultiRow
)

ROW_CLASSES: dict[str, type[DataFormRowsT]] = {
    "boolean": BooleanRow,
    "jid-multi": JidMultiRow,
    "jid-single": TextSingleRow,
    "list-multi": ListMultiRow,
    "list-single": ListSingleRow,
    "text-multi": TextMultiRow,
    "text-private": TextPrivateRow,
    "text-single": TextSingleRow,
}


class DataFormPage(Adw.PreferencesPage, SignalManager):
    __gsignals__ = {
        "is-valid": (GObject.SignalFlags.RUN_LAST, None, (bool,)),
    }

    def __init__(
        self,
        form: SimpleDataForm,
        *,
        read_only: bool = False,
        hide_fallback_fields: bool = False,
        entry_activates_default: bool = False,
    ) -> None:
        Adw.PreferencesPage.__init__(
            self,
            hexpand=True,
            vexpand=True,
            description=make_href_markup(form.instructions),
            description_centered=False,
        )
        SignalManager.__init__(self)

        self._form = form
        self._rows: list[DataFormRowsT] = []
        self._new_group(form.title or "")

        # A form asking for one choice, like an ad-hoc command list, is
        # completed by activating an option
        row_classes = ROW_CLASSES
        fields = [field for field in form.iter_fields() if field.type_ in ROW_CLASSES]
        if len(fields) == 1 and fields[0].type_ == "list-single":
            row_classes = ROW_CLASSES | {"list-single": ListSingleChoiceRow}

        for field in form.iter_fields():
            if field.type_ == "fixed":
                self._add_fixed(cast(StringField, field).value)
                continue

            row_cls = row_classes.get(field.type_)
            if row_cls is None:
                continue

            # ejabberd adds fallback fields to registration forms (XEP-0077)
            if hide_fallback_fields and "fallback" in field.var:
                continue

            if field.media is not None:
                uri = self._get_image_uri(field.type_, field.media)
                if uri is None:
                    # Without the media the field cannot be filled in
                    continue
                self._add_row(ImageMediaRow(uri))

            if read_only:
                self._add_row(ReadOnlyRow(field))
                continue

            row = row_cls(cast(Any, field))
            if entry_activates_default and isinstance(row, Adw.EntryRow):
                row.set_activates_default(True)
            row.set_validation(*field.is_valid())
            self._connect(row, "field-changed", self._on_field_changed, field)
            if isinstance(row, ListSingleChoiceRow):
                self._connect(row, "option-activated", self._on_option_activated)
            self._add_row(row)
            self._rows.append(row)

        self._original_hash = hash(str(form))
        self._emit_valid()

    def run_destroy(self) -> None:
        self._disconnect_all()
        for row in self._rows:
            row.run_destroy()
        self._rows.clear()
        app.check_finalize(self)

    def get_submit_form(self) -> SimpleDataForm:
        self._form.type_ = "submit"
        return self._form

    def was_modified(self) -> bool:
        return self._original_hash != hash(str(self._form))

    def reset_form_hash(self) -> None:
        self._original_hash = hash(str(self._form))

    @staticmethod
    def _get_image_uri(type_: str, media: Media) -> Uri | None:
        if type_ not in ("text-single", "text-private", "text-multi"):
            return None

        for uri in media.uris:
            if (uri.type_ or "").startswith("image/") and uri.uri_data.startswith(
                "cid:"
            ):
                return uri
        return None

    def _add_row(self, row: Gtk.Widget) -> None:
        self._group.add(row)
        self._group_has_rows = True

    def _new_group(self, title: str = "") -> None:
        self._group = Adw.PreferencesGroup(title=GLib.markup_escape_text(title))
        self._group_has_rows = False
        self.add(self._group)

    def _add_fixed(self, text: str) -> None:
        # Short fixed fields are section headers, longer ones are explanations
        is_title = len(text) < 40
        if self._group_has_rows or (is_title and self._group.get_title()):
            self._new_group()

        if is_title:
            self._group.set_title(GLib.markup_escape_text(text))
            return

        description = self._group.get_description()
        text = make_href_markup(text)
        self._group.set_description(f"{description}\n{text}" if description else text)

    def _on_field_changed(self, row: DataFormRowsT, field: DataField) -> None:
        row.set_validation(*field.is_valid())
        self._emit_valid()

    def _on_option_activated(self, _row: ListSingleChoiceRow) -> None:
        cast(Gtk.Window, self.get_root()).activate_default()

    def _emit_valid(self) -> None:
        self.emit("is-valid", self._form.is_valid())
