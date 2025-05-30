# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import Literal
from typing import Optional

import functools
import inspect
import sys
from collections.abc import Callable
from dataclasses import dataclass

from gi.repository import Gio
from gi.repository import GLib
from nbxmpp.protocol import JID

from gajim.common.structs import VariantMixin


@dataclass
class OpenEventActionParams(VariantMixin):
    # Event which is used for Notifications and gets sent over DBus
    # Don’t use Optional types here because DBus does not support "None"
    type: str
    sub_type: str
    account: str
    jid: str
    context_id: str


@dataclass
class AddChatActionParams(VariantMixin):
    account: str
    jid: JID
    type: Literal["chat", "groupchat", "pm"]
    select: bool


@dataclass
class ChatListEntryParam(VariantMixin):
    workspace_id: str
    source_workspace_id: str
    account: str
    jid: JID


@dataclass
class MuteContactParam(VariantMixin):
    account: str
    jid: JID
    state: int


@dataclass
class AccountJidParam(VariantMixin):
    account: str
    jid: JID


@dataclass
class OccupantParam(VariantMixin):
    account: str
    jid: JID
    resource: str
    occupant_id: str


@dataclass
class ExportHistoryParam(VariantMixin):
    account: str
    jid: Optional[JID]  # noqa: UP007


@dataclass
class ModerateMessageParam(VariantMixin):
    account: str
    jid: JID
    stanza_ids: list[str]
    namespace: str


@dataclass
class RetractMessageParam(VariantMixin):
    account: str
    jid: JID
    retract_ids: list[str]


@dataclass
class ModerateAllMessagesParam(VariantMixin):
    account: str
    jid: JID
    occupant_id: str
    nickname: str
    namespace: str


@dataclass
class DeleteMessageParam(VariantMixin):
    account: str
    jid: JID
    pk: int


@dataclass
class SubscriptionAcceptParam(VariantMixin):
    account: str
    jid: JID
    nickname: Optional[str]  # noqa: UP007


def get_params_class(func: Callable[..., Any]) -> Any:
    module = sys.modules[__name__]
    params = inspect.signature(func).parameters
    cls_string = params["params"].annotation
    cls_string = cls_string.rsplit(".", maxsplit=1)[-1]
    return getattr(module, cls_string)


def actionmethod(
    func: Callable[[Any, Gio.SimpleAction, Any], None]
) -> Callable[[Any, Gio.SimpleAction, GLib.Variant], None]:
    @functools.wraps(func)
    def method_wrapper(obj: Any, action: Gio.SimpleAction, param: GLib.Variant) -> None:
        params_cls = get_params_class(func)
        params = params_cls.from_variant(param)
        return func(obj, action, params)

    return method_wrapper


def actionfunction(
    func: Callable[[Gio.SimpleAction, Any], None]
) -> Callable[[Gio.SimpleAction, GLib.Variant], None]:
    @functools.wraps(func)
    def func_wrapper(action: Gio.SimpleAction, param: GLib.Variant) -> None:
        params_cls = get_params_class(func)
        params = params_cls.from_variant(param)
        return func(action, params)

    return func_wrapper
