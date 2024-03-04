# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import typing

import inspect
import logging
from importlib import import_module
from pathlib import Path

from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common.modules.base import BaseModule

if typing.TYPE_CHECKING:
    from gajim.common.types import Client


log = logging.getLogger('gajim.c.m')

_modules: dict[str, dict[str, BaseModule]] = {}
_store_publish_modules = [
    'UserLocation',
    'UserTune',
]


def register_modules(client: Client) -> None:
    if client.account in _modules:
        return

    _modules[client.account] = {}

    path = Path(__file__).parent
    for module in path.iterdir():
        if module.suffix not in ['.py', '.pyc']:
            continue

        if module.name.startswith('__'):
            continue

        name = module.stem
        module = import_module('.%s' % name, package='gajim.common.modules')
        for _, base_class in inspect.getmembers(module, inspect.isclass):

            if base_class is BaseModule:
                continue

            if BaseModule not in inspect.getmro(base_class):
                continue

            instance = base_class.get_instance(client)
            module_name = base_class.__name__
            _modules[client.account][module_name] = instance


def register_single_module(client: Client,
                           instance: BaseModule,
                           name: str) -> None:

    if client.account not in _modules:
        raise ValueError('Unknown account name: %s' % client.account)
    _modules[client.account][name] = instance


def unregister_modules(client: Client) -> None:
    for instance in _modules[client.account].values():
        if hasattr(instance, 'cleanup'):
            instance.cleanup()
        app.check_finalize(instance)
    del _modules[client.account]


def unregister_single_module(client: Client, name: str) -> None:
    if client.account not in _modules:
        return
    if name not in _modules[client.account]:
        return
    del _modules[client.account][name]


def send_stored_publish(account: str) -> None:
    for name in _store_publish_modules:
        _modules[account][name].send_stored_publish()


def get(account: str, name: str) -> BaseModule:
    return _modules[account][name]


def get_handlers(client: Client) -> list[StanzaHandler]:
    handlers: list[StanzaHandler] = []
    for module in _modules[client.account].values():
        handlers += module.handlers
    return handlers
