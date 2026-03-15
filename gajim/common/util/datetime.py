# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import datetime as dt

from gi.repository import GLib
from nbxmpp.modules.vcard4 import TzProperty
from nbxmpp.modules.vcard4 import VCard

from gajim.common.iana import ZONE_DATA

FIRST_UTC_DATETIME = dt.datetime(1970, 1, 1, tzinfo=dt.UTC)
FIRST_LOCAL_DATETIME = FIRST_UTC_DATETIME.astimezone()


def convert_epoch_to_local_datetime(utc_timestamp: float) -> dt.datetime:
    utc = dt.datetime.fromtimestamp(utc_timestamp, tz=dt.UTC)
    return utc.astimezone()


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def get_start_of_day(datetime: dt.datetime) -> dt.datetime:
    return datetime.replace(hour=0, minute=0, second=0, microsecond=0)


def get_local_timezone() -> str | None:
    timezone = GLib.TimeZone.new_local().get_identifier() or None
    if timezone not in ZONE_DATA:
        return None
    return timezone


def get_timezone_from_vcard(vcard: VCard) -> str | None:
    for prop in vcard.get_properties():
        match prop:
            case TzProperty():
                return prop.value or None

            case _:
                pass
