# $Id: __init__.py,v 1.9 2005/03/07 09:34:51 snakeru Exp $

"""
Gajim maintains a fork of the xmpppy jabber python library. Most of the code is
inherited but has been extended by implementation of non-blocking transports
and new features like BOSH.

Most of the xmpp classes are ancestors of PlugIn class to share a single set of methods in order to compile a featured and extensible XMPP client.

Thanks and credits to the xmpppy developers. See: http://xmpppy.sourceforge.net/
"""

import simplexml, protocol, auth_nb, transports_nb, roster_nb
import dispatcher_nb, features_nb, idlequeue, bosh, tls_nb, proxy_connectors
from client_nb import NonBlockingClient
from client import PlugIn
from protocol import *

# vim: se ts=3:
