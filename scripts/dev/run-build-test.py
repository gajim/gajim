#!/usr/bin/env python

import os
import sys

if os.getcwd().endswith('dev'):
    os.chdir('../../') # we were in scripts/dev

ret = 0
ret += os.system("make clean > " + os.devnull)
ret += os.system("make > " + os.devnull)
ret += os.system("make check > " + os.devnull)

if ret == 0:
    print "Build successfull"
    sys.exit(0)
else:
    print >>sys.stderr, "Build failed"
    sys.exit(1)
