# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import sys
from types import TracebackType
from unittest.mock import MagicMock

from gajim.common import app

from gajim.gtk.exception import ExceptionDialog

from . import util


def _create_traceback(message: str) -> TracebackType | None:
    tb = None
    depth = 0
    while True:
        try:
            frame = sys._getframe(depth)  # type: ignore
            depth += 1
        except ValueError as _exc:
            break

        tb = TracebackType(tb, frame, frame.f_lasti, frame.f_lineno)

    return tb


tb = _create_traceback("Test")
assert isinstance(tb, TracebackType)

util.init_settings()

app.is_installed = MagicMock(return_value=True)

window = ExceptionDialog(BaseException, Exception(), tb)
window.show()

util.run_app()
