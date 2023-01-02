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

from cryptography.hazmat.primitives import hashes
from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import Gtk

from gajim.common import app
from gajim.common.helpers import get_x509_cert_from_gio_cert
from gajim.common.i18n import _

from .builder import get_builder


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
        self._it_org_unit = ''
        for attribute in cert.subject:
            # See https://datatracker.ietf.org/doc/html/rfc4514.html
            dotted_string = attribute.oid.dotted_string
            if dotted_string == '2.5.4.3':
                self._ib_common_name = str(attribute.value)
            if dotted_string == '2.5.4.10':
                self._ib_organization = str(attribute.value)
            if dotted_string == '2.5.4.11':
                self._ib_org_unit = str(attribute.value)

        it_serial_no = str(cert.serial_number)
        it_serial_no_half = int(len(it_serial_no) / 2)
        self._it_serial_number = '%s\n%s' % (
            it_serial_no[:it_serial_no_half],
            it_serial_no[it_serial_no_half:])

        self._ib_common_name = ''
        self._ib_organization = ''
        self._ib_org_unit = ''
        for attribute in cert.issuer:
            # See https://datatracker.ietf.org/doc/html/rfc4514.html
            dotted_string = attribute.oid.dotted_string
            if dotted_string == '2.5.4.3':
                self._ib_common_name = str(attribute.value)
            if dotted_string == '2.5.4.10':
                self._ib_organization = str(attribute.value)
            if dotted_string == '2.5.4.11':
                self._ib_org_unit = str(attribute.value)

        self._issued = cert.not_valid_before.strftime('%c %Z')
        self._expires = cert.not_valid_after.strftime('%c %Z')

        sha1_bytes = cert.fingerprint(hashes.SHA1())
        sha1 = ':'.join(f'{b:02X}' for b in sha1_bytes)
        self._sha1 = '%s\n%s' % (sha1[:29], sha1[30:])

        sha256_bytes = cert.fingerprint(hashes.SHA256())
        sha256 = ':'.join(f'{b:02X}' for b in sha256_bytes)
        self._sha256 = '%s\n%s\n%s\n%s' % (
            sha256[:23], sha256[24:47], sha256[48:71], sha256[72:])

        self._ui.label_cert_for_account.set_text(self._headline)
        self._ui.data_it_common_name.set_text(self._it_common_name)
        self._ui.data_it_organization.set_text(self._it_organization)
        self._ui.data_it_organizational_unit.set_text(self._it_org_unit)
        self._ui.data_it_serial_number.set_text(self._it_serial_number)
        self._ui.data_ib_common_name.set_text(self._ib_common_name)
        self._ui.data_ib_organization.set_text(self._ib_organization)
        self._ui.data_ib_organizational_unit.set_text(self._ib_org_unit)
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
            _('Organizational Unit (OU): ') + self._it_org_unit + '\n' + \
            _('Serial Number: ') + self._it_serial_number + '\n\n' + \
            _('Issued by\n') + \
            _('Common Name (CN): ') + self._ib_common_name + '\n' + \
            _('Organization (O): ') + self._ib_organization + '\n' + \
            _('Organizational Unit (OU): ') + self._ib_org_unit + '\n\n' + \
            _('Validity\n') + \
            _('Issued on: ') + self._issued + '\n' + \
            _('Expires on: ') + self._expires + '\n\n' + \
            _('SHA-1:') + '\n' + \
            self._sha1 + '\n' + \
            _('SHA-256:') + '\n' + \
            self._sha256 + '\n'

        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(clipboard_text, -1)
