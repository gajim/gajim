docdir = '../'

datadir = '../'

version = '0.11.1.3'

import sys, os.path
for base in ('.', 'common'):
	sys.path.append(os.path.join(base, '.libs'))
