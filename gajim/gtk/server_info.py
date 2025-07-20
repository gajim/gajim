# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import Any
from typing import cast
from typing import NamedTuple

import logging
from datetime import timedelta

from gi.repository import Adw
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.modules.dataforms import DataForm
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import LastActivityData
from nbxmpp.structs import SoftwareVersionResult
from nbxmpp.task import Task

from gajim.common import app
from gajim.common import ged
from gajim.common.const import TLS_VERSION_STRINGS
from gajim.common.events import ServerDiscoReceived
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.util.uri import open_uri

from gajim.gtk.builder import get_builder
from gajim.gtk.certificate_dialog import CertificateBox
from gajim.gtk.widgets import GajimAppWindow

log = logging.getLogger("gajim.gtk.server_info")


class Feature(NamedTuple):
    name: str
    available: bool
    additional: str | None = None


class ServerInfo(GajimAppWindow, EventHelper):
    def __init__(self, account: str) -> None:
        GajimAppWindow.__init__(
            self,
            name="ServerInfo",
            title=_("Server Info"),
            default_width=600,
            default_height=700,
        )
        EventHelper.__init__(self)

        self.account = account
        self._client = app.get_client(account)

        if app.settings.get("use_kib_mib"):
            self._units = GLib.FormatSizeFlags.IEC_UNITS
        else:
            self._units = GLib.FormatSizeFlags.DEFAULT

        self._ui = get_builder("server_info.ui")
        self.set_child(self._ui.box)

        self._connect(
            self._ui.clipboard_button, "clicked", self._on_clipboard_button_clicked
        )

        self.register_events(
            [
                ("server-disco-received", ged.GUI1, self._server_disco_received),
            ]
        )

        self._version = ""
        self._hostname = app.get_hostname_from_account(account, prefer_custom=True)
        self._ui.server_hostname_row.set_subtitle(self._hostname)

        domain = self._client.get_own_jid().domain
        self._client.get_module("SoftwareVersion").request_software_version(
            domain, callback=self._software_version_received
        )

        self._client.get_module("LastActivity").request_last_activity(
            domain, callback=self._on_last_activity
        )

        server_info = self._client.get_module("Discovery").server_info
        assert server_info is not None
        self._add_contact_addresses(server_info.dataforms)

        self._add_connection_info()

        if self._client.certificate is None:
            self._ui.no_certificate_label.set_visible(True)
        else:
            cert_box = CertificateBox(account, self._client.certificate)
            self._ui.cert_box.append(cert_box)

        for feature in self._get_features():
            self._add_feature(feature)

    def _cleanup(self, *args: Any) -> None:
        self.unregister_events()

    def _add_connection_info(self) -> None:
        # Connection type
        nbxmpp_client = self._client.connection
        address = nbxmpp_client.current_address

        assert address is not None
        assert address.domain is not None
        self._ui.domain_row.set_subtitle(address.domain)

        visible = address.service is not None
        self._ui.dns_row.set_visible(visible)
        self._ui.dns_row.set_subtitle(address.service or "")

        visible = nbxmpp_client.remote_address is not None
        self._ui.ip_port_row.set_visible(visible)
        self._ui.ip_port_row.set_subtitle(nbxmpp_client.remote_address or "")

        visible = address.uri is not None
        self._ui.websocket_row.set_visible(visible)
        self._ui.websocket_row.set_subtitle(address.uri or "")

        self._ui.connection_type_row.set_subtitle(address.type.value)
        if address.type.is_plain:
            self._ui.connection_type_row.add_css_class("error")

        assert nbxmpp_client is not None
        assert nbxmpp_client.tls_version is not None
        tls_version = TLS_VERSION_STRINGS.get(nbxmpp_client.tls_version)
        self._ui.tls_version_row.set_subtitle(tls_version or _("Not available"))

        self._ui.cipher_suite_row.set_subtitle(
            nbxmpp_client.ciphersuite or _("Not available")
        )

        # Connection proxy
        proxy = address.proxy
        if proxy is not None:
            self._ui.proxy_type_row.set_subtitle(proxy.type)
            self._ui.proxy_host_row.set_subtitle(proxy.host or "-")

    def _add_contact_addresses(self, dataforms: list[DataForm]) -> None:
        fields = {
            "admin-addresses": _("Admin"),
            "status-addresses": _("Status"),
            "support-addresses": _("Support"),
            "security-addresses": _("Security"),
            "feedback-addresses": _("Feedback"),
            "abuse-addresses": _("Abuse"),
            "sales-addresses": _("Sales"),
        }

        addresses = self._get_addresses(fields, dataforms)
        if addresses is None:
            return

        for address_type, values in addresses.items():
            contact_address_row = Adw.ActionRow(title=fields[address_type])
            contact_address_row.add_css_class("property")

            addresses_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, spacing=2
            )
            addresses_box.add_css_class("p-6")
            for value in values:
                label = self._get_address_label(value)
                addresses_box.append(label)

            contact_address_row.add_suffix(addresses_box)

            self._ui.contact_addresses_listbox.append(contact_address_row)

    @staticmethod
    def _get_addresses(
        fields: dict[str, str], dataforms: list[DataForm]
    ) -> dict[str, list[str]] | None:
        addresses: dict[str, list[str]] = {}
        for form in dataforms:
            field = form.vars.get("FORM_TYPE")
            if field.value != "http://jabber.org/network/serverinfo":
                continue

            for address_type in fields:
                field = form.vars.get(address_type)
                if field is None:
                    continue

                if field.type_ != "list-multi":
                    continue

                if not field.values:
                    continue
                addresses[address_type] = field.values

            return addresses or None
        return None

    def _get_address_label(self, address: str) -> Gtk.Label:
        label = Gtk.Label()
        label.set_markup(f'<a href="{address}">{address}</a>')
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_xalign(1)
        label.set_halign(Gtk.Align.END)
        label.add_css_class("link-button")
        label.add_css_class("small-label")
        self._connect(label, "activate-link", self._on_activate_link)
        return label

    def _on_activate_link(self, label: Gtk.Label, *args: Any) -> int:
        open_uri(label.get_text())
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
        uptime = _("%(days)s days, %(hours)s hours") % {
            "days": delta.days,
            "hours": hours,
        }
        self._ui.server_uptime_row.set_subtitle(uptime)

    def _software_version_received(self, task: Task) -> None:
        try:
            result = cast(SoftwareVersionResult, task.finish())
        except StanzaError:
            self._version = _("Unknown")
        else:
            self._version = f"{result.name} {result.version}"

        self._ui.server_software_row.set_subtitle(self._version)

    def _server_disco_received(self, _event: ServerDiscoReceived) -> None:
        features = self._get_features()
        for index, item in enumerate(features):
            row = cast(FeatureItem, self._ui.features_listbox.get_row_at_index(index))
            row.update(item)

    def _add_feature(self, feature: Feature) -> None:
        item = FeatureItem(feature)
        self._ui.features_listbox.append(item)

    def _get_features(self) -> list[Feature]:
        http_upload_module = self._client.get_module("HTTPUpload")
        http_upload_info = http_upload_module.httpupload_namespace
        if http_upload_module.available:
            max_size = http_upload_module.max_file_size
            if max_size is not None:
                max_size = GLib.format_size_full(int(max_size), self._units)
                http_upload_info = f"{http_upload_info} (max. {max_size})"

        assert self._client.features is not None

        return [
            Feature(
                "XEP-0045: Multi-User Chat", self._client.get_module("MUC").supported
            ),
            Feature(
                "XEP-0054: vcard-temp", self._client.get_module("VCardTemp").supported
            ),
            Feature(
                "XEP-0077: In-Band Registration",
                self._client.get_module("Register").supported,
            ),
            Feature(
                "XEP-0163: Personal Eventing Protocol",
                self._client.get_module("PEP").supported,
            ),
            Feature(
                "XEP-0163: #publish-options",
                self._client.get_module("PubSub").publish_options,
            ),
            Feature(
                "XEP-0191: Blocking Command",
                self._client.get_module("Blocking").supported,
                Namespace.BLOCKING,
            ),
            Feature(
                "XEP-0198: Stream Management",
                self._client.features.has_sm(),
                Namespace.STREAM_MGMT,
            ),
            Feature(
                "XEP-0258: Security Labels in XMPP",
                self._client.get_module("SecLabels").supported,
                Namespace.SECLABEL,
            ),
            Feature(
                "XEP-0280: Message Carbons",
                self._client.get_module("Carbons").supported,
                Namespace.CARBONS,
            ),
            Feature(
                "XEP-0313: Message Archive Management",
                self._client.get_module("MAM").available,
            ),
            Feature(
                "XEP-0363: HTTP File Upload",
                self._client.get_module("HTTPUpload").available,
                http_upload_info,
            ),
            Feature(
                "XEP-0398: Avatar Conversion",
                self._client.get_module("VCardAvatars").avatar_conversion_available,
            ),
            Feature(
                "XEP-0411: Bookmarks Conversion",
                self._client.get_module("Bookmarks").conversion,
            ),
            Feature(
                "XEP-0402: Bookmarks Compat",
                self._client.get_module("Bookmarks").compat,
            ),
            Feature(
                "XEP-0402: Bookmarks Compat PEP",
                self._client.get_module("Bookmarks").compat_pep,
            ),
        ]

    def _on_clipboard_button_clicked(self, _widget: Gtk.Button) -> None:
        server_software = _("Server Software: %s\n") % self._version
        server_features = ""

        for feature in self._get_features():
            if feature.available:
                available = _("Available")
            else:
                available = _("Not available")
            additional = ""
            if feature.additional is not None:
                additional = f"({feature.additional})"
            server_features += f"{feature.name}: {available} {additional}\n"

        self.window.get_clipboard().set(server_software + server_features)


class FeatureItem(Adw.ActionRow):
    def __init__(self, feature: Feature) -> None:
        Adw.ActionRow.__init__(self)
        self._feature = feature

        self._icon = Gtk.Image()
        self.add_prefix(self._icon)
        self._update()

    def _update(self) -> None:
        self.set_title(self._feature.name)
        self.set_subtitle(self._feature.additional or "")

        self._icon.remove_css_class("error")
        self._icon.remove_css_class("success")

        if self._feature.available:
            self._icon.set_from_icon_name("feather-check-symbolic")
            self._icon.add_css_class("success")
        else:
            self._icon.set_from_icon_name("window-close-symbolic")
            self._icon.add_css_class("error")

    def update(self, feature: Feature) -> None:
        self._feature = feature
        self._update()
