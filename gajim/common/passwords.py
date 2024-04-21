# Copyright (C) 2006 Gustavo J. A. M. Carneiro <gjcarneiro AT gmail.com>
#                    Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2007 Jean-Marie Traissard <jim AT lapin.org>
#                    Julien Pivotto <roidelapluie AT gmail.com>
# Copyright (C) 2008 Stephan Erb <steve-e AT h3c.de>
# Copyright (c) 2009 Thorsten Glaser <t.glaser AT tarent.de>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import cast

import logging

import keyring

from gajim.common import app
from gajim.common.helpers import package_version

__all__ = [
    'init',
    'is_keyring_available',
    'get_password',
    'save_password',
    'delete_password'
]

log = logging.getLogger('gajim.c.passwords')


class Interface:
    def __init__(self):
        self.backend = cast(keyring.backend.KeyringBackend, None)
        self._is_keyring_available = False

    @property
    def is_keyring_available(self):
        return self._is_keyring_available

    def init(self) -> None:
        backends = keyring.backend.get_all_keyring()
        for backend in backends:
            log.info('Found keyring backend: %s', backend)

        if (app.settings.get('enable_keepassxc_integration') and
                package_version('keyring>=23.8.1')):
            _keyring = keyring.get_keyring()
            self.backend = _keyring.with_properties(scheme='KeePassXC')
        else:
            self.backend = keyring.get_keyring()
        log.info('Select %s backend', self.backend)

        self._is_keyring_available = keyring.core.recommended(self.backend)


class SecretPasswordStorage:
    '''
    Store password using Keyring
    '''

    @staticmethod
    def save_password(account_name: str, password: str) -> bool:
        if not is_keyring_available():
            log.warning('No recommended keyring backend available.'
                        'Passwords cannot be stored.')
            return False

        account_jid = app.get_jid_from_account(account_name)

        try:
            log.info('Save password to keyring')
            _interface.backend.set_password('gajim', account_jid, password)
            return True
        except Exception:
            log.exception('Save password failed')
            return False

    @staticmethod
    def get_password(account_name: str) -> str | None:
        if not is_keyring_available():
            return

        log.info('Request password from keyring')

        account_jid = app.get_jid_from_account(account_name)

        try:
            # For security reasons remove clear-text password
            ConfigPasswordStorage.delete_password(account_name)
            password = _interface.backend.get_password('gajim', account_jid)
        except Exception:
            log.exception('Request password failed')
            return

        if password is not None:
            return password

        # Migration from account name to account jid
        try:
            password = _interface.backend.get_password('gajim', account_name)
        except Exception:
            log.exception('Request password failed')
            return

        if password is not None:
            result = SecretPasswordStorage.save_password(account_name, password)
            if not result:
                log.error('Password migration failed')

        return password

    @staticmethod
    def delete_password(account_name: str) -> None:
        if not is_keyring_available():
            return

        log.info('Remove password from keyring')

        account_jid = app.get_jid_from_account(account_name)

        keyring_errors = (
            keyring.errors.PasswordDeleteError,
            keyring.errors.InitError
        )
        try:
            _interface.backend.delete_password('gajim', account_name)
        except keyring_errors:
            pass

        try:
            return _interface.backend.delete_password('gajim', account_jid)
        except keyring_errors as error:
            log.warning('Removing password failed: %s', error)
        except Exception:
            log.exception('Removing password failed')


class ConfigPasswordStorage:
    '''
    Store password directly in Gajim's config
    '''

    @staticmethod
    def get_password(account_name: str) -> str:
        return app.settings.get_account_setting(account_name, 'password')

    @staticmethod
    def save_password(account_name: str, password: str) -> bool:
        app.settings.set_account_setting(account_name, 'password', password)
        return True

    @staticmethod
    def delete_password(account_name: str) -> None:
        app.settings.set_account_setting(account_name, 'password', '')


class MemoryPasswordStorage:
    '''
    Store password in memory
    '''

    _passwords: dict[str, str] = {}

    def get_password(self, account_name: str) -> str:
        return self._passwords.get(account_name, '')

    def save_password(self, account_name: str, password: str) -> bool:
        self._passwords[account_name] = password
        return True

    def delete_password(self, account_name: str) -> None:
        self._passwords[account_name] = ''


def init() -> None:
    _interface.init()


def is_keyring_available() -> bool:
    return _interface.is_keyring_available


def get_password(account_name: str) -> str | None:
    if not app.settings.get_account_setting(account_name, 'savepass'):
        return MemoryPasswordStorage().get_password(account_name)

    if app.settings.get('use_keyring'):
        return SecretPasswordStorage.get_password(account_name)
    return ConfigPasswordStorage.get_password(account_name)


def save_password(account_name: str, password: str) -> bool:
    if not app.settings.get_account_setting(account_name, 'savepass'):
        return MemoryPasswordStorage().save_password(account_name, password)

    if app.settings.get('use_keyring'):
        return SecretPasswordStorage.save_password(account_name, password)
    return ConfigPasswordStorage.save_password(account_name, password)


def delete_password(account_name: str) -> None:
    if app.settings.get('use_keyring'):
        return SecretPasswordStorage.delete_password(account_name)
    return ConfigPasswordStorage.delete_password(account_name)


_interface = Interface()
