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

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import GObject

from gajim.common import app
from gajim.common import ged
from gajim.common.i18n import _
from gajim.common.nec import EventHelper

from gajim.gtk.dialogs import ErrorDialog
from gajim.gtk.util import get_builder


class PrivacyListWindow(EventHelper):
    def __init__(self, account, privacy_list_name, action):
        # action is 'EDIT' or 'NEW' depending on if we create a new priv list
        # or edit an already existing one
        EventHelper.__init__(self)
        self.account = account
        self.privacy_list_name = privacy_list_name

        # Dicts and Default Values
        self.active_rule = ''
        self.global_rules = {}
        self.list_of_groups = {}

        self.max_order = 0

        # Default Edit Values
        self.edit_rule_type = 'jid'
        self.allow_deny = 'allow'

        # Connect to gtk builder
        self._ui = get_builder('privacy_list_window.ui')
        self.window = self._ui.get_object('privacy_list_edit_window')

        self._ui.privacy_lists_title_label.set_label(
            _('Privacy List <b><i>%s</i></b>') %
            GLib.markup_escape_text(self.privacy_list_name))

        if len(app.connections) > 1:
            title = _('Privacy List for %s') % self.account
        else:
            title = _('Privacy List')

        self._ui.delete_rule_button.set_sensitive(False)
        self._ui.open_rule_button.set_sensitive(False)
        self._ui.privacy_list_active_checkbutton.set_sensitive(False)
        self._ui.privacy_list_default_checkbutton.set_sensitive(False)
        self._ui.list_of_rules_combobox.set_sensitive(False)

        # set jabber id completion
        jids_list_store = Gtk.ListStore(GObject.TYPE_STRING)
        for jid in app.contacts.get_jid_list(self.account):
            jids_list_store.append([jid])
        jid_entry_completion = Gtk.EntryCompletion()
        jid_entry_completion.set_text_column(0)
        jid_entry_completion.set_model(jids_list_store)
        jid_entry_completion.set_popup_completion(True)
        self._ui.edit_type_jabberid_entry.set_completion(jid_entry_completion)
        if action == 'EDIT':
            self.refresh_rules()

        model = self._ui.edit_type_group_combobox.get_model()
        count = 0
        for group in app.groups[self.account]:
            self.list_of_groups[group] = count
            count += 1
            model.append([group])
        self._ui.edit_type_group_combobox.set_active(0)

        self.window.set_title(title)

        # pylint: disable=line-too-long
        self.register_events([
            ('privacy-list-received', ged.GUI1, self._nec_privacy_list_received),
            ('privacy-lists-received', ged.GUI1, self._nec_privacy_lists_received)
        ])
        # pylint: enable=line-too-long

        self.window.show_all()
        self._ui.add_edit_vbox.hide()

        self._ui.connect_signals(self)

    def on_key_press_event(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.window.destroy()

    def _on_edit_window_destroy(self, _widget):
        key_name = 'privacy_list_%s' % self.privacy_list_name
        if key_name in app.interface.instances[self.account]:
            del app.interface.instances[self.account][key_name]
        self.unregister_events()

    def _nec_privacy_lists_received(self, obj):
        if obj.conn.name != self.account:
            return
        if obj.active_list == self.privacy_list_name:
            self._ui.privacy_list_active_checkbutton.set_active(True)
        else:
            self._ui.privacy_list_active_checkbutton.set_active(False)
        if obj.default_list == self.privacy_list_name:
            self._ui.privacy_list_default_checkbutton.set_active(True)
        else:
            self._ui.privacy_list_default_checkbutton.set_active(False)

    def privacy_list_received(self, rules):
        model = self._ui.list_of_rules_combobox.get_model()
        model.clear()
        self.global_rules = {}
        for rule in rules:
            if 'type' in rule:
                text_item = _(
                    'Order: %(order)s, action: %(action)s, type: %(type)s'
                    ', value: %(value)s') % {
                        'order': rule['order'],
                        'action': rule['action'],
                        'type': rule['type'],
                        'value': rule['value']}
            else:
                text_item = _('Order: %(order)s, action: %(action)s') % \
                        {'order': rule['order'], 'action': rule['action']}
            if int(rule['order']) > self.max_order:
                self.max_order = int(rule['order'])
            self.global_rules[text_item] = rule
            model.append([text_item])
        if not rules:
            self._ui.title_hbox.set_sensitive(False)
            self._ui.list_of_rules_combobox.set_sensitive(False)
            self._ui.delete_rule_button.set_sensitive(False)
            self._ui.open_rule_button.set_sensitive(False)
            self._ui.privacy_list_active_checkbutton.set_sensitive(False)
            self._ui.privacy_list_default_checkbutton.set_sensitive(False)
        else:
            self._ui.list_of_rules_combobox.set_active(0)
            self._ui.title_hbox.set_sensitive(True)
            self._ui.list_of_rules_combobox.set_sensitive(True)
            self._ui.delete_rule_button.set_sensitive(True)
            self._ui.open_rule_button.set_sensitive(True)
            self._ui.privacy_list_active_checkbutton.set_sensitive(True)
            self._ui.privacy_list_default_checkbutton.set_sensitive(True)
        self.reset_fields()
        con = app.connections[self.account]
        con.get_module('PrivacyLists').get_privacy_lists()

    def _nec_privacy_list_received(self, obj):
        if obj.conn.name != self.account:
            return
        if obj.list_name != self.privacy_list_name:
            return
        self.privacy_list_received(obj.rules)

    def refresh_rules(self):
        con = app.connections[self.account]
        con.get_module('PrivacyLists').get_privacy_list(self.privacy_list_name)

    def on_delete_rule_button_clicked(self, _widget):
        model = self._ui.list_of_rules_combobox.get_model()
        iter_ = self._ui.list_of_rules_combobox.get_active_iter()
        _rule = model[iter_][0]
        tags = []
        for rule in self.global_rules:
            if rule != _rule:
                tags.append(self.global_rules[rule])
        con = app.connections[self.account]
        con.get_module('PrivacyLists').set_privacy_list(
            self.privacy_list_name, tags)
        self.privacy_list_received(tags)
        self._ui.add_edit_vbox.hide()
        if not tags:  # we removed latest rule
            if 'privacy_lists' in app.interface.instances[self.account]:
                win = app.interface.instances[self.account]['privacy_lists']
                win.remove_privacy_list(self.privacy_list_name)
                win.draw_widgets()

    def on_open_rule_button_clicked(self, _widget):
        self._ui.add_edit_rule_label.set_label(_('<b>Edit a rule</b>'))
        active_num = self._ui.list_of_rules_combobox.get_active()
        if active_num == -1:
            self.active_rule = ''
        else:
            model = self._ui.list_of_rules_combobox.get_model()
            iter_ = self._ui.list_of_rules_combobox.get_active_iter()
            self.active_rule = model[iter_][0]
        if self.active_rule != '':
            rule_info = self.global_rules[self.active_rule]
            self._ui.edit_order_spinbutton.set_value(int(rule_info['order']))
            if 'type' in rule_info:
                if rule_info['type'] == 'jid':
                    self._ui.edit_type_jabberid_radiobutton.set_active(True)
                    self._ui.edit_type_jabberid_entry.set_text(
                        rule_info['value'])
                elif rule_info['type'] == 'group':
                    self._ui.edit_type_group_radiobutton.set_active(True)
                    if rule_info['value'] in self.list_of_groups:
                        self._ui.edit_type_group_combobox.set_active(
                            self.list_of_groups[rule_info['value']])
                    else:
                        self._ui.edit_type_group_combobox.set_active(0)
                elif rule_info['type'] == 'subscription':
                    self._ui.edit_type_subscription_radiobutton.set_active(True)
                    sub_value = rule_info['value']
                    if sub_value == 'none':
                        self._ui.edit_type_subscription_combobox.set_active(0)
                    elif sub_value == 'both':
                        self._ui.edit_type_subscription_combobox.set_active(1)
                    elif sub_value == 'from':
                        self._ui.edit_type_subscription_combobox.set_active(2)
                    elif sub_value == 'to':
                        self._ui.edit_type_subscription_combobox.set_active(3)
                else:
                    self._ui.edit_type_select_all_radiobutton.set_active(True)
            else:
                self._ui.edit_type_select_all_radiobutton.set_active(True)
            self._ui.edit_send_messages_checkbutton.set_active(False)
            self._ui.edit_queries_send_checkbutton.set_active(False)
            self._ui.edit_view_status_checkbutton.set_active(False)
            self._ui.edit_send_status_checkbutton.set_active(False)
            self._ui.edit_all_checkbutton.set_active(False)
            if not rule_info['child']:
                self._ui.edit_all_checkbutton.set_active(True)
            else:
                if 'presence-out' in rule_info['child']:
                    self._ui.edit_send_status_checkbutton.set_active(True)
                if 'presence-in' in rule_info['child']:
                    self._ui.edit_view_status_checkbutton.set_active(True)
                if 'iq' in rule_info['child']:
                    self._ui.edit_queries_send_checkbutton.set_active(True)
                if 'message' in rule_info['child']:
                    self._ui.edit_send_messages_checkbutton.set_active(True)

            if rule_info['action'] == 'allow':
                self._ui.edit_allow_radiobutton.set_active(True)
            else:
                self._ui.edit_deny_radiobutton.set_active(True)
        self._ui.add_edit_vbox.show()

    def on_edit_all_checkbutton_toggled(self, widget):
        if widget.get_active():
            self._ui.edit_send_messages_checkbutton.set_active(True)
            self._ui.edit_queries_send_checkbutton.set_active(True)
            self._ui.edit_view_status_checkbutton.set_active(True)
            self._ui.edit_send_status_checkbutton.set_active(True)
            self._ui.edit_send_messages_checkbutton.set_sensitive(False)
            self._ui.edit_queries_send_checkbutton.set_sensitive(False)
            self._ui.edit_view_status_checkbutton.set_sensitive(False)
            self._ui.edit_send_status_checkbutton.set_sensitive(False)
        else:
            self._ui.edit_send_messages_checkbutton.set_active(False)
            self._ui.edit_queries_send_checkbutton.set_active(False)
            self._ui.edit_view_status_checkbutton.set_active(False)
            self._ui.edit_send_status_checkbutton.set_active(False)
            self._ui.edit_send_messages_checkbutton.set_sensitive(True)
            self._ui.edit_queries_send_checkbutton.set_sensitive(True)
            self._ui.edit_view_status_checkbutton.set_sensitive(True)
            self._ui.edit_send_status_checkbutton.set_sensitive(True)

    def _on_privacy_list_active_toggled(self, widget):
        name = None
        if widget.get_active():
            name = self.privacy_list_name

        con = app.connections[self.account]
        con.get_module('PrivacyLists').set_active_list(name)

    def _on_privacy_list_default_toggled(self, widget):
        name = None
        if widget.get_active():
            name = self.privacy_list_name

        con = app.connections[self.account]
        con.get_module('PrivacyLists').set_default_list(name)

    def on_new_rule_button_clicked(self, _widget):
        self.reset_fields()
        self._ui.add_edit_vbox.show()

    def reset_fields(self):
        self._ui.edit_type_jabberid_entry.set_text('')
        self._ui.edit_allow_radiobutton.set_active(True)
        self._ui.edit_type_jabberid_radiobutton.set_active(True)
        self.active_rule = ''
        self._ui.edit_send_messages_checkbutton.set_active(False)
        self._ui.edit_queries_send_checkbutton.set_active(False)
        self._ui.edit_view_status_checkbutton.set_active(False)
        self._ui.edit_send_status_checkbutton.set_active(False)
        self._ui.edit_all_checkbutton.set_active(False)
        self._ui.edit_order_spinbutton.set_value(self.max_order + 1)
        self._ui.edit_type_group_combobox.set_active(0)
        self._ui.edit_type_subscription_combobox.set_active(0)
        self._ui.add_edit_rule_label.set_label(_('<b>Add a rule</b>'))

    def get_current_tags(self):
        if self._ui.edit_type_jabberid_radiobutton.get_active():
            edit_type = 'jid'
            edit_value = self._ui.edit_type_jabberid_entry.get_text()
        elif self._ui.edit_type_group_radiobutton.get_active():
            edit_type = 'group'
            model = self._ui.edit_type_group_combobox.get_model()
            iter_ = self._ui.edit_type_group_combobox.get_active_iter()
            edit_value = model[iter_][0]
        elif self._ui.edit_type_subscription_radiobutton.get_active():
            edit_type = 'subscription'
            subs = ['none', 'both', 'from', 'to']
            edit_value = subs[
                self._ui.edit_type_subscription_combobox.get_active()]
        elif self._ui.edit_type_select_all_radiobutton.get_active():
            edit_type = ''
            edit_value = ''
        edit_order = str(self._ui.edit_order_spinbutton.get_value_as_int())
        if self._ui.edit_allow_radiobutton.get_active():
            edit_deny = 'allow'
        else:
            edit_deny = 'deny'
        child = []
        if not self._ui.edit_all_checkbutton.get_active():
            if self._ui.edit_send_messages_checkbutton.get_active():
                child.append('message')
            if self._ui.edit_queries_send_checkbutton.get_active():
                child.append('iq')
            if self._ui.edit_send_status_checkbutton.get_active():
                child.append('presence-out')
            if self._ui.edit_view_status_checkbutton.get_active():
                child.append('presence-in')
        if edit_type != '':
            return {'order': edit_order, 'action': edit_deny,
                    'type': edit_type, 'value': edit_value, 'child': child}
        return {'order': edit_order, 'action': edit_deny, 'child': child}

    def on_save_rule_button_clicked(self, _widget):
        tags = []
        current_tags = self.get_current_tags()
        if int(current_tags['order']) > self.max_order:
            self.max_order = int(current_tags['order'])
        if self.active_rule == '':
            tags.append(current_tags)

        for rule in self.global_rules:
            if rule != self.active_rule:
                tags.append(self.global_rules[rule])
            else:
                tags.append(current_tags)

        con = app.connections[self.account]
        con.get_module('PrivacyLists').set_privacy_list(
            self.privacy_list_name, tags)
        self.refresh_rules()
        self._ui.add_edit_vbox.hide()
        if 'privacy_lists' in app.interface.instances[self.account]:
            win = app.interface.instances[self.account]['privacy_lists']
            win.add_privacy_list_to_combobox(self.privacy_list_name)
            win.draw_widgets()

    def _on_list_of_rules_changed(self, _widget):
        self._ui.add_edit_vbox.hide()

    def _on_edit_type_changed(self, widget, radiobutton):
        active_bool = widget.get_active()
        if active_bool:
            self.edit_rule_type = radiobutton

    def _on_edit_allow_changed(self, widget, radiobutton):
        active_bool = widget.get_active()
        if active_bool:
            self.allow_deny = radiobutton

    def _on_close_clicked(self, _widget):
        self.window.destroy()


class PrivacyListsWindow(EventHelper):
    """
    Window that is the main window for Privacy Lists; we can list there the
    privacy lists and ask to create a new one or edit an already there one
    """
    def __init__(self, account):
        EventHelper.__init__(self)
        self.account = account
        self.privacy_lists_save = []

        self._ui = get_builder('privacy_lists_window.ui')

        self.window = self._ui.get_object('privacy_lists_first_window')

        self.draw_privacy_lists_in_combobox([])
        self.privacy_lists_refresh()

        self.enabled = True

        if len(app.connections) > 1:
            title = _('Privacy Lists for %s') % self.account
        else:
            title = _('Privacy Lists')

        self.window.set_title(title)

        # pylint: disable=line-too-long
        self.register_events([
            ('privacy-lists-received', ged.GUI1, self._nec_privacy_lists_received),
            ('privacy-list-removed', ged.GUI1, self._nec_privacy_lists_removed),
        ])
        # pylint: enable=line-too-long

        self.window.show_all()

        self._ui.connect_signals(self)

    def on_key_press_event(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.window.destroy()

    def _on_privacy_lists_first_destroy(self, _widget):
        if 'privacy_lists' in app.interface.instances[self.account]:
            del app.interface.instances[self.account]['privacy_lists']
        self.unregister_events()

    def remove_privacy_list(self, privacy_list):
        if privacy_list not in self.privacy_lists_save:
            return

        model = self._ui.list_of_privacy_lists_combobox.get_model()
        for entry in model:
            if entry[0] == privacy_list:
                model.remove(entry.iter)

        self.privacy_lists_save.remove(privacy_list)

    def add_privacy_list_to_combobox(self, privacy_list):
        if privacy_list in self.privacy_lists_save:
            return
        model = self._ui.list_of_privacy_lists_combobox.get_model()
        model.append([privacy_list])
        self.privacy_lists_save.append(privacy_list)

    def draw_privacy_lists_in_combobox(self, privacy_lists):
        self._ui.list_of_privacy_lists_combobox.set_active(-1)
        self._ui.list_of_privacy_lists_combobox.get_model().clear()
        self.privacy_lists_save = []
        for add_item in privacy_lists:
            self.add_privacy_list_to_combobox(add_item)
        self.draw_widgets()

    def draw_widgets(self):
        if not self.privacy_lists_save:
            self._ui.list_of_privacy_lists_combobox.set_sensitive(False)
            self._ui.open_privacy_list_button.set_sensitive(False)
            self._ui.delete_privacy_list_button.set_sensitive(False)
        else:
            self._ui.list_of_privacy_lists_combobox.set_sensitive(True)
            self._ui.list_of_privacy_lists_combobox.set_active(0)
            self._ui.open_privacy_list_button.set_sensitive(True)
            self._ui.delete_privacy_list_button.set_sensitive(True)

    def _on_close_clicked(self, _widget):
        self.window.destroy()

    def _on_delete_privacy_list_clicked(self, _widget):
        active_list = self.privacy_lists_save[
            self._ui.list_of_privacy_lists_combobox.get_active()]
        con = app.connections[self.account]
        con.get_module('PrivacyLists').del_privacy_list(active_list)

    def privacy_list_removed(self, active_list):
        self.privacy_lists_save.remove(active_list)
        self.privacy_lists_received(self.privacy_lists_save)

    def _nec_privacy_lists_removed(self, obj):
        if obj.conn.name != self.account:
            return
        self.privacy_list_removed(obj.list_name)

    def privacy_lists_received(self, lists):
        privacy_lists = []
        for privacy_list in lists:
            privacy_lists.append(privacy_list)
        self.draw_privacy_lists_in_combobox(privacy_lists)

    def _nec_privacy_lists_received(self, obj):
        if obj.conn.name != self.account:
            return
        self.privacy_lists_received(obj.lists)

    def privacy_lists_refresh(self):
        con = app.connections[self.account]
        con.get_module('PrivacyLists').get_privacy_lists()

    def _on_new_privacy_list_clicked(self, _widget):
        name = self._ui.new_privacy_list_entry.get_text()
        if not name:
            ErrorDialog(
                _('Invalid List Name'),
                _('You must enter a name to create a privacy list.'),
                transient_for=self.window)
            return
        key_name = 'privacy_list_%s' % name
        if key_name in app.interface.instances[self.account]:
            app.interface.instances[self.account][key_name].window.present()
        else:
            app.interface.instances[self.account][key_name] = \
                PrivacyListWindow(self.account, name, 'NEW')
        self._ui.new_privacy_list_entry.set_text('')

    def _on_privacy_lists_refresh_clicked(self, _widget):
        self.privacy_lists_refresh()

    def _on_open_privacy_list_clicked(self, _widget):
        name = self.privacy_lists_save[
            self._ui.list_of_privacy_lists_combobox.get_active()]
        key_name = 'privacy_list_%s' % name
        if key_name in app.interface.instances[self.account]:
            app.interface.instances[self.account][key_name].window.present()
        else:
            app.interface.instances[self.account][key_name] = \
                PrivacyListWindow(self.account, name, 'EDIT')
