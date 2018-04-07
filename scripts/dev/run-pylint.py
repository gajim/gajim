#!/usr/bin/env python3
# Copyright (C) 2006 Nikos Kouremenos <kourem@gmail.com>
# Copyright (C) 2016 Yann Leboulanger <asterix AT lagaule.org>

import os
import sys

if os.getcwd().endswith('dev'):
    os.chdir('../../gajim/') # we were in scripts/dev

os.system("pylint3 --generated-members= --additional-builtins='_' --disable=C0103,C0111,W0703,W0511,W0142,W0613,R0201,design " + "".join(sys.argv[1:]))
