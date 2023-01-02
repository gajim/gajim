#!/usr/bin/env python3

import subprocess

from gajim import gajim

try:
    p = subprocess.Popen('git rev-parse --short=12 HEAD', shell=True,
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    node = p.communicate()[0]
    if node:
        import gajim as g
        g.__version__ += '+' + node.decode('utf-8').strip()
except Exception:
    pass

gajim.main()
