'''
Tests for Account classes
'''
import unittest

import lib
lib.setup_env()

from common.account import Account

class Test(unittest.TestCase):

	def testInstantiate(self):
		account = Account(gc_contacts=None)
		
		self.assertTrue(account.gc_contacts is None)

if __name__ == "__main__":
	unittest.main()