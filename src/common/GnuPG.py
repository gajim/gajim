##	common/GnuPG.py
##
## Gajim Team:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Vincent Hanquez <tab@snarc.org>
##	- Nikos Kouremenos <nkour@jabber.org>
##
##	Copyright (C) 2003-2005 Gajim Team
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

from tempfile import *

USE_GPG = True

try:
	import GnuPGInterface # Debian package doesn't distribute 'our' file
except ImportError:
	try:
		from common import GnuPGInterface # use 'our' file
	except ImportError:
		USE_GPG = False # user can't do OpenGPG only if he removed the file!
	
else:
	class GnuPG(GnuPGInterface.GnuPG):
		def __init__(self):
			GnuPGInterface.GnuPG.__init__(self)
			self._setup_my_options()

		def _setup_my_options(self):
			self.options.armor = 1
			self.options.meta_interactive = 0
			self.options.extra_args.append('--no-secmem-warning')
			# Nolith's patch - prevent crashs on non fully-trusted keys
			self.options.extra_args.append('--always-trust')

		def _read_response(self, child_stdout):
			# Internal method: reads all the output from GPG, taking notice
			# only of lines that begin with the magic [GNUPG:] prefix.
			# (See doc/DETAILS in the GPG distribution for info on GPG's
			# output when --status-fd is specified.)
			#
			# Returns a dictionary, mapping GPG's keywords to the arguments
			# for that keyword.

			resp = {}
			while 1:
				line = child_stdout.readline()
				if line == "": break
				line = line.rstrip()
				if line[0:9] == '[GNUPG:] ':
					# Chop off the prefix
					line = line[9:]
					L = line.split(None, 1)
					keyword = L[0]
					if len(L) > 1:
						resp[ keyword ] = L[1]
					else:
						resp[ keyword ] = ""
			return resp

		def encrypt(self, str, recipients):
			if not USE_GPG:
				return str
			self.options.recipients = recipients   # a list!

			proc = self.run(['--encrypt'], create_fhs=['stdin', 'stdout'])
			proc.handles['stdin'].write(str)
			proc.handles['stdin'].close()

			output = proc.handles['stdout'].read()
			proc.handles['stdout'].close()

			try: proc.wait()
			except IOError: pass
			return self._stripHeaderFooter(output)

		def decrypt(self, str, keyID):
			if not USE_GPG:
				return str
			proc = self.run(['--decrypt', '-q', '-u %s'%keyID], create_fhs=['stdin', 'stdout'])
			enc = self._addHeaderFooter(str, 'MESSAGE')
			proc.handles['stdin'].write(enc)
			proc.handles['stdin'].close()
	
			output = proc.handles['stdout'].read()
			proc.handles['stdout'].close()

			try: proc.wait()
			except IOError: pass
			return output

		def sign(self, str, keyID):
			if not USE_GPG:
				return str
			proc = self.run(['-b', '-u %s'%keyID], create_fhs=['stdin', 'stdout', 'status', 'stderr'])
			proc.handles['stdin'].write(str)
			proc.handles['stdin'].close()

			output = proc.handles['stdout'].read()
			proc.handles['stdout'].close()
			proc.handles['stderr'].close()

			stat = proc.handles['status']
			resp = self._read_response(stat)
			proc.handles['status'].close()

			try: proc.wait()
			except IOError: pass
			if resp.has_key('GOOD_PASSPHRASE'):
				return self._stripHeaderFooter(output)
			return 'BAD_PASSPHRASE'

		def verify(self, str, sign):
			if not USE_GPG:
				return str
			if not str:
				return ''
			f = TemporaryFile(prefix='gajim')
			fd = f.fileno()
			f.write(str)
			f.seek(0)

			proc = self.run(['--verify', '--enable-special-filenames', '-', '-&%s'%fd], create_fhs=['stdin', 'status', 'stderr'])

			f.close()
			sign = self._addHeaderFooter(sign, 'SIGNATURE')
			proc.handles['stdin'].write(sign)
			proc.handles['stdin'].close()
			proc.handles['stderr'].close()

			stat = proc.handles['status']
			resp = self._read_response(stat)
			proc.handles['status'].close()

			try: proc.wait()
			except IOError: pass

			keyid = ''
			if resp.has_key('GOODSIG'):
				keyid = resp['GOODSIG'].split()[0]
			elif resp.has_key('BADSIG'):
				keyid = resp['BADSIG'].split()[0]
			return keyid

		def get_keys(self, secret = False):
			if not USE_GPG:
				return {}
			if secret:
				opt = '--list-secret-keys'
			else:
				opt = '--list-keys'
			proc = self.run(['--with-colons', opt], \
				create_fhs=['stdout'])
			output = proc.handles['stdout'].read()
			proc.handles['stdout'].close()

			keys = {}
			lines = output.split('\n')
			for line in lines:
				sline = line.split(':')
				if (sline[0] == 'sec' and secret) or \
						(sline[0] == 'pub' and not secret):
					keys[sline[4][8:]] = sline[9]
			return keys
			try: proc.wait()
			except IOError: pass

		def get_secret_keys(self):
			return self.get_keys(True)

		def _stripHeaderFooter(self, data):
			"""Remove header and footer from data"""
			if not data: return ''
			lines = data.split('\n')
			while lines[0] != '':
				lines.remove(lines[0])
			while lines[0] == '':
				lines.remove(lines[0])
			i = 0
			for line in lines:
				if line:
					if line[0] == '-': break
				i = i+1
			line = '\n'.join(lines[0:i])
			return line

		def _addHeaderFooter(self, data, type):
			"""Add header and footer from data"""
			out = "-----BEGIN PGP %s-----\n" % type
			out = out + "Version: PGP\n"
			out = out + "\n"
			out = out + data + "\n"
			out = out + "-----END PGP %s-----\n" % type
			return out
