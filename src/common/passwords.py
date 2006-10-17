##
## Copyright (C) 2006 Gustavo J. A. M. Carneiro <gjcarneiro@gmail.com>
## Copyright (C) 2006 Nikos Kouremenos <kourem@gmail.com>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 2 only.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##

__all__ = ['get_password', 'save_password']

import gobject

from common import gajim

try:
	import gnomekeyring
except ImportError:
	USER_HAS_GNOMEKEYRING = False
else:
	USER_HAS_GNOMEKEYRING = True

class PasswordStorage(object):
	def get_password(self, account_name):
		raise NotImplementedError
	def save_password(self, account_name, password):
		raise NotImplementedError
	

class SimplePasswordStorage(PasswordStorage):
	def get_password(self, account_name):
		return gajim.config.get_per('accounts', account_name, 'password')

	def save_password(self, account_name, password):
		gajim.config.set_per('accounts', account_name, 'password', password)
		gajim.connections[account_name].password = password


class GnomePasswordStorage(PasswordStorage):
	def __init__(self):
		self.keyring = gnomekeyring.get_default_keyring_sync()

	def get_password(self, account_name):
		conf = gajim.config.get_per('accounts', account_name, 'password')
		if conf is None:
			return None
		try:
			unused, auth_token = conf.split('gnomekeyring:')
			auth_token = int(auth_token)
		except ValueError:
			password = conf
			## migrate the password over to keyring
			try:
				self.save_password(account_name, password, update=False)
			except gnomekeyring.NoKeyringDaemonError:
				## no keyring daemon: in the future, stop using it
				set_storage(SimplePasswordStorage())
			return password
		try:
			return gnomekeyring.item_get_info_sync(self.keyring,
				auth_token).get_secret()
		except gnomekeyring.DeniedError:
			return None
		except gnomekeyring.NoKeyringDaemonError:
			## no keyring daemon: in the future, stop using it
			set_storage(SimplePasswordStorage())
			return None
		
	def save_password(self, account_name, password, update=True):
		display_name = _('Gajim account %s') % account_name
		attributes = dict(account_name=str(account_name), gajim=1)
		auth_token = gnomekeyring.item_create_sync(
			self.keyring, gnomekeyring.ITEM_GENERIC_SECRET,
			display_name, attributes, password, update)
		token = 'gnomekeyring:%i' % auth_token
		gajim.config.set_per('accounts', account_name, 'password', token)


storage = None
def get_storage():
	global storage
	if storage is None: # None is only in first time get_storage is called
		if USER_HAS_GNOMEKEYRING and gnomekeyring.is_available():
			try:
				storage = GnomePasswordStorage()
			except gnomekeyring.NoKeyringDaemonError:
				storage = SimplePasswordStorage()
		else:
			storage = SimplePasswordStorage()
	return storage

def set_storage(storage_):
	global storage
	assert isinstance(storage, PasswordStorage)
	storage = storage_


def get_password(account_name):
	return get_storage().get_password(account_name)

def save_password(account_name, password):
	return get_storage().save_password(account_name, password)
