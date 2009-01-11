import sys
import os
import getopt

use_x = True
shortargs = 'hnv:'
longargs = 'help no-x verbose='
opts, args = getopt.getopt(sys.argv[1:], shortargs, longargs.split())
for o, a in opts:
	if o in ('-n', '--no-x'):
		use_x = False

gajim_root = os.path.join(os.path.abspath(os.path.dirname(__file__)), '../..')

# look for modules in the CWD, then gajim/test/lib, then gajim/src,
# then everywhere else
sys.path.insert(1, gajim_root + '/src')
sys.path.insert(1, gajim_root + '/test/lib')

# a temporary version of ~/.gajim for testing
configdir = gajim_root + '/test/tmp'

# define _ for i18n
import __builtin__
__builtin__._ = lambda x: x

def setup_env():
	# wipe config directory
	if os.path.isdir(configdir):
		import shutil
		shutil.rmtree(configdir)

	os.mkdir(configdir)

	import common.configpaths
	common.configpaths.gajimpaths.init(configdir)
	common.configpaths.gajimpaths.init_profile()

	# for some reason common.gajim needs to be imported before xmpppy?
	from common import gajim

	import logging
	logging.basicConfig()

	gajim.DATA_DIR = gajim_root + '/data'
	gajim.use_x = use_x

	if use_x:
		import gtkgui_helpers
		gtkgui_helpers.GLADE_DIR = gajim_root + '/data/glade'

# vim: se ts=3:
