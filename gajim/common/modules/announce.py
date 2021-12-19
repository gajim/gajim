# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

# Server MOTD and Announce

import nbxmpp

from gajim.common.modules.base import BaseModule


class Announce(BaseModule):
    def __init__(self, con):
        BaseModule.__init__(self, con)

    def delete_motd(self):
        server = self._con.get_own_jid().domain
        jid = '%s/announce/motd/delete' % server
        self.set_announce(jid)

    def set_announce(self, jid, subject=None, body=None):
        message = nbxmpp.Message(to=jid, body=body, subject=subject)
        self._nbxmpp().send(message)
