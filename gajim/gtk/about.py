# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import cairo
import nbxmpp
from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.const import ARTISTS
from gajim.common.const import DEVELOPERS
from gajim.common.const import MAINTAINERS
from gajim.common.const import THANKS
from gajim.common.i18n import _
from gajim.common.util.app import get_extended_app_version
from gajim.common.util.uri import open_uri
from gajim.common.util.version import get_glib_version
from gajim.common.util.version import get_gobject_version
from gajim.common.util.version import get_soup_version

from gajim.gtk.util import get_gtk_version
from gajim.gtk.util import SignalManager


class AboutDialog(Gtk.AboutDialog, SignalManager):
    def __init__(self):
        Gtk.AboutDialog.__init__(
            self,
            transient_for=app.window,
            name="Gajim",
            version=get_extended_app_version(),
            copyright="Copyright © 2003-2024 Gajim Team",
            license_type=Gtk.License.GPL_3_0_ONLY,
            website="https://gajim.org/",
            logo_icon_name="gajim",
            translator_credits=_("translator-credits"),
        )
        SignalManager.__init__(self)

        cairo_ver = cairo.cairo_version_string()
        python_cairo_ver = cairo.version

        comments: list[str] = []
        comments.append(_("A fully-featured XMPP chat client"))
        comments.append("")
        comments.append(_("GTK Version: %s") % get_gtk_version())
        comments.append(_("GLib Version: %s") % get_glib_version())
        comments.append(_("Pango Version: %s") % Pango.version_string())
        comments.append(_("PyGObject Version: %s") % get_gobject_version())
        comments.append(_("cairo Version: %s") % cairo_ver)
        comments.append(_("pycairo Version: %s") % python_cairo_ver)
        comments.append(_("python-nbxmpp Version: %s") % nbxmpp.__version__)
        comments.append(_("libsoup Version: %s") % get_soup_version())

        self.set_comments("\n".join(comments))

        self.add_credit_section(_("Maintainers"), MAINTAINERS)
        self.add_credit_section(_("Developers"), DEVELOPERS)
        self.add_credit_section(_("Artists"), ARTISTS)

        thanks = list(THANKS)
        thanks.append("")
        thanks.append(_("Last but not least"))
        thanks.append(_("we would like to thank all the package maintainers."))
        self.add_credit_section(_("Thanks"), thanks)

        self._connect(self, "activate-link", self._on_activate_link)
        self._connect(self, "close-request", self._on_close_request)
        self.show()

    def _on_close_request(self, window: AboutDialog) -> None:
        self._disconnect_all()
        app.check_finalize(self)

    @staticmethod
    def _on_activate_link(_label: Gtk.Label, uri: str) -> int:
        # We have to use this, because the default GTK handler
        # is not cross-platform compatible
        open_uri(uri)
        return Gdk.EVENT_STOP
