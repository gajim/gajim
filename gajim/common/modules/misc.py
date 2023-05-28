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
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

# All XEPs that don’t need their own module


import logging

from nbxmpp.structs import MessageProperties

from gajim.common.helpers import AdditionalDataDict
from gajim.common.i18n import get_rfc5646_lang

log = logging.getLogger('gajim.c.m.misc')


# XEP-0066: Out of Band Data
def parse_oob(properties: MessageProperties,
              additional_data: AdditionalDataDict
              ) -> None:
    if not properties.is_oob:
        return

    assert properties.oob is not None
    additional_data.set_value('gajim', 'oob_url', properties.oob.url)
    if properties.oob.desc is not None:
        additional_data.set_value('gajim', 'oob_desc',
                                  properties.oob.desc)


# XEP-0308: Last Message Correction
def parse_correction(properties: MessageProperties) -> str | None:
    if not properties.is_correction:
        return None
    assert properties.correction is not None
    return properties.correction.id


# XEP-0071: XHTML-IM
def parse_xhtml(properties: MessageProperties,
                additional_data: AdditionalDataDict
                ) -> None:
    if not properties.has_xhtml:
        return

    assert properties.xhtml is not None
    body = properties.xhtml.get_body(get_rfc5646_lang())
    additional_data.set_value('gajim', 'xhtml', body)
