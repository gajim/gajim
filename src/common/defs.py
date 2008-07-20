import re

docdir = '../'
datadir = '../'

version = '0.11.4.4-svn'

rev = re.sub('[^0-9]', '', '$Rev$')
if rev is not '':
	version += ' r' + rev

import sys, os.path
for base in ('.', 'common'):
	sys.path.append(os.path.join(base, '.libs'))
