#!/usr/bin/env python


'''
Runs Gajim's Test Suite

Non GUI related tests will be run on each commit.
'''

import sys
import unittest
import getopt
use_x = True
verbose = 1

try:
	shortargs = 'hnv:'
	longargs = 'help no-x verbose='
	opts, args = getopt.getopt(sys.argv[1:], shortargs, longargs.split())
except getopt.error, msg:
	print msg
	print 'for help use --help'
	sys.exit(2)
for o, a in opts:
	if o in ('-h', '--help'):
		print 'runtests [--help] [--no-x] [--verbose level]'
		sys.exit()
	elif o in ('-n', '--no-x'):
		use_x = False
	elif o in ('-v', '--verbose'):
		try:
			verbose = int(a)
		except Exception:
			print 'verbose must be a number >= 0'
			sys.exit(2)

# new test modules need to be added manually
modules = ( 'test_xmpp_dispatcher_nb',
				'test_xmpp_client_nb',
				'test_xmpp_transports_nb',
				'test_resolver',
				'test_caps',
				'test_contacts',
			 )
#modules = ()

if use_x:
	modules += ('test_misc_interface',
					'test_roster',
					'test_sessions',
	)

nb_errors = 0
nb_failures = 0

for mod in modules:
	suite = unittest.defaultTestLoader.loadTestsFromName(mod)
	result = unittest.TextTestRunner(verbosity=verbose).run(suite)
	nb_errors += len(result.errors)
	nb_failures += len(result.failures)

sys.exit(nb_errors + nb_failures)

# vim: se ts=3:
