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

import os

from OpenSSL import crypto

from gi.repository import Gtk

from gajim.common import app
from gajim.common import configpaths
from gajim.common.const import SSLError
from gajim.common.connection_handlers_events import OurShowEvent
from gajim.common.i18n import _

from gajim.gtk.dialogs import CertificateDialog
from gajim.gtk.util import get_builder


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
        ssl_error = SSLError.get(self._error_num, unknown_error)
        self._ui.ssl_error.set_text(ssl_error)

        if self._error_num in (18, 27):
            # Errors: 18 Self signed certificate; 27 Certificate not trusted
            self._ui.add_certificate_checkbutton.show()

    def _on_abort_clicked(self, _button):
        self._con.disconnect(reconnect=False)
        app.nec.push_incoming_event(OurShowEvent(None, conn=self._con,
                                                 show='offline'))
        self.destroy()

    def _on_view_cert_clicked(self, _button):
        window = app.get_app_window(CertificateDialog, self.account)
        if window is None:
            CertificateDialog(self, self.account, self._cert)
        else:
            window.present()

    def _on_connect_clicked(self, _button):
        # Ignore this error
        if self._ui.ignore_error_checkbutton.get_active():
            ignore_ssl_errors = app.config.get_per(
                'accounts', self.account, 'ignore_ssl_errors').split()
            ignore_ssl_errors.append(str(self._error_num))
            app.config.set_per('accounts', self.account, 'ignore_ssl_errors',
                               ' '.join(ignore_ssl_errors))

        if self._ui.add_certificate_checkbutton.get_active():
            pem = crypto.dump_certificate(
                crypto.FILETYPE_PEM, self._cert).decode('utf-8')

            # Check if cert is already in file
            certs = ''
            my_ca_certs = configpaths.get('MY_CACERTS')
            if os.path.isfile(my_ca_certs):
                with open(my_ca_certs, encoding='utf-8') as f:
                    certs = f.read()
            if pem not in certs:
                with open(my_ca_certs, 'a', encoding='utf-8') as f:
                    f.write(self._server + '\n')
                    f.write(pem + '\n\n')

        self._con.process_ssl_errors()
        self.destroy()
