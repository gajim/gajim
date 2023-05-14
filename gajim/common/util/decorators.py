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

from typing import Any

from functools import lru_cache
from functools import wraps
from time import monotonic


def lru_cache_with_ttl(maxsize: int,
                       typed: bool = False,
                       ttl: int = 2
                       ) -> Any:
    '''LRU-Cache with TTL'''

    class Result:
        __slots__ = ('value', 'timeout')

        def __init__(self, value: Any, timeout: float) -> None:
            self.value = value
            self.timeout = timeout

    def decorator(func: Any) -> Any:
        @lru_cache(maxsize=maxsize, typed=typed)
        def cached_func(*args: Any, **kwargs: Any) -> Result:
            value = func(*args, **kwargs)
            timeout = monotonic() + ttl
            return Result(value, timeout)

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = cached_func(*args, **kwargs)
            if result.timeout < monotonic():
                result.value = func(*args, **kwargs)
                result.timeout = monotonic() + ttl
            return result.value

        return wrapper

    return decorator
