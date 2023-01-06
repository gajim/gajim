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

from typing import Any
from typing import cast
from typing import NamedTuple
from typing import Optional

import logging
from datetime import timedelta

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.modules.dataforms import SimpleDataForm
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import LastActivityData
from nbxmpp.structs import SoftwareVersionResult
from nbxmpp.task import Task

from gajim.common import app
from gajim.common import ged
from gajim.common.const import TLS_VERSION_STRINGS
from gajim.common.events import ServerDiscoReceived
from gajim.common.helpers import open_uri
from gajim.common.i18n import _

from .builder import get_builder
from .certificate_dialog import CertificateBox
from .util import EventHelper

log = logging.getLogger('gajim.gui.server_info')


class Feature(NamedTuple):
    name: str
    available: bool
    additional: Optional[str] = None


class ServerInfo(Gtk.ApplicationWindow, EventHelper):
    def __init__(self, account: str) -> None:
        Gtk.ApplicationWindow.__init__(self)
        EventHelper.__init__(self)
        self.set_name('ServerInfo')
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_default_size(500, 600)
        self.set_show_menubar(False)
        self.set_title(_('Server Info'))
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)

        self.account = account
        self._client = app.get_client(account)
        self._destroyed = False

        if app.settings.get('use_kib_mib'):
            self._units = GLib.FormatSizeFlags.IEC_UNITS
        else:
            self._units = GLib.FormatSizeFlags.DEFAULT

        self._ui = get_builder('server_info.ui')
        self.add(self._ui.server_info_notebook)

        self.connect('destroy', self._on_destroy)
        self.connect('key-press-event', self._on_key_press)
        self._ui.connect_signals(self)

        self.register_events([
            ('server-disco-received', ged.GUI1, self._server_disco_received),
        ])

        self._version = ''
        self._hostname = app.get_hostname_from_account(account)
        self._ui.server_hostname.set_text(self._hostname)
        self._client.get_module('SoftwareVersion').request_software_version(
            self._hostname, callback=self._software_version_received)

        self._client.get_module('LastActivity').request_last_activity(
            self._hostname, callback=self._on_last_activity)

        server_info = self._client.get_module('Discovery').server_info
        self._add_contact_addresses(server_info.dataforms)

        self._cert = self._client.certificate
        self._add_connection_info()

        cert_box = CertificateBox(account, self._cert)
        self._ui.cert_scrolled.add(cert_box)

        for feature in self._get_features():
            self._add_feature(feature)
        self._clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

        self.show_all()

    def _on_destroy(self, *args: Any) -> None:
        self._destroyed = True

    def _on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> None:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _add_connection_info(self) -> None:
        # Connection type
        nbxmpp_client = self._client.connection
        address = nbxmpp_client.current_address

        self._ui.connection_type.set_text(address.type.value)
        if address.type.is_plain:
            self._ui.connection_type.get_style_context().add_class(
                'error-color')

        # Connection proxy
        proxy = address.proxy
        if proxy is not None:
            self._ui.proxy_type.set_text(proxy.type)
            self._ui.proxy_host.set_text(proxy.host)

        self._ui.domain.set_text(address.domain)

        visible = address.service is not None
        self._ui.dns_label.set_visible(visible)
        self._ui.dns.set_visible(visible)
        self._ui.dns.set_text(address.service or '')

        visible = nbxmpp_client.remote_address is not None
        self._ui.ip_port_label.set_visible(visible)
        self._ui.ip_port.set_visible(visible)
        self._ui.ip_port.set_text(nbxmpp_client.remote_address or '')

        visible = address.uri is not None
        self._ui.websocket_label.set_visible(visible)
        self._ui.websocket.set_visible(visible)
        self._ui.websocket.set_text(address.uri or '')

        tls_version = TLS_VERSION_STRINGS.get(nbxmpp_client.tls_version)
        self._ui.tls_version.set_text(tls_version or _('Not available'))

        self._ui.cipher_suite.set_text(nbxmpp_client.ciphersuite or
                                       _('Not available'))

    def _add_contact_addresses(self, dataforms: list[SimpleDataForm]) -> None:
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
    def _get_addresses(fields: dict[str, str],
                       dataforms: list[SimpleDataForm]
                       ) -> Optional[dict[str, list[str]]]:
        addresses: dict[str, list[str]] = {}
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
    def _get_address_type_label(text: str) -> Gtk.Label:
        label = Gtk.Label(label=text)
        label.set_halign(Gtk.Align.END)
        label.set_valign(Gtk.Align.START)
        label.get_style_context().add_class('dim-label')
        return label

    def _get_address_label(self,
                           address: str,
                           last: bool = False
                           ) -> Gtk.Label:
        label = Gtk.Label()
        label.set_markup(f'<a href="{address}">{address}</a>')
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_xalign(0)
        label.set_halign(Gtk.Align.START)
        label.get_style_context().add_class('link-button')
        label.connect('activate-link', self._on_activate_link)
        if last:
            label.set_margin_bottom(6)
        return label

    def _on_activate_link(self, label: Gtk.Label, *args: Any) -> int:
        open_uri(label.get_text(), account=self.account)
        return Gdk.EVENT_STOP

    def _on_last_activity(self, task: Task) -> None:
        try:
            result = cast(LastActivityData, task.finish())
        except (StanzaError, MalformedStanzaError) as error:
            log.warning(error)
            return

        delta = timedelta(seconds=result.seconds)
        hours = 0
        if result.seconds >= 3600:
            hours = delta.seconds // 3600
        uptime = _('%(days)s days, %(hours)s hours') % {
            'days': delta.days,
            'hours': hours}
        self._ui.server_uptime.set_text(uptime)

    def _software_version_received(self, task: Task) -> None:
        try:
            result = cast(SoftwareVersionResult, task.finish())
        except StanzaError:
            self._version = _('Unknown')
        else:
            self._version = f'{result.name} {result.version}'

        self._ui.server_software.set_text(self._version)

    def _server_disco_received(self, _event: ServerDiscoReceived) -> None:
        features = self._get_features()
        for index, item in enumerate(features):
            row = cast(
                FeatureItem, self._ui.features_listbox.get_row_at_index(index))
            row.update(item)

    def _add_feature(self, feature: Feature) -> None:
        item = FeatureItem(feature)
        self._ui.features_listbox.add(item)

    def _get_features(self) -> list[Feature]:
        http_upload_module = self._client.get_module('HTTPUpload')
        http_upload_info = http_upload_module.httpupload_namespace
        if http_upload_module.available:
            max_size = http_upload_module.max_file_size
            if max_size is not None:
                max_size = GLib.format_size_full(max_size, self._units)
                http_upload_info = f'{http_upload_info} (max. {max_size})'

        return [
            Feature('XEP-0045: Multi-User Chat',
                    self._client.get_module('MUC').supported),
            Feature('XEP-0054: vcard-temp',
                    self._client.get_module('VCardTemp').supported),
            Feature('XEP-0077: In-Band Registration',
                    self._client.get_module('Register').supported),
            Feature('XEP-0163: Personal Eventing Protocol',
                    self._client.get_module('PEP').supported),
            Feature('XEP-0163: #publish-options',
                    self._client.get_module('PubSub').publish_options),
            Feature('XEP-0191: Blocking Command',
                    self._client.get_module('Blocking').supported,
                    Namespace.BLOCKING),
            Feature('XEP-0198: Stream Management',
                    self._client.features.has_sm,
                    Namespace.STREAM_MGMT),
            Feature('XEP-0258: Security Labels in XMPP',
                    self._client.get_module('SecLabels').supported,
                    Namespace.SECLABEL),
            Feature('XEP-0280: Message Carbons',
                    self._client.get_module('Carbons').supported,
                    Namespace.CARBONS),
            Feature('XEP-0313: Message Archive Management',
                    self._client.get_module('MAM').available),
            Feature('XEP-0363: HTTP File Upload',
                    self._client.get_module('HTTPUpload').available,
                    http_upload_info),
            Feature('XEP-0398: Avatar Conversion',
                    self._client.get_module(
                        'VCardAvatars').avatar_conversion_available),
            Feature('XEP-0411: Bookmarks Conversion',
                    self._client.get_module('Bookmarks').conversion),
            Feature('XEP-0402: Bookmarks Compat',
                    self._client.get_module('Bookmarks').compat),
            Feature('XEP-0402: Bookmarks Compat PEP',
                    self._client.get_module('Bookmarks').compat_pep)
        ]

    def _on_clipboard_button_clicked(self, _widget: Gtk.Button) -> None:
        server_software = _('Server Software: %s\n') % self._version
        server_features = ''

        for feature in self._get_features():
            if feature.available:
                available = _('Available')
            else:
                available = _('Not available')
            additional = ''
            if feature.additional is not None:
                additional = f'({feature.additional})'
            server_features += f'{feature.name}: {available} {additional}\n'

        clipboard_text = server_software + server_features
        self._clipboard.set_text(clipboard_text, -1)


class FeatureItem(Gtk.ListBoxRow):
    def __init__(self, feature: Feature) -> None:
        Gtk.ListBoxRow.__init__(self)
        self._feature = feature

        grid = Gtk.Grid(row_spacing=3, column_spacing=12)

        self._icon = Gtk.Image()
        self._feature_label = Gtk.Label()
        self._feature_label.set_halign(Gtk.Align.START)
        self._additional_label = Gtk.Label()
        self._additional_label.set_halign(Gtk.Align.START)
        self._additional_label.set_no_show_all(True)
        self._additional_label.get_style_context().add_class('dim-label')

        grid.attach(self._icon, 0, 0, 1, 1)
        grid.attach(self._feature_label, 1, 0, 1, 1)
        grid.attach(self._additional_label, 1, 1, 1, 1)

        self._set_feature()

        self.add(grid)
        self.show_all()

    def _set_feature(self) -> None:
        self._feature_label.set_text(self._feature.name)
        if self._feature.additional is not None:
            self._additional_label.set_text(self._feature.additional)
            self._additional_label.show()

        self._icon.get_style_context().remove_class('error-color')
        self._icon.get_style_context().remove_class('success-color')

        if self._feature.available:
            self._icon.set_from_icon_name(
                'emblem-ok-symbolic', Gtk.IconSize.MENU)
            self._icon.get_style_context().add_class('success-color')
        else:
            self._icon.set_from_icon_name(
                'window-close-symbolic', Gtk.IconSize.MENU)
            self._icon.get_style_context().add_class('error-color')

    def update(self, feature: Feature) -> None:
        self._feature = feature
        self._set_feature()
