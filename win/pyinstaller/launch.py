#!/usr/bin/env python3

# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

import sys

from gajim.main import run

if __name__ == "__main__":
    # Protect the entry point of the application because we use
    # the multiprocessing module with "spawn"
    sys.exit(run())
