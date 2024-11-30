from __future__ import annotations

import typing

import winrt.system

TResult = typing.TypeVar("TResult")
TSender = typing.TypeVar("TSender")
TypedEventHandler = typing.Callable[
    [typing.Optional[TSender], typing.Optional[TResult]], None
]

@typing.final
class EventRegistrationToken:
    value: winrt.system.Int64
