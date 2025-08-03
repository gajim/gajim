# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import random

from nbxmpp.const import Affiliation
from nbxmpp.const import Role
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common import types
from gajim.common.const import CONSONANTS
from gajim.common.const import VOWELS


def is_affiliation_change_allowed(
    self_contact: types.GroupchatParticipant,
    contact: types.GroupchatParticipant,
    target_aff: str | Affiliation,
) -> bool:
    if isinstance(target_aff, str):
        target_aff = Affiliation(target_aff)

    if contact.affiliation == target_aff:
        # Contact has already the target affiliation
        return False

    if self_contact.affiliation.is_owner:
        return True

    if not self_contact.affiliation.is_admin:
        return False

    if target_aff in (Affiliation.OWNER, Affiliation.ADMIN):
        # Admin can’t edit admin/owner list
        return False

    return self_contact.affiliation > contact.affiliation


def is_role_change_allowed(
    self_contact: types.GroupchatParticipant, contact: types.GroupchatParticipant
) -> bool:

    if self_contact.role < Role.MODERATOR:
        return False
    return self_contact.affiliation >= contact.affiliation


def is_moderation_allowed(
    self_contact: types.GroupchatParticipant
) -> bool:

    return self_contact.role >= Role.MODERATOR


def get_default_muc_config() -> dict[str, bool | str]:
    return {
        # XEP-0045 options
        # https://xmpp.org/registrar/formtypes.html
        'muc#roomconfig_allowinvites': True,
        'muc#roomconfig_allowpm': 'anyone',
        'muc#roomconfig_changesubject': False,
        'muc#roomconfig_enablelogging': False,
        'muc#roomconfig_membersonly': True,
        'muc#roomconfig_moderatedroom': False,
        'muc#roomconfig_passwordprotectedroom': False,
        'muc#roomconfig_persistentroom': True,
        'muc#roomconfig_publicroom': False,
        'muc#roomconfig_whois': 'moderators',
        # Ejabberd options
        'allow_voice_requests': False,
        'public_list': False,
        'mam': True,
        # Prosody options
        '{http://prosody.im/protocol/muc}roomconfig_allowmemberinvites': False,
        'muc#roomconfig_enablearchiving': True,
    }


def get_random_muc_localpart() -> str:
    rand = random.randrange(4)
    is_vowel = bool(random.getrandbits(1))
    result = ''
    for _n in range(rand * 2 + (5 - rand)):
        if is_vowel:
            result = f'{result}{VOWELS[random.randrange(len(VOWELS))]}'
        else:
            result = f'{result}{CONSONANTS[random.randrange(len(CONSONANTS))]}'
        is_vowel = not is_vowel
    return result


def message_needs_highlight(text: str, nickname: str, own_jid: str) -> bool:
    '''
    Check whether 'text' contains 'nickname', 'own_jid', or any string of the
    'muc_highlight_words' setting.
    '''

    search_strings = app.settings.get('muc_highlight_words').split(';')
    search_strings.append(nickname)
    search_strings.append(own_jid)

    search_strings = [word.lower() for word in search_strings if word]
    text = text.lower()

    for search_string in search_strings:
        match = text.find(search_string)

        while match > -1:
            search_end = match + len(search_string)

            if match == 0 and search_end == len(text):
                # Text contains search_string only (exact match)
                return True

            # Exclude some characters preceding the match:
            # - any alpha chars
            # - / which may be commands
            # - - which may connect multiple words
            # - ' which may be part of a contraction, such as o'clock, 'tis
            excluded_chars = ('/', '-', '\'')

            char_before = text[match - 1]
            char_before_allowed = bool(
                match == 0
                or (not char_before.isalpha() and char_before not in excluded_chars)
            )

            if char_before_allowed and search_end == len(text):
                # search_string found at the end of text and
                # char before search_string is allowed.
                return True

            if char_before_allowed and not text[search_end].isalpha():
                # char_before search_string is allowed and
                # char_after search_string is not alpha.
                return True

            start = match + 1
            match = text.find(search_string, start)

    return False


def get_groupchat_name(client: types.Client, jid: JID) -> str:
    name = client.get_module('Bookmarks').get_name_from_bookmark(jid)
    if name:
        return name

    disco_info = app.storage.cache.get_last_disco_info(jid)
    if disco_info is not None:
        if disco_info.muc_name:
            return disco_info.muc_name

    assert jid.localpart is not None
    return jid.localpart


def get_group_chat_nick(account: str, room_jid: JID | str) -> str:
    client = app.get_client(account)

    bookmark = client.get_module('Bookmarks').get_bookmark(room_jid)
    if bookmark is not None:
        if bookmark.nick is not None:
            return bookmark.nick

    return app.nicks[account]
