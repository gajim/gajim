from common.configpaths import gajimpaths

from common import crypto
from common import exceptions

import dialogs

import os
import pickle

import gtk

import Crypto.Cipher.AES
import Crypto.Hash.SHA256
import Crypto.PublicKey.RSA

secrets_filename = gajimpaths['SECRETS_FILE']
secrets_cache = None

secrets_cipher = None
secrets_counter = None

# strength of the encryption used on SECRETS_FILE
n = 256

class Counter:
	def __init__(self, n, iv):
		self.n = n
		self.c = crypto.decode_mpi(iv)

	def __call__(self):
		self.c = (self.c + 1) % (2 ** self.n)
		return crypto.encode_mpi_with_padding(self.c)

# return en/decrypter if it's cached, otherwise create it from the user's 
# passphrase
def get_key(counter, passph=None):
	global secrets_cipher, secrets_counter

	if secrets_cipher:
		return secrets_cipher

	if not passph:
		passph, checked = dialogs.PassphraseDialog(_('Passphrase Required'),
			_('To continue, Gajim needs to access your stored secrets. Enter your passphrase')
			).run()

		if passph == -1:
			raise exceptions.Cancelled

	sh = Crypto.Hash.SHA256.new()
	sh.update(passph)
	key = sh.digest()

	secrets_counter = counter

	secrets_cipher = Crypto.Cipher.AES.new(key, Crypto.Cipher.AES.MODE_CTR,
		counter=secrets_counter)

	return secrets_cipher

class Secrets:
	def __init__(self, filename):
		self.filename = filename
		self.srs = {}
		self.pubkeys = {}
		self.privkeys = {}

	def _save(self):
		global secrets_cipher, secrets_counter

		old_counter = secrets_counter.c

		# pickle doesn't appear to have problems with trailing whitespace
		padded = crypto.pad_to_multiple(pickle.dumps(self), n / 8, ' ', False)
		encrypted = secrets_cipher.encrypt(padded)

		f = open(secrets_filename, 'w')
		f.write(crypto.encode_mpi_with_padding(old_counter) + encrypted)
		f.close()

	def cancel(self):
		raise exceptions.Cancelled

	def save(self):
		passph1 = None

		def _cont1(passph, checked):
			dialogs.PassphraseDialog(_('Confirm Passphrase'),
				_('Enter your new passphrase again for confirmation'),
				is_modal=False, ok_handler=(_cont2, passph), cancel_handler=self.cancel)

		def _cont2(passph, checked, passph1):
			if passph != passph1:
				dialogs.PassphraseDialog(_('Create Passphrase'),
					_('Passphrases did not match.\n') + 
					_('Gajim needs you to create a passphrase to encrypt stored secrets'),
					is_modal=False, ok_handler=_cont1, cancel_handler=self.cancel)
				return

			counter = Counter(16, crypto.random_bytes(16))
			get_key(counter, passph1)

			self._save()

		if not os.path.exists(self.filename):
			dialogs.PassphraseDialog(_('Create Passphrase'),
				_('Gajim needs you to create a passphrase to encrypt stored secrets'),
				is_modal=False, ok_handler=_cont1, cancel_handler=self.cancel)
		else:
			self._save()

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

	counter = Counter(16, f.read(16))

	decrypted = get_key(counter).decrypt(f.read())

	try:
		secrets = pickle.loads(decrypted)
	except:
		f.close()

		global secrets_cipher

		secrets_cipher = None

		return load_secrets(filename)
	else:
		f.close()

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
