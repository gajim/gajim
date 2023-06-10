#!/usr/bin/env python3

import os
import subprocess

import gajim
import gajim.main

try:
    res = subprocess.check_output(
        ['git',
         '-C',
         f'{os.path.dirname(__file__)}',
         'rev-parse',
         '--short=12',
         'HEAD'])
    gajim.__version__ += f'+{res.decode().strip()}'
except Exception:
    pass

gajim.main.run()
