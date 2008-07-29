import re

docdir = '../'
datadir = '../'

version = '0.11.4.4-svn'

import sys, os.path
for base in ('.', 'common'):
	sys.path.append(os.path.join(base, '.libs'))

# vim: se ts=3: