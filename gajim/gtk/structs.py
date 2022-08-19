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

from typing import Any
from typing import Callable

import sys
import inspect
import functools
from dataclasses import dataclass
from gi.repository import GLib, Gio

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


@dataclass
class RemoveHistoryActionParams(VariantMixin):
    account: str
    jid: JID


@dataclass
class AddChatActionParams(VariantMixin):
    account: str
    jid: JID
    type: str
    select: bool


@dataclass
class ChatListEntryParam(VariantMixin):
    workspace_id: str
    source_workspace_id: str
    account: str
    jid: JID


@dataclass
class AccountJidParam(VariantMixin):
    account: str
    jid: JID


def get_params_class(func: Callable[..., Any]) -> Any:
    module = sys.modules[__name__]
    params = inspect.signature(func).parameters
    cls_string = params['params'].annotation
    cls_string = cls_string.rsplit('.', maxsplit=1)[-1]
    return getattr(module, cls_string)


def actionmethod(func: Callable[[Any, Gio.SimpleAction, Any], None]
                 ) -> Callable[[Any, Gio.SimpleAction, GLib.Variant], None]:
    @functools.wraps(func)
    def method_wrapper(obj: Any,
                       action: Gio.SimpleAction,
                       param: GLib.Variant) -> None:
        params_cls = get_params_class(func)
        params = params_cls.from_variant(param)
        return func(obj, action, params)
    return method_wrapper


def actionfunction(func: Callable[[Gio.SimpleAction, Any], None]
                   ) -> Callable[[Gio.SimpleAction, GLib.Variant], None]:
    @functools.wraps(func)
    def func_wrapper(action: Gio.SimpleAction,
                     param: GLib.Variant) -> None:
        params_cls = get_params_class(func)
        params = params_cls.from_variant(param)
        return func(action, params)
    return func_wrapper
