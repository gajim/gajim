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


from gi.repository import Gtk
from gi.repository import Gio

from gajim.common import app

from gajim.common.const import GIO_TLS_ERRORS
from gajim.common.i18n import _

from gajim.gtk.util import get_builder
from gajim.gtk.util import open_window


class SSLErrorDialog(Gtk.ApplicationWindow):
    def __init__(self, account, connection, cert, error_num):
        Gtk.ApplicationWindow.__init__(self)
        self.set_name('SSLErrorDialog')
        self.set_application(app.app)
        self.set_show_menubar(False)
        self.set_resizable(False)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_title(_('SSL Certificate Verification Error'))

        self._ui = get_builder('ssl_error_dialog.ui')
        self.add(self._ui.ssl_error_box)

        self.account = account
        self._error_num = error_num
        self._con = connection
        self._cert = cert
        self._server = app.config.get_per('accounts', self.account, 'hostname')

        self._process_error()

        self._ui.connect_signals(self)
        self.show_all()

    def _process_error(self):
        self._ui.intro_text.set_text(
            _('There was an error while attempting to verify the SSL '
              'certificate of your XMPP server (%s).') % self._server)

        unknown_error = _('Unknown SSL error \'%s\'') % self._error_num
        ssl_error = GIO_TLS_ERRORS.get(self._error_num, unknown_error)
        self._ui.ssl_error.set_text(ssl_error)

        if self._error_num == Gio.TlsCertificateFlags.UNKNOWN_CA:
            self._ui.add_certificate_checkbutton.show()

    def _on_view_cert_clicked(self, _button):
        open_window('CertificateDialog',
                    account=self.account,
                    transient_for=self,
                    cert=self._cert)

    def _on_connect_clicked(self, _button):
        # Ignore this error
        if self._ui.ignore_error_checkbutton.get_active():
            ignore_ssl_errors = app.config.get_per(
                'accounts', self.account, 'ignore_ssl_errors').split()
            ignore_ssl_errors.append(str(int(self._error_num)))
            app.config.set_per('accounts', self.account, 'ignore_ssl_errors',
                               ' '.join(ignore_ssl_errors))

        if self._ui.add_certificate_checkbutton.get_active():
            app.cert_store.add_certificate(self._cert)

        self.destroy()
        self._con.process_tls_errors()
