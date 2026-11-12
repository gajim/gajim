# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

# macOS quarantine for files received from the network. Gatekeeper only
# checks downloaded apps and scripts on first launch if they are
# quarantined, and Finder passes the quarantine on when extracting
# archives. Browsers quarantine every download; Gajim has to do the same.
#
# The quarantine is set through the documented API (the quarantine
# properties of NSURL), not by writing the com.apple.quarantine extended
# attribute directly, which Apple does not consider API. Only the agent name
# and the download type are set: no origin or data URL.

from __future__ import annotations

from typing import Any

import logging
import sys
from pathlib import Path

log = logging.getLogger("gajim.c.util.quarantine")

# Keys and values of the quarantine properties (LSQuarantine.h)
QUARANTINE_AGENT_NAME_KEY = "LSQuarantineAgentName"
QUARANTINE_TYPE_KEY = "LSQuarantineType"
QUARANTINE_TYPE_WEB_DOWNLOAD = "LSQuarantineTypeWebDownload"


def get_quarantine_properties(path: Path) -> dict[str, Any] | None:
    """Return the quarantine properties of a file, None if it has none (macOS only)"""
    if sys.platform != "darwin":
        return None

    from Foundation import NSURL
    from Foundation import NSURLQuarantinePropertiesKey

    url = NSURL.fileURLWithPath_(str(path))
    ok, value, error = url.getResourceValue_forKey_error_(
        None, NSURLQuarantinePropertiesKey, None
    )
    if not ok:
        raise OSError(f"{path}: {error}")
    if value is None:
        return None
    return dict(value)


def _set_properties(path: Path, properties: dict[str, Any]) -> None:
    from Foundation import NSURL
    from Foundation import NSURLQuarantinePropertiesKey

    url = NSURL.fileURLWithPath_(str(path))
    ok, error = url.setResourceValue_forKey_error_(
        properties, NSURLQuarantinePropertiesKey, None
    )
    if not ok:
        raise OSError(f"{path}: {error}")


def set_quarantine(path: Path) -> None:
    """Mark a file received from the network as downloaded (macOS only)"""
    if sys.platform != "darwin":
        return

    properties = {
        QUARANTINE_AGENT_NAME_KEY: "Gajim",
        QUARANTINE_TYPE_KEY: QUARANTINE_TYPE_WEB_DOWNLOAD,
    }
    try:
        _set_properties(path, properties)
    except OSError as error:
        log.warning("Could not quarantine %s: %s", path, error)


def copy_quarantine(src: Path, dst: Path) -> None:
    """Pass the quarantine of src on to its copy dst (macOS only)"""
    if sys.platform != "darwin":
        return

    try:
        properties = get_quarantine_properties(src)
        if properties is not None:
            _set_properties(dst, properties)
    except OSError as error:
        log.warning("Could not copy quarantine to %s: %s", dst, error)
