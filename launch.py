#!/usr/bin/env python3

# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

import subprocess
from pathlib import Path

if __name__ == "__main__":
    # Protect the entry point of the application because we use
    # the multiprocessing module with "spawn"

    import gajim
    import gajim.main

    try:
        res = subprocess.check_output(
            [
                "git",
                "-C",
                f"{Path(__file__).parent}",
                "rev-parse",
                "--short=12",
                "HEAD",
            ],
            stderr=subprocess.DEVNULL,
        )
        gajim.__version__ += f"+{res.decode().strip()}"
    except Exception:
        pass

    gajim.main.run()
