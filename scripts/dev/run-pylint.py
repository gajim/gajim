#!/usr/bin/env python
# (C) 2006 Nikos Kouremenos <kourem@gmail.com>

import os
import sys

if os.getcwd().endswith('dev'):
	os.chdir('../../src/') # we were in scripts/dev

os.system("pylint --indent-string='\t' --additional-builtins='_' --disable-msg=C0111,C0103,C0111,C0112 --disable-checker=design " + "".join(sys.argv[1:]))


# vim: se ts=3:
