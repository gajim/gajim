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

from typing import Union


def from_xs_boolean(value: Union[str, bool]) -> bool:
    if isinstance(value, bool):
        return value

    if value in ('1', 'true', 'True'):
        return True

    if value in ('0', 'false', 'False', ''):
        return False

    raise ValueError('Cant convert %s to python boolean' % value)


def to_xs_boolean(value: Union[bool, None]) -> str:
    # Convert to xs:boolean ('true', 'false')
    # from a python boolean (True, False) or None
    if value is True:
        return 'true'

    if value is False:
        return 'false'

    if value is None:
        return 'false'

    raise ValueError(
        'Cant convert %s to xs:boolean' % value)
