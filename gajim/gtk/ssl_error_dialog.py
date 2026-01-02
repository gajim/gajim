# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from gi.repository import Gio
from gi.repository import Gtk

from gajim.common import app
from gajim.common.client import Client
from gajim.common.const import GIO_TLS_ERRORS
from gajim.common.i18n import _

from gajim.gtk.builder import get_builder
from gajim.gtk.util.window import open_window
from gajim.gtk.window import GajimAppWindow


class SSLErrorDialog(GajimAppWindow):
    def __init__(
        self,
        account: str,
        client: Client,
        cert: Gio.TlsCertificate,
        ignored_errors: set[Gio.TlsCertificateFlags],
        error: Gio.TlsCertificateFlags,
    ) -> None:
        GajimAppWindow.__init__(
            self,
            name="SSLErrorDialog",
            title=_("SSL Certificate Verification Error"),
            add_window_padding=True,
            header_bar=True,
        )

        self._ui = get_builder("ssl_error_dialog.ui")
        self.set_child(self._ui.ssl_error_box)

        self._connect(
            self._ui.add_certificate_checkbutton,
            "toggled",
            self._on_add_certificate_toggled,
        )
        self._connect(self._ui.view_cert_button, "clicked", self._on_view_cert_clicked)
        self._connect(self._ui.connect_button, "clicked", self._on_connect_clicked)

        self.account = account
        self._error = error
        self._ignored_errors = ignored_errors
        self._client = client
        self._cert = cert
        self._server = app.get_hostname_from_account(self.account)

        self._process_error()

    def _cleanup(self) -> None:
        pass

    def _process_error(self) -> None:
        self._ui.intro_text.set_text(
            _(
                "There was an error while attempting to verify the SSL "
                "certificate of your XMPP server (%s)."
            )
            % self._server
        )

        unknown_error = _('Unknown SSL error "%s"') % self._error
        ssl_error = GIO_TLS_ERRORS.get(self._error, unknown_error)
        self._ui.ssl_error.set_text(ssl_error)

        if self._error == Gio.TlsCertificateFlags.UNKNOWN_CA:
            self._ui.add_certificate_checkbutton.set_visible(True)

        elif self._error == Gio.TlsCertificateFlags.EXPIRED:
            self._ui.connect_button.set_sensitive(True)

        else:
            self._ui.connect_button.set_visible(False)
            self._ui.connect_button.set_visible(False)

    def _on_view_cert_clicked(self, _button: Gtk.Button) -> None:
        open_window(
            "CertificateDialog",
            account=self.account,
            transient_for=self,
            cert=self._cert,
        )

    def _on_add_certificate_toggled(self, checkbutton: Gtk.CheckButton) -> None:
        self._ui.connect_button.set_sensitive(checkbutton.get_active())

    def _on_connect_clicked(self, _button: Gtk.Button) -> None:
        if self._ui.add_certificate_checkbutton.get_active():
            app.cert_store.add_certificate(self._cert)

        if self._error == Gio.TlsCertificateFlags.EXPIRED:
            self._ignored_errors.add(Gio.TlsCertificateFlags.EXPIRED)

        self._client.connect(ignored_tls_errors=self._ignored_errors)
        self.close()
