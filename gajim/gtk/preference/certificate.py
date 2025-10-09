# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import cast

import logging

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.dsa import DSAPublicKey
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicKey
from cryptography.hazmat.primitives.asymmetric.ed448 import Ed448PublicKey
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.utils import int_to_bytes
from cryptography.x509 import DNSName
from cryptography.x509 import ExtensionNotFound
from cryptography.x509.oid import ExtensionOID
from gi.repository import Adw
from gi.repository import Gio
from gi.repository import Gtk

from gajim.common import app
from gajim.common.helpers import get_x509_cert_from_gio_cert
from gajim.common.i18n import _
from gajim.common.util.text import format_bytes_as_hex
from gajim.common.util.version import package_version

from gajim.gtk.preference.widgets import CopyButton
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import get_ui_string

log = logging.getLogger("gajim.gtk.preferences.certificate")


@Gtk.Template.from_string(string=get_ui_string("preference/certificate.ui"))
class CertificatePage(Adw.PreferencesPage, SignalManager):

    __gtype_name__ = "CertificatePage"

    _clipboard_button: CopyButton = Gtk.Template.Child()
    _account_label_row: Adw.ActionRow = Gtk.Template.Child()
    _account_address_row: Adw.ActionRow = Gtk.Template.Child()
    _issued_to_common_name_row: Adw.ActionRow = Gtk.Template.Child()
    _issued_to_organization_row: Adw.ActionRow = Gtk.Template.Child()
    _issued_to_subject_alt_names_row: Adw.ActionRow = Gtk.Template.Child()
    _issued_to_serial_number_row: Adw.ActionRow = Gtk.Template.Child()
    _issued_by_common_name_row: Adw.ActionRow = Gtk.Template.Child()
    _issued_by_organization_row: Adw.ActionRow = Gtk.Template.Child()
    _issue_date_row: Adw.ActionRow = Gtk.Template.Child()
    _expiry_date_row: Adw.ActionRow = Gtk.Template.Child()
    _fingerprint_sha1_row: Adw.ActionRow = Gtk.Template.Child()
    _fingerprint_sha256_row: Adw.ActionRow = Gtk.Template.Child()
    _algorithm_row: Adw.ActionRow = Gtk.Template.Child()
    _key_size_row: Adw.ActionRow = Gtk.Template.Child()

    def __init__(self, account: str | None, certificate: Gio.TlsCertificate) -> None:
        Adw.PreferencesPage.__init__(self)
        SignalManager.__init__(self)

        self._connect(self._clipboard_button, "clicked", self._on_copy_button_clicked)

        self._account_label = ""
        self._account_address = ""
        if account is not None:
            self._account_label = app.settings.get_account_setting(
                account, "account_label"
            )
            self._account_address = app.settings.get_account_setting(account, "address")

        cert = get_x509_cert_from_gio_cert(certificate)

        self._it_common_name = "-"
        self._it_organization = "-"
        for attribute in cert.subject:
            # See https://datatracker.ietf.org/doc/html/rfc4514.html
            dotted_string = attribute.oid.dotted_string
            if dotted_string == "2.5.4.3":
                self._it_common_name = str(attribute.value)
            if dotted_string == "2.5.4.10":
                self._it_organization = str(attribute.value)

        # Get the subjectAltName extension from the certificate
        try:
            subject_ext = cert.extensions.get_extension_for_oid(
                ExtensionOID.SUBJECT_ALTERNATIVE_NAME
            )
            # Get the DNSName entries from the SAN extension
            alt_names = cast(
                list[str],
                subject_ext.value.get_values_for_type(DNSName),  # pyright: ignore
            )
            self._it_subject_alt_names = "\n".join(alt_names)
        except ExtensionNotFound as err:
            log.info("Certificate does not have extension: %s", err)
            self._it_subject_alt_names = "-"

        serial_bytes = format_bytes_as_hex(int_to_bytes(cert.serial_number), 2)
        self._it_serial_number = serial_bytes

        self._ib_common_name = "-"
        self._ib_organization = "-"
        for attribute in cert.issuer:
            # See https://datatracker.ietf.org/doc/html/rfc4514.html
            dotted_string = attribute.oid.dotted_string
            if dotted_string == "2.5.4.3":
                self._ib_common_name = str(attribute.value)
            if dotted_string == "2.5.4.10":
                self._ib_organization = str(attribute.value)

        if package_version("cryptography>=42.0.0"):
            self._issued = str(cert.not_valid_before_utc.strftime("%c %Z"))
            self._expires = str(cert.not_valid_after_utc.strftime("%c %Z"))
        else:
            self._issued = str(cert.not_valid_before.strftime("%c %Z"))
            self._expires = str(cert.not_valid_after.strftime("%c %Z"))

        sha1_bytes = cert.fingerprint(hashes.SHA1())
        self._sha1 = format_bytes_as_hex(sha1_bytes, 2)

        sha256_bytes = cert.fingerprint(hashes.SHA256())
        self._sha256 = format_bytes_as_hex(sha256_bytes, 4)

        public_key = cert.public_key()
        self._pk_algorithm = "-"
        if isinstance(public_key, RSAPublicKey):
            self._pk_algorithm = "RSA"
        elif isinstance(public_key, DSAPublicKey):
            self._pk_algorithm = "DSA"
        elif isinstance(public_key, EllipticCurvePublicKey):
            self._pk_algorithm = "Elliptic Curve"
        elif isinstance(public_key, Ed25519PublicKey):
            self._pk_algorithm = "ED25519"
        elif isinstance(public_key, Ed448PublicKey):
            self._pk_algorithm = "ED448"

        self._pk_size = _("Unknown")
        if isinstance(public_key, RSAPublicKey | DSAPublicKey | EllipticCurvePublicKey):
            self._pk_size = f"{public_key.key_size} Bit"

        self._account_label_row.set_subtitle(self._account_label)
        self._account_address_row.set_subtitle(self._account_address)

        self._issued_to_common_name_row.set_subtitle(self._it_common_name)
        self._issued_to_organization_row.set_subtitle(self._it_organization)
        self._issued_to_subject_alt_names_row.set_subtitle(self._it_subject_alt_names)
        self._issued_to_serial_number_row.set_subtitle(self._it_serial_number)

        self._issued_by_common_name_row.set_subtitle(self._ib_common_name)
        self._issued_by_organization_row.set_subtitle(self._ib_organization)

        self._issue_date_row.set_subtitle(self._issued)
        self._expiry_date_row.set_subtitle(self._expires)

        self._fingerprint_sha1_row.set_subtitle(self._sha1)
        self._fingerprint_sha256_row.set_subtitle(self._sha256)

        self._algorithm_row.set_subtitle(self._pk_algorithm)
        self._key_size_row.set_subtitle(self._pk_size)

    def do_unroot(self) -> None:
        self._disconnect_all()
        Adw.PreferencesPage.do_unroot(self)
        app.check_finalize(self)

    def _on_copy_button_clicked(self, _widget: Gtk.Button) -> None:
        clipboard_text = (
            _("Certificate")
            + "\n"
            + _("Account name: ")
            + self._account_label
            + "\n"
            + _("Account address: ")
            + self._account_address
            + "\n"
            + _("Issued to\n")
            + _("Common Name (CN): ")
            + self._it_common_name
            + "\n"
            + _("Organization (O): ")
            + self._it_organization
            + "\n"
            + _("Subject Alt Names: ")
            + self._it_subject_alt_names
            + "\n"
            + _("Serial Number: ")
            + self._it_serial_number
            + "\n\n"
            + _("Issued by\n")
            + _("Common Name (CN): ")
            + self._ib_common_name
            + "\n"
            + _("Organization (O): ")
            + self._ib_organization
            + "\n"
            + _("Validity\n")
            + _("Issued on: ")
            + self._issued
            + "\n"
            + _("Expires on: ")
            + self._expires
            + "\n\n"
            + _("SHA-1:")
            + "\n"
            + self._sha1
            + "\n"
            + _("SHA-256:")
            + "\n"
            + self._sha256
            + "\n\n"
            + _("Public Key: ")
            + self._pk_algorithm
            + " "
            + self._pk_size
        )

        app.window.get_clipboard().set(clipboard_text)
