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

from __future__ import annotations

from typing import Optional

from dataclasses import dataclass

from nbxmpp.protocol import JID

from gajim.common.structs import VariantMixin


@dataclass
class OpenEventActionParams(VariantMixin):
    type: str
    sub_type: Optional[str]
    account: str
    jid: Optional[JID]


@dataclass
class RemoveHistoryActionParams(VariantMixin):
    account: str
    jid: Optional[JID] = None


@dataclass
class ForgetGroupchatActionParams(VariantMixin):
    account: str
    jid: JID
