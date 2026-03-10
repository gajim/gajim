# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import cast

from nbxmpp.structs import AdHocCommand
from nbxmpp.task import Task

from gajim.common import types
from gajim.common.modules.base import BaseModule


class AdHocCommands(BaseModule):

    _nbxmpp_extends = 'AdHoc'
    _nbxmpp_methods = [
        'request_command_list',
        'execute_command',
    ]

    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)

        self._domain = self._get_own_bare_jid().domain
        self._domain_commands: dict[str, AdHocCommand] = {}

    def get_command(self, node: str) -> AdHocCommand | None:
        return self._domain_commands.get(node)

    def request_commands(self) -> None:
        self.request_command_list(jid=self._domain, callback=self._on_commands_received)

    def _on_commands_received(self, task: Task) -> None:
        try:
            commands = cast(list[AdHocCommand], task.finish())
        except Exception as error:
            self._log.warning(error)
            return

        self._domain_commands = {cmd.node: cmd for cmd in commands}
        self._log.info("Received account commands: %s",
                       ", ".join(self._domain_commands.keys()))
