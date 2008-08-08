#!/usr/bin/env python

import unittest

# new test modules need to be added manually
modules = ( 'test_caps',
				'test_dispatcher_nb',
				'test_misc_interface',
				'test_roster',
				'test_sessions',
												)
for mod in modules:
	suite = unittest.defaultTestLoader.loadTestsFromName(mod)
	unittest.TextTestRunner(verbosity=1).run(suite)

# vim: se ts=3:
