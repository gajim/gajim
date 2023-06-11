# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# All XEPs that don’t need their own module


import logging

from nbxmpp.structs import MessageProperties

from gajim.common.storage.archive import models as mod

log = logging.getLogger('gajim.c.m.misc')


# XEP-0066: Out of Band Data
def parse_oob(properties: MessageProperties) -> list[mod.OOB]:
    if not properties.is_oob:
        return []

    assert properties.oob is not None

    return [
        mod.OOB(
        url=properties.oob.url,
        description=properties.oob.desc)
    ]
