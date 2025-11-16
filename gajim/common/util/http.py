# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only


import binascii
import logging

from gajim.common.aes import AESKeyData

log = logging.getLogger("gajim.c.util.http")


def get_aes_key_data(fragment_string: str) -> AESKeyData:
    if not fragment_string:
        raise ValueError("Invalid fragment")

    fragment = binascii.unhexlify(fragment_string)
    size = len(fragment)
    # Clients started out with using a 16 byte IV but long term
    # want to switch to the more performant 12 byte IV
    # We have to support both
    if size == 48:
        key = fragment[16:]
        iv = fragment[:16]
    elif size == 44:
        key = fragment[12:]
        iv = fragment[:12]
    else:
        raise ValueError("Invalid fragment size: %s" % size)

    return AESKeyData(key, iv)
