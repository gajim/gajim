import unittest

from gajim.common import app  # noqa F401  (avoid circular imports)
from gajim.common.const import XmppUriQuery
from gajim.common.helpers import _xmpp_query_type_handlers


class Test(unittest.TestCase):
    def test_xmpp_query_type_handlers_dict(self):
        for t in XmppUriQuery:
            self.assertIn(t, _xmpp_query_type_handlers)


if __name__ == '__main__':
    unittest.main()
