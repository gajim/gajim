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

from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Pango

from gajim.common.i18n import _


class DataFormWidget(Gtk.ScrolledWindow):

    __gsignals__ = {'is-valid': (GObject.SignalFlags.RUN_LAST, None, (bool,))}

    def __init__(self, form_node, options=None):
        Gtk.ScrolledWindow.__init__(self)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.get_style_context().add_class('data-form-widget')

        self._form_node = form_node

        if options is None:
            options = {}
        self._form_grid = FormGrid(form_node, options)

        self.add(self._form_grid)

    @property
    def title(self):
        return self._form_grid.title

    @property
    def instructions(self):
        return self._form_grid.instructions

    def validate(self):
        return self._form_grid.validate(True)

    def get_submit_form(self):
        self._form_node.type_ = 'submit'
        return self._form_node


class FormGrid(Gtk.Grid):
    def __init__(self, form_node, options):
        Gtk.Grid.__init__(self)
        self.set_column_spacing(12)
        self.set_row_spacing(12)
        self.set_halign(Gtk.Align.CENTER)
        self.row_count = 0
        self.rows = []

        self._data_form = form_node

        self.title = None
        self.instructions = None

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

        if form_node.title is not None:
            self.title = form_node.title
            self.add_row(Title(form_node.title))
        if form_node.instructions is not None:
            self.instructions = form_node.instructions
            self.add_row(Instructions(form_node.instructions))

        self.analyse_fields(form_node, options)
        self.parse_form(form_node, options)

    def add_row(self, field):
        field.add(self, self.row_count)
        self.row_count += 1
        self.rows.append(field)

    @staticmethod
    def analyse_fields(form_node, options):
        if 'right_align' in options:
            # Dont overwrite option
            return

        label_lengths = set([0])
        for field in form_node.iter_fields():
            if field.type_ == 'hidden':
                continue

            if field.label is None:
                continue

            label_lengths.add(len(field.label))

        options['right_align'] = max(label_lengths) < 30

    def parse_form(self, form_node, options):
        for field in form_node.iter_fields():
            if field.type_ == 'hidden':
                continue

            widget = self._fields[field.type_]
            self.add_row(widget(field, self, options))

    def validate(self, is_valid):
        value = self._data_form.is_valid() if is_valid else False
        self.get_parent().get_parent().emit('is-valid', value)


class Title:
    def __init__(self, title):
        self._label = Gtk.Label(label=title)
        self._label.get_style_context().add_class('data-form-title')

    def add(self, form_grid, row_number):
        form_grid.attach(self._label, 0, row_number, 2, 1)


class Instructions:
    def __init__(self, instructions):
        self._label = Gtk.Label(label=instructions)
        self._label.set_line_wrap(True)
        self._label.set_line_wrap_mode(Pango.WrapMode.WORD)

    def add(self, form_grid, row_number):
        form_grid.attach(self._label, 0, row_number, 2, 1)


class Field:
    def __init__(self, field, form_grid, options):
        self._field = field
        self._form_grid = form_grid
        self._validate_source_id = None

        self._label = Gtk.Label(label=field.label)
        self._label.set_single_line_mode(False)
        self._label.set_line_wrap(True)
        self._label.set_line_wrap_mode(Pango.WrapMode.WORD)
        self._label.set_width_chars(15)
        self._label.set_size_request(100, -1)
        self._label.set_xalign(bool(options.get('right_align')))
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

    def add(self, form_grid, row_number):
        form_grid.attach(self._label, 0, row_number, 1, 1)
        form_grid.attach_next_to(self._widget,
                                 self._label,
                                 Gtk.PositionType.RIGHT, 1, 1)
        if self._field.type_ in ('jid-single',
                                 'jid-multi',
                                 'text-single',
                                 'text-private',
                                 'text-multi'):
            form_grid.attach_next_to(self._warning_box,
                                     self._widget,
                                     Gtk.PositionType.RIGHT, 1, 1)
            self._set_warning(False, '')

    def _set_warning(self, is_valid, error):
        if not self._field.required and not is_valid and not error:
            # If its not valid and no error is given, its the inital call
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

    def _validate(self):
        if self._validate_source_id is not None:
            GLib.source_remove(self._validate_source_id)

        def _start_validation():
            is_valid, error = self._field.is_valid()
            self._set_warning(is_valid, error)
            self._form_grid.validate(is_valid)
            self._validate_source_id = None

        self._validate_source_id = GLib.timeout_add(500, _start_validation)


class BooleanField(Field):
    def __init__(self, field, form_grid, options):
        Field.__init__(self, field, form_grid, options)

        self._widget = Gtk.CheckButton()
        self._widget.set_active(field.value)
        self._widget.connect('toggled', self._toggled)

    def _toggled(self, _widget):
        self._field.value = self._widget.get_active()


class FixedField(Field):
    def __init__(self, field, form_grid, options):
        Field.__init__(self, field, form_grid, options)

        self._label.set_text(field.value)

        # If the value is more than 40 chars it proabably isnt
        # meant as a section header
        if len(field.value) < 40:
            self._label.get_style_context().add_class('field-fixed')
        else:
            self._label.set_xalign(0.5)

    def add(self, form_grid, row_number):
        if len(self._field.value) < 40:
            form_grid.attach(self._label, 0, row_number, 1, 1)
        else:
            form_grid.attach(self._label, 0, row_number, 2, 1)


class ListSingleField(Field):
    def __init__(self, field, form_grid, options):
        Field.__init__(self, field, form_grid, options)

        self._widget = Gtk.ComboBoxText()
        for value, label in field.iter_options():
            if not label:
                label = value
            self._widget.append(value, label)

        self._widget.set_active_id(field.value)
        self._widget.connect('changed', self._changed)

    def _changed(self, widget):
        self._field.value = widget.get_active_id()


class ListMultiField(Field):
    def __init__(self, field, form_grid, options):
        Field.__init__(self, field, form_grid, options)
        self._label.set_valign(Gtk.Align.START)

        self._treeview = ListMutliTreeView(field)

        self._widget = Gtk.ScrolledWindow()
        self._widget.set_propagate_natural_height(True)
        self._widget.set_min_content_height(100)
        self._widget.set_max_content_height(300)
        self._widget.add(self._treeview)


class ListMutliTreeView(Gtk.TreeView):
    def __init__(self, field):
        Gtk.TreeView.__init__(self)

        self._field = field

        self._store = Gtk.ListStore(str, str, bool)

        col = Gtk.TreeViewColumn()
        cell = Gtk.CellRendererText()
        col.pack_start(cell, True)
        col.set_attributes(cell, text=0)
        self.append_column(col)

        col = Gtk.TreeViewColumn()
        cell = Gtk.CellRendererToggle()
        cell.set_activatable(True)
        cell.connect('toggled', self._toggled)
        col.pack_start(cell, True)
        col.set_attributes(cell, active=2)
        self.append_column(col)

        self.set_headers_visible(False)

        for option in field.options:
            # option = (label, value)
            self._store.append(
                [*option, option[1] in field.values])

        self.set_model(self._store)

    def _toggled(self, _renderer, path):
        iter_ = self._store.get_iter(path)
        current_value = self._store[iter_][2]
        self._store.set_value(iter_, 2, not current_value)
        self._set_values()

    def _set_values(self):
        values = []
        for row in self.get_model():
            if not row[2]:
                continue
            values.append(row[1])
        self._field.values = values


class JidMultiField(Field):
    def __init__(self, field, form_grid, options):
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
        self._widget.pack_end(self._toolbar, False, False, 0)

    def _add_clicked(self, _widget):
        self._treeview.get_model().append([''])

    def _remove_clicked(self, _widget):
        mod, paths = self._treeview.get_selection().get_selected_rows()
        for path in paths:
            iter_ = mod.get_iter(path)
            self._treeview.get_model().remove(iter_)

        jids = []
        for row in self._treeview.get_model():
            if not row[0]:
                continue
            jids.append(row[0])
        self._field.values = jids
        self._validate()

    def validate(self):
        self._validate()


class JidMutliTreeView(Gtk.TreeView):
    def __init__(self, field, multi_field):
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

    def _jid_edited(self, _renderer, path, new_text):
        iter_ = self._store.get_iter(path)
        self._store.set_value(iter_, 0, new_text)
        self._set_values()
        self._multi_field.validate()

    def _set_values(self):
        jids = []
        for row in self._store:
            if not row[0]:
                continue
            jids.append(row[0])
        self._field.values = jids


class TextSingleField(Field):
    def __init__(self, field, form_grid, options):
        Field.__init__(self, field, form_grid, options)

        self._widget = Gtk.Entry()
        self._widget.set_text(field.value)
        self._widget.connect('changed', self._changed)

    def _changed(self, _widget):
        self._field.value = self._widget.get_text()
        self._validate()


class TextPrivateField(TextSingleField):
    def __init__(self, field, form_grid, options):
        TextSingleField.__init__(self, field, form_grid, options)
        self._widget.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self._widget.set_visibility(False)


class JidSingleField(TextSingleField):
    def __init__(self, field, form_grid, options):
        TextSingleField.__init__(self, field, form_grid, options)


class TextMultiField(Field):
    def __init__(self, field, form_grid, options):
        Field.__init__(self, field, form_grid, options)
        self._label.set_valign(Gtk.Align.START)

        self._widget = Gtk.ScrolledWindow()
        self._widget.set_propagate_natural_height(True)
        self._widget.set_min_content_height(100)
        self._widget.set_max_content_height(300)

        self._textview = Gtk.TextView()
        self._textview.get_buffer().set_text(field.value)
        self._textview.get_buffer().connect('changed', self._changed)

        self._widget.add(self._textview)

    def _changed(self, widget):
        self._field.value = widget.get_text(*widget.get_bounds(), False)
        self._validate()
