# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast

import logging
from datetime import timedelta

from gi.repository import Adw
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.modules.dataforms import MultipleDataForm
from nbxmpp.modules.dataforms import SimpleDataForm
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import LastActivityData
from nbxmpp.structs import SoftwareVersionResult
from nbxmpp.task import Task

from gajim.common import app
from gajim.common.i18n import _

from gajim.gtk.const import SettingType
from gajim.gtk.preference.widgets import CopyButton
from gajim.gtk.preference.widgets import PlaceholderBox
from gajim.gtk.settings import GajimPreferencePage
from gajim.gtk.settings import GajimPreferencesGroup
from gajim.gtk.settings import SubPageSetting
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import get_ui_string
from gajim.gtk.util.misc import open_uri

log = logging.getLogger("gajim.gtk.preference.server_info")


@Gtk.Template.from_string(string=get_ui_string("preference/provider_info.ui"))
class AccountProviderInfoGroup(Adw.PreferencesGroup, SignalManager):
    __gtype_name__ = "AccountProviderInfoGroup"

    _clipboard_button: CopyButton = Gtk.Template.Child()
    _hostname_row: Adw.ActionRow = Gtk.Template.Child()
    _software_row: Adw.ActionRow = Gtk.Template.Child()
    _uptime_row: Adw.ActionRow = Gtk.Template.Child()

    def __init__(self, account: str) -> None:
        Adw.PreferencesGroup.__init__(self)
        SignalManager.__init__(self)

        self._hostname = app.get_hostname_from_account(account, prefer_custom=True)
        self._software = ""
        self._uptime = ""

        self._hostname_row.set_subtitle(self._hostname)

        client = app.get_client(account)
        domain = client.get_own_jid().domain
        client.get_module("SoftwareVersion").request_software_version(
            domain, callback=self._software_version_received
        )

        client.get_module("LastActivity").request_last_activity(
            domain, callback=self._on_last_activity
        )

        self.add(
            SubPageSetting(
                account,
                None,
                _("Contacts"),
                SettingType.DIALOG,
                None,
                None,
                subpage=f"{account}-provider-contacts",
            )
        )

        self._connect(
            self._clipboard_button, "clicked", self._on_clipboard_button_clicked
        )

    def _on_clipboard_button_clicked(self, _widget: Gtk.Button) -> None:
        string = _(
            "Hostname: %(hostname)s\nSoftware: %(software)s\nUptime: %(uptime)s\n"
        )

        app.window.get_clipboard().set(
            string
            % {
                "hostname": self._hostname,
                "software": self._software,
                "uptime": self._uptime,
            }
        )

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
        self._uptime = _("%(days)s days, %(hours)s hours") % {
            "days": delta.days,
            "hours": hours,
        }
        self._uptime_row.set_subtitle(self._uptime)

    def _software_version_received(self, task: Task) -> None:
        try:
            result = cast(SoftwareVersionResult, task.finish())
        except StanzaError:
            self._software = _("Unknown")
        else:
            self._software = f"{result.name} {result.version}"

        self._software_row.set_subtitle(self._software)

    def do_unroot(self) -> None:
        self._disconnect_all()
        Adw.PreferencesGroup.do_unroot(self)


class AccountProviderContactsGroup(GajimPreferencesGroup):
    def __init__(self, account: str) -> None:
        GajimPreferencesGroup.__init__(
            self,
            key=f"{account}-provider-contacts",
            account=account,
            title=_("Contacts"),
        )

        client = app.get_client(account)
        server_info = client.get_module("Discovery").server_info
        if server_info is None:
            return

        self._add_contact_addresses(server_info.dataforms)

    def _add_contact_addresses(
        self, dataforms: list[SimpleDataForm | MultipleDataForm]
    ) -> None:
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
            label = Gtk.Label(
                label=_("No contact addresses published for this server."),
                wrap=True,
                max_width_chars=50,
            )
            label.add_css_class("dimmed")
            label.add_css_class("p-18")
            self.add(label)
            return

        for address_type, values in addresses.items():
            contact_address_row = Adw.ActionRow(title=fields[address_type])

            addresses_box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, spacing=2
            )
            addresses_box.add_css_class("p-6")
            for value in values:
                label = self._get_address_label(value)
                addresses_box.append(label)

            contact_address_row.add_suffix(addresses_box)

            self.add(contact_address_row)

    @staticmethod
    def _get_addresses(
        fields: dict[str, str], dataforms: list[SimpleDataForm | MultipleDataForm]
    ) -> dict[str, list[str]] | None:
        addresses: dict[str, list[str]] = {}
        for form in dataforms:
            if not isinstance(form, SimpleDataForm):
                continue

            field = form.vars.get("FORM_TYPE")
            if field is None or field.value != "http://jabber.org/network/serverinfo":
                continue

            for address_type in fields:
                field = form.vars.get(address_type)
                if field is None:
                    continue

                if field.type_ != "list-multi":
                    continue

                if not field.values:
                    continue
                addresses[address_type] = cast(list[str], field.values)

            return addresses or None
        return None

    def _get_address_label(self, address: str) -> Gtk.Label:
        label = Gtk.Label(
            ellipsize=Pango.EllipsizeMode.END,
            halign=Gtk.Align.END,
            label=f'<a href="{address}">{address}</a>',
            use_markup=True,
            xalign=1,
        )

        label.add_css_class("link-button")
        label.add_css_class("small-label")
        self._connect(label, "activate-link", self._on_activate_link)
        return label

    def _on_activate_link(self, label: Gtk.Label, *args: Any) -> int:
        open_uri(label.get_text())
        return Gdk.EVENT_STOP


class AccountProviderFeaturesGroup(GajimPreferencesGroup):
    def __init__(self, account: str) -> None:
        GajimPreferencesGroup.__init__(
            self,
            key=f"{account}-provider-features",
            account=account,
            title=_("Features"),
            description=_("Your service offers the following features"),
        )

        if app.settings.get("use_kib_mib"):
            self._units = GLib.FormatSizeFlags.IEC_UNITS
        else:
            self._units = GLib.FormatSizeFlags.DEFAULT

        self._add_features()
        self.add_copy_button()

    def do_unroot(self) -> None:
        GajimPreferencesGroup.do_unroot(self)
        self._features.clear()

    def _get_clipboard_text(self) -> str:
        string = ""
        for feature in self._features:
            string += feature.get_clipboard_text()
        return string

    def _add_features(self) -> None:
        assert self.account is not None
        client = app.get_client(self.account)

        http_upload_module = client.get_module("HTTPUpload")
        http_upload_info = http_upload_module.httpupload_namespace
        if http_upload_module.available:
            max_size = http_upload_module.max_file_size
            if max_size is not None:
                max_size = GLib.format_size_full(int(max_size), self._units)
                http_upload_info = f"{http_upload_info} (max. {max_size})"

        assert client.features is not None

        self._features = [
            FeatureRow("XEP-0045: Multi-User Chat", client.get_module("MUC").supported),
            FeatureRow(
                "XEP-0054: vcard-temp", client.get_module("VCardTemp").supported
            ),
            FeatureRow(
                "XEP-0077: In-Band Registration",
                client.get_module("Register").supported,
            ),
            FeatureRow(
                "XEP-0163: Personal Eventing Protocol",
                client.get_module("PEP").supported,
            ),
            FeatureRow(
                "XEP-0163: #publish-options",
                client.get_module("PubSub").publish_options,
            ),
            FeatureRow(
                "XEP-0191: Blocking Command",
                client.get_module("Blocking").supported,
                Namespace.BLOCKING,
            ),
            FeatureRow(
                "XEP-0198: Stream Management",
                client.features.has_sm(),
                Namespace.STREAM_MGMT,
            ),
            FeatureRow(
                "XEP-0258: Security Labels in XMPP",
                client.get_module("SecLabels").supported,
                Namespace.SECLABEL,
            ),
            FeatureRow(
                "XEP-0280: Message Carbons",
                client.get_module("Carbons").supported,
                Namespace.CARBONS,
            ),
            FeatureRow(
                "XEP-0313: Message Archive Management",
                client.get_module("MAM").available,
            ),
            FeatureRow(
                "XEP-0363: HTTP File Upload",
                client.get_module("HTTPUpload").available,
                http_upload_info,
            ),
            FeatureRow(
                "XEP-0398: Avatar Conversion",
                client.get_module("VCardAvatars").avatar_conversion_available,
            ),
            FeatureRow(
                "XEP-0411: Bookmarks Conversion",
                client.get_module("Bookmarks").conversion,
            ),
            FeatureRow(
                "XEP-0402: Bookmarks Compat",
                client.get_module("Bookmarks").compat,
            ),
            FeatureRow(
                "XEP-0402: Bookmarks Compat PEP",
                client.get_module("Bookmarks").compat_pep,
            ),
        ]

        for feature in self._features:
            self.add(feature)


class FeatureRow(Adw.ActionRow):
    def __init__(
        self, name: str, available: bool, additional: str | None = None
    ) -> None:
        Adw.ActionRow.__init__(self)

        self.set_title(name)
        self.set_subtitle(additional or "")

        self._available = available

        self._icon = Gtk.Image()
        self.add_prefix(self._icon)

        if available:
            self._icon.set_from_icon_name("lucide-check-symbolic")
            self._icon.add_css_class("success")
        else:
            self._icon.set_from_icon_name("lucide-x-symbolic")
            self._icon.add_css_class("error")

    def get_clipboard_text(self) -> str:
        if self._available:
            available = _("Available")
        else:
            available = _("Not available")

        string = f"{self.get_title()}: {available}"

        if additional := self.get_subtitle():
            string += f" ({additional})"

        return f"{string}\n"


class AccountProviderContactsPage(GajimPreferencePage):
    key = "provider-contacts"

    def __init__(self, account: str) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("Provider Contacts - %(account)s") % {"account": account},
            groups=[],
            tag_prefix=f"{account}-",
        )

        if not app.account_is_available(account):
            self.set_content(PlaceholderBox(valign=Gtk.Align.CENTER))
            return

        self.add(AccountProviderContactsGroup(account))


class AccountProviderPage(GajimPreferencePage):
    key = "provider"
    icon_name = "lucide-server-symbolic"
    label = _("Service Provider")

    def __init__(self, account: str) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("Provider - %(account)s") % {"account": account},
            groups=[],
            tag_prefix=f"{account}-",
        )

        if not app.account_is_available(account):
            self.set_content(PlaceholderBox(valign=Gtk.Align.CENTER))
            return

        self.add(AccountProviderInfoGroup(account))
        self.add(AccountProviderFeaturesGroup(account))
