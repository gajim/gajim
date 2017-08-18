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

# look for modules in the CWD, then gajim/test/lib, then gajim/gajim,
# then everywhere else
sys.path.insert(1, gajim_root)
sys.path.insert(1, gajim_root + '/test/lib')

# a temporary version of ~/.gajim for testing
configdir = gajim_root + '/test/tmp'
# plugins config dir
pluginsconfigdir = configdir + '/pluginsconfig'

# define _ for i18n
import builtins
builtins._ = lambda x: x

def setup_env():
    # wipe config directory
    if os.path.isdir(configdir):
        import shutil
        shutil.rmtree(configdir)

    os.mkdir(configdir)
    os.mkdir(pluginsconfigdir)

    import gajim.common.configpaths
    gajim.common.configpaths.gajimpaths.init(configdir)

    # for some reason gajim.common.app needs to be imported before xmpppy?
    from gajim.common import app

    import logging
    logging.basicConfig()

    app.DATA_DIR = gajim_root + '/data'
    app.use_x = use_x

    if use_x:
        from gajim import gtkgui_helpers
        gtkgui_helpers.GUI_DIR = gajim_root + '/data/gui'
        from gajim.gajim import GajimApplication
        app.app = GajimApplication()
