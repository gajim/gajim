#!/usr/bin/env python3

# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

import os
import sys

if getattr(sys, "frozen", False):
    # PyInstaller's GStreamer runtime hook puts the whole bundle on
    # GST_PLUGIN_PATH, so GStreamer dlopen()s every bundled library while
    # scanning for plugins, and it keeps the registry inside the app bundle.
    # The *_1_0 variables take precedence and are inherited by the
    # multiprocessing workers, where the runtime hook runs again.
    bundle_dir = str(sys._MEIPASS)  # type: ignore
    os.environ["GST_PLUGIN_PATH_1_0"] = os.path.join(bundle_dir, "gst_plugins")
    cache_dir = os.path.expanduser("~/Library/Caches/Gajim")
    os.makedirs(cache_dir, exist_ok=True)
    os.environ["GST_REGISTRY_1_0"] = os.path.join(cache_dir, "gstreamer-registry.bin")

from gajim.main import run  # noqa: E402

if __name__ == "__main__":
    # Protect the entry point of the application because we use
    # the multiprocessing module with "spawn"
    sys.exit(run())
