# -*- coding: utf-8 -*-
#
# Copyright (C) 2017 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of Gajim.
#
# Gajim is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

from collections import namedtuple

import nbxmpp
from gi.repository import Gtk

from gajim.common import gajim
from gajim.common import ged
from gajim.gtkgui_helpers import get_icon_pixmap, Color

class ServerInfoDialog(Gtk.Dialog):
    def __init__(self, account):
        flags = Gtk.DialogFlags.DESTROY_WITH_PARENT
        super().__init__(_('Server Info'), None, flags)

        self.account = account
        self.set_transient_for(gajim.interface.roster.window)
        self.set_resizable(False)

        grid = Gtk.Grid()
        grid.set_name('ServerInfoGrid')
        grid.set_row_spacing(10)
        grid.set_hexpand(True)

        self.info_listbox = Gtk.ListBox()
        self.info_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.info_listbox.set_header_func(self.header_func, 'Information')
        grid.attach(self.info_listbox, 0, 0, 1, 1)

        self.feature_listbox = Gtk.ListBox()
        self.feature_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.feature_listbox.set_header_func(self.header_func, 'Features')
        grid.attach(self.feature_listbox, 0, 1, 1, 1)

        box = self.get_content_area()
        box.pack_start(grid, True, True, 0)
        box.set_property('margin', 12)
        box.set_spacing(18)

        self.connect('response', self.on_response)
        self.connect('destroy', self.on_destroy)

        gajim.ged.register_event_handler('version-result-received',
                                         ged.CORE,
                                         self._nec_version_result_received)

        gajim.ged.register_event_handler('agent-info-received',
                                         ged.GUI1,
                                         self._nec_agent_info_received)

        self.version = ''
        self.hostname = gajim.get_hostname_from_account(account)
        gajim.connections[account].request_os_info(self.hostname, None)

        for feature in self.get_features():
            self.add_feature(feature)

        for info in self.get_infos():
            self.add_info(info)

        self.show_all()

    @staticmethod
    def header_func(row, before, user_data):
        if before:
            row.set_header(None)
        else:
            label = Gtk.Label(label=user_data)
            label.set_halign(Gtk.Align.START)
            row.set_header(label)

    @staticmethod
    def update(func, listbox):
        for index, item in enumerate(func()):
            row = listbox.get_row_at_index(index)
            row.get_child().update(item)
            row.set_tooltip_text(item.tooltip)

    def _nec_version_result_received(self, obj):
        if obj.jid != self.hostname:
            return
        self.version = obj.client_info
        self.update(self.get_infos, self.info_listbox)

    def _nec_agent_info_received(self, obj):
        if not 'Gajim_' in obj.id_:
            return
        self.update(self.get_features, self.feature_listbox)

    def add_feature(self, feature):
        item = FeatureItem(feature)
        self.feature_listbox.add(item)
        item.get_parent().set_tooltip_text(feature.tooltip)

    def get_features(self):
        con = gajim.connections[self.account]
        Feature = namedtuple('Feature', ['name', 'enabled', 'tooltip'])

        return [
            Feature('XEP-0016: Privacy Lists', con.privacy_rules_supported, None),
            Feature('XEP-0045: Multi-User Chat', con.muc_jid, None),
            Feature('XEP-0054: vcard-temp', con.vcard_supported, None),
            Feature('XEP-0163: Personal Eventing Protocol', con.pep_supported, None),
            Feature('XEP-0191: Blocking Command', con.blocking_supported, nbxmpp.NS_BLOCKING),
            Feature('XEP-0198: Stream Management', con.sm.enabled, nbxmpp.NS_STREAM_MGMT),
            Feature('XEP-0280: Message Carbons', con.carbons_enabled, nbxmpp.NS_CARBONS),
            Feature('XEP-0313: Message Archive Management', con.archiving_namespace, con.archiving_namespace),
            Feature('XEP-0363: HTTP File Upload', con.httpupload, nbxmpp.NS_HTTPUPLOAD)]

    def add_info(self, info):
        self.info_listbox.add(ServerInfoItem(info))

    def get_infos(self):
        Info = namedtuple('Info', ['name', 'value', 'tooltip'])
        return [
            Info(_('Hostname'), self.hostname, None),
            Info(_('Server Software'), self.version, None)]

    def on_response(self, dialog, response):
        if response == Gtk.ResponseType.OK:
            self.destroy()

    def on_destroy(self, *args):
        del gajim.interface.instances[self.account]['server_info']
        gajim.ged.remove_event_handler('version-result-received',
                                       ged.CORE,
                                       self._nec_version_result_received)

        gajim.ged.remove_event_handler('agent-info-received',
                                       ged.GUI1,
                                       self._nec_agent_info_received)

class FeatureItem(Gtk.Grid):
    def __init__(self, feature):
        super().__init__()

        self.set_column_spacing(6)

        self.icon = Gtk.Image()
        self.feature_label = Gtk.Label(label=feature.name)
        self.set_feature_enabled(bool(feature.enabled))

        self.add(self.icon)
        self.add(self.feature_label)

    def set_feature_enabled(self, enabled):
        if enabled:
            self.icon.set_from_pixbuf(
                get_icon_pixmap('emblem-ok-symbolic', color=[Color.GREEN]))
        else:
            self.icon.set_from_pixbuf(
                get_icon_pixmap('window-close-symbolic', color=[Color.RED]))

    def update(self, feature):
        self.set_feature_enabled(bool(feature.enabled))

class ServerInfoItem(Gtk.Grid):
    def __init__(self, info):
        super().__init__()

        self.set_hexpand(True)
        self.insert_column(0)
        self.set_column_homogeneous(True)

        self.info = Gtk.Label(label=info.name)
        self.info.set_halign(Gtk.Align.START)
        self.info.set_hexpand(True)
        self.value = Gtk.Label(label=info.value)
        self.value.set_halign(Gtk.Align.START)
        self.value.set_hexpand(True)

        self.add(self.info)
        self.add(self.value)

    def update(self, info):
        self.value.set_text(info.value)
