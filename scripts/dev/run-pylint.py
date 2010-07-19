#!/usr/bin/env python
# (C) 2006 Nikos Kouremenos <kourem@gmail.com>

import os
import sys

if os.getcwd().endswith('dev'):
    os.chdir('../../src/') # we were in scripts/dev

os.system("pylint --include-ids=y --additional-builtins='_' --disable-msg=C0103,C0111,W0703,W0511,W0142,W0613,R0201 --disable-checker=design " + "".join(sys.argv[1:]))
