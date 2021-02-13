'''
Some diverse tests covering functionality in the GUI Interface class.
'''
import unittest

from test import lib
lib.setup_env()

from gajim.common import logging_helpers
logging_helpers.set_quiet()

from gajim.common import app

from gajim.gui_interface import Interface

from gi.repository import GLib

class TestInterface(unittest.TestCase):

    def test_instantiation(self):
        ''' Test that we can proper initialize and do not fail on globals '''
        def close_app():
            app.app.quit()
        GLib.idle_add(close_app)
        app.app.run()


if __name__ == "__main__":
    unittest.main()
