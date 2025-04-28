# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import ParamSpec
from typing import TypeVar

import logging
from collections.abc import Callable
from functools import wraps
from time import monotonic

from gi.repository import GLib

P = ParamSpec('P')
R = TypeVar('R')


log = logging.getLogger('gajim.c.util.decorators')


def cache_with_ttl(ttl: int = 2) -> Any:

    class Result:
        __slots__ = ('timeout', 'value')

        def __init__(self, value: Any, timeout: float) -> None:
            self.value = value
            self.timeout = timeout

    def decorator(func: Any) -> Any:
        def cached_func(*args: Any) -> Result:
            value = func(*args)
            timeout = monotonic() + ttl
            return Result(value, timeout)

        @wraps(func)
        def wrapper(module: Any, *args: Any) -> Any:
            ttl_cache = module.get_ttl_cache()
            result = ttl_cache.get((module, *args))
            if result is not None:
                if result.timeout < monotonic():
                    result.value = func(module, *args)
                    result.timeout = monotonic() + ttl

                return result.value

            result = cached_func(module, *args)
            ttl_cache[(module, *args)] = result
            return result.value

        return wrapper

    return decorator


def catch_exceptions(func: Callable[P, R]) -> Callable[P, R | None]:
    @wraps(func)
    def func_wrapper(*args: P.args, **kwargs: P.kwargs) -> R | None:
        try:
            result = func(*args, **kwargs)
        except Exception as error:
            log.exception(error)
            return None

        return result

    return func_wrapper


def event_filter(filter_: Any):
    def event_filter_decorator(func: Any) -> Any:
        @wraps(func)
        def func_wrapper(self: Any, event: Any, *args: Any, **kwargs: Any) -> Any:
            for attr in filter_:
                if '=' in attr:
                    attr1, attr2 = attr.split('=')
                else:
                    attr1, attr2 = attr, attr
                try:
                    if getattr(event, attr1) != getattr(self, attr2):
                        return None
                except AttributeError:
                    if getattr(event, attr1) != getattr(self, f'_{attr2}'):
                        return None

            return func(self, event, *args, **kwargs)

        return func_wrapper

    return event_filter_decorator


def delay_execution(milliseconds: int) -> Any:
    # Delay the first call for `milliseconds`
    # ignore all other calls while the delay is active
    def delay_execution_decorator(func: Any) -> Any:
        @wraps(func)
        def func_wrapper(*args: Any, **kwargs: Any) -> Any:
            def timeout_wrapper():
                func(*args, **kwargs)
                delattr(func_wrapper, 'source_id')

            if hasattr(func_wrapper, 'source_id'):
                return
            func_wrapper.source_id = GLib.timeout_add(  # type: ignore
                milliseconds, timeout_wrapper
            )

        return func_wrapper

    return delay_execution_decorator
