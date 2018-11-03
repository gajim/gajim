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
from gi.repository import Pango


class DataFormWidget(Gtk.ScrolledWindow):
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
            self.add_row(widget(field, options))

    def is_valid(self):
        return self._data_form.is_valid()


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
    def __init__(self, field, options):
        self._field = field

        self._label = Gtk.Label(label=field.label)
        self._label.set_single_line_mode(False)
        self._label.set_line_wrap(True)
        self._label.set_line_wrap_mode(Pango.WrapMode.WORD)
        self._label.set_width_chars(15)
        self._label.set_size_request(100, -1)
        self._label.set_xalign(bool(options.get('right_align')))
        self._label.set_tooltip_text(field.description)

    def add(self, form_grid, row_number):
        form_grid.attach(self._label, 0, row_number, 1, 1)
        form_grid.attach_next_to(
            self._widget, self._label, Gtk.PositionType.RIGHT, 1, 1)


class BooleanField(Field):
    def __init__(self, field, options):
        Field.__init__(self, field, options)

        self._widget = Gtk.CheckButton()
        self._widget.set_active(field.value)
        self._widget.connect('toggled', self._toggled)

    def _toggled(self, _widget):
        self._field.value = self._widget.get_active()


class FixedField(Field):
    def __init__(self, field, options):
        Field.__init__(self, field, options)

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
    def __init__(self, field, options):
        Field.__init__(self, field, options)

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
    def __init__(self, field, options):
        Field.__init__(self, field, options)
        self._label.set_valign(Gtk.Align.START)

        self._treeview = ListMutliTreeView(field)

        self._widget = Gtk.ScrolledWindow()
        self._widget.set_propagate_natural_height(True)
        self._widget.set_min_content_height(100)
        self._widget.set_max_content_height(300)
        self._widget.add(self._treeview)
        self._widget.get_style_context().add_class('field-normal')


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
    def __init__(self, field, options):
        Field.__init__(self, field, options)
        self._label.set_valign(Gtk.Align.START)

        self._treeview = JidMutliTreeView(field)

        self._add_button = Gtk.Button.new_from_icon_name(
            'list-add-symbolic', Gtk.IconSize.MENU)
        self._add_button.connect('clicked', self._add_clicked)
        self._add_button.set_halign(Gtk.Align.START)

        self._remove_button = Gtk.Button.new_from_icon_name(
            'list-remove-symbolic', Gtk.IconSize.MENU)
        self._remove_button.connect('clicked', self._remove_clicked)
        self._remove_button.set_halign(Gtk.Align.START)

        self._button_box = Gtk.ButtonBox(
            orientation=Gtk.Orientation.HORIZONTAL)
        self._button_box.set_layout(Gtk.ButtonBoxStyle.START)
        self._button_box.add(self._add_button)
        self._button_box.add(self._remove_button)
        self._button_box.set_child_non_homogeneous(self._add_button, True)
        self._button_box.set_child_non_homogeneous(self._remove_button, True)

        self._widget = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._widget.set_spacing(6)

        self._scrolled_window = Gtk.ScrolledWindow()
        self._scrolled_window.set_propagate_natural_height(True)
        self._scrolled_window.set_min_content_height(100)
        self._scrolled_window.set_max_content_height(300)
        self._scrolled_window.add(self._treeview)

        self._widget.pack_start(self._scrolled_window, True, True, 0)
        self._widget.pack_end(self._button_box, False, False, 0)

        self._treeview.update_required_css()

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
        self._treeview.update_required_css()


class JidMutliTreeView(Gtk.TreeView):
    def __init__(self, field):
        Gtk.TreeView.__init__(self)

        self._field = field

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
        self.update_required_css()

    def _set_values(self):
        jids = []
        for row in self._store:
            if not row[0]:
                continue
            jids.append(row[0])
        self._field.values = jids

    def update_required_css(self):
        style = self.get_parent().get_style_context()
        if not self._field.required:
            style.add_class('field-normal')
            return

        if self._field.values:
            style.remove_class('field-required')
            style.add_class('field-normal')
        else:
            style.remove_class('field-normal')
            style.add_class('field-required')


class TextSingleField(Field):
    def __init__(self, field, options):
        Field.__init__(self, field, options)

        self._widget = Gtk.Entry()
        self._widget.set_text(field.value)
        self._widget.connect('changed', self._changed)
        self._update_required_css()

    def _changed(self, _widget):
        self._field.value = self._widget.get_text()
        self._update_required_css()

    def _update_required_css(self):
        if not self._field.required:
            return
        style = self._widget.get_style_context()
        if self._field.value:
            style.remove_class('entry-field-required')
        else:
            style.add_class('entry-field-required')


class TextPrivateField(TextSingleField):
    def __init__(self, field, options):
        TextSingleField.__init__(self, field, options)
        self._widget.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self._widget.set_visibility(False)


class JidSingleField(TextSingleField):
    def __init__(self, field, options):
        TextSingleField.__init__(self, field, options)


class TextMultiField(Field):
    def __init__(self, field, options):
        Field.__init__(self, field, options)
        self._label.set_valign(Gtk.Align.START)

        self._widget = Gtk.ScrolledWindow()
        self._widget.set_propagate_natural_height(True)
        self._widget.set_min_content_height(100)
        self._widget.set_max_content_height(300)

        self._textview = Gtk.TextView()
        self._textview.get_buffer().set_text(field.value)
        self._textview.get_buffer().connect('changed', self._changed)

        self._widget.add(self._textview)
        self._update_required_css()

    def _changed(self, widget):
        self._field.value = widget.get_text(*widget.get_bounds(), False)
        self._update_required_css()

    def _update_required_css(self):
        if not self._field.required:
            return
        style = self._widget.get_style_context()
        if self._field.value:
            style.remove_class('field-required')
        else:
            style.add_class('field-required')
