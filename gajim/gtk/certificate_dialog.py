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

from typing import cast

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.dsa import DSAPublicKey
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicKey
from cryptography.hazmat.primitives.asymmetric.ed448 import Ed448PublicKey
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.x509 import DNSName
from cryptography.x509.oid import ExtensionOID
from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import Gtk

from gajim.common import app
from gajim.common.helpers import get_x509_cert_from_gio_cert
from gajim.common.i18n import _
from gajim.common.util.text import format_sha_bytes

from gajim.gtk.builder import get_builder


class CertificateDialog(Gtk.ApplicationWindow):
    def __init__(self,
                 transient_for: Gtk.Window,
                 account: str,
                 cert: Gio.TlsCertificate
                 ) -> None:

        Gtk.ApplicationWindow.__init__(self)
        self.account = account
        self.set_name('CertificateDialog')
        self.set_application(app.app)
        self.set_show_menubar(False)
        self.set_resizable(True)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_title(_('Certificate'))

        self.add(CertificateBox(account, cert))

        self.connect('key-press-event', self._on_key_press)

        self.set_transient_for(transient_for)
        self.show_all()

    def _on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> None:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()


class CertificateBox(Gtk.Box):
    def __init__(self, account: str, certificate: Gio.TlsCertificate) -> None:
        Gtk.Box.__init__(self)

        self._ui = get_builder('certificate.ui')
        self._headline = _('Certificate for \n%s') % account

        cert = get_x509_cert_from_gio_cert(certificate)

        self._it_common_name = ''
        self._it_organization = ''
        for attribute in cert.subject:
            # See https://datatracker.ietf.org/doc/html/rfc4514.html
            dotted_string = attribute.oid.dotted_string
            if dotted_string == '2.5.4.3':
                self._it_common_name = str(attribute.value)
            if dotted_string == '2.5.4.10':
                self._it_organization = str(attribute.value)

        # Get the subjectAltName extension from the certificate
        subject_ext = cert.extensions.get_extension_for_oid(
            ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
        # Get the DNSName entries from the SAN extension
        alt_names = cast(
            list[str],
            subject_ext.value.get_values_for_type(DNSName))  # pyright: ignore
        self._it_subject_alt_names = '\n'.join(alt_names)

        serial_str = '0{:02X}'.format(cert.serial_number)
        serial_str_foratted = ':'.join(
            map('{}{}'.format, *(serial_str[::2], serial_str[1::2])))
        self._it_serial_number = serial_str_foratted

        self._ib_common_name = ''
        self._ib_organization = ''
        for attribute in cert.issuer:
            # See https://datatracker.ietf.org/doc/html/rfc4514.html
            dotted_string = attribute.oid.dotted_string
            if dotted_string == '2.5.4.3':
                self._ib_common_name = str(attribute.value)
            if dotted_string == '2.5.4.10':
                self._ib_organization = str(attribute.value)

        self._issued = cert.not_valid_before.strftime('%c %Z')
        self._expires = cert.not_valid_after.strftime('%c %Z')

        sha1_bytes = cert.fingerprint(hashes.SHA1())
        self._sha1 = format_sha_bytes('sha1', sha1_bytes)

        sha256_bytes = cert.fingerprint(hashes.SHA256())
        self._sha256 = format_sha_bytes('sha256', sha256_bytes)

        public_key = cert.public_key()
        self._pk_algorithm = ''
        if isinstance(public_key, RSAPublicKey):
            self._pk_algorithm = 'RSA'
        elif isinstance(public_key, DSAPublicKey):
            self._pk_algorithm = 'DSA'
        elif isinstance(public_key, EllipticCurvePublicKey):
            self._pk_algorithm = 'Elliptic Curve'
        elif isinstance(public_key, Ed25519PublicKey):
            self._pk_algorithm = 'ED25519'
        elif isinstance(public_key, Ed448PublicKey):
            self._pk_algorithm = 'ED448'

        self._pk_size = _('Unknown')
        if isinstance(public_key,
                      RSAPublicKey | DSAPublicKey | EllipticCurvePublicKey):
            self._pk_size = f'{public_key.key_size} Bit'

        self._ui.public_key_algorithm.set_text(self._pk_algorithm)
        self._ui.public_key_size.set_text(self._pk_size)

        self._ui.label_cert_for_account.set_text(self._headline)
        self._ui.data_it_common_name.set_text(self._it_common_name)
        self._ui.data_it_organization.set_text(self._it_organization)
        self._ui.data_it_subject_alt_names.set_text(
            self._it_subject_alt_names)
        self._ui.data_it_serial_number.set_text(self._it_serial_number)
        self._ui.data_ib_common_name.set_text(self._ib_common_name)
        self._ui.data_ib_organization.set_text(self._ib_organization)
        self._ui.data_issued_on.set_text(self._issued)
        self._ui.data_expires_on.set_text(self._expires)
        self._ui.data_sha1.set_text(self._sha1)
        self._ui.data_sha256.set_text(self._sha256)

        self.add(self._ui.certificate_box)

        self._ui.connect_signals(self)

    def _on_copy_cert_info_button_clicked(self, _widget: Gtk.Button) -> None:
        clipboard_text = \
            self._headline + '\n\n' + \
            _('Issued to\n') + \
            _('Common Name (CN): ') + self._it_common_name + '\n' + \
            _('Organization (O): ') + self._it_organization + '\n' + \
            _('Subject Alt Names: ') + self._it_subject_alt_names + '\n' + \
            _('Serial Number: ') + self._it_serial_number + '\n\n' + \
            _('Issued by\n') + \
            _('Common Name (CN): ') + self._ib_common_name + '\n' + \
            _('Organization (O): ') + self._ib_organization + '\n' + \
            _('Validity\n') + \
            _('Issued on: ') + self._issued + '\n' + \
            _('Expires on: ') + self._expires + '\n\n' + \
            _('SHA-1:') + '\n' + \
            self._sha1 + '\n' + \
            _('SHA-256:') + '\n' + \
            self._sha256 + '\n\n' + \
            _('Public Key: ') + self._pk_algorithm + ' ' + self._pk_size

        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(clipboard_text, -1)
