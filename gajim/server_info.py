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
from datetime import timedelta
import logging

from gi.repository import Gtk
import nbxmpp

from gajim.common import app
from gajim.common import ged
from gajim.gtkgui_helpers import get_icon_pixmap, Color

log = logging.getLogger('gajim.serverinfo')


class ServerInfoDialog(Gtk.Dialog):
    def __init__(self, account):
        flags = Gtk.DialogFlags.DESTROY_WITH_PARENT
        super().__init__(_('Server Info'), None, flags)

        self.account = account
        self.set_transient_for(app.interface.roster.window)
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

        app.ged.register_event_handler('version-result-received',
                                       ged.CORE,
                                       self._nec_version_result_received)

        app.ged.register_event_handler('agent-info-received',
                                       ged.GUI1,
                                       self._nec_agent_info_received)

        self.version = ''
        self.uptime = ''
        self.hostname = app.get_hostname_from_account(account)
        con = app.connections[account]
        con.get_module('SoftwareVersion').request_os_info(self.hostname, None)
        self.request_last_activity()

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
            row.set_tooltip_text(row.get_child().tooltip)

    def request_last_activity(self):
        if not app.account_is_connected(self.account):
            return
        con = app.connections[self.account]
        iq = nbxmpp.Iq(to=self.hostname, typ='get', queryNS=nbxmpp.NS_LAST)
        con.connection.SendAndCallForResponse(iq, self._on_last_activity)

    def _on_last_activity(self, stanza):
        if 'server_info' not in app.interface.instances[self.account]:
            # Window got closed in the meantime
            return
        if not nbxmpp.isResultNode(stanza):
            log.warning('Received malformed result: %s', stanza)
            return
        if stanza.getQueryNS() != nbxmpp.NS_LAST:
            log.warning('Wrong namespace on result: %s', stanza)
            return
        try:
            seconds = int(stanza.getQuery().getAttr('seconds'))
        except (ValueError, TypeError, AttributeError):
            log.exception('Received malformed last activity result')
        else:
            delta = timedelta(seconds=seconds)
            hours = 0
            if seconds >= 3600:
                hours = delta.seconds // 3600
            self.uptime = _('%(days)s days, %(hours)s hours') % {
                'days': delta.days, 'hours': hours}
            self.update(self.get_infos, self.info_listbox)

    def _nec_version_result_received(self, obj):
        if obj.jid != self.hostname:
            return
        self.version = obj.client_info
        self.update(self.get_infos, self.info_listbox)

    def _nec_agent_info_received(self, obj):
        if 'Gajim_' not in obj.id_:
            return
        self.update(self.get_features, self.feature_listbox)

    def add_feature(self, feature):
        item = FeatureItem(feature)
        self.feature_listbox.add(item)
        item.get_parent().set_tooltip_text(item.tooltip)

    def get_features(self):
        con = app.connections[self.account]
        Feature = namedtuple('Feature',
                             ['name', 'available', 'tooltip', 'enabled'])

        carbons_enabled = app.config.get_per('accounts', self.account,
                                             'enable_message_carbons')
        mam_enabled = app.config.get_per('accounts', self.account,
                                         'sync_logs_with_server')

        return [
            Feature('XEP-0016: Privacy Lists',
                    con.privacy_rules_supported, '', None),
            Feature('XEP-0045: Multi-User Chat', con.muc_jid, '', None),
            Feature('XEP-0054: vcard-temp', con.vcard_supported, '', None),
            Feature('XEP-0163: Personal Eventing Protocol',
                    con.pep_supported, '', None),
            Feature('XEP-0163: #publish-options',
                    con.pubsub_publish_options_supported, '', None),
            Feature('XEP-0191: Blocking Command',
                    con.blocking_supported, nbxmpp.NS_BLOCKING, None),
            Feature('XEP-0198: Stream Management',
                    con.sm.enabled, nbxmpp.NS_STREAM_MGMT, None),
            Feature('XEP-0280: Message Carbons',
                    con.carbons_available, nbxmpp.NS_CARBONS, carbons_enabled),
            Feature('XEP-0313: Message Archive Management',
                    con.get_module('MAM').archiving_namespace,
                    con.get_module('MAM').archiving_namespace,
                    mam_enabled),
            Feature('XEP-0363: HTTP File Upload',
                    con.get_module('HTTPUpload').available,
                    con.get_module('HTTPUpload').httpupload_namespace, None)]

    def add_info(self, info):
        self.info_listbox.add(ServerInfoItem(info))

    def get_infos(self):
        Info = namedtuple('Info', ['name', 'value', 'tooltip'])
        return [
            Info(_('Hostname'), self.hostname, None),
            Info(_('Server Software'), self.version, None),
            Info(_('Server Uptime'), self.uptime, None)]

    def on_response(self, dialog, response):
        if response == Gtk.ResponseType.OK:
            self.destroy()

    def on_destroy(self, *args):
        del app.interface.instances[self.account]['server_info']
        app.ged.remove_event_handler('version-result-received',
                                     ged.CORE,
                                     self._nec_version_result_received)

        app.ged.remove_event_handler('agent-info-received',
                                     ged.GUI1,
                                     self._nec_agent_info_received)


class FeatureItem(Gtk.Grid):
    def __init__(self, feature):
        super().__init__()
        self.tooltip = feature.tooltip
        self.set_column_spacing(6)

        self.icon = Gtk.Image()
        self.feature_label = Gtk.Label(label=feature.name)
        self.set_feature(feature.available, feature.enabled)

        self.add(self.icon)
        self.add(self.feature_label)

    def set_feature(self, available, enabled):
        if not available:
            self.icon.set_from_pixbuf(
                get_icon_pixmap('window-close-symbolic', color=[Color.RED]))
        elif enabled is False:
            self.icon.set_from_pixbuf(
                get_icon_pixmap('dialog-warning-symbolic',
                                color=[Color.ORANGE]))
            self.tooltip += _('\nDisabled in config')
        else:
            self.icon.set_from_pixbuf(
                get_icon_pixmap('emblem-ok-symbolic', color=[Color.GREEN]))

    def update(self, feature):
        self.tooltip = feature.tooltip
        self.set_feature(feature.available, feature.enabled)


class ServerInfoItem(Gtk.Grid):
    def __init__(self, info):
        super().__init__()
        self.tooltip = info.tooltip
        self.set_hexpand(True)
        self.insert_column(0)
        self.set_column_homogeneous(True)

        self.info = Gtk.Label(label=info.name)
        self.info.set_halign(Gtk.Align.START)
        self.info.set_hexpand(True)
        self.value = Gtk.Label(label=info.value)
        self.value.set_halign(Gtk.Align.START)
        self.value.set_hexpand(True)
        self.value.set_selectable(True)

        self.add(self.info)
        self.add(self.value)

    def update(self, info):
        self.value.set_text(info.value)
