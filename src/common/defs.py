import re

docdir = '../'
datadir = '../'

version = '0.12-alpha'

import sys, os.path
for base in ('.', 'common'):
	sys.path.append(os.path.join(base, '.libs'))

# vim: se ts=3:
