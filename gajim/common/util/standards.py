# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gajim.common.const import RFC5646_LANGUAGE_TAGS
from gajim.common.i18n import get_default_lang


def get_rfc5646_lang() -> str:
    lang = get_default_lang()
    lang = lang.replace("_", "-")
    return lang if lang in RFC5646_LANGUAGE_TAGS else "en"
