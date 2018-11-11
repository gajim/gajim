import os

from tempfile import gettempdir

# a temporary version of ~/.gajim for testing
configdir = os.path.join(gettempdir(), 'gajim')
os.makedirs(configdir, exist_ok=True)

# plugins config dir
pluginsconfigdir = configdir + '/pluginsconfig'
# theme config directory
themedir = configdir + '/theme'

# define _ for i18n
import builtins
builtins._ = lambda x: x

from gajim.common.contacts import LegacyContactsAPI

def setup_env(use_x=True):
    # wipe config directory
    if os.path.isdir(configdir):
        import shutil
        shutil.rmtree(configdir)

    os.mkdir(configdir)
    os.mkdir(pluginsconfigdir)
    os.mkdir(themedir)

    from gajim.common import configpaths
    configpaths.set_config_root(configdir)
    configpaths.init()

    # for some reason gajim.common.app needs to be imported before xmpppy?
    from gajim.common import app

    import logging
    logging.basicConfig()

    app.use_x = use_x
    app.contacts = LegacyContactsAPI()
    app.connections = {}

    if use_x:
        from gajim.application import GajimApplication
        app.app = GajimApplication()
