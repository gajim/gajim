# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import Literal

from gajim.common import app
from gajim.common.const import SHOW_LIST
from gajim.common.const import SHOW_STRING
from gajim.common.const import SHOW_STRING_MNEMONIC


def get_client_status(account: str) -> str:
    client = app.get_client(account)
    if client.state.is_disconnected:
        return 'offline'

    if (
        client.state.is_reconnect_scheduled
        or client.state.is_connecting
        or client.state.is_connected
    ):
        return 'connecting'

    return client.status


def get_global_show() -> str:
    maxi = 0
    for client in app.get_clients():
        if not app.settings.get_account_setting(
            client.account, 'sync_with_global_status'
        ):
            continue
        status = get_client_status(client.account)
        index = SHOW_LIST.index(status)
        if index > maxi:
            maxi = index
    return SHOW_LIST[maxi]


def get_global_status_message() -> str:
    maxi = 0
    status_message = ''
    for client in app.get_clients():
        if not app.settings.get_account_setting(
            client.account, 'sync_with_global_status'
        ):
            continue
        index = SHOW_LIST.index(client.status)
        if index > maxi:
            maxi = index
            status_message = client.status_message
    return status_message


def statuses_unified() -> bool:
    '''
    Test if all statuses are the same
    '''
    reference = None
    for client in app.get_clients():
        account = client.account
        if not app.settings.get_account_setting(account, 'sync_with_global_status'):
            continue

        if reference is None:
            reference = get_client_status(account)

        elif reference != get_client_status(account):
            return False
    return True


def get_uf_show(show: str, use_mnemonic: bool = False) -> str:
    if use_mnemonic:
        return SHOW_STRING_MNEMONIC[show]
    return SHOW_STRING[show]


def get_idle_status_message(
    state: Literal['away'] | Literal['xa'], status_message: str
) -> str:
    if state == 'away':
        message = app.settings.get('autoaway_message')
        idle_time = app.settings.get('autoawaytime')
    else:
        message = app.settings.get('autoxa_message')
        idle_time = app.settings.get('autoxatime')

    if not message:
        return status_message

    message = message.replace('$S', '%(status)s')
    message = message.replace('$T', '%(time)s')

    return message % {'status': status_message, 'time': idle_time}
