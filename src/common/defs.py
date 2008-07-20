docdir = '../'

datadir = '../'

version = '0.11.4.4-svn'
rev = '$Rev$'.replace('$', '').replace('Rev', '').replace(': ', '')
if rev is not '':
	version += ' r' + rev

import sys, os.path
for base in ('.', 'common'):
	sys.path.append(os.path.join(base, '.libs'))
