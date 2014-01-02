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

__all__ = ['get_password', 'save_password']

import warnings
from common import gajim
from common import kwalletbinding
from common.exceptions import GnomeKeyringError

USER_HAS_GNOMEKEYRING = False
USER_USES_GNOMEKEYRING = False
USER_HAS_KWALLETCLI = False
GnomeKeyring = None

class PasswordStorage(object):
    def get_password(self, account_name):
        raise NotImplementedError
    def save_password(self, account_name, password):
        raise NotImplementedError


class SimplePasswordStorage(PasswordStorage):
    def get_password(self, account_name):
        passwd = gajim.config.get_per('accounts', account_name, 'password')
        if passwd and (passwd.startswith('gnomekeyring:') or \
         passwd == '<kwallet>'):
            # this is not a real password, it's either a gnome
            # keyring token or stored in the KDE wallet
            return None
        else:
            return passwd

    def save_password(self, account_name, password):
        gajim.config.set_per('accounts', account_name, 'password', password)
        if account_name in gajim.connections:
            gajim.connections[account_name].password = password


class GnomePasswordStorage(PasswordStorage):
    def __init__(self):
        (err, self.keyring) = GnomeKeyring.get_default_keyring_sync()
        if err  != GnomeKeyring.Result.OK:
            raise GnomeKeyringError(err)
        if self.keyring is None:
            self.keyring = 'login'
        err = GnomeKeyring.create_sync(self.keyring, None)
        if err not in (GnomeKeyring.Result.OK,
        GnomeKeyring.Result.KEYRING_ALREADY_EXISTS):
            raise GnomeKeyringError(err)

    def get_password(self, account_name):
        conf = gajim.config.get_per('accounts', account_name, 'password')
        if conf is None or conf == '<kwallet>':
            return None
        if not conf.startswith('gnomekeyring:'):
            password = conf
            ## migrate the password over to keyring
            try:
                self.save_password(account_name, password, update=False)
            except GnomeKeyringError as e:
                if e.error == GnomeKeyring.Result.NO_KEYRING_DAEMON:
                    ## no keyring daemon: in the future, stop using it
                    set_storage(SimplePasswordStorage())
            return password
        server = gajim.config.get_per('accounts', account_name, 'hostname')
        user = gajim.config.get_per('accounts', account_name, 'name')
        attributes1 = GnomeKeyring.attribute_list_new()
        GnomeKeyring.attribute_list_append_string(attributes1, 'server',
            str(server))
        GnomeKeyring.attribute_list_append_string(attributes1, 'user',
            str(user))
        GnomeKeyring.attribute_list_append_string(attributes1, 'protocol',
            'xmpp')
        attributes2 = GnomeKeyring.attribute_list_new()
        GnomeKeyring.attribute_list_append_string(attributes2, 'account_name',
            str(account_name))
        GnomeKeyring.attribute_list_append_string(attributes2, 'gajim',
            '1')
        (err, items) = GnomeKeyring.find_items_sync(
            GnomeKeyring.ItemType.NETWORK_PASSWORD, attributes1)
        if err != GnomeKeyring.Result.OK:
            (err, items) = GnomeKeyring.find_items_sync(
                GnomeKeyring.ItemType.GENERIC_SECRET, attributes2)
            if err == GnomeKeyring.Result.OK and len(items) > 0:
                password = items[0].secret
                self.save_password(account_name, password)
                for item in items:
                    GnomeKeyring.item_delete_sync(item.keyring,
                        int(item.item_id))
            else:
                items = []
        if len(items) > 1:
            warnings.warn("multiple gnome keyring items found for account %s;"
                " trying to use the first one..." % account_name)
        if items:
            return items[0].secret
        else:
            return None
        if err == GnomeKeyring.Result.NO_KEYRING_DAEMON:
            ## no keyring daemon: in the future, stop using it
            set_storage(SimplePasswordStorage())
        return None

    def save_password(self, account_name, password, update=True):
        server = gajim.config.get_per('accounts', account_name, 'hostname')
        user = gajim.config.get_per('accounts', account_name, 'name')
        display_name = _('XMPP account %s@%s') % (user, server)
        attributes1 = GnomeKeyring.attribute_list_new()
        GnomeKeyring.attribute_list_append_string(attributes1, 'server',
            str(server))
        GnomeKeyring.attribute_list_append_string(attributes1, 'user',
            str(user))
        GnomeKeyring.attribute_list_append_string(attributes1, 'protocol',
            'xmpp')
        if password is None:
            password = str()
        (err, auth_token) = GnomeKeyring.item_create_sync(self.keyring,
            GnomeKeyring.ItemType.NETWORK_PASSWORD, display_name, attributes1,
            password, update)
        if err != GnomeKeyring.Result.OK:
            if err in (GnomeKeyring.Result.DENIED,
            GnomeKeyring.Result.CANCELLED):
                set_storage(SimplePasswordStorage())
                storage.save_password(account_name, password)
                return
            else:
                raise GnomeKeyringError(err)
        gajim.config.set_per('accounts', account_name, 'password',
            'gnomekeyring:')
        if account_name in gajim.connections:
            gajim.connections[account_name].password = password

class KWalletPasswordStorage(PasswordStorage):
    def get_password(self, account_name):
        pw = gajim.config.get_per('accounts', account_name, 'password')
        if not pw or pw.startswith('gnomekeyring:'):
            # unset, empty or not ours
            return None
        if pw != '<kwallet>':
            # migrate the password
            if kwalletbinding.kwallet_put('gajim', account_name, pw):
                gajim.config.set_per('accounts', account_name, 'password',
                 '<kwallet>')
            else:
                # stop using the KDE Wallet
                set_storage(SimplePasswordStorage())
            return pw
        pw = kwalletbinding.kwallet_get('gajim', account_name)
        if pw is None:
            # stop using the KDE Wallet
            set_storage(SimplePasswordStorage())
        if not pw:
            # False, None, or the empty string
            return None
        return pw

    def save_password(self, account_name, password):
        if not kwalletbinding.kwallet_put('gajim', account_name, password):
            # stop using the KDE Wallet
            set_storage(SimplePasswordStorage())
            storage.save_password(account_name, password)
            return
        pwtoken = '<kwallet>'
        if not password:
            # no sense in looking up the empty string in the KWallet
            pwtoken = ''
        gajim.config.set_per('accounts', account_name, 'password', pwtoken)
        if account_name in gajim.connections:
            gajim.connections[account_name].password = password


storage = None
def get_storage():
    global storage
    if storage is None: # None is only in first time get_storage is called
        if gajim.config.get('use_gnomekeyring'):
            global GnomeKeyring
            try:
                gir = __import__('gi.repository', globals(), locals(),
                    ['GnomeKeyring'], 0)
                GnomeKeyring = gir.GnomeKeyring
            except (ImportError, AttributeError):
                pass
            else:
                global USER_HAS_GNOMEKEYRING
                global USER_USES_GNOMEKEYRING
                USER_HAS_GNOMEKEYRING = True
                if GnomeKeyring.is_available():
                    USER_USES_GNOMEKEYRING = True
                else:
                    USER_USES_GNOMEKEYRING = False
        if USER_USES_GNOMEKEYRING:
            try:
                storage = GnomePasswordStorage()
            except GnomeKeyringError:
                storage = None
        if storage is None:
            if gajim.config.get('use_kwalletcli'):
                global USER_HAS_KWALLETCLI
                if kwalletbinding.kwallet_available():
                    USER_HAS_KWALLETCLI = True
                if USER_HAS_KWALLETCLI:
                    storage = KWalletPasswordStorage()
        if storage is None:
            storage = SimplePasswordStorage()
    return storage

def set_storage(storage_):
    global storage
    storage = storage_


def get_password(account_name):
    return get_storage().get_password(account_name)

def save_password(account_name, password):
    return get_storage().save_password(account_name, password)
