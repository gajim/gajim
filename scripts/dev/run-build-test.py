#!/usr/bin/env python

import os
import sys

if os.getcwd().endswith('dev'):
	os.chdir('../../') # we were in scripts/dev

ret1 = os.system("make clean > " + os.devnull + " 2>&1")
ret2 = os.system("make > " + os.devnull + " 2>&1")  

if ret1 + ret2 == 0:
	print "Build successfull"
	sys.exit(0)
else:
	print >>sys.stderr, "Build failed"
	sys.exit(1)

# vim: se ts=3:

