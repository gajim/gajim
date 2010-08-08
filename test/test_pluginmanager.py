#!/usr/bin/env python
# -*- coding: utf-8 -*-

## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim.  If not, see <http://www.gnu.org/licenses/>.
##

'''
Testing PluginManager class.

:author: Mateusz Biliński <mateusz@bilinski.it>
:since: 05/30/2008
:copyright: Copyright (2008) Mateusz Biliński <mateusz@bilinski.it>
:license: GPL
'''

import sys
import os
import unittest

gajim_root = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..')
sys.path.append(gajim_root + '/src')

# a temporary version of ~/.gajim for testing
configdir = gajim_root + '/test/tmp'

import time

# define _ for i18n
import __builtin__
__builtin__._ = lambda x: x

# wipe config directory
import os
if os.path.isdir(configdir):
    import shutil
    shutil.rmtree(configdir)

os.mkdir(configdir)

import common.configpaths
common.configpaths.gajimpaths.init(configdir)
common.configpaths.gajimpaths.init_profile()

# for some reason common.gajim needs to be imported before xmpppy?
from common import gajim
from common import xmpp

gajim.DATA_DIR = gajim_root + '/data'

from common.stanza_session import StanzaSession

# name to use for the test account
account_name = 'test'

from plugins import PluginManager

class PluginManagerTestCase(unittest.TestCase):
    def setUp(self):
        self.pluginmanager = PluginManager()

    def tearDown(self):
        pass

    def test_01_Singleton(self):
        """ 1. Checking whether PluginManger class is singleton. """
        self.pluginmanager.test_arg = 1
        secondPluginManager = PluginManager()

        self.failUnlessEqual(id(secondPluginManager), id(self.pluginmanager),
                                                 'Different IDs in references to PluginManager objects (not a singleton)')
        self.failUnlessEqual(secondPluginManager.test_arg, 1,
                                                 'References point to different PluginManager objects (not a singleton')

def suite():
    suite = unittest.TestLoader().loadTestsFromTestCase(PluginManagerTestCase)
    return suite

if __name__=='__main__':
    runner = unittest.TextTestRunner()
    test_suite = suite()
    runner.run(test_suite)
