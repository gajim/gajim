# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import cairo
import nbxmpp
from gi.repository import Adw
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.const import ARTISTS
from gajim.common.const import DEVELOPERS
from gajim.common.const import Display
from gajim.common.const import GAJIM_ISSUES_URI
from gajim.common.const import MAINTAINERS
from gajim.common.const import THANKS
from gajim.common.i18n import _
from gajim.common.util.app import get_extended_app_version
from gajim.common.util.version import get_glib_version
from gajim.common.util.version import get_gobject_version
from gajim.common.util.version import get_os_info
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
            copyright="Copyright © 2003-2026 Gajim Team",
            license_type=Gtk.License.GPL_3_0_ONLY,
            website="https://gajim.org/",
            issue_url=GAJIM_ISSUES_URI,
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
        debug_info = f"""
## Versions

- OS: {get_os_info()}
- Display: {self._get_display()}
- Gajim: {get_extended_app_version()}
- python-nbxmpp: {nbxmpp.__version__}
- GTK: {get_gtk_version()}
- Adw: {get_adw_version()}
- GLib: {get_glib_version()}
- PyGObject: {get_gobject_version()}
- libsoup: {get_soup_version()}
- Pango: {Pango.version_string()}
- cairo: {cairo.cairo_version_string()}
- pycairo: {cairo.version}
"""
        return debug_info

    def _get_display(self) -> str:
        if app.is_display(Display.WAYLAND):
            return "Wayland"
        if app.is_display(Display.X11):
            return "X11"
        if app.is_display(Display.WIN32):
            return "Win32"
        if app.is_display(Display.QUARTZ):
            return "Quartz"
        return "Unknown"

    def _on_dialog_closed(self, _dialog: AboutDialog) -> None:
        self._dialog = None
