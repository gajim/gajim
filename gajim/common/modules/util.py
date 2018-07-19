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
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

# Util module

import nbxmpp

from gajim.common import app


def is_self_message(message, groupchat=False):
    if groupchat:
        return False
    frm = message.getFrom()
    to = message.getTo()
    return frm.bareMatch(to)


def is_muc_pm(message, jid, groupchat=False):
    if groupchat:
        return False
    muc_user = message.getTag('x', namespace=nbxmpp.NS_MUC_USER)
    if muc_user is not None:
        return muc_user.getChildren() == []
    else:
        # muc#user namespace was added in MUC 1.28 so we need a fallback
        # Check if we know the jid
        if app.logger.jid_is_room_jid(jid.getStripped()):
            return True
        return False
