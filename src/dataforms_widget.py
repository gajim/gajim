# -*- coding:utf-8 -*-
## src/dataforms_widget.py
##
## Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2006 Tomasz Melcer <liori AT exroot.org>
## Copyright (C) 2006-2007 Jean-Marie Traissard <jim AT lapin.org>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

''' This module contains widget that can display data form (JEP-0004).
Words single and multiple refers here to types of data forms:
single means these with one record of data (without <reported/> element),
multiple - these which may contain more data (with <reported/> element).'''

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GObject
from gi.repository import GLib
import base64

import gtkgui_helpers
import dialogs

import common.dataforms as dataforms
from common import helpers

import itertools

class DataFormWidget(Gtk.Alignment, object):
# "public" interface
    """
    Data Form widget. Use like any other widget
    """

    __gsignals__ = dict(
        validated = (GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION, None, ())
    )

    def __init__(self, dataformnode=None):
        ''' Create a widget. '''
        GObject.GObject.__init__(self, xscale=1.0, yscale=1.0)

        self._data_form = None
        self.selectable = False

        self.xml = gtkgui_helpers.get_gtk_builder('data_form_window.ui',
                'data_form_vbox')
        self.xml.connect_signals(self)
        for name in ('instructions_label', 'instructions_hseparator',
                        'single_form_viewport', 'data_form_types_notebook',
                        'single_form_scrolledwindow', 'multiple_form_hbox',
                        'records_treeview', 'buttons_vbox', 'add_button', 'remove_button',
                        'edit_button', 'up_button', 'down_button', 'clear_button'):
            self.__dict__[name] = self.xml.get_object(name)

        self.add(self.xml.get_object('data_form_vbox'))

        if dataformnode is not None:
            self.set_data_form(dataformnode)

        selection = self.records_treeview.get_selection()
        selection.connect('changed', self.on_records_selection_changed)
        selection.set_mode(Gtk.SelectionMode.MULTIPLE)

    def on_data_form_vbox_key_press_event(self, widget, event):
        print('key pressed')

    def set_data_form(self, dataform):
        """
        Set the data form (nbxmpp.DataForm) displayed in widget
        """
        assert isinstance(dataform, dataforms.DataForm)

        self.del_data_form()
        self._data_form = dataform
        if isinstance(dataform, dataforms.SimpleDataForm):
            self.build_single_data_form()
        else:
            self.build_multiple_data_form()

        # create appropriate description for instructions field if there isn't any
        if dataform.instructions == '':
            self.instructions_label.set_no_show_all(True)
            self.instructions_label.hide()
        else:
            self.instructions_label.set_text(dataform.instructions)
            gtkgui_helpers.label_set_autowrap(self.instructions_label)

    def get_data_form(self):
        """
        Data form displayed in the widget or None if no form
        """
        return self._data_form

    def del_data_form(self):
        self.clean_data_form()
        self._data_form = None

    data_form = property(get_data_form, set_data_form, del_data_form,
            'Data form presented in a widget')

    def get_title(self):
        """
        Get the title of data form. If no title or no form,
        returns ''. Useful for setting window title
        """
        if self._data_form is not None:
            if self._data_form.title is not None:
                return self._data_form.title
        return ''

    title = property(get_title, None, None, 'Data form title')

    def show(self):
        ''' Treat 'us' as one widget. '''
        self.show_all()

# "private" methods

# we have actually two different kinds of data forms: one is a simple form to fill,
# second is a table with several records;

    def empty_method(self):
        pass

    def clean_data_form(self):
        """
        Remove data about existing form. This metod is empty, because it is
        rewritten by build_*_data_form, according to type of form which is
        actually displayed
        """
        pass

    def build_single_data_form(self):
        '''Invoked when new single form is to be created.'''
        assert isinstance(self._data_form, dataforms.SimpleDataForm)

        self.clean_data_form()

        self.singleform = SingleForm(self._data_form,
            selectable=self.selectable)
        def _on_validated(widget):
            self.emit('validated')
        self.singleform.connect('validated', _on_validated)
        self.singleform.show()
        self.single_form_viewport.add(self.singleform)
        self.data_form_types_notebook.set_current_page(
                self.data_form_types_notebook.page_num(
                        self.single_form_scrolledwindow))

        self.clean_data_form = self.clean_single_data_form

    def clean_single_data_form(self):
        """
        Called as clean_data_form, read the docs of clean_data_form(). Remove
        form from widget
        """
        self.singleform.destroy()
        self.clean_data_form = self.empty_method        # we won't call it twice
        del self.singleform

    def build_multiple_data_form(self):
        """
        Invoked when new multiple form is to be created
        """
        assert isinstance(self._data_form, dataforms.MultipleDataForm)

        self.clean_data_form()

        # creating model for form...
        fieldtypes = []
        fieldvars = []
        for field in self._data_form.reported.iter_fields():
            # note: we store also text-private and hidden fields,
            # we just do not display them.
            # TODO: boolean fields
            #elif field.type_=='boolean': fieldtypes.append(bool)
            fieldtypes.append(str)
            fieldvars.append(field.var)

        self.multiplemodel = Gtk.ListStore(*fieldtypes)

        # moving all data to model
        for item in self._data_form.iter_records():
            iter_ = self.multiplemodel.append()
            for field in item.iter_fields():
                if field.var in fieldvars:
                    self.multiplemodel.set_value(iter_,
                        fieldvars.index(field.var), field.value)

        # constructing columns...
        for field, counter in zip(self._data_form.reported.iter_fields(),
        itertools.count()):
            self.records_treeview.append_column(
                    Gtk.TreeViewColumn(field.label, Gtk.CellRendererText(),
                            text=counter))

        self.records_treeview.set_model(self.multiplemodel)
        self.records_treeview.show_all()

        self.data_form_types_notebook.set_current_page(
                self.data_form_types_notebook.page_num(
                        self.multiple_form_hbox))

        self.clean_data_form = self.clean_multiple_data_form

        readwrite = self._data_form.type_ != 'result'
        if not readwrite:
            self.buttons_vbox.set_no_show_all(True)
            self.buttons_vbox.hide()
        else:
            self.buttons_vbox.set_no_show_all(False)
            # refresh list look
            self.refresh_multiple_buttons()

    def clean_multiple_data_form(self):
        """
        Called as clean_data_form, read the docs of clean_data_form(). Remove
        form from widget
        """
        self.clean_data_form = self.empty_method        # we won't call it twice
        del self.multiplemodel

    def refresh_multiple_buttons(self):
        """
        Checks for treeview state and makes control buttons sensitive
        """
        selection = self.records_treeview.get_selection()
        model = self.records_treeview.get_model()
        count = selection.count_selected_rows()
        if count == 0:
            self.remove_button.set_sensitive(False)
            self.edit_button.set_sensitive(False)
            self.up_button.set_sensitive(False)
            self.down_button.set_sensitive(False)
        elif count == 1:
            self.remove_button.set_sensitive(True)
            self.edit_button.set_sensitive(True)
            _, (path,) = selection.get_selected_rows()
            iter_ = model.get_iter(path)
            if model.iter_next(iter_) is None:
                self.up_button.set_sensitive(True)
                self.down_button.set_sensitive(False)
            elif path == (0, ):
                self.up_button.set_sensitive(False)
                self.down_button.set_sensitive(True)
            else:
                self.up_button.set_sensitive(True)
                self.down_button.set_sensitive(True)
        else:
            self.remove_button.set_sensitive(True)
            self.edit_button.set_sensitive(True)
            self.up_button.set_sensitive(False)
            self.down_button.set_sensitive(False)

        if len(model) == 0:
            self.clear_button.set_sensitive(False)
        else:
            self.clear_button.set_sensitive(True)

    def on_clear_button_clicked(self, widget):
        self.records_treeview.get_model().clear()

    def on_remove_button_clicked(self, widget):
        selection = self.records_treeview.get_selection()
        model, rowrefs = selection.get_selected_rows()
        # rowref is a list of paths
        for i in list(range(len(rowrefs))):
            rowrefs[i] = Gtk.TreeRowReference.new(model, rowrefs[i])
        # rowref is a list of row references; need to convert because we will
        # modify the model, paths would change
        for rowref in rowrefs:
            del model[rowref.get_path()]

    def on_up_button_clicked(self, widget):
        selection = self.records_treeview.get_selection()
        model, (path,) = selection.get_selected_rows()
        iter_ = model.get_iter(path)
        # constructing path for previous iter
        previter = model.get_iter((path[0]-1,))
        model.swap(iter_, previter)

        self.refresh_multiple_buttons()

    def on_down_button_clicked(self, widget):
        selection = self.records_treeview.get_selection()
        model, (path,) = selection.get_selected_rows()
        iter_ = model.get_iter(path)
        nextiter = model.iter_next(iter_)
        model.swap(iter_, nextiter)

        self.refresh_multiple_buttons()

    def on_records_selection_changed(self, widget):
        self.refresh_multiple_buttons()

class SingleForm(Gtk.Table, object):
    """
    Widget that represent DATAFORM_SINGLE mode form. Because this is used not
    only to display single forms, but to form input windows of multiple-type
    forms, it is in another class
    """

    __gsignals__ = dict(
        validated = (GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION, None, ())
    )

    def __init__(self, dataform, selectable=False):
        assert isinstance(dataform, dataforms.SimpleDataForm)

        GObject.GObject.__init__(self)
        self.set_col_spacings(12)
        self.set_row_spacings(6)

        def decorate_with_tooltip(widget, field):
            """
            Adds a tooltip containing field's description to a widget.  Creates
            EventBox if widget doesn't have its own gdk window.  Returns decorated
            widget
            """
            if field.description != '':
                if not widget.get_window():
                #if widget.flags() & Gtk.NO_WINDOW:
                    evbox = Gtk.EventBox()
                    evbox.add(widget)
                    widget = evbox
                widget.set_tooltip_text(field.description)
            return widget

        self._data_form = dataform

        # building widget
        linecounter = 0

        # is the form changeable?
        readwrite = dataform.type_ != 'result'

        # for each field...
        for field in self._data_form.iter_fields():
            if field.type_ == 'hidden': continue

            commonlabel = True
            commonlabelcenter = False
            commonwidget = True
            widget = None

            if field.type_ == 'boolean':
                commonlabelcenter = True
                widget = Gtk.CheckButton()
                widget.connect('toggled', self.on_boolean_checkbutton_toggled,
                        field)
                widget.set_active(field.value)

            elif field.type_ == 'fixed':
                leftattach = 1
                rightattach = 2
                if field.label is None:
                    commonlabel = False
                    leftattach = 0

                commonwidget = False
                widget = Gtk.Label(label=field.value)
                widget.set_property('selectable', selectable)
                widget.set_line_wrap(True)
                self.attach(widget, leftattach, rightattach, linecounter,
                    linecounter+1, xoptions=Gtk.AttachOptions.FILL,
                    yoptions=Gtk.AttachOptions.FILL)

            elif field.type_ == 'list-single':
                # TODO: What if we have radio buttons and non-required field?
                # TODO: We cannot deactivate them all...
                if len(field.options) < 6:
                    # 5 option max: show radiobutton
                    widget = Gtk.VBox()
                    first_radio = None
                    for value, label in field.iter_options():
                        if not label:
                            label = value
                        radio = Gtk.RadioButton.new_with_label_from_widget(
                            first_radio, label)
                        radio.connect('toggled',
                            self.on_list_single_radiobutton_toggled, field, value)
                        if first_radio is None:
                            first_radio = radio
                            if field.value == '':   # TODO: is None when done
                                field.value = value
                        if value == field.value:
                            radio.set_active(True)
                        widget.pack_start(radio, False, True, 0)
                else:
                    # more than 5 options: show combobox
                    def on_list_single_combobox_changed(combobox, f):
                        iter_ = combobox.get_active_iter()
                        if iter_:
                            model = combobox.get_model()
                            f.value = model[iter_][1]
                        else:
                            f.value = ''
                    widget = gtkgui_helpers.create_combobox(field.options,
                            field.value)
                    widget.connect('changed', on_list_single_combobox_changed, field)
                widget.set_sensitive(readwrite)

            elif field.type_ == 'list-multi':
                # TODO: When more than few choices, make a list
                if len(field.options) < 6:
                    # 5 option max: show checkbutton
                    widget = Gtk.VBox()
                    for value, label in field.iter_options():
                        check = Gtk.CheckButton(label, use_underline=False)
                        check.set_active(value in field.values)
                        check.connect('toggled',
                                self.on_list_multi_checkbutton_toggled, field, value)
                        widget.pack_start(check, False, True, 0)
                        widget.set_sensitive(readwrite)
                else:
                    # more than 5 options: show combobox
                    def on_list_multi_treeview_changed(selection, f):
                        def for_selected(treemodel, path, iter):
                            vals.append(treemodel[iter][1])
                        vals = []
                        selection.selected_foreach(for_selected)
                        field.values = vals[:]
                    widget = Gtk.ScrolledWindow()
                    widget.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
                    tv = gtkgui_helpers.create_list_multi(field.options,
                            field.values)
                    widget.add(tv)
                    widget.set_size_request(-1, 120)
                    tv.get_selection().connect('changed',
                            on_list_multi_treeview_changed, field)
                    tv.set_sensitive(readwrite)

            elif field.type_ == 'jid-single':
                widget = Gtk.Entry()
                widget.connect('changed', self.on_text_single_entry_changed, field)
                widget.set_text(field.value)

            elif field.type_ == 'jid-multi':
                commonwidget = False

                xml = gtkgui_helpers.get_gtk_builder('data_form_window.ui',
                    'multiple_form_hbox')
                widget = xml.get_object('multiple_form_hbox')
                treeview = xml.get_object('records_treeview')

                listmodel = Gtk.ListStore(str)
                for value in field.iter_values():
                    # nobody will create several megabytes long stanza
                    listmodel.insert(999999, (value,))

                treeview.set_model(listmodel)

                renderer = Gtk.CellRendererText()
                renderer.set_property('editable', True)
                renderer.connect('edited',
                        self.on_jid_multi_cellrenderertext_edited, treeview, listmodel,
                        field)

                treeview.append_column(Gtk.TreeViewColumn(None, renderer,
                        text=0))

                decorate_with_tooltip(treeview, field)

                add_button=xml.get_object('add_button')
                add_button.connect('clicked',
                        self.on_jid_multi_add_button_clicked, treeview, listmodel, field)
                edit_button=xml.get_object('edit_button')
                edit_button.connect('clicked',
                        self.on_jid_multi_edit_button_clicked, treeview)
                remove_button=xml.get_object('remove_button')
                remove_button.connect('clicked',
                        self.on_jid_multi_remove_button_clicked, treeview, field)
                clear_button=xml.get_object('clear_button')
                clear_button.connect('clicked',
                        self.on_jid_multi_clean_button_clicked, listmodel, field)
                if not readwrite:
                    add_button.set_no_show_all(True)
                    edit_button.set_no_show_all(True)
                    remove_button.set_no_show_all(True)
                    clear_button.set_no_show_all(True)

                widget.set_sensitive(readwrite)
                self.attach(widget, 1, 2, linecounter, linecounter+1)

                del xml

            elif field.type_ == 'text-private':
                commonlabelcenter = True
                widget = Gtk.Entry()
                widget.connect('changed', self.on_text_single_entry_changed, field)
                widget.set_visibility(False)
                widget.set_text(field.value)

            elif field.type_ == 'text-multi':
                # TODO: bigger text view
                commonwidget = False

                textwidget = Gtk.TextView()
                textwidget.set_wrap_mode(Gtk.WrapMode.WORD)
                textwidget.get_buffer().connect('changed',
                        self.on_text_multi_textbuffer_changed, field)
                textwidget.get_buffer().set_text(field.value)
                if readwrite:
                    textwidget.set_sensitive(True)
                else:
                    if selectable:
                        textwidget.set_editable(True)
                    else:
                        textwidget.set_sensitive(False)

                widget = Gtk.ScrolledWindow()
                widget.add(textwidget)

                widget=decorate_with_tooltip(widget, field)
                self.attach(widget, 1, 2, linecounter, linecounter+1)

            else:
                # field.type_ == 'text-single' or field.type_ is nonstandard:
                # JEP says that if we don't understand some type, we
                # should handle it as text-single
                commonlabelcenter = True
                if readwrite:
                    widget = Gtk.Entry()
                    def kpe(widget, event):
                        if event.keyval == Gdk.KEY_Return or \
                        event.keyval == Gdk.KEY_KP_Enter:
                            self.emit('validated')
                    widget.connect('key-press-event', kpe)
                    widget.connect('changed', self.on_text_single_entry_changed,
                            field)
                    widget.set_sensitive(readwrite)
                    if field.value is None:
                        field.value = ''
                    widget.set_text(field.value)
                else:
                    commonwidget=False
                    widget = Gtk.Label(label=field.value)
                    widget.set_property('selectable', selectable)
                    widget.set_sensitive(True)
                    widget.set_alignment(0.0, 0.5)
                    widget=decorate_with_tooltip(widget, field)
                    self.attach(widget, 1, 2, linecounter, linecounter+1,
                            yoptions=Gtk.AttachOptions.FILL)

            if commonlabel and field.label is not None:
                label = Gtk.Label(label=field.label)
                if commonlabelcenter:
                    label.set_alignment(0.0, 0.5)
                else:
                    label.set_alignment(0.0, 0.0)
                label = decorate_with_tooltip(label, field)
                self.attach(label, 0, 1, linecounter, linecounter+1,
                        xoptions=Gtk.AttachOptions.FILL, yoptions=Gtk.AttachOptions.FILL)

            if field.media is not None:
                for uri in field.media.uris:
                    if uri.type_.startswith('image/'):
                        try:
                            img_data = base64.b64decode(uri.uri_data)
                            pixbuf_l = GdkPixbuf.PixbufLoader()
                            pixbuf_l.write(img_data)
                            pixbuf_l.close()
                            media = Gtk.Image.new_from_pixbuf(pixbuf_l.\
                                get_pixbuf())
                        except Exception:
                            media = Gtk.Label(label=_('Unable to load image'))
                    else:
                        media = Gtk.Label(label=_('Media type not supported: %s') % \
                            uri.type_)
                    linecounter += 1
                    self.attach(media, 0, 1, linecounter, linecounter+1,
                        xoptions=Gtk.AttachOptions.FILL, yoptions=Gtk.AttachOptions.FILL)

            if commonwidget:
                assert widget is not None
                widget.set_sensitive(readwrite)
                widget = decorate_with_tooltip(widget, field)
                self.attach(widget, 1, 2, linecounter, linecounter+1,
                        yoptions=Gtk.AttachOptions.FILL)

            if field.required:
                label = Gtk.Label(label='*')
                label.set_tooltip_text(_('This field is required'))
                self.attach(label, 2, 3, linecounter, linecounter+1, xoptions=0,
                    yoptions=0)

            linecounter+=1
        if self.get_property('visible'):
            self.show_all()

    def show(self):
        # simulate that we are one widget
        self.show_all()

    def on_boolean_checkbutton_toggled(self, widget, field):
        field.value = widget.get_active()

    def on_list_single_radiobutton_toggled(self, widget, field, value):
        field.value = value

    def on_list_multi_checkbutton_toggled(self, widget, field, value):
        # TODO: make some methods like add_value and remove_value
        if widget.get_active() and value not in field.values:
            field.values += [value]
        elif not widget.get_active() and value in field.values:
            field.values = [v for v in field.values if v!=value]

    def on_text_single_entry_changed(self, widget, field):
        field.value = widget.get_text()

    def on_text_multi_textbuffer_changed(self, widget, field):
        field.value = widget.get_text(widget.get_start_iter(),
            widget.get_end_iter(), True)

    def on_jid_multi_cellrenderertext_edited(self, cell, path, newtext, treeview,
    model, field):
        old = model[path][0]
        if old == newtext:
            return
        try:
            newtext = helpers.parse_jid(newtext)
        except helpers.InvalidFormat as s:
            dialogs.ErrorDialog(_('Invalid Jabber ID'), str(s))
            return
        if newtext in field.values:
            dialogs.ErrorDialog(
                    _('Jabber ID already in list'),
                    _('The Jabber ID you entered is already in the list. Choose another one.'))
            GLib.idle_add(treeview.set_cursor, path)
            return
        model[path][0]=newtext

        values = field.values
        values[values.index(old)]=newtext
        field.values = values

    def on_jid_multi_add_button_clicked(self, widget, treeview, model, field):
        #Default jid
        jid = _('new@jabber.id')
        if jid in field.values:
            i = 1
            while _('new%d@jabber.id') % i in field.values:
                i += 1
            jid = _('new%d@jabber.id') % i
        iter_ = model.insert(999999, (jid,))
        treeview.set_cursor(model.get_path(iter_), treeview.get_column(0), True)
        field.values = field.values + [jid]

    def on_jid_multi_edit_button_clicked(self, widget, treeview):
        model, iter_ = treeview.get_selection().get_selected()
        assert iter_ is not None

        treeview.set_cursor(model.get_path(iter_), treeview.get_column(0), True)

    def on_jid_multi_remove_button_clicked(self, widget, treeview, field):
        selection = treeview.get_selection()
        deleted = []

        def remove(model, path, iter_, deleted):
            deleted+=model[iter_]
            model.remove(iter_)

        selection.selected_foreach(remove, deleted)
        field.values = (v for v in field.values if v not in deleted)

    def on_jid_multi_clean_button_clicked(self, widget, model, field):
        model.clear()
        del field.values
