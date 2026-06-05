# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

import signal
import sys
from types import FrameType

from gi.repository import Adw
from nbxmpp.protocol import JID

import gajim.common.i18n
from gajim.common import app
from gajim.common import configpaths
from gajim.common.application import CoreApplication

from gajim.gtk.avatar import AvatarStorage
from gajim.gtk.util.icons import get_icon_theme


class GajimTestApplication(Adw.Application, CoreApplication):
    def __init__(self) -> None:
        CoreApplication.__init__(self)
        Adw.Application.__init__(self, application_id="org.gajim.GajimTest")

        self.avatar_storage = AvatarStorage()

        self.connect("startup", self._on_startup)

    def _init_signals(self) -> None:
        def sigint_cb(num: int, stack: FrameType | None) -> None:
            print(" SIGINT/SIGTERM received")
            self.start_shutdown()

        # ^C exits the application normally
        signal.signal(signal.SIGINT, sigint_cb)
        signal.signal(signal.SIGTERM, sigint_cb)
        if sys.platform != "win32":
            signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    def _on_startup(self, _application: Adw.Application) -> None:
        gajim.common.i18n.init()
        self._init_signals()

        configpaths.set_config_root(str(configpaths.get_temp_dir()))
        if not self._init_core(in_memory=True):
            return

        app.load_css_config()

        icon_theme = get_icon_theme()
        icon_theme.add_search_path(str(configpaths.get("ICONS")))

    def add_account(self, name: str) -> None:
        self.create_account(
            name, JID.from_string(f"{name}@example.com"), "", None, None
        )
        self.enable_account(name, connect=False)

        app.css_config.refresh()

    def start_shutdown(self) -> None:
        self._start_shutdown()

    def _shutdown_complete(self) -> None:
        CoreApplication._shutdown_complete(self)
        self.quit()
