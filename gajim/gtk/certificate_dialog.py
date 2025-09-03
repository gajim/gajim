# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

import logging

from gi.repository import Gio
from gi.repository import Gtk

from gajim.common.i18n import _

from gajim.gtk.preference.certificate import CertificatePage
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
            default_width=600,
            default_height=800,
            transient_for=transient_for,
        )

        self.account = account

        self.set_child(CertificatePage(account, cert))

    def _cleanup(self) -> None:
        pass
