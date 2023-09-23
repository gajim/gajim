#!/usr/bin/env python3

import subprocess
from pathlib import Path

import gajim
import gajim.main

try:
    res = subprocess.check_output(
        ['git',
         '-C',
         f'{Path(__file__).parent}',
         'rev-parse',
         '--short=12',
         'HEAD'])
    gajim.__version__ += f'+{res.decode().strip()}'
except Exception:
    pass

gajim.main.run()
