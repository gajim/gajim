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

import logging
from collections import namedtuple
from datetime import timedelta

import nbxmpp
from nbxmpp.util import is_error_result
from nbxmpp.namespaces import Namespace
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Pango

from gajim.common import app
from gajim.common import ged
from gajim.common.helpers import open_uri
from gajim.common.i18n import _

from gajim.gtk.util import ensure_not_destroyed
from gajim.gtk.util import get_builder
from gajim.gtk.util import EventHelper
from gajim.gtk.util import open_window

log = logging.getLogger('gajim.gtk.server_info')


class ServerInfo(Gtk.ApplicationWindow, EventHelper):
    def __init__(self, account):
        Gtk.ApplicationWindow.__init__(self)
        EventHelper.__init__(self)
        self.set_name('ServerInfo')
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_default_size(400, 600)
        self.set_show_menubar(False)
        self.set_title(_('Server Info'))

        self.account = account
        self._destroyed = False

        self._ui = get_builder('server_info.ui')
        self.add(self._ui.server_info_notebook)

        self.connect('destroy', self.on_destroy)
        self.connect('key-press-event', self._on_key_press)
        self._ui.connect_signals(self)

        self.register_events([
            ('server-disco-received', ged.GUI1, self._server_disco_received),
        ])

        self.version = ''
        self.hostname = app.get_hostname_from_account(account)
        self._ui.server_hostname.set_text(self.hostname)
        con = app.connections[account]
        con.get_module('SoftwareVersion').request_software_version(
            self.hostname, callback=self._software_version_received)
        self.request_last_activity()

        server_info = con.get_module('Discovery').server_info
        self._add_contact_addresses(server_info.dataforms)

        self.cert = con.certificate
        self._add_connection_info()

        self.feature_listbox = Gtk.ListBox()
        self.feature_listbox.set_name('ServerInfo')
        self.feature_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self._ui.features_scrolled.add(self.feature_listbox)
        for feature in self.get_features():
            self.add_feature(feature)
        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

        self.show_all()

    def _on_key_press(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _add_connection_info(self):
        # Connection type
        client = app.connections[self.account].connection
        con_type = client.current_connection_type
        self._ui.connection_type.set_text(con_type.value)
        if con_type.is_plain:
            self._ui.conection_type.get_style_context().add_class(
                'error-color')

        is_websocket = app.connections[self.account].connection.is_websocket
        protocol = 'WebSocket' if is_websocket else 'TCP'
        self._ui.connection_protocol.set_text(protocol)

        # Connection proxy
        proxy = client.proxy
        if proxy is not None:
            self._ui.proxy_type.set_text(proxy.type)
            self._ui.proxy_host.set_text(proxy.host)

        self._ui.cert_button.set_sensitive(self.cert)

    def _on_cert_button_clicked(self, _button):
        open_window('CertificateDialog',
                    account=self.account,
                    transient_for=self,
                    cert=self.cert)

    def request_last_activity(self):
        if not app.account_is_connected(self.account):
            return
        con = app.connections[self.account]
        iq = nbxmpp.Iq(to=self.hostname, typ='get', queryNS=Namespace.LAST)
        con.connection.SendAndCallForResponse(iq, self._on_last_activity)

    def _add_contact_addresses(self, dataforms):
        fields = {
            'admin-addresses': _('Admin'),
            'status-addresses': _('Status'),
            'support-addresses': _('Support'),
            'security-addresses': _('Security'),
            'feedback-addresses': _('Feedback'),
            'abuse-addresses': _('Abuse'),
            'sales-addresses': _('Sales'),
        }

        addresses = self._get_addresses(fields, dataforms)
        if addresses is None:
            self._ui.no_addresses_label.set_visible(True)
            return

        row_count = 4
        for address_type, values in addresses.items():
            label = self._get_address_type_label(fields[address_type])
            self._ui.server.attach(label, 0, row_count, 1, 1)
            for index, value in enumerate(values):
                last = index == len(values) - 1
                label = self._get_address_label(value, last=last)
                self._ui.server.attach(label, 1, row_count, 1, 1)
                row_count += 1

    @staticmethod
    def _get_addresses(fields, dataforms):
        addresses = {}
        for form in dataforms:
            field = form.vars.get('FORM_TYPE')
            if field.value != 'http://jabber.org/network/serverinfo':
                continue

            for address_type in fields:
                field = form.vars.get(address_type)
                if field is None:
                    continue

                if field.type_ != 'list-multi':
                    continue

                if not field.values:
                    continue
                addresses[address_type] = field.values

            return addresses or None
        return None

    @staticmethod
    def _get_address_type_label(text):
        label = Gtk.Label(label=text)
        label.set_halign(Gtk.Align.END)
        label.set_valign(Gtk.Align.START)
        label.get_style_context().add_class('dim-label')
        return label

    def _get_address_label(self, address, last=False):
        label = Gtk.Label()
        label.set_markup('<a href="%s">%s</a>' % (address, address))
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_xalign(0)
        label.set_halign(Gtk.Align.START)
        label.get_style_context().add_class('link-button')
        label.connect('activate-link', self._on_activate_link)
        if last:
            label.set_margin_bottom(6)
        return label

    def _on_activate_link(self, label, *args):
        open_uri(label.get_text(), account=self.account)
        return Gdk.EVENT_STOP

    def _on_last_activity(self, _nbxmpp_client, stanza):
        if self._destroyed:
            # Window got closed in the meantime
            return
        if not nbxmpp.isResultNode(stanza):
            log.warning('Received malformed result: %s', stanza)
            return
        if stanza.getQueryNS() != Namespace.LAST:
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
            uptime = _('%(days)s days, %(hours)s hours') % {
                'days': delta.days, 'hours': hours}
            self._ui.server_uptime.set_text(uptime)

    @ensure_not_destroyed
    def _software_version_received(self, result):
        if is_error_result(result):
            self.version = _('Unknown')
        else:
            self.version = '%s %s' % (result.name, result.version)
        self._ui.server_software.set_text(self.version)

    @staticmethod
    def update(func, listbox):
        for index, item in enumerate(func()):
            row = listbox.get_row_at_index(index)
            row.get_child().update(item)
            row.set_tooltip_text(row.get_child().tooltip)

    def _server_disco_received(self, _event):
        self.update(self.get_features, self.feature_listbox)

    def add_feature(self, feature):
        item = FeatureItem(feature)
        self.feature_listbox.add(item)
        item.get_parent().set_tooltip_text(item.tooltip or '')

    def get_features(self):
        con = app.connections[self.account]
        Feature = namedtuple('Feature',
                             ['name', 'available', 'tooltip', 'enabled'])
        Feature.__new__.__defaults__ = (None, None)  # type: ignore

        # HTTP File Upload
        http_upload_info = con.get_module('HTTPUpload').httpupload_namespace
        if con.get_module('HTTPUpload').available:
            max_file_size = con.get_module('HTTPUpload').max_file_size
            if max_file_size is not None:
                max_file_size = max_file_size / (1024 * 1024)
                http_upload_info = http_upload_info + ' (max. %s MiB)' % \
                    max_file_size

        return [
            Feature('XEP-0045: Multi-User Chat',
                    con.get_module('MUC').supported),
            Feature('XEP-0054: vcard-temp',
                    con.get_module('VCardTemp').supported),
            Feature('XEP-0163: Personal Eventing Protocol',
                    con.get_module('PEP').supported),
            Feature('XEP-0163: #publish-options',
                    con.get_module('PubSub').publish_options),
            Feature('XEP-0191: Blocking Command',
                    con.get_module('Blocking').supported,
                    Namespace.BLOCKING),
            Feature('XEP-0198: Stream Management',
                    con.features.has_sm, Namespace.STREAM_MGMT),
            Feature('XEP-0258: Security Labels in XMPP',
                    con.get_module('SecLabels').supported,
                    Namespace.SECLABEL),
            Feature('XEP-0280: Message Carbons',
                    con.get_module('Carbons').supported,
                    Namespace.CARBONS),
            Feature('XEP-0313: Message Archive Management',
                    con.get_module('MAM').available),
            Feature('XEP-0363: HTTP File Upload',
                    con.get_module('HTTPUpload').available,
                    http_upload_info),
            Feature('XEP-0398: Avatar Conversion',
                    con.avatar_conversion),
            Feature('XEP-0411: Bookmarks Conversion',
                    con.get_module('Bookmarks').conversion)
        ]

    def _on_clipboard_button_clicked(self, _widget):
        server_software = 'Server Software: %s\n' % self.version
        server_features = ''

        for feature in self.get_features():
            if feature.available:
                available = 'Yes'
            else:
                available = 'No'
            if feature.tooltip is not None:
                tooltip = '(%s)' % feature.tooltip
            else:
                tooltip = ''
            server_features += '%s: %s %s\n' % (
                feature.name, available, tooltip)

        clipboard_text = server_software + server_features
        self.clipboard.set_text(clipboard_text, -1)

    def on_destroy(self, *args):
        self._destroyed = True


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
        self.icon.get_style_context().remove_class('error-color')
        self.icon.get_style_context().remove_class('warning-color')
        self.icon.get_style_context().remove_class('success-color')

        if not available:
            self.icon.set_from_icon_name('window-close-symbolic',
                                         Gtk.IconSize.MENU)
            self.icon.get_style_context().add_class('error-color')
        elif enabled is False:
            self.icon.set_from_icon_name('dialog-warning-symbolic',
                                         Gtk.IconSize.MENU)
            self.tooltip += _('\nDisabled in preferences')
            self.icon.get_style_context().add_class('warning-color')
        else:
            self.icon.set_from_icon_name('emblem-ok-symbolic',
                                         Gtk.IconSize.MENU)
            self.icon.get_style_context().add_class('success-color')

    def update(self, feature):
        self.tooltip = feature.tooltip
        self.set_feature(feature.available, feature.enabled)
