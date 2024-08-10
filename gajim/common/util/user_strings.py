# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

import datetime as dt
from string import Template

from nbxmpp.const import Affiliation
from nbxmpp.const import Chatstate
from nbxmpp.const import Role
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.i18n import ngettext
from gajim.common.i18n import p_


def format_idle_time(idle_time: dt.datetime) -> str:
    now = dt.datetime.now(dt.timezone.utc)

    now_date = now.date()
    idle_date = idle_time.date()

    if idle_date == now_date:
        return idle_time.strftime(app.settings.get('time_format'))
    if idle_date == now_date - dt.timedelta(days=1):
        return _('Yesterday (%s)') % idle_time.strftime(app.settings.get('time_format'))
    if idle_date >= now_date - dt.timedelta(days=6):
        return idle_time.strftime(f'%a {app.settings.get("time_format")}')

    return idle_date.strftime(app.settings.get('date_format'))


def get_subscription_request_msg(account: str | None = None) -> str:
    if account is None:
        return _('I would like to add you to my contact list.')

    message = app.settings.get_account_setting(account, 'subscription_request_msg')
    if message:
        return message

    message = _('Hello, I am $name. %s') % message
    return Template(message).safe_substitute({'name': app.nicks[account]})


def get_moderation_text(by: str | JID | None, reason: str | None) -> str:
    by_text = ''
    if by is not None:
        by_text = _(' by %s') % by
    text = _('This message has been moderated%s.') % by_text
    if reason is not None:
        text += ' ' + _('Reason: %s') % reason
    return text


def get_uf_sub(sub: str) -> str:
    if sub == 'none':
        return p_('Contact subscription', 'None')

    if sub == 'to':
        return p_('Contact subscription', 'To')

    if sub == 'from':
        return p_('Contact subscription', 'From')

    if sub == 'both':
        return p_('Contact subscription', 'Both')

    return p_('Contact subscription', 'Unknown')


def get_uf_ask(ask: str | None) -> str:
    if ask is None:
        return p_('Contact subscription', 'None')

    if ask == 'subscribe':
        return p_('Contact subscription', 'Subscribe')

    return ask


def get_uf_role(role: Role | str, plural: bool = False) -> str:
    '''plural determines if you get Moderators or Moderator'''
    if not isinstance(role, str):
        role = role.value

    if role == 'none':
        return p_('Group chat contact role', 'None')
    if role == 'moderator':
        if plural:
            return p_('Group chat contact role', 'Moderators')
        return p_('Group chat contact role', 'Moderator')
    if role == 'participant':
        if plural:
            return p_('Group chat contact role', 'Participants')
        return p_('Group chat contact role', 'Participant')
    if role == 'visitor':
        if plural:
            return p_('Group chat contact role', 'Visitors')
        return p_('Group chat contact role', 'Visitor')
    return ''


def get_uf_affiliation(affiliation: Affiliation | str, plural: bool = False) -> str:
    '''Get a nice and translated affilition for muc'''
    if not isinstance(affiliation, str):
        affiliation = affiliation.value

    if affiliation == 'none':
        return p_('Group chat contact affiliation', 'None')
    if affiliation == 'owner':
        if plural:
            return p_('Group chat contact affiliation', 'Owners')
        return p_('Group chat contact affiliation', 'Owner')
    if affiliation == 'admin':
        if plural:
            return p_('Group chat contact affiliation', 'Administrators')
        return p_('Group chat contact affiliation', 'Administrator')
    if affiliation == 'member':
        if plural:
            return p_('Group chat contact affiliation', 'Members')
        return p_('Group chat contact affiliation', 'Member')
    return ''


def get_uf_relative_time(date_time: dt.datetime, now: dt.datetime | None = None) -> str:
    if now is None:  # used by unittest
        now = dt.datetime.now()
    timespan = now - date_time

    if timespan < dt.timedelta(minutes=1):
        return _('Just now')
    if timespan < dt.timedelta(minutes=15):
        minutes = int(timespan.seconds / 60)
        return ngettext(
            '%s min ago', '%s mins ago', minutes, str(minutes), str(minutes)
        )
    today = now.date()
    if date_time.date() == today:
        format_string = app.settings.get('time_format')
        return date_time.strftime(format_string)
    yesterday = now.date() - dt.timedelta(days=1)
    if date_time.date() == yesterday:
        return _('Yesterday')
    if timespan < dt.timedelta(days=7):  # this week
        return date_time.strftime('%a')  # weekday
    if timespan < dt.timedelta(days=365):  # this year
        return date_time.strftime('%b %d')
    return str(date_time.year)


def chatstate_to_string(chatstate: Chatstate | None) -> str:
    if chatstate is None:
        return ''

    if chatstate == Chatstate.ACTIVE:
        return ''

    if chatstate == Chatstate.COMPOSING:
        return _('is composing a message…')

    if chatstate in (Chatstate.INACTIVE, Chatstate.GONE):
        return _('is doing something else')

    if chatstate == Chatstate.PAUSED:
        return _('paused composing a message')

    raise ValueError(f'unknown value: {chatstate}')
