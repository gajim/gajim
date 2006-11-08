docdir = '../'

datadir = '../'

version = '0.10.1.7'

import sys, os.path
for base in ('.', 'common'):
	sys.path.append(os.path.join(base, '.libs'))
