from gi.repository import Gtk, GLib, Gdk, GObject
from gajim.common import app
from gajim.common import passwords
from gajim import gtkgui_helpers
from gajim.common.const import OptionKind, OptionType
from gajim.common.exceptions import GajimGeneralException
from gajim import dialogs


class OptionsDialog(Gtk.ApplicationWindow):
    def __init__(self, parent, title, flags, options, account,
                 extend=None):
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_show_menubar(False)
        self.set_title(title)
        self.set_transient_for(parent)
        self.set_resizable(False)
        self.set_default_size(250, -1)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.account = account
        if flags == Gtk.DialogFlags.MODAL:
            self.set_modal(True)
        elif flags == Gtk.DialogFlags.DESTROY_WITH_PARENT:
            self.set_destroy_with_parent(True)

        self.listbox = OptionsBox(account, extend)
        self.listbox.set_hexpand(True)
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)

        for option in options:
            self.listbox.add_option(option)
        self.listbox.update_states()

        self.add(self.listbox)

        self.show_all()
        self.listbox.connect('row-activated', self.on_row_activated)
        self.connect('key-press-event', self.on_key_press)

    def on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    @staticmethod
    def on_row_activated(listbox, row):
        row.get_child().on_row_activated()

    def get_option(self, name):
        return self.listbox.get_option(name)


class OptionsBox(Gtk.ListBox):
    def __init__(self, account, extend=None):
        Gtk.ListBox.__init__(self)
        self.set_name('OptionsBox')
        self.account = account
        self.named_options = {}

        self.map = {
            OptionKind.SWITCH: SwitchOption,
            OptionKind.SPIN: SpinOption,
            OptionKind.DIALOG: DialogOption,
            OptionKind.ENTRY: EntryOption,
            OptionKind.ACTION: ActionOption,
            OptionKind.LOGIN: LoginOption,
            OptionKind.FILECHOOSER: FileChooserOption,
            OptionKind.CALLBACK: CallbackOption,
            OptionKind.PROXY: ProxyComboOption,
            OptionKind.PRIORITY: PriorityOption,
            OptionKind.HOSTNAME: CutstomHostnameOption,
            OptionKind.CHANGEPASSWORD: ChangePasswordOption,
            OptionKind.GPG: GPGOption,
            }

        if extend is not None:
            for option, callback in extend:
                self.map[option] = callback

    def add_option(self, option):
        if option.props is not None:
            listitem = self.map[option.kind](
                self.account, *option[1:-1], **option.props)
        else:
            listitem = self.map[option.kind](self.account, *option[1:-1])
        listitem.connect('notify::option-value', self.on_option_changed)
        if option.name is not None:
            self.named_options[option.name] = listitem
        self.add(listitem)

    def get_option(self, name):
        return self.named_options[name]

    def update_states(self):
        values = []
        values.append((None, None))
        for row in self.get_children():
            name = row.get_child().name
            if name is None:
                continue
            value = row.get_child().get_property('option-value')
            values.append((name, value))

        for name, value in values:
            for row in self.get_children():
                row.get_child().set_activatable(name, value)

    def on_option_changed(self, widget, *args):
        value = widget.get_property('option-value')
        for row in self.get_children():
            row.get_child().set_activatable(widget.name, value)


class GenericOption(Gtk.Grid):
    def __init__(self, account, label, type_, value,
                 name, callback, data, desc, enabledif):
        Gtk.Grid.__init__(self)
        self.set_column_spacing(12)
        self.set_size_request(-1, 25)
        self.callback = callback
        self.type_ = type_
        self.value = value
        self.data = data
        self.label = label
        self.account = account
        self.name = name
        self.enabledif = enabledif
        self.option_value = self.get_value()

        description_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=0)
        description_box.set_valign(Gtk.Align.CENTER)

        optiontext = Gtk.Label(label=label)
        optiontext.set_hexpand(True)
        optiontext.set_halign(Gtk.Align.START)
        optiontext.set_valign(Gtk.Align.CENTER)
        optiontext.set_vexpand(True)
        description_box.add(optiontext)

        if desc is not None:
            description = Gtk.Label(label=desc)
            description.set_name('SubDescription')
            description.set_hexpand(True)
            description.set_halign(Gtk.Align.START)
            description.set_valign(Gtk.Align.CENTER)
            description_box.add(description)

        self.add(description_box)

        self.option_box = Gtk.Box(spacing=6)
        self.option_box.set_size_request(200, -1)
        self.option_box.set_valign(Gtk.Align.CENTER)
        self.option_box.set_name('GenericOptionBox')
        self.add(self.option_box)

    def do_get_property(self, prop):
        if prop.name == 'option-value':
            return self.option_value
        else:
            raise AttributeError('unknown property %s' % prop.name)

    def do_set_property(self, prop, value):
        if prop.name == 'option-value':
            self.option_value = value
        else:
            raise AttributeError('unknown property %s' % prop.name)

    def get_value(self):
        return self.__get_value(self.type_, self.value, self.account)

    @staticmethod
    def __get_value(type_, value, account):
        if value is None:
            return
        if type_ == OptionType.VALUE:
            return value
        elif type_ == OptionType.CONFIG:
            return app.config.get(value)
        elif type_ == OptionType.ACCOUNT_CONFIG:
            if value == 'password':
                return passwords.get_password(account)
            elif value == 'no_log_for':
                no_log = app.config.get_per(
                    'accounts', account, 'no_log_for').split()
                return account not in no_log
            else:
                return app.config.get_per('accounts', account, value)
        elif type_ == OptionType.ACTION:
            if value.startswith('-'):
                return account + value
            return value
        else:
            raise ValueError('Wrong OptionType?')

    def set_value(self, state):
        if self.type_ == OptionType.CONFIG:
            app.config.set(self.value, state)
        if self.type_ == OptionType.ACCOUNT_CONFIG:
            if self.value == 'password':
                passwords.save_password(self.account, state)
            if self.value == 'no_log_for':
                self.set_no_log_for(self.account, state)
            else:
                app.config.set_per('accounts', self.account, self.value, state)

        if self.callback is not None:
            self.callback(state, self.data)

        self.set_property('option-value', state)

    @staticmethod
    def set_no_log_for(account, state):
        no_log = app.config.get_per('accounts', account, 'no_log_for').split()
        if state and account in no_log:
            no_log.remove(account)
        elif not state and account not in no_log:
            no_log.append(account)
        app.config.set_per('accounts', account, 'no_log_for', ' '.join(no_log))

    def on_row_activated(self):
        raise NotImplementedError

    def set_activatable(self, name, value):
        if self.enabledif is None or self.enabledif[0] != name:
            return
        activatable = (name, value) == self.enabledif
        self.get_parent().set_activatable(activatable)
        self.set_sensitive(activatable)


class SwitchOption(GenericOption):

    __gproperties__ = {
        "option-value": (bool, 'Switch Value', '', False,
                         GObject.ParamFlags.READWRITE),}

    def __init__(self, *args):
        GenericOption.__init__(self, *args)

        self.switch = Gtk.Switch()
        self.switch.set_active(self.option_value)
        self.switch.connect('notify::active', self.on_switch)
        self.switch.set_hexpand(True)
        self.switch.set_halign(Gtk.Align.END)
        self.switch.set_valign(Gtk.Align.CENTER)

        self.option_box.add(self.switch)

        self.show_all()

    def on_row_activated(self):
        state = self.switch.get_active()
        self.switch.set_active(not state)

    def on_switch(self, switch, *args):
        value = switch.get_active()
        self.set_value(value)


class EntryOption(GenericOption):

    __gproperties__ = {
        "option-value": (str, 'Entry Value', '', '',
                         GObject.ParamFlags.READWRITE),}

    def __init__(self, *args):
        GenericOption.__init__(self, *args)

        self.entry = Gtk.Entry()
        self.entry.set_text(str(self.option_value))
        self.entry.connect('notify::text', self.on_text_change)
        self.entry.set_valign(Gtk.Align.CENTER)

        if self.value == 'password':
            self.entry.set_invisible_char('*')
            self.entry.set_visibility(False)

        self.option_box.pack_end(self.entry, True, True, 0)

        self.show_all()

    def on_text_change(self, *args):
        text = self.entry.get_text()
        self.set_value(text)

    def on_row_activated(self):
        self.entry.grab_focus()


class DialogOption(GenericOption):

    __gproperties__ = {
        "option-value": (str, 'Dummy', '', '',
                         GObject.ParamFlags.READWRITE),}

    def __init__(self, *args, dialog):
        GenericOption.__init__(self, *args)
        self.dialog = dialog

        self.option_value = Gtk.Label()
        self.option_value.set_text(self.get_option_value())
        self.option_value.set_halign(Gtk.Align.END)
        self.option_box.pack_start(self.option_value, True, True, 0)

        self.show_all()

    def show_dialog(self, parent):
        if self.dialog:
            dialog = self.dialog(self.account, parent)
            dialog.connect('destroy', self.on_destroy)

    def on_destroy(self, *args):
        self.option_value.set_text(self.get_option_value())

    def get_option_value(self):
        self.option_value.hide()
        return ''

    def on_row_activated(self):
        self.show_dialog(self.get_toplevel())


class SpinOption(GenericOption):

    __gproperties__ = {
        "option-value": (int, 'Priority', '', -128, 127, 0,
                         GObject.ParamFlags.READWRITE),}

    def __init__(self, *args, range_):
        GenericOption.__init__(self, *args)

        lower, upper = range_
        adjustment = Gtk.Adjustment(0, lower, upper, 1, 10, 0)

        self.spin = Gtk.SpinButton()
        self.spin.set_adjustment(adjustment)
        self.spin.set_numeric(True)
        self.spin.set_update_policy(Gtk.SpinButtonUpdatePolicy.IF_VALID)
        self.spin.set_value(self.option_value)
        self.spin.set_halign(Gtk.Align.END)
        self.spin.set_valign(Gtk.Align.CENTER)
        self.spin.connect('notify::value', self.on_value_change)

        self.option_box.pack_start(self.spin, True, True, 0)

        self.show_all()

    def on_row_activated(self):
        self.spin.grab_focus()

    def on_value_change(self, spin, *args):
        value = spin.get_value_as_int()
        self.set_value(value)


class FileChooserOption(GenericOption):

    __gproperties__ = {
        "option-value": (str, 'Certificate Path', '', '',
                         GObject.ParamFlags.READWRITE),}

    def __init__(self, *args, filefilter):
        GenericOption.__init__(self, *args)

        button = Gtk.FileChooserButton(self.label, Gtk.FileChooserAction.OPEN)
        button.set_halign(Gtk.Align.END)

        # GTK Bug: The FileChooserButton expands without limit
        # get the label and use set_max_wide_chars()
        label = button.get_children()[0].get_children()[0].get_children()[1]
        label.set_max_width_chars(20)

        if filefilter:
            name, pattern = filefilter
            filter_ = Gtk.FileFilter()
            filter_.set_name(name)
            filter_.add_pattern(pattern)
            button.add_filter(filter_)
            button.set_filter(filter_)

        filter_ = Gtk.FileFilter()
        filter_.set_name(_('All files'))
        filter_.add_pattern('*')
        button.add_filter(filter_)

        if self.option_value:
            button.set_filename(self.option_value)
        button.connect('selection-changed', self.on_select)

        clear_button = gtkgui_helpers.get_image_button(
            'edit-clear-all-symbolic', _('Clear File'))
        clear_button.connect('clicked', lambda *args: button.unselect_all())
        self.option_box.pack_start(button, True, True, 0)
        self.option_box.pack_start(clear_button, False, False, 0)

        self.show_all()

    def on_select(self, filechooser):
        self.set_value(filechooser.get_filename() or '')

    def on_row_activated(self):
        pass


class CallbackOption(GenericOption):

    __gproperties__ = {
        "option-value": (str, 'Dummy', '', '',
                         GObject.ParamFlags.READWRITE),}

    def __init__(self, *args, callback):
        GenericOption.__init__(self, *args)
        self.callback = callback
        self.show_all()

    def on_row_activated(self):
        self.callback()


class ActionOption(GenericOption):

    __gproperties__ = {
        "option-value": (str, 'Dummy', '', '',
                         GObject.ParamFlags.READWRITE),}

    def __init__(self, *args, action_args):
        GenericOption.__init__(self, *args)
        self.action = gtkgui_helpers.get_action(self.option_value)
        self.variant = GLib.Variant.new_string(action_args)
        self.on_enable()

        self.show_all()
        self.action.connect('notify::enabled', self.on_enable)

    def on_enable(self, *args):
        self.set_sensitive(self.action.get_enabled())

    def on_row_activated(self):
        self.action.activate(self.variant)


class LoginOption(DialogOption):
    def __init__(self, *args, **kwargs):
        DialogOption.__init__(self, *args, **kwargs)
        self.option_value.set_selectable(True)

    def get_option_value(self):
        jid = app.get_jid_from_account(self.account)
        return jid

    def set_activatable(self, name, value):
        DialogOption.set_activatable(self, name, value)
        anonym = app.config.get_per('accounts', self.account, 'anonymous_auth')
        self.get_parent().set_activatable(not anonym)


class ProxyComboOption(GenericOption):

    __gproperties__ = {
        "option-value": (str, 'Proxy', '', '',
                         GObject.ParamFlags.READWRITE),}

    def __init__(self, *args):
        GenericOption.__init__(self, *args)

        self.combo = Gtk.ComboBoxText()
        self.update_values()

        self.combo.connect('changed', self.on_value_change)
        self.combo.set_valign(Gtk.Align.CENTER)

        button = gtkgui_helpers.get_image_button(
            'preferences-system-symbolic', _('Manage Proxies'))
        button.set_action_name('app.manage-proxies')
        button.set_valign(Gtk.Align.CENTER)

        self.option_box.pack_start(self.combo, True, True, 0)
        self.option_box.pack_start(button, False, True, 0)
        self.show_all()

    def update_values(self):
        proxies = app.config.get_per('proxies')
        proxies.insert(0, _('None'))
        self.combo.remove_all()
        for index, value in enumerate(proxies):
            self.combo.insert_text(-1, value)
            if value == self.option_value or index == 0:
                self.combo.set_active(index)

    def on_value_change(self, combo):
        self.set_value(combo.get_active_text())

    def on_row_activated(self):
        pass


class PriorityOption(DialogOption):
    def __init__(self, *args, **kwargs):
        DialogOption.__init__(self, *args, **kwargs)

    def get_option_value(self):
        adjust = app.config.get_per(
            'accounts', self.account, 'adjust_priority_with_status')
        if adjust:
            return _('Adjust to Status')

        priority = app.config.get_per('accounts', self.account, 'priority')
        return str(priority)


class CutstomHostnameOption(DialogOption):
    def __init__(self, *args, **kwargs):
        DialogOption.__init__(self, *args, **kwargs)

    def get_option_value(self):
        custom = app.config.get_per('accounts', self.account, 'use_custom_host')
        return _('On') if custom else _('Off')


class ChangePasswordOption(DialogOption):
    def __init__(self, *args, **kwargs):
        DialogOption.__init__(self, *args, **kwargs)

    def show_dialog(self, parent):
        try:
            self.change_dialog = dialogs.ChangePasswordDialog(
                self.account, self.on_changed, parent)
        except GajimGeneralException:
            return
        self.change_dialog.dialog.set_modal(True)

    def on_changed(self, new_password):
        if new_password is not None:
            app.connections[self.account].change_password(new_password)
            self.set_value(new_password)

    def set_activatable(self, name, value):
        activatable = False
        if self.account in app.connections:
            con = app.connections[self.account]
            activatable = con.connected >= 2 and con.register_supported
        self.get_parent().set_activatable(activatable)


class GPGOption(DialogOption):
    def __init__(self, *args, **kwargs):
        DialogOption.__init__(self, *args, **kwargs)

    def show_dialog(self, parent):
        secret_keys = app.connections[self.account].ask_gpg_secrete_keys()
        secret_keys[_('None')] = _('None')

        if not secret_keys:
            dialogs.ErrorDialog(
                _('Failed to get secret keys'),
                _('There is no OpenPGP secret key available.'),
                transient_for=parent)
            return

        dialog = dialogs.ChooseGPGKeyDialog(
            _('OpenPGP Key Selection'), _('Choose your OpenPGP key'),
            secret_keys, self.on_key_selected, transient_for=parent)
        dialog.window.connect('destroy', self.on_destroy)

    def on_key_selected(self, keyID):
        if keyID is None:
            return
        keyid_new, keyname_new = keyID

        keyid = app.config.get_per('accounts', self.account, 'keyid')

        if keyid_new == _('None'):
            if keyid == '':
                return
            app.config.set_per('accounts', self.account, 'keyname', '')
            app.config.set_per('accounts', self.account, 'keyid', '')
        else:
            if keyid == keyid_new:
                return
            app.config.set_per(
                'accounts', self.account, 'keyname', keyname_new)
            app.config.set_per(
                'accounts', self.account, 'keyid', keyid_new)

    def get_option_value(self):
        keyid = app.config.get_per('accounts', self.account, 'keyid')
        keyname = app.config.get_per('accounts', self.account, 'keyname')
        if keyid is not None:
            return '\n'.join((keyid, keyname))
        return ''

    def set_activatable(self, name, value):
        active = self.account in app.connections
        self.get_parent().set_activatable(app.HAVE_GPG and active)
