# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import cairo
import nbxmpp
from gi.repository import Adw
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common.const import ARTISTS
from gajim.common.const import DEVELOPERS
from gajim.common.const import MAINTAINERS
from gajim.common.const import THANKS
from gajim.common.i18n import _
from gajim.common.util.app import get_extended_app_version
from gajim.common.util.version import get_glib_version
from gajim.common.util.version import get_gobject_version
from gajim.common.util.version import get_soup_version

from gajim.gtk.util.misc import get_adw_version
from gajim.gtk.util.misc import get_gtk_version


class AboutDialog:
    def __init__(self) -> None:
        self._dialog = None

    def present(self) -> None:
        if self._dialog is None:
            self._dialog = self._get_dialog()
        self._dialog.present()

    def _get_dialog(self) -> Adw.AboutDialog:
        dialog = Adw.AboutDialog(
            application_name="Gajim",
            application_icon="gajim",
            version=get_extended_app_version(),
            copyright="Copyright © 2003-2025 Gajim Team",
            license_type=Gtk.License.GPL_3_0_ONLY,
            website="https://gajim.org/",
            issue_url="https://dev.gajim.org/gajim/gajim/-/issues/",
            developer_name="\n".join(MAINTAINERS),
            developers=MAINTAINERS + DEVELOPERS,
            designers=ARTISTS,
            debug_info=self._get_debug_info(),
            debug_info_filename="gajim_version_info.txt",
            translator_credits=_("translator-credits"),
        )
        dialog.add_acknowledgement_section(_("Thanks"), THANKS)
        dialog.add_acknowledgement_section(
            _("Packages"), [_("Thanks to all the package maintainers.")]
        )
        dialog.connect("closed", self._on_dialog_closed)
        return dialog

    def _get_debug_info(self) -> str:
        debug_info = [
            _("GTK Version: %s") % get_gtk_version(),
            _("Adw Version: %s") % get_adw_version(),
            _("GLib Version: %s") % get_glib_version(),
            _("Pango Version: %s") % Pango.version_string(),
            _("PyGObject Version: %s") % get_gobject_version(),
            _("cairo Version: %s") % cairo.cairo_version_string(),
            _("pycairo Version: %s") % cairo.version,
            _("python-nbxmpp Version: %s") % nbxmpp.__version__,
            _("libsoup Version: %s") % get_soup_version(),
        ]
        return "\n".join(debug_info)

    def _on_dialog_closed(self, _dialog: AboutDialog) -> None:
        self._dialog = None
