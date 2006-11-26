docdir = '../'

datadir = '../'

version = '0.10.1.8'

import sys, os.path
for base in ('.', 'common'):
	sys.path.append(os.path.join(base, '.libs'))
