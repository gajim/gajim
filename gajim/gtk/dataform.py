# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast

from collections.abc import Callable

from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango
from nbxmpp.modules.dataforms import DataField
from nbxmpp.modules.dataforms import extend_form
from nbxmpp.modules.dataforms import MultipleDataForm
from nbxmpp.modules.dataforms import SimpleDataForm
from nbxmpp.modules.dataforms import Uri
from nbxmpp.protocol import InvalidJid
from nbxmpp.simplexml import Node

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.util.image import scale_pixbuf_from_data
from gajim.common.util.uri import open_uri

from gajim.gtk.util import make_href_markup
from gajim.gtk.util import MaxWidthComboBoxText
from gajim.gtk.util import MultiLineLabel

# Options

#  no-scrolling                 No scrollbars
#  form-width                   Minimal form width
#  right-align                  Right align labels
#  hide-fallback-fields         Hide fallback fields in IBR form (ejabberd)
#  left-width                   Width for labels
#  read-only                    Read only mode for fields
#  entry-activates-default      Form entry activates the default widget


class DataFormWidget(Gtk.ScrolledWindow):

    __gsignals__ = {
        'is-valid': (GObject.SignalFlags.RUN_LAST, None, (bool,)),
    }

    def __init__(self,
                 form_node: SimpleDataForm | MultipleDataForm,
                 options: dict[str, Any] | None = None
                 ) -> None:

        Gtk.ScrolledWindow.__init__(self)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.get_style_context().add_class('data-form-widget')
        self.set_overlay_scrolling(False)

        if options is None:
            options = {}

        if options.get('no-scrolling', False):
            self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)

        self._form_node = form_node
        if self._form_node.is_reported:
            self._form_widget = DataFormReportedTable(form_node)
        else:
            self._form_widget = FormGrid(form_node, options)
            self._form_widget.connect('form-completed', self._on_form_completed)
        self._original_form_hash = self.get_form_hash()

        self.add(self._form_widget)

        self.connect('destroy', self._on_destroy)

    @property
    def title(self) -> str | None:
        return self._form_widget.title

    @property
    def instructions(self) -> str | None:
        return self._form_widget.instructions

    def validate(self) -> None:
        return self._form_widget.validate(True)

    def get_form(self) -> SimpleDataForm | MultipleDataForm:
        return self._form_node

    def get_submit_form(self) -> SimpleDataForm:
        if self._form_node.is_reported:
            raise ValueError('MultipleDataForm cannot be submitted')
        self._form_node.type_ = 'submit'
        return self._form_node

    def get_form_hash(self) -> int:
        return hash(str(self._form_node))

    def was_modified(self) -> bool:
        return self._original_form_hash != self.get_form_hash()

    def reset_form_hash(self) -> None:
        self._original_form_hash = self.get_form_hash()

    def focus_first_entry(self) -> None:
        if self._form_node.is_reported:
            return

        for row in range(self._form_widget.row_count):
            widget = self._form_widget.get_child_at(1, row)
            if isinstance(widget, Gtk.Entry):
                widget.grab_focus_without_selecting()
                break

    def _on_destroy(self, widget: Gtk.ScrolledWindow) -> None:
        self._form_widget.destroy()

    def _on_form_completed(self, *_args) -> None:
        self.get_toplevel().activate_default()


class FormGrid(Gtk.Grid):

    __gsignals__ = {
        'form-completed': (GObject.SignalFlags.RUN_LAST, None, ())
    }

    def __init__(self,
                 form_node: SimpleDataForm,
                 options: dict[str, Any]
                 ) -> None:

        Gtk.Grid.__init__(self)
        self.set_column_spacing(12)
        self.set_row_spacing(12)
        self.set_halign(Gtk.Align.CENTER)
        self.row_count = 0

        self.rows: list[(SizeAdjustment |
                         Title |
                         Instructions |
                         Field |
                         ImageMediaField)] = []

        form_width = options.get('form-width', 435)
        self.set_size_request(form_width, -1)

        self._data_form = form_node

        self.title: str | None = None
        self.instructions: str | None = None

        self._fields = {
            'boolean': BooleanField,
            'fixed': FixedField,
            'list-single': ListSingleField,
            'list-multi': ListMultiField,
            'jid-single': JidSingleField,
            'jid-multi': JidMultiField,
            'text-single': TextSingleField,
            'text-private': TextPrivateField,
            'text-multi': TextMultiField
        }

        self._add_row(SizeAdjustment(options))

        if form_node.title is not None:
            self.title = form_node.title
            self._add_row(Title(form_node.title))
        if form_node.instructions:
            self.instructions = form_node.instructions
            self._add_row(Instructions(form_node.instructions))

        self._analyse_fields(form_node, options)
        self._parse_form(form_node, options)

        self.connect('destroy', self._on_destroy)

    def _add_row(
        self,
        field: SizeAdjustment | Title | Instructions | Field | ImageMediaField
    ) -> None:

        field.add(self, self.row_count)
        self.row_count += 1
        self.rows.append(field)

    @staticmethod
    def _analyse_fields(form_node: SimpleDataForm,
                        options: dict[str, Any]
                        ) -> None:

        if 'right-align' in options:
            # Don’t overwrite option
            return

        label_lengths = {0}
        for field in form_node.iter_fields():
            if field.type_ == 'hidden':
                continue

            if field.label is None:
                continue

            label_lengths.add(len(field.label))

        options['right-align'] = max(label_lengths) < 30

    def _parse_form(self,
                    form_node: SimpleDataForm,
                    options: dict[str, Any]
                    ) -> None:

        single_field = len(
            [field for field in form_node.fields
             if field.type_ not in ('fixed', 'hidden')]) == 1

        for field in form_node.iter_fields():
            if field.type_ == 'hidden':
                continue

            if options.get('hide-fallback-fields'):
                if field.var is not None and 'fallback' in field.var:
                    continue

            if field.media:
                if not self._add_media_field(field, options):
                    # We don’t understand this media element, ignore it
                    continue

            widget = self._fields[field.type_]
            if single_field and widget is ListSingleField:
                row = widget(field, self, options, treeview=True)
                row.connect(
                    'row-activated', self._on_single_list_field_activated)
                self._add_row(row)
            else:
                self._add_row(widget(field, self, options))

    def _add_media_field(self,
                         field: DataField,
                         options: dict[str, Any]
                         ) -> bool:

        if field.type_ not in ('text-single', 'text-private', 'text-multi'):
            return False

        for uri in field.media.uris:
            if not uri.type_.startswith('image/'):
                continue

            if not uri.uri_data.startswith('cid'):
                continue

            self._add_row(ImageMediaField(uri, self, options))
            return True
        return False

    def validate(self, is_valid: bool) -> None:
        value: bool = self._data_form.is_valid() if is_valid else False
        viewport = cast(Gtk.Viewport, self.get_parent())
        dataform_widget = cast(DataFormWidget, viewport.get_parent())
        dataform_widget.emit('is-valid', value)

    def _on_single_list_field_activated(self, widget: ListSingleField) -> None:
        self.emit('form-completed')

    def _on_destroy(self, widget: Gtk.Grid) -> None:
        for row in self.rows:
            if isinstance(row, Field):
                row.destroy()
        self.rows.clear()


class SizeAdjustment:
    def __init__(self, options: dict[str, Any]) -> None:
        self._left_box = Gtk.Box()
        self._right_box = Gtk.Box()

        left_width = options.get('left-width', 100)
        self._left_box.set_size_request(left_width, -1)
        self._right_box.set_hexpand(True)
        self._right_box.set_size_request(250, -1)

    def add(self, form_grid: FormGrid, row_number: int) -> None:
        form_grid.attach(self._left_box, 0, row_number, 1, 1)
        form_grid.attach_next_to(self._right_box,
                                 self._left_box,
                                 Gtk.PositionType.RIGHT, 1, 1)


class Title:
    def __init__(self, title: str) -> None:
        self._label = Gtk.Label(label=title)
        self._label.set_line_wrap(True)
        self._label.set_line_wrap_mode(Pango.WrapMode.WORD)
        self._label.set_justify(Gtk.Justification.CENTER)
        self._label.get_style_context().add_class('data-form-title')

    def add(self, form_grid: FormGrid, row_number: int) -> None:
        form_grid.attach(self._label, 0, row_number, 2, 1)


class Instructions:
    def __init__(self, instructions: str) -> None:
        self._label = Gtk.Label()
        self._label.set_markup(make_href_markup(instructions))
        self._label.set_line_wrap(True)
        self._label.set_line_wrap_mode(Pango.WrapMode.WORD)
        self._label.set_justify(Gtk.Justification.CENTER)

    def add(self, form_grid: FormGrid, row_number: int) -> None:
        form_grid.attach(self._label, 0, row_number, 2, 1)


class Field(GObject.GObject):
    def __init__(self,
                 field: DataField,
                 form_grid: FormGrid,
                 options: dict[str, Any]
                 ) -> None:

        GObject.GObject.__init__(self)

        self._widget: Gtk.Widget | None = None
        self._field = field
        self._form_grid = form_grid
        self._validate_source_id: int | None = None
        self._read_only = options.get('read-only', False)

        self._label = Gtk.Label(label=field.label)
        self._label.set_single_line_mode(False)
        self._label.set_line_wrap(True)
        self._label.set_line_wrap_mode(Pango.WrapMode.WORD)
        self._label.set_width_chars(15)
        self._label.set_xalign(bool(options.get('right-align')))
        self._label.set_tooltip_text(field.description)

        self._warning_image = Gtk.Image.new_from_icon_name(
            'dialog-warning-symbolic', Gtk.IconSize.MENU)
        self._warning_image.get_style_context().add_class('warning-color')
        self._warning_image.set_no_show_all(True)
        self._warning_image.set_valign(Gtk.Align.CENTER)
        self._warning_image.set_tooltip_text(_('Required'))
        self._warning_box = Gtk.Box()
        self._warning_box.set_size_request(16, -1)
        self._warning_box.add(self._warning_image)

    @property
    def read_only(self) -> bool:
        return self._read_only

    def add(self,
            form_grid: FormGrid,
            row_number: int
            ) -> None:

        assert self._widget is not None
        form_grid.attach(self._label, 0, row_number, 1, 1)
        form_grid.attach_next_to(self._widget,
                                 self._label,
                                 Gtk.PositionType.RIGHT, 1, 1)
        if self._field.type_ in ('jid-single',
                                 'jid-multi',
                                 'text-single',
                                 'text-private',
                                 'text-multi',
                                 'list-multi'):
            form_grid.attach_next_to(self._warning_box,
                                     self._widget,
                                     Gtk.PositionType.RIGHT, 1, 1)

            is_valid, error = self._field.is_valid()
            self._set_warning(is_valid, error)

    def _set_warning(self,
                     is_valid: bool,
                     error: str | InvalidJid
                     ) -> None:

        if not self._field.required and not is_valid and not error:
            # If its not valid and no error is given, its the initial call
            # to show all icons on required fields.
            return

        style = self._warning_image.get_style_context()
        if error:
            style.remove_class('warning-color')
            style.add_class('error-color')
        else:
            error = _('Required')
            style.remove_class('error-color')
            style.add_class('warning-color')
        self._warning_image.set_tooltip_text(str(error))
        self._warning_image.set_visible(not is_valid)

    def _validate(self, delay: bool = True) -> None:
        self._form_grid.validate(False)
        if self._validate_source_id is not None:
            GLib.source_remove(self._validate_source_id)

        def _start_validation() -> None:
            is_valid, error = self._field.is_valid()
            self._set_warning(is_valid, error)
            self._form_grid.validate(is_valid)
            self._validate_source_id = None

        if delay:
            self._validate_source_id = GLib.timeout_add(200, _start_validation)
        else:
            _start_validation()

    def destroy(self) -> None:
        if self._validate_source_id is not None:
            GLib.source_remove(self._validate_source_id)


class BooleanField(Field):
    def __init__(self,
                 field: DataField,
                 form_grid: FormGrid,
                 options: dict[str, Any]
                 ) -> None:

        Field.__init__(self, field, form_grid, options)

        if self.read_only:
            label = _('Yes') if field.value else _('No')
            self._widget = Gtk.Label(label=label, selectable=True)
            self._widget.set_xalign(0)
        else:
            self._widget = Gtk.CheckButton()
            self._widget.set_active(field.value)
            self._widget.connect('toggled', self._toggled)
        self._widget.set_valign(Gtk.Align.CENTER)

    def _toggled(self, _widget: Gtk.CheckButton) -> None:
        assert isinstance(self._widget, Gtk.CheckButton)
        self._field.value = self._widget.get_active()
        self._validate()


class FixedField(Field):
    def __init__(self,
                 field: DataField,
                 form_grid: FormGrid,
                 options: dict[str, Any]
                 ) -> None:

        Field.__init__(self, field, form_grid, options)

        self._label.set_markup(make_href_markup(field.value))

        # If the value is more than 40 chars it proabably isn’t
        # meant as a section header
        if len(field.value) < 40:
            self._label.get_style_context().add_class('field-fixed')
        else:
            self._label.set_xalign(0.5)

    def add(self, form_grid: FormGrid, row_number: int) -> None:
        if len(self._field.value) < 40:
            form_grid.attach(self._label, 0, row_number, 1, 1)
        else:
            form_grid.attach(self._label, 0, row_number, 2, 1)


class ListSingleField(Field):

    __gsignals__ = {
        'row-activated': (GObject.SignalFlags.RUN_LAST, None, ())
    }

    def __init__(self,
                 field: DataField,
                 form_grid: FormGrid,
                 options: dict[str, Any],
                 treeview: bool = False,
                 ) -> None:

        Field.__init__(self, field, form_grid, options)

        self._unique = treeview

        if self.read_only:
            self._widget = Gtk.Label(label=field.value, selectable=True)
            self._widget.set_xalign(0)
            return

        if treeview:
            self._setup_treeview(field)
        else:
            self._setup_dropdown(field)

    def _setup_dropdown(self, field: DataField) -> None:
        self._widget = MaxWidthComboBoxText()
        self._widget.set_valign(Gtk.Align.CENTER)
        for value, label in field.iter_options():
            if not label:
                label = value
            self._widget.append(value, label)

        self._widget.set_active_id(field.value)
        self._widget.connect('changed', self._changed)

    def _changed(self, widget: MaxWidthComboBoxText) -> None:
        self._field.value = widget.get_active_id()
        self._validate()

    def _setup_treeview(self, field: DataField) -> None:
        self._treeview = ListSingleTreeView(field, self)
        self._treeview.connect('row-activated', self._on_row_activated)
        self._treeview.connect('cursor-changed', self._on_cursor_changed)

        self._widget = Gtk.ScrolledWindow()
        self._widget.set_propagate_natural_height(True)
        self._widget.set_hexpand(True)
        self._widget.set_vexpand(True)
        self._widget.set_min_content_height(100)
        self._widget.set_max_content_height(300)
        self._widget.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._widget.add(self._treeview)


    def _on_cursor_changed(self, *_args: Any) -> None:
        model, treeiter = self._treeview.get_selection().get_selected()
        if treeiter is None:
            return None
        self._field.value = model[treeiter][1]
        self._validate(delay=False)

    def _on_row_activated(self, *_args: Any) -> None:
        self.emit('row-activated')

    def add(self,
            form_grid: FormGrid,
            row_number: int
            ) -> None:
        if self._unique:
            form_grid.attach(self._widget, 0, row_number, 2, 1)
        else:
            super().add(form_grid, row_number)


class ListSingleTreeView(Gtk.TreeView):
    def __init__(self,
                 field: DataField,
                 multi_field: ListSingleField
                 ) -> None:

        Gtk.TreeView.__init__(self)

        self._field = field
        self._multi_field = multi_field

        # label, value, tooltip
        self._store = Gtk.ListStore(str, str, str)

        col = Gtk.TreeViewColumn(field.label)
        cell = Gtk.CellRendererText()
        cell.set_property('ellipsize', Pango.EllipsizeMode.END)
        cell.set_property('width-chars', 80)
        col.pack_start(cell, True)
        col.set_attributes(cell, text=0)
        self.append_column(col)

        self.set_headers_visible(True)

        for option in field.options:
            label, value = option
            self._store.append([label, value, label])

        if any(filter(lambda x: len(x[0]) > 80, field.options)):
            self.set_tooltip_column(2)

        self.set_model(self._store)


class ListMultiField(Field):
    def __init__(self,
                 field: DataField,
                 form_grid: FormGrid,
                 options: dict[str, Any]
                 ) -> None:

        Field.__init__(self, field, form_grid, options)
        self._label.set_valign(Gtk.Align.START)

        self._treeview = ListMultiTreeView(field, self)

        self._widget = Gtk.ScrolledWindow()
        self._widget.set_propagate_natural_height(True)
        self._widget.set_min_content_height(100)
        self._widget.set_max_content_height(300)
        self._widget.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._widget.add(self._treeview)

    def validate(self) -> None:
        self._validate()


class ListMultiTreeView(Gtk.TreeView):
    def __init__(self,
                 field: DataField,
                 multi_field: ListMultiField
                 ) -> None:

        Gtk.TreeView.__init__(self)

        self._field = field
        self._multi_field = multi_field

        # label, value, tooltip, toggled
        self._store = Gtk.ListStore(str, str, str, bool)

        col = Gtk.TreeViewColumn()
        cell = Gtk.CellRendererText()
        cell.set_property('ellipsize', Pango.EllipsizeMode.END)
        cell.set_property('width-chars', 40)
        col.pack_start(cell, True)
        col.set_attributes(cell, text=0)
        self.append_column(col)

        col = Gtk.TreeViewColumn()
        cell = Gtk.CellRendererToggle()
        cell.set_activatable(True)
        cell.set_property('xalign', 1)
        cell.set_property('xpad', 10)
        cell.connect('toggled', self._toggled)
        col.pack_start(cell, True)
        col.set_attributes(cell, active=3)

        if not multi_field.read_only:
            self.append_column(col)

        self.set_headers_visible(False)

        for option in field.options:
            label, value = option
            if multi_field.read_only and value not in field.values:
                continue
            self._store.append(
                [label, value, label, value in field.values])

        if any(filter(lambda x: len(x[0]) > 40, field.options)):
            self.set_tooltip_column(2)

        self.set_model(self._store)

    def _toggled(self,
                 _renderer: Gtk.CellRendererToggle,
                 path: str
                 ) -> None:

        iter_ = self._store.get_iter(path)
        current_value = self._store[iter_][3]
        self._store.set_value(iter_, 3, not current_value)
        self._set_values()
        self._multi_field.validate()

    def _set_values(self) -> None:
        values: list[str] = []
        model = self.get_model()
        assert model is not None
        for row in model:
            if not row[3]:
                continue
            values.append(row[1])
        self._field.values = values


class JidMultiField(Field):
    def __init__(self,
                 field: DataField,
                 form_grid: FormGrid,
                 options: dict[str, Any]
                 ) -> None:

        Field.__init__(self, field, form_grid, options)
        self._label.set_valign(Gtk.Align.START)

        self._treeview = JidMutliTreeView(field, self)

        self._add_button = Gtk.ToolButton(icon_name='list-add-symbolic')
        self._add_button.connect('clicked', self._add_clicked)

        self._remove_button = Gtk.ToolButton(icon_name='list-remove-symbolic')
        self._remove_button.connect('clicked', self._remove_clicked)

        self._toolbar = Gtk.Toolbar()
        self._toolbar.set_icon_size(Gtk.IconSize.MENU)
        self._toolbar.set_style(Gtk.ToolbarStyle.ICONS)
        self._toolbar.get_style_context().add_class('inline-toolbar')
        self._toolbar.add(self._add_button)
        self._toolbar.add(self._remove_button)

        self._widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self._scrolled_window = Gtk.ScrolledWindow()
        self._scrolled_window.set_propagate_natural_height(True)
        self._scrolled_window.set_min_content_height(100)
        self._scrolled_window.set_max_content_height(300)
        self._scrolled_window.add(self._treeview)

        self._widget.pack_start(self._scrolled_window, True, True, 0)

        if not self._read_only:
            self._widget.pack_end(self._toolbar, False, False, 0)

    def _add_clicked(self, _widget: Gtk.ToolButton) -> None:
        model = self._treeview.get_model()
        assert isinstance(model, Gtk.ListStore)
        model.append([''])

    def _remove_clicked(self, _widget: Gtk.ToolButton) -> None:
        mod, paths = self._treeview.get_selection().get_selected_rows()
        for path in paths:
            iter_ = mod.get_iter(path)
            model = self._treeview.get_model()
            assert isinstance(model, Gtk.ListStore)
            model.remove(iter_)

        jids: list[str] = []
        model = self._treeview.get_model()
        assert model is not None
        for row in model:
            if not row[0]:
                continue
            jids.append(row[0])
        self._field.values = jids
        self._validate()

    def validate(self) -> None:
        self._validate()


class JidMutliTreeView(Gtk.TreeView):
    def __init__(self,
                 field: DataField,
                 multi_field: JidMultiField
                 ) -> None:

        Gtk.TreeView.__init__(self)

        self._field = field
        self._multi_field = multi_field

        self._store = Gtk.ListStore(str)

        col = Gtk.TreeViewColumn()
        cell = Gtk.CellRendererText()
        cell.set_property('editable', True)
        cell.set_property('placeholder-text', 'user@example.org')
        cell.connect('edited', self._jid_edited)
        col.pack_start(cell, True)
        col.set_attributes(cell, text=0)
        self.append_column(col)

        self.set_headers_visible(False)

        for value in field.values:
            self._store.append([value])

        self.set_model(self._store)

    def _jid_edited(self,
                    _renderer: Gtk.CellRendererText,
                    path: str,
                    new_text: str
                    ) -> None:

        iter_ = self._store.get_iter(path)
        self._store.set_value(iter_, 0, new_text)
        self._set_values()
        self._multi_field.validate()

    def _set_values(self) -> None:
        jids: list[str] = []
        for row in self._store:
            if not row[0]:
                continue
            jids.append(row[0])
        self._field.values = jids


class TextSingleField(Field):
    def __init__(self,
                 field: DataField,
                 form_grid: FormGrid,
                 options: dict[str, Any]
                 ) -> None:

        Field.__init__(self, field, form_grid, options)

        if self.read_only:
            self._widget = Gtk.Label(label=field.value, selectable=True)
            self._widget.set_xalign(0)
            self._widget.set_selectable(True)
        else:
            self._widget = Gtk.Entry()
            self._widget.set_text(field.value)
            self._widget.connect('changed', self._changed)
            if options.get('entry-activates-default', False):
                self._widget.set_activates_default(True)
        self._widget.set_valign(Gtk.Align.CENTER)

    def _changed(self, _widget: Gtk.Entry) -> None:
        assert isinstance(self._widget, Gtk.Entry)
        self._field.value = self._widget.get_text()
        self._validate()


class TextPrivateField(TextSingleField):
    def __init__(self,
                 field: DataField,
                 form_grid: FormGrid,
                 options: dict[str, Any]
                 ) -> None:

        TextSingleField.__init__(self, field, form_grid, options)
        if isinstance(self._widget, Gtk.Entry):
            self._widget.set_input_purpose(Gtk.InputPurpose.PASSWORD)
            self._widget.set_visibility(False)


class JidSingleField(TextSingleField):
    def __init__(self,
                 field: DataField,
                 form_grid: FormGrid,
                 options: dict[str, Any]
                 ) -> None:

        TextSingleField.__init__(self, field, form_grid, options)


class TextMultiField(Field):
    def __init__(self,
                 field: DataField,
                 form_grid: FormGrid,
                 options: dict[str, Any]
                 ) -> None:

        Field.__init__(self, field, form_grid, options)
        self._label.set_valign(Gtk.Align.START)

        length = len(field.value)

        if self.read_only:
            self._textview = MultiLineLabel(label=field.value, xalign=0)

        else:
            self._textview = Gtk.TextView()
            self._textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
            self._textview.get_buffer().set_text(field.value)
            self._textview.get_buffer().connect('changed', self._changed)

        if self.read_only and length < 500:
            self._widget = self._textview
        else:
            self._widget = Gtk.ScrolledWindow()
            self._widget.set_policy(Gtk.PolicyType.NEVER,
                                    Gtk.PolicyType.AUTOMATIC)
            self._widget.set_propagate_natural_height(True)
            self._widget.set_min_content_height(100)

            self._widget.add(self._textview)

    def _changed(self, widget: Gtk.TextBuffer) -> None:
        self._field.value = widget.get_text(*widget.get_bounds(), False)
        self._validate()


class ImageMediaField:
    def __init__(self,
                 uri: Uri,
                 form_grid: FormGrid,
                 _options: dict[str, Any]
                 ) -> None:

        self._uri = uri
        self._form_grid = form_grid

        filename = uri.uri_data.split(':')[1].split('@')[0]
        data = app.bob_cache.get(filename)
        if data is None:
            self._image = Gtk.Image()
            return

        pixbuf = scale_pixbuf_from_data(data, 170)
        self._image = Gtk.Image.new_from_pixbuf(pixbuf)
        self._image.set_halign(Gtk.Align.CENTER)
        self._image.get_style_context().add_class('preview-image')

    def add(self, form_grid: FormGrid, row_number: int) -> None:
        form_grid.attach(self._image, 1, row_number, 1, 1)


class FakeDataFormWidget(Gtk.ScrolledWindow):
    def __init__(self, fields: dict[str, str]) -> None:
        Gtk.ScrolledWindow.__init__(self)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_overlay_scrolling(False)
        self.get_style_context().add_class('data-form-widget')

        self._grid = Gtk.Grid()
        self._grid.set_column_spacing(12)
        self._grid.set_row_spacing(12)
        self._grid.set_halign(Gtk.Align.CENTER)

        self._fields = fields
        self._entries: dict[str, Gtk.Entry] = {}
        self._row_count = 0

        instructions = fields.pop('instructions', None)
        if instructions is not None:
            label = Gtk.Label(label=instructions)
            label.set_justify(Gtk.Justification.CENTER)
            label.set_max_width_chars(40)
            label.set_line_wrap(True)
            label.set_line_wrap_mode(Pango.WrapMode.WORD)
            self._grid.attach(label, 0, self._row_count, 2, 1)
            self._row_count += 1

        redirect_url = fields.pop('redirect-url', None)
        if not fields and redirect_url is not None:
            # Server wants to redirect registration
            button = Gtk.Button(label='Register')
            button.set_halign(Gtk.Align.CENTER)
            button.get_style_context().add_class('suggested-action')
            button.connect('clicked', lambda *args: open_uri(redirect_url))
            self._grid.attach(button, 0, self._row_count, 2, 1)
        else:
            self._add_fields()
        self.add(self._grid)
        self.show_all()

    def _add_fields(self) -> None:
        for name, value in self._fields.items():
            if name in ('key', 'x', 'registered'):
                continue

            label = Gtk.Label(label=name.capitalize())
            label.set_xalign(1)
            self._grid.attach(label, 0, self._row_count, 1, 1)
            self._row_count += 1

            entry = Gtk.Entry()
            entry.set_text(value)
            if name == 'password':
                entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
                entry.set_visibility(False)
            self._entries[name] = entry

            self._grid.attach_next_to(entry, label,
                                      Gtk.PositionType.RIGHT, 1, 1)

    def get_submit_form(self) -> dict[str, str]:
        fields: dict[str, str] = {}
        for name, entry in self._entries.items():
            fields[name] = entry.get_text()
        return fields


class DataFormDialog(Gtk.Dialog):
    def __init__(self,
                 title: str,
                 transient_for: Gtk.Window,
                 form: SimpleDataForm,
                 node: Node,
                 submit_callback: Callable[..., Any]
                 ) -> None:

        Gtk.Dialog.__init__(self,
                            title=title,
                            transient_for=transient_for,
                            modal=False)
        self.set_default_size(600, 500)

        self._submit_callback = submit_callback
        self._form = DataFormWidget(extend_form(node=form))
        self._node = node

        self.get_content_area().get_style_context().add_class('dialog-margin')
        self.get_content_area().add(self._form)

        self.add_button(_('Cancel'), Gtk.ResponseType.CANCEL)

        submit_button = self.add_button(_('Submit'), Gtk.ResponseType.OK)
        submit_button.get_style_context().add_class('suggested-action')
        self.set_default_response(Gtk.ResponseType.OK)

        self.connect('response', self._on_response)
        self.show_all()

    def _on_response(self,
                     _dialog: Gtk.Window,
                     response: Gtk.ResponseType
                     ) -> None:

        if response == Gtk.ResponseType.OK:
            self._submit_callback(self._form.get_submit_form(), self._node)
        self.destroy()


class DataFormReportedTable(Gtk.Grid):
    '''
    A widget representing the results of a command as a table, when the data
    form contains a <reported> element.
    '''

    def __init__(self, form_node: MultipleDataForm) -> None:
        super().__init__(row_spacing=10)
        self._form_node = form_node

        self.title = form_node.title
        self.instructions = form_node.instructions

        self._process_form()
        self._build_list_store()
        self._build_treeview()
        self._build_scrolled_window()

    def _process_form(self) -> None:
        self._column_names: list[str] = []
        self._column_types: list[str] = []
        for field in self._form_node.reported.iter_fields():
            self._column_types.append(field.type_)
            self._column_names.append(field.label)

        rows: list[list[str]] = [[f.value for f in record.fields]
                                 for record in self._form_node.items]

        self._rows = rows

    def _build_list_store(self) -> None:
        self._list_store = Gtk.ListStore(*(str for _ in self._column_names))
        for row in self._rows:
            self._list_store.append(row)

    def _build_treeview(self) -> None:
        self._treeview = Gtk.TreeView(model=self._list_store.filter_new())
        self._treeview.connect('row-activated', self._on_row_activate)

        for i, column_title in enumerate(self._column_names):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            self._treeview.append_column(column)

    def _build_scrolled_window(self) -> None:
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_vexpand(True)
        scrolled_window.set_hexpand(True)
        scrolled_window.add(self._treeview)

        title = f'<big>{GLib.markup_escape_text(self._form_node.title)}</big>'
        self.attach(Gtk.Label(label=title, use_markup=True), 0, 0, 1, 1)
        self.attach(scrolled_window, 0, 2, 1, 1)

    def _on_row_activate(
        self,
        _tree_view: Gtk.TreeView,
        path: Gtk.TreePath,
        column: Gtk.TreeViewColumn,
    ) -> None:
        row = self._rows[int(path.to_string())]
        col = self._column_names.index(column.get_title())
        # If the activated cell is a JID, start a chat with it.
        if self._column_types[col] == 'jid-single':
            dest: str | None = row[col]
        else:
            # else, try to find a column that is a JID
            for i, t in enumerate(self._column_types):
                if t == 'jid-single':
                    dest = row[i]
                    break
            else:
                dest = None
        if dest:
            app.app.activate_action(
                'start-chat', GLib.Variant('as', [dest, '']))

    def validate(self, is_valid: bool) -> None:
        viewport = cast(Gtk.Viewport, self.get_parent())
        dataform_widget = cast(DataFormWidget, viewport.get_parent())
        dataform_widget.emit('is-valid', is_valid)
