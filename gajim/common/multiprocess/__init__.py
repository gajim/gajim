# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import signal


def init_process() -> None:
    from gajim.main import set_proc_title

    set_proc_title("gajim-worker")

    signal.signal(signal.SIGINT, signal.SIG_IGN)

    gi_require_versions()


def gi_require_versions() -> None:
    import gi

    gi.require_versions(
        {
            "GLib": "2.0",
            "GdkPixbuf": "2.0",
        }
    )
