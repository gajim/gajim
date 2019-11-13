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
from gi.repository import Gtk
from gi.repository import Gdk

from gajim.common import app
from gajim.common import ged
from gajim.common.i18n import _

from gajim.gtk.dialogs import CertificateDialog
from gajim.gtk.util import ensure_not_destroyed
from gajim.gtk.util import get_builder
from gajim.gtk.util import EventHelper

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

        self.cert = con.connection.Connection.ssl_certificate
        self._add_connection_info()

        self.feature_listbox = Gtk.ListBox()
        self.feature_listbox.set_name('ServerInfo')
        self.feature_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.feature_listbox.set_header_func(self.header_func, 'Features')
        self._ui.features_scrolled.add(self.feature_listbox)
        for feature in self.get_features():
            self.add_feature(feature)
        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

        self.show_all()

    def _on_key_press(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    @staticmethod
    def header_func(row, before, user_data):
        if before:
            row.set_header(None)
        else:
            label = Gtk.Label(label=user_data)
            label.set_halign(Gtk.Align.START)
            row.set_header(label)

    def _add_connection_info(self):
        ssl_con = app.connections[self.account].connection.get_ssl_connection()
        ssl_version = None
        cipher_name = None
        if ssl_con is not None:
            ssl_version = ssl_con.get_cipher_version()
            cipher_name = ssl_con.get_cipher_name()

        host, proxy = app.connections[self.account].get_connection_info()
        con_type = host['type']

        # Connection type
        self._ui.connection_type.set_text(con_type.upper())
        if con_type == 'plain':
            self._ui.conection_type.get_style_context().add_class(
                'error-color')

        # Connection security
        if ssl_version is not None:
            self._ui.connection_security.set_text(ssl_version)

        # Connection cipher
        if cipher_name is not None:
            self._ui.connection_cipher.set_text(cipher_name)

        # Connection proxy
        if proxy:
            if proxy['type'] == 'bosh':
                self._ui.connection_proxy_header.set_text(_('BOSH'))
                self._ui.connection_proxy.set_text(proxy['bosh_uri'])
            if proxy['type'] in ['http', 'socks5'] or proxy['bosh_useproxy']:
                self._ui.connection_proxy.set_text(
                    proxy['host'] + ':' + proxy['port'])

        self._ui.cert_button.set_sensitive(self.cert)

    def _on_cert_button_clicked(self, button_):
        window = app.get_app_window(CertificateDialog, self.account)
        if window is None:
            CertificateDialog(self, self.account, self.cert)
        else:
            window.present()

    def request_last_activity(self):
        if not app.account_is_connected(self.account):
            return
        con = app.connections[self.account]
        iq = nbxmpp.Iq(to=self.hostname, typ='get', queryNS=nbxmpp.NS_LAST)
        con.connection.SendAndCallForResponse(iq, self._on_last_activity)

    def _on_last_activity(self, stanza):
        if self._destroyed:
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

    def _server_disco_received(self, obj):
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
            Feature('XEP-0016: Privacy Lists',
                    con.get_module('PrivacyLists').supported),
            Feature('XEP-0045: Multi-User Chat', con.muc_jid),
            Feature('XEP-0054: vcard-temp',
                    con.get_module('VCardTemp').supported),
            Feature('XEP-0163: Personal Eventing Protocol',
                    con.get_module('PEP').supported),
            Feature('XEP-0163: #publish-options',
                    con.get_module('PubSub').publish_options),
            Feature('XEP-0191: Blocking Command',
                    con.get_module('Blocking').supported,
                    nbxmpp.NS_BLOCKING),
            Feature('XEP-0198: Stream Management',
                    con.connection.sm_enabled, nbxmpp.NS_STREAM_MGMT),
            Feature('XEP-0258: Security Labels in XMPP',
                    con.get_module('SecLabels').supported,
                    nbxmpp.NS_SECLABEL),
            Feature('XEP-0280: Message Carbons',
                    con.get_module('Carbons').supported,
                    nbxmpp.NS_CARBONS),
            Feature('XEP-0313: Message Archive Management',
                    con.get_module('MAM').available,
                    con.get_module('MAM').archiving_namespace),
            Feature('XEP-0363: HTTP File Upload',
                    con.get_module('HTTPUpload').available,
                    http_upload_info),
            Feature('XEP-0398: Avatar Conversion',
                    con.avatar_conversion),
            Feature('XEP-0411: Bookmarks Conversion',
                    con.get_module('Bookmarks').conversion)
        ]

    def _on_clipboard_button_clicked(self, widget):
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
