# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import Any

import datetime

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp.modules.vcard4 import VCard

from gajim.common.const import URIType
from gajim.common.i18n import _
from gajim.common.i18n import p_
from gajim.common.structs import URI
from gajim.common.util.text import escape_iri_path_segment
from gajim.common.util.uri import open_uri
from gajim.common.util.uri import parse_uri

from gajim.gtk.util import gtk_month
from gajim.gtk.util import python_month

LABEL_DICT = {
    'fn': _('Full Name'),
    'n': _('Name'),
    'bday': _('Birthday'),
    'gender': _('Gender'),
    'adr': p_('Profile', 'Address'),
    'tel': _('Phone No.'),
    'email': _('Email'),
    'impp': p_('Profile', 'IM Address'),
    'title': p_('Profile', 'Title'),
    'role': p_('Profile', 'Role'),
    'org': p_('Profile', 'Organisation'),
    'note': p_('Profile', 'Note'),
    'url': _('URL'),
    'key': p_('Profile', 'Public Encryption Key'),
}


FIELD_TOOLTIPS = {
    'key': _('Your public key or authentication certificate')
}


ADR_FIELDS = ['street', 'ext', 'pobox', 'code', 'locality', 'region', 'country']


ADR_PLACEHOLDER_TEXT = {
    'pobox': _('Post Office Box'),
    'street': _('Street'),
    'ext': _('Extended Address'),
    'locality': _('City'),
    'region': _('State'),
    'code': _('Postal Code'),
    'country': _('Country'),
}


DEFAULT_KWARGS: dict[str, Any] = {
    'fn': {'value': ''},
    'bday': {'value': '', 'value_type': 'date'},
    'gender': {'sex': '', 'identity': ''},
    'adr': {},
    'email': {'value': ''},
    'impp': {'value': ''},
    'tel': {'value': '', 'value_type': 'text'},
    'org': {'values': []},
    'title': {'value': ''},
    'role': {'value': ''},
    'url': {'value': ''},
    'key': {'value': '', 'value_type': 'text'},
    'note': {'value': ''},
}


PROPERTIES_WITH_TYPE = [
    'adr',
    'email',
    'impp',
    'tel',
    'key',
]


ORDER = [
    'fn',
    'gender',
    'bday',
    'adr',
    'email',
    'impp',
    'tel',
    'org',
    'title',
    'role',
    'url',
    'key',
    'note',
]


SEX_VALUES = {
    'M': _('Male'),
    'F': _('Female'),
    'O': p_('Gender', 'Other'),
    'N': p_('Gender', 'None'),
    'U': _('Unknown')
}


TYPE_VALUES = {
    '-': None,
    'home': _('Home'),
    'work': _('Work')
}


class VCardGrid(Gtk.Grid):
    def __init__(self, account: str) -> None:
        Gtk.Grid.__init__(self)

        self._callbacks = {
            'fn': TextEntryProperty,
            'bday': DateProperty,
            'gender': GenderProperty,
            'adr': AdrProperty,
            'tel': TextEntryProperty,
            'email': TextEntryProperty,
            'impp': TextEntryProperty,
            'title': TextEntryProperty,
            'role': TextEntryProperty,
            'org': TextEntryProperty,
            'url': TextEntryProperty,
            'key': KeyProperty,
            'note': MultiLineProperty,
        }

        self.set_column_spacing(12)
        self.set_row_spacing(12)
        self.set_no_show_all(True)
        self.set_visible(True)
        self.set_halign(Gtk.Align.CENTER)
        self.set_size_request(300, -1)

        self._account = account
        self._row_count: int = 0
        self._vcard: VCard | None = None
        self._props = []

    def set_editable(self, enabled: bool) -> None:
        for prop in self._props:
            prop.set_editable(enabled)

    def set_vcard(self, vcard: VCard) -> None:
        self.clear()
        self._vcard = vcard

        for entry in ORDER:
            for prop in vcard.get_properties():
                if entry != prop.name:
                    continue

                self.add_property(prop)

    def get_vcard(self) -> VCard | None:
        return self._vcard

    def validate(self) -> None:
        for prop in list(self._props):
            base_prop = prop.get_base_property()
            if base_prop.is_empty:
                self.remove_property(prop)

    def add_new_property(self, name: str) -> None:
        kwargs = DEFAULT_KWARGS[name]
        prop = self._vcard.add_property(name, **kwargs)
        self.add_property(prop, editable=True)

    def add_property(self, prop, editable=False):
        prop_class = self._callbacks.get(prop.name)
        if prop_class is None:
            return
        prop_obj = prop_class(prop, self._account)
        prop_obj.set_editable(editable)
        prop_obj.add_to_grid(self, self._row_count)

        self._props.append(prop_obj)
        self._row_count += 1

    def remove_property(self, prop):
        self.remove_row(prop.row_number)
        self._props.remove(prop)
        self._vcard.remove_property(prop.get_base_property())

    def clear(self) -> None:
        self._vcard = None
        self._row_count = 0
        for prop in list(self._props):
            self.remove_row(prop.row_number)

        self._props = []

    def sort(self) -> None:
        self.set_vcard(self._vcard)


class DescriptionLabel(Gtk.Label):
    def __init__(self, value: str) -> None:
        Gtk.Label.__init__(self, label=LABEL_DICT[value])
        if value == 'adr':
            self.set_valign(Gtk.Align.START)
        else:
            self.set_valign(Gtk.Align.CENTER)
        self.get_style_context().add_class('dim-label')
        self.get_style_context().add_class('margin-right18')
        self.set_visible(True)
        self.set_xalign(1)
        self.set_tooltip_text(FIELD_TOOLTIPS.get(value, ''))


class ValueLabel(Gtk.Label):
    def __init__(self, prop, account):
        Gtk.Label.__init__(self)
        self._prop = prop
        self._uri: URI | None = None
        self._account = account
        self.set_selectable(True)
        self.set_xalign(0)
        self.set_max_width_chars(50)
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.START)

        self.connect('activate-link', self._on_activate_link)
        if prop.name == 'org':
            self.set_value(prop.values[0] if prop.values else '')
        else:
            self.set_value(prop.value)

    def set_value(self, value: str) -> None:
        # EMAIL https://rfc-editor.org/rfc/rfc6350#section-6.4.2
        if self._prop.name == 'email':
            uri = 'mailto:' + escape_iri_path_segment(value)
            self.set_value_with_uri(value, uri)

        # All the properties that can be (single) URIs:
        # SOURCE    https://rfc-editor.org/rfc/rfc6350#section-6.1.3
        # PHOTO     https://rfc-editor.org/rfc/rfc6350#section-6.2.4
        # TEL       https://rfc-editor.org/rfc/rfc6350#section-6.4.1
        # IMPP      https://rfc-editor.org/rfc/rfc6350#section-6.4.3
        # TZ        https://rfc-editor.org/rfc/rfc6350#section-6.5.1
        # GEO       https://rfc-editor.org/rfc/rfc6350#section-6.5.2
        # LOGO      https://rfc-editor.org/rfc/rfc6350#section-6.6.3
        # MEMBER    https://rfc-editor.org/rfc/rfc6350#section-6.6.5
        # RELATED   https://rfc-editor.org/rfc/rfc6350#section-6.6.6
        # SOUND     https://rfc-editor.org/rfc/rfc6350#section-6.7.5
        # UID       https://rfc-editor.org/rfc/rfc6350#section-6.7.6
        # URL       https://rfc-editor.org/rfc/rfc6350#section-6.7.8
        # KEY       https://rfc-editor.org/rfc/rfc6350#section-6.8.1
        # FBURL     https://rfc-editor.org/rfc/rfc6350#section-6.9.1
        # CALADRURI https://rfc-editor.org/rfc/rfc6350#section-6.9.2
        # CALURI    https://rfc-editor.org/rfc/rfc6350#section-6.9.3
        elif self._prop.name in ('source', 'photo', 'tel', 'impp', 'tz', 'geo',
                                 'logo', 'member', 'related', 'sound', 'uid',
                                 'url', 'key', 'fburl', 'caladruri', 'caluri'):
            self.set_value_with_uri(value, value)

        else:
            self.set_text(value)

    def set_value_with_uri(self, value: str, uri: str) -> None:
        puri = parse_uri(uri)
        if puri.type == URIType.INVALID:
            self.set_text(value)
            return
        self._uri = puri
        super().set_markup('<a href="{}">{}</a>'.format(  # noqa: UP032
            GLib.markup_escape_text(uri),
            GLib.markup_escape_text(value)))

    def _on_activate_link(self, _label: Gtk.Label, _value: str) -> int:
        open_uri(self._uri, self._account)
        return Gdk.EVENT_STOP


class SexLabel(Gtk.Label):
    def __init__(self, prop):
        Gtk.Label.__init__(self)
        self._prop = prop

        self.set_selectable(True)
        self.set_xalign(0)
        self.set_max_width_chars(50)
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.START)

        self.set_text(prop.sex)

    def set_text(self, value: str) -> None:
        if not value or value == '-':
            super().set_text('')
        else:
            super().set_text(SEX_VALUES[value])


class IdentityLabel(Gtk.Label):
    def __init__(self, prop):
        Gtk.Label.__init__(self)
        self._prop = prop

        self.set_selectable(True)
        self.set_xalign(0)
        self.set_max_width_chars(50)
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.START)

        self.set_text(prop.identity)

    def set_text(self, value: str) -> None:
        super().set_text('' if not value else value)


class ValueEntry(Gtk.Entry):
    def __init__(self, prop):
        Gtk.Entry.__init__(self)
        self.set_valign(Gtk.Align.CENTER)
        self.set_max_width_chars(50)
        if prop.name == 'org':
            self.set_text(prop.values[0] if prop.values else '')
        else:
            self.set_text(prop.value)


class AdrEntry(Gtk.Entry):
    def __init__(self, prop, type_):
        Gtk.Entry.__init__(self)
        self.set_valign(Gtk.Align.CENTER)
        self.set_max_width_chars(50)
        values = getattr(prop, type_)
        if not values:
            value = ''
        else:
            value = values[0]
        self.set_text(value)
        self.set_placeholder_text(ADR_PLACEHOLDER_TEXT.get(type_))


class IdentityEntry(Gtk.Entry):
    def __init__(self, prop):
        Gtk.Entry.__init__(self)
        self.set_valign(Gtk.Align.CENTER)
        self.set_max_width_chars(50)
        self.set_text('' if not prop.identity else prop.identity)


class AdrBox(Gtk.Box):

    __gsignals__ = {
        'field-changed': (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            (str, str)
        )}

    def __init__(self, prop):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=6)

        for field in ADR_FIELDS:
            entry = AdrEntry(prop, field)
            entry.connect('notify::text', self._on_text_changed, field)
            self.add(entry)

        self.show_all()

    def _on_text_changed(self,
                         entry: Gtk.Entry,
                         _param: Any,
                         field: str
                         ) -> None:
        self.emit('field-changed', field, entry.get_text())


class AdrLabel(Gtk.Label):
    def __init__(self, prop, type_):
        Gtk.Label.__init__(self)
        self.set_selectable(True)
        self.set_xalign(0)
        self.set_max_width_chars(50)
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.START)
        values = getattr(prop, type_)
        if not values:
            value = ''
        else:
            value = values[0]
        self.set_text(value)

    def set_text(self, value: str) -> None:
        self.set_visible(bool(value))
        super().set_text(value)


class AdrBoxReadOnly(Gtk.Box):
    def __init__(self, prop):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=6)

        self._labels: dict[str, AdrLabel] = {}

        for field in ADR_FIELDS:
            label = AdrLabel(prop, field)
            self._labels[field] = label
            self.add(label)

    def set_field(self, field: str, value: str) -> None:
        self._labels[field].set_text(value)


class ValueTextView(Gtk.TextView):
    def __init__(self, prop):
        Gtk.TextView.__init__(self)
        self.props.right_margin = 8
        self.props.left_margin = 8
        self.props.top_margin = 8
        self.props.bottom_margin = 8

        self.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.set_hexpand(True)
        self.set_valign(Gtk.Align.FILL)

        self._prop = prop
        self.get_buffer().set_text(prop.value)
        self.get_buffer().connect('notify::text', self._on_text_changed)

    def get_text(self) -> str:
        start_iter, end_iter = self.get_buffer().get_bounds()
        return self.get_buffer().get_text(start_iter, end_iter, False)

    def _on_text_changed(self, _buffer: Gtk.TextBuffer, _param: Any) -> None:
        self._prop.value = self.get_text()


class TypeComboBox(Gtk.ComboBoxText):
    def __init__(self, parameters):
        Gtk.ComboBoxText.__init__(self)
        self.set_valign(Gtk.Align.CENTER)
        self._parameters = parameters
        self.append('-', '-')
        self.append('home', _('Home'))
        self.append('work', _('Work'))

        values = self._parameters.get_types()
        if 'home' in values:
            self.set_active_id('home')

        elif 'work' in values:
            self.set_active_id('work')

        else:
            self.set_active_id('-')

        self.connect('notify::active-id', self._on_active_id_changed)

    def _on_active_id_changed(self,
                              _combobox: Gtk.ComboBox,
                              _param: Any
                              ) -> None:
        type_ = self.get_active_id()
        if type_ == '-':
            self._parameters.remove_types(['work', 'home'])

        elif type_ == 'work':
            self._parameters.add_types(['work'])
            self._parameters.remove_types(['home'])

        elif type_ == 'home':
            self._parameters.add_types(['home'])
            self._parameters.remove_types(['work'])

    def get_text(self) -> str:
        type_value = self.get_active_id()
        if type_value == '-':
            return ''
        return self.get_active_text()


class GenderComboBox(Gtk.ComboBoxText):
    def __init__(self, prop):
        Gtk.ComboBoxText.__init__(self)
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.START)

        self._prop = prop

        self.append('-', '-')
        for key, value in SEX_VALUES.items():
            self.append(key, value)

        if not prop.sex:
            self.set_active_id('-')
        else:
            self.set_active_id(prop.sex)


class RemoveButton(Gtk.Button):
    def __init__(self):
        Gtk.Button.__init__(self)
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.START)
        image = Gtk.Image.new_from_icon_name('user-trash-symbolic',
                                             Gtk.IconSize.MENU)
        self.set_image(image)
        self.set_no_show_all(True)


class VCardProperty:
    def __init__(self, prop):
        self._prop = prop

        self._second_column: list[Gtk.Widget] = []
        self._third_column: list[Gtk.Widget] = []

        self._desc_label = DescriptionLabel(prop.name)
        self._remove_button = RemoveButton()
        self._remove_button.connect('clicked', self._on_remove_clicked)

        self._edit_widgets: list[Gtk.Widget] = [self._remove_button]
        self._read_widgets: list[Gtk.Widget] = []

        if prop.name in PROPERTIES_WITH_TYPE:
            self._type_combobox = TypeComboBox(prop.parameters)
            self._type_combobox.connect('notify::active-id',
                                        self._on_type_changed)
            type_ = self._type_combobox.get_active_id()
            icon_name = self._get_icon_name(type_)
            self._type_image = Gtk.Image.new_from_icon_name(
                icon_name, Gtk.IconSize.MENU)
            self._type_image.set_tooltip_text(TYPE_VALUES[type_])

            if prop.name == 'adr':
                self._type_image.set_valign(Gtk.Align.START)
                self._type_combobox.set_valign(Gtk.Align.START)

            self._edit_widgets.append(self._type_combobox)
            self._read_widgets.append(self._type_image)
            self._second_column.extend([self._type_combobox, self._type_image])

    @staticmethod
    def _get_icon_name(type_: str) -> str | None:
        if type_ == 'home':
            return 'feather-home'
        if type_ == 'work':
            return 'feather-briefcase'
        return None

    def _on_type_changed(self, _combobox: Gtk.ComboBox, _param: Any) -> None:
        type_ = self._type_combobox.get_active_id()
        icon_name = self._get_icon_name(type_)
        self._type_image.set_from_icon_name(icon_name, Gtk.IconSize.MENU)
        self._type_image.set_tooltip_text(TYPE_VALUES[type_])

    def _on_remove_clicked(self, button: Gtk.Button) -> None:
        button.get_parent().remove_property(self)

    @property
    def row_number(self) -> int:
        grid = self._desc_label.get_parent()
        return grid.child_get_property(self._desc_label, 'top-attach')

    def get_base_property(self):
        return self._prop

    def set_editable(self, enabled: bool) -> None:
        for widget in self._edit_widgets:
            widget.set_visible(enabled)

        for widget in self._read_widgets:
            widget.set_visible(not enabled)

    def add_to_grid(self, grid: Gtk.Grid, row_number: int) -> None:
        # child, left, top, width, height
        grid.attach(self._desc_label, 0, row_number, 1, 1)

        for widget in self._second_column:
            grid.attach(widget, 1, row_number, 1, 1)

        for widget in self._third_column:
            grid.attach(widget, 2, row_number, 1, 1)

        grid.attach(self._remove_button, 3, row_number, 1, 1)


class TextEntryProperty(VCardProperty):
    def __init__(self, prop, account):
        VCardProperty.__init__(self, prop)

        self._value_entry = ValueEntry(prop)
        self._value_entry.connect('notify::text', self._on_text_changed)

        self._value_label = ValueLabel(prop, account)

        self._edit_widgets.append(self._value_entry)
        self._read_widgets.append(self._value_label)

        self._third_column = [self._value_entry, self._value_label]

    def _on_text_changed(self, entry: Gtk.Entry, _param: Any) -> None:
        text = entry.get_text()
        if self._prop.name == 'org':
            self._prop.values = [text]
        else:
            self._prop.value = text
        self._value_label.set_value(text)


class MultiLineProperty(VCardProperty):
    def __init__(self, prop, _account):
        VCardProperty.__init__(self, prop)

        self._edit_text_view = ValueTextView(prop)
        self._edit_text_view.show()

        self._edit_scrolled = Gtk.ScrolledWindow()
        self._edit_scrolled.set_policy(Gtk.PolicyType.NEVER,
                                       Gtk.PolicyType.AUTOMATIC)
        self._edit_scrolled.add(self._edit_text_view)
        self._edit_scrolled.set_valign(Gtk.Align.CENTER)
        self._edit_scrolled.set_size_request(-1, 100)
        self._edit_scrolled.get_style_context().add_class('profile-scrolled')

        self._read_text_view = ValueTextView(prop)
        self._read_text_view.set_sensitive(False)
        self._read_text_view.set_left_margin(0)
        self._read_text_view.show()

        self._read_scrolled = Gtk.ScrolledWindow()
        self._read_scrolled.set_policy(Gtk.PolicyType.NEVER,
                                       Gtk.PolicyType.AUTOMATIC)
        self._read_scrolled.add(self._read_text_view)
        self._read_scrolled.set_valign(Gtk.Align.CENTER)
        self._read_scrolled.set_size_request(-1, 100)
        self._read_scrolled.get_style_context().add_class(
            'profile-scrolled-read')

        self._edit_widgets.append(self._edit_scrolled)
        self._read_widgets.append(self._read_scrolled)

        self._third_column = [self._edit_scrolled, self._read_scrolled]


class DateProperty(VCardProperty):
    def __init__(self, prop, account):
        VCardProperty.__init__(self, prop)

        self._box = Gtk.Box(spacing=6)
        self._value_entry = ValueEntry(prop)
        self._value_entry.set_placeholder_text(_('YYYY-MM-DD'))
        self._value_entry.connect('notify::text', self._on_text_changed)

        self._calendar_button = Gtk.MenuButton()
        image = Gtk.Image.new_from_icon_name(
            'x-office-calendar-symbolic', Gtk.IconSize.BUTTON)
        self._calendar_button.set_image(image)
        self._calendar_button.connect(
            'clicked', self._on_calendar_button_clicked)
        self._box.add(self._value_entry)
        self._box.add(self._calendar_button)
        self._box.show_all()

        self.calendar = Gtk.Calendar(year=1980, month=5, day=15)
        self.calendar.set_visible(True)
        self.calendar.connect(
            'day-selected', self._on_calendar_day_selected)

        popover = Gtk.Popover()
        popover.add(self.calendar)
        self._calendar_button.set_popover(popover)

        self._value_label = ValueLabel(prop, account)

        self._edit_widgets.append(self._box)
        self._read_widgets.append(self._value_label)

        self._third_column = [self._box, self._value_label]

    def _on_text_changed(self, entry: Gtk.Entry, _param: Any) -> None:
        text = entry.get_text()
        self._prop.value = text
        self._value_label.set_value(text)

    def _on_calendar_button_clicked(self, _button: Gtk.Button) -> None:
        birthday = self._value_entry.get_text()
        if not birthday:
            return
        try:
            date = datetime.datetime.strptime(birthday, '%Y-%m-%d')
        except ValueError:
            return
        month = gtk_month(date.month)
        self.calendar.select_month(month, date.year)
        self.calendar.select_day(date.day)

    def _on_calendar_day_selected(self, _calendar: Gtk.Calendar) -> None:
        year, month, day = self.calendar.get_date()
        month = python_month(month)
        date_str = datetime.date(year, month, day).strftime('%Y-%m-%d')
        self._value_entry.set_text(date_str)


class KeyProperty(VCardProperty):
    def __init__(self, prop, _account):
        VCardProperty.__init__(self, prop)

        self._value_text_view = ValueTextView(prop)
        self._value_text_view.show()

        self._scrolled_window = Gtk.ScrolledWindow()
        self._scrolled_window.set_policy(Gtk.PolicyType.NEVER,
                                         Gtk.PolicyType.AUTOMATIC)
        self._scrolled_window.add(self._value_text_view)
        self._scrolled_window.set_valign(Gtk.Align.CENTER)
        self._scrolled_window.set_size_request(350, 200)
        self._scrolled_window.get_style_context().add_class('profile-scrolled')

        self._copy_button = Gtk.Button.new_from_icon_name('edit-copy-symbolic',
                                                          Gtk.IconSize.MENU)
        self._copy_button.connect('clicked', self._on_copy_clicked)
        self._copy_button.set_halign(Gtk.Align.START)
        self._copy_button.set_valign(Gtk.Align.CENTER)

        self._edit_widgets.append(self._scrolled_window)
        self._read_widgets.append(self._copy_button)

        self._third_column = [self._scrolled_window, self._copy_button]

    def _on_copy_clicked(self, _button: Gtk.Button) -> None:
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(self._value_text_view.get_text(), -1)


class GenderProperty(VCardProperty):
    def __init__(self, prop, _account):
        VCardProperty.__init__(self, prop)

        value_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self._value_combobox = GenderComboBox(prop)
        self._value_combobox.connect('notify::active-id',
                                     self._on_active_id_changed)
        self._value_combobox.show()

        self._value_entry = IdentityEntry(prop)
        self._value_entry.show()
        self._value_entry.connect('notify::text', self._on_text_changed)

        value_box.add(self._value_combobox)
        value_box.add(self._value_entry)

        label_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self._identity_label = IdentityLabel(prop)
        self._identity_label.show()
        self._sex_label = SexLabel(prop)
        self._sex_label.show()

        label_box.add(self._sex_label)
        label_box.add(self._identity_label)

        self._edit_widgets.append(value_box)
        self._read_widgets.append(label_box)

        self._third_column = [value_box, label_box]

    def _on_text_changed(self, entry: Gtk.Entry, _param: Any) -> None:
        text = entry.get_text()
        self._prop.identity = text
        self._identity_label.set_text(text)

    def _on_active_id_changed(self,
                              combobox: Gtk.ComboBox,
                              _param: Any
                              ) -> None:
        sex = combobox.get_active_id()
        self._prop.sex = None if sex == '-' else sex
        assert sex is not None
        self._sex_label.set_text(sex)


class AdrProperty(VCardProperty):
    def __init__(self, prop, _account):
        VCardProperty.__init__(self, prop)

        self._entry_box = AdrBox(prop)
        self._entry_box.connect('field-changed', self._on_field_changed)

        self._read_box = AdrBoxReadOnly(prop)

        self._edit_widgets.append(self._entry_box)
        self._read_widgets.append(self._read_box)

        self._third_column = [self._entry_box, self._read_box]

    def _on_field_changed(self, _box, field, value):
        setattr(self._prop, field, [value])
        self._read_box.set_field(field, value)
