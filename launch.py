#!/usr/bin/env python3

import subprocess

import gajim
import gajim.main

try:
    res = subprocess.check_output(
        ['git', 'rev-parse', '--short=12', 'HEAD'])  # noqa: S603, S607
    gajim.__version__ += f'+{res.decode().strip()}'
except Exception:
    pass

gajim.main.run()
