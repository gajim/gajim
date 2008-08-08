import sys
import os.path

gajim_root = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..')

# look for modules in the CWD, then gajim/src, then everywhere else
sys.path.insert(1, gajim_root + '/src')

# a temporary version of ~/.gajim for testing
configdir = gajim_root + '/test/tmp'

# define _ for i18n
import __builtin__
__builtin__._ = lambda x: x

import os

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

	gajim.DATA_DIR = gajim_root + '/data'

	import gtkgui_helpers
	gtkgui_helpers.GLADE_DIR = gajim_root + '/data/glade'

# vim: se ts=3:
