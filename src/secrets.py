from common.configpaths import gajimpaths

from common import crypto
from common import exceptions

import dialogs

import os
import pickle

import gtk

secrets_filename = gajimpaths['SECRETS_FILE']
secrets_cache = None

class Secrets:
	def __init__(self, filename):
		self.filename = filename
		self.srs = {}
		self.pubkeys = {}
		self.privkeys = {}

	def cancel(self):
		raise exceptions.Cancelled

	def save(self):
		pickle.dumps(self)

		f = open(secrets_filename, 'w')
		f.write(pickle.dumps(self))
		f.close()

	def retained_secrets(self, account, bare_jid):
		try:
			return self.srs[account][bare_jid]
		except KeyError:
			return []

	# retained secrets are stored as a tuple of the secret and whether the user 
	# has verified it
	def save_new_srs(self, account, jid, secret, verified):
		if not account in self.srs:
			self.srs[account] = {}

		if not jid in self.srs[account]:
			self.srs[account][jid] = []

		self.srs[account][jid].append((secret, verified))

		self.save()

	def find_srs(self, account, jid, srs):
		our_secrets = self.srs[account][jid]
		return filter(lambda (x,y): x == srs, our_secrets)[0]

	# has the user verified this retained secret?
	def srs_verified(self, account, jid, srs):
		return self.find_srs(account, jid, srs)[1]

	def replace_srs(self, account, jid, old_secret, new_secret, verified):
		our_secrets = self.srs[account][jid]

		idx = our_secrets.index(self.find_srs(account, jid, old_secret))

		our_secrets[idx] = (new_secret, verified)

		self.save()

	# the public key associated with 'account'
	def my_pubkey(self, account):
		try:
			pk = self.privkeys[account]
		except KeyError:
			pk = Crypto.PublicKey.RSA.generate(384, crypto.random_bytes)

			self.privkeys[account] = pk
			self.save()

		return pk

def load_secrets(filename):
	f = open(filename, 'r')

	try:
		secrets = pickle.loads(f.read())
	except KeyError:
		f.close()
		secrets = Secrets(filename)

	return secrets

def secrets():
	global secrets_cache

	if secrets_cache:
		return secrets_cache

	if os.path.exists(secrets_filename):
		secrets_cache = load_secrets(secrets_filename)
	else:
		secrets_cache = Secrets(secrets_filename)

	return secrets_cache
