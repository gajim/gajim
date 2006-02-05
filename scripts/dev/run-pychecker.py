#! /usr/bin/env python
# (C) 2006 Nikos Kouremenos <kourem@gmail.com>

import os
import sys

if os.getcwd().endswith('dev'):
	os.chdir('../../src/') # we were in scripts/dev

os.system('pychecker --limit 10000 --no-shadowbuiltin *.py &> /tmp/pychecker-gajim.log')
os.system('$EDITOR /tmp/pychecker-gajim.log')

