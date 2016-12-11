# -*- coding:utf-8 -*-
## src/common/passwords.py
##
## Copyright (C) 2006 Gustavo J. A. M. Carneiro <gjcarneiro AT gmail.com>
##                    Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2007 Jean-Marie Traissard <jim AT lapin.org>
##                    Julien Pivotto <roidelapluie AT gmail.com>
## Copyright (C) 2008 Stephan Erb <steve-e AT h3c.de>
## Copyright (c) 2009 Thorsten Glaser <t.glaser AT tarent.de>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

import os
import logging
import gi
from common import gajim

__all__ = ['get_password', 'save_password']

log = logging.getLogger('gajim.password')

if os.name == 'nt':
    try:
        import keyring
    except ImportError:
        log.debug('python-keyring missing, falling back to plaintext storage')


Secret = None

class PasswordStorage(object):
    def get_password(self, account_name):
        raise NotImplementedError
    def save_password(self, account_name, password):
        raise NotImplementedError


class SimplePasswordStorage(PasswordStorage):
    def get_password(self, account_name):
        passwd = gajim.config.get_per('accounts', account_name, 'password')
        if passwd and passwd.startswith('libsecret:'):
            # this is not a real password, it’s stored through libsecret.
            return None
        else:
            return passwd

    def save_password(self, account_name, password):
        gajim.config.set_per('accounts', account_name, 'password', password)
        if account_name in gajim.connections:
            gajim.connections[account_name].password = password


class SecretPasswordStorage(PasswordStorage):
    def __init__(self):
        self.GAJIM_SCHEMA = Secret.Schema.new("org.gnome.keyring.NetworkPassword",
            Secret.SchemaFlags.NONE,
            {
                'user': Secret.SchemaAttributeType.STRING,
                'server':  Secret.SchemaAttributeType.STRING,
                'protocol': Secret.SchemaAttributeType.STRING,
            }
        )

    def get_password(self, account_name):
        conf = gajim.config.get_per('accounts', account_name, 'password')
        if conf is None:
            return None
        if not conf.startswith('libsecret:'):
            password = conf
            ## migrate the password over to keyring
            try:
                self.save_password(account_name, password, update=False)
            except Exception:
                ## no keyring daemon: in the future, stop using it
                set_storage(SimplePasswordStorage())
            return password
        server = gajim.config.get_per('accounts', account_name, 'hostname')
        user = gajim.config.get_per('accounts', account_name, 'name')
        password = Secret.password_lookup_sync(self.GAJIM_SCHEMA, {'user': user,
            'server': server, 'protocol': 'xmpp'}, None)
        return password

    def save_password(self, account_name, password, update=True):
        server = gajim.config.get_per('accounts', account_name, 'hostname')
        user = gajim.config.get_per('accounts', account_name, 'name')
        display_name = _('XMPP account %s@%s') % (user, server)
        if password is None:
            password = str()
        attributes = {'user': user, 'server': server, 'protocol': 'xmpp'}
        Secret.password_store_sync(self.GAJIM_SCHEMA, attributes,
            Secret.COLLECTION_DEFAULT, display_name, password, None)
        gajim.config.set_per('accounts', account_name, 'password',
            'libsecret:')
        if account_name in gajim.connections:
            gajim.connections[account_name].password = password


class SecretWindowsPasswordStorage(PasswordStorage):
    """ Windows Keyring """

    def __init__(self):
        self.win_keyring = keyring.get_keyring()

    def save_password(self, account_name, password):
        self.win_keyring.set_password('gajim', account_name, password)
        gajim.config.set_per('accounts', account_name, 'password', 'winvault:')

    def get_password(self, account_name):
        log.debug('getting password')
        conf = gajim.config.get_per('accounts', account_name, 'password')
        if conf is None:
            return None
        if not conf.startswith('winvault:'):
            password = conf
            # migrate the password over to keyring
            try:
                self.save_password(account_name, password)
            except Exception:
                log.exception('error: ')
            return password
        return self.win_keyring.get_password('gajim', account_name)


storage = None
def get_storage():
    global storage
    if storage is None: # None is only in first time get_storage is called
        global Secret
        try:
            gi.require_version('Secret', '1')
            gir = __import__('gi.repository', globals(), locals(),
                ['Secret'], 0)
            Secret = gir.Secret
        except (ValueError, AttributeError):
            pass
        try:
            if os.name != 'nt':
                storage = SecretPasswordStorage()
            else:
                storage = SecretWindowsPasswordStorage()
        except Exception:
            storage = SimplePasswordStorage()
    return storage

def set_storage(storage_):
    global storage
    storage = storage_

def get_password(account_name):
    return get_storage().get_password(account_name)

def save_password(account_name, password):
    return get_storage().save_password(account_name, password)
