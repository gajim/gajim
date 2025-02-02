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
from gi.repository import Gio
from gi.repository import Gtk

from gajim.common import app
from gajim.common.helpers import get_x509_cert_from_gio_cert
from gajim.common.i18n import _
from gajim.common.util.text import format_bytes_as_hex
from gajim.common.util.version import package_version

from gajim.gtk.builder import get_builder
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.widgets import GajimAppWindow

log = logging.getLogger("gajim.gtk.certificate_dialog")


class CertificateDialog(GajimAppWindow):
    def __init__(
        self, transient_for: Gtk.Window | None, account: str, cert: Gio.TlsCertificate
    ) -> None:

        GajimAppWindow.__init__(
            self,
            name="CertificateDialog",
            title=_("Certificate"),
            transient_for=transient_for,
        )

        self.account = account

        self.set_child(CertificateBox(account, cert))

    def _cleanup(self) -> None:
        pass


class CertificateBox(Gtk.Box, SignalManager):
    def __init__(self, account: str, certificate: Gio.TlsCertificate) -> None:
        Gtk.Box.__init__(self)
        SignalManager.__init__(self)

        self._ui = get_builder("certificate.ui")
        self._headline = _("Certificate for \n%s") % account
        self.set_size_request(500, -1)

        self._connect(self._ui.copy_button, "clicked", self._on_copy_button_clicked)

        cert = get_x509_cert_from_gio_cert(certificate)

        self._it_common_name = ""
        self._it_organization = ""
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
            self._it_subject_alt_names = ""

        serial_bytes = format_bytes_as_hex(int_to_bytes(cert.serial_number), 2)
        self._it_serial_number = serial_bytes

        self._ib_common_name = ""
        self._ib_organization = ""
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
        self._pk_algorithm = ""
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

        self._ui.public_key_algorithm.set_text(self._pk_algorithm)
        self._ui.public_key_size.set_text(self._pk_size)

        self._ui.label_cert_for_account.set_text(self._headline)
        self._ui.data_it_common_name.set_text(self._it_common_name)
        self._ui.data_it_organization.set_text(self._it_organization)
        self._ui.data_it_subject_alt_names.set_text(self._it_subject_alt_names)
        self._ui.data_it_serial_number.set_text(self._it_serial_number)
        self._ui.data_ib_common_name.set_text(self._ib_common_name)
        self._ui.data_ib_organization.set_text(self._ib_organization)
        self._ui.data_issued_on.set_text(self._issued)
        self._ui.data_expires_on.set_text(self._expires)
        self._ui.data_sha1.set_text(self._sha1)
        self._ui.data_sha256.set_text(self._sha256)

        self.append(self._ui.certificate_box)

    def do_unroot(self) -> None:
        self._disconnect_all()
        Gtk.Box.do_unroot(self)
        app.check_finalize(self)

    def _on_copy_button_clicked(self, _widget: Gtk.Button) -> None:
        clipboard_text = (
            self._headline
            + "\n\n"
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

        self.get_clipboard().set(clipboard_text)
