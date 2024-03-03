# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

import cairo
import nbxmpp
from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.const import ARTISTS
from gajim.common.const import DEVS_CURRENT
from gajim.common.const import DEVS_PAST
from gajim.common.const import THANKS
from gajim.common.helpers import get_glib_version
from gajim.common.helpers import get_gobject_version
from gajim.common.helpers import get_soup_version
from gajim.common.helpers import open_uri
from gajim.common.i18n import _

from gajim.gtk.util import get_gtk_version


class AboutDialog(Gtk.AboutDialog):
    def __init__(self):
        Gtk.AboutDialog.__init__(self)
        self.set_transient_for(app.window)
        self.set_name('Gajim')
        self.set_version(app.version)
        self.set_copyright('Copyright © 2003-2024 Gajim Team')
        self.set_license_type(Gtk.License.GPL_3_0_ONLY)
        self.set_website('https://gajim.org/')

        cairo_ver = cairo.cairo_version_string()
        python_cairo_ver = cairo.version

        comments: list[str] = []
        comments.append(_('A fully-featured XMPP chat client'))
        comments.append('')
        comments.append(_('GTK Version: %s') % get_gtk_version())
        comments.append(_('GLib Version: %s') % get_glib_version())
        comments.append(_('Pango Version: %s') % Pango.version_string())
        comments.append(_('PyGObject Version: %s') % get_gobject_version())
        comments.append(_('cairo Version: %s') % cairo_ver)
        comments.append(_('pycairo Version: %s') % python_cairo_ver)
        comments.append(_('python-nbxmpp Version: %s') % nbxmpp.__version__)
        comments.append(_('libsoup Version: %s') % get_soup_version())

        self.set_comments('\n'.join(comments))

        self.add_credit_section(_('Current Developers'), DEVS_CURRENT)
        self.add_credit_section(_('Past Developers'), DEVS_PAST)
        self.add_credit_section(_('Artists'), ARTISTS)

        thanks = list(THANKS)
        thanks.append('')
        thanks.append(_('Last but not least'))
        thanks.append(_('we would like to thank all the package maintainers.'))
        self.add_credit_section(_('Thanks'), thanks)

        self.set_translator_credits(_('translator-credits'))
        self.set_logo_icon_name('org.gajim.Gajim')

        self.connect('activate-link', self._on_activate_link)
        self.connect('response', self._on_response)
        self.show()

    @staticmethod
    def _on_activate_link(_label: Gtk.Label, uri: str) -> int:
        # We have to use this, because the default GTK handler
        # is not cross-platform compatible
        open_uri(uri)
        return Gdk.EVENT_STOP

    def _on_response(self,
                     _dialog: Gtk.AboutDialog,
                     response: Gtk.ResponseType
                     ) -> None:
        if response == Gtk.ResponseType.DELETE_EVENT:
            self.destroy()
