# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# XEP-0083: Nested Roster Groups

from __future__ import annotations

from collections.abc import Generator

from nbxmpp.errors import is_error

from gajim.common import types
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import as_task


class Delimiter(BaseModule):

    _nbxmpp_extends = 'Delimiter'
    _nbxmpp_methods = [
        'request_delimiter',
        'set_delimiter'
    ]

    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)
        self.available = False
        self.delimiter = '::'

    @as_task
    def get_roster_delimiter(self) -> Generator[str | None, None, None]:
        _task = yield  # noqa: F841

        delimiter = yield self.request_delimiter()
        if is_error(delimiter) or delimiter is None:
            result = yield self.set_delimiter(self.delimiter)
            if is_error(result):
                self._con.connect_machine()
                return

            delimiter = self.delimiter

        self.delimiter = delimiter
        self.available = True
        self._con.connect_machine()
