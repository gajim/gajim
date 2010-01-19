## src/common/GnuPG.py
##
## Copyright (C) 2003-2008 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005 Alex Mauer <hawke AT hawkesnest.net>
## Copyright (C) 2005-2006 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2005-2008 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2007 Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2008 Jean-Marie Traissard <jim AT lapin.org>
##                    Jonathan Schleifer <js-gajim AT webkeks.org>
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

import gajim
from os import tmpfile
from common import helpers

if gajim.HAVE_GPG:
	import GnuPGInterface

	class GnuPG(GnuPGInterface.GnuPG):
		def __init__(self, use_agent = False):
			GnuPGInterface.GnuPG.__init__(self)
			self.use_agent = use_agent
			self._setup_my_options()
			self.always_trust = False

		def _setup_my_options(self):
			self.options.armor = 1
			self.options.meta_interactive = 0
			self.options.extra_args.append('--no-secmem-warning')
			# disable photo viewer when verifying keys
			self.options.extra_args.append('--verify-options')
			self.options.extra_args.append('no-show-photo')
			if self.use_agent:
				self.options.extra_args.append('--use-agent')

		def _read_response(self, child_stdout):
			# Internal method: reads all the output from GPG, taking notice
			# only of lines that begin with the magic [GNUPG:] prefix.
			# (See doc/DETAILS in the GPG distribution for info on GPG's
			# output when --status-fd is specified.)
			#
			# Returns a dictionary, mapping GPG's keywords to the arguments
			# for that keyword.

			resp = {}
			while True:
				line = helpers.temp_failure_retry(child_stdout.readline)
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

		def encrypt(self, str_, recipients, always_trust=False):
			self.options.recipients = recipients   # a list!

			opt = ['--encrypt']
			if always_trust or self.always_trust:
				opt.append('--always-trust')
			proc = self.run(opt, create_fhs=['stdin', 'stdout', 'status',
				'stderr'])
			proc.handles['stdin'].write(str_)
			try:
				proc.handles['stdin'].close()
			except IOError:
				pass

			output = proc.handles['stdout'].read()
			try:
				proc.handles['stdout'].close()
			except IOError:
				pass

			stat = proc.handles['status']
			resp = self._read_response(stat)
			try:
				proc.handles['status'].close()
			except IOError:
				pass

			error = proc.handles['stderr'].read()
			proc.handles['stderr'].close()

			try: proc.wait()
			except IOError: pass
			if 'INV_RECP' in resp and resp['INV_RECP'].split()[0] == '10':
				# unusable recipient "Key not trusted"
				return '', 'NOT_TRUSTED'
			if 'BEGIN_ENCRYPTION' in resp and 'END_ENCRYPTION' in resp:
				# Encryption succeeded, even if there is output on stderr. Maybe
				# verbose is on
				error = ''
			return self._stripHeaderFooter(output), helpers.decode_string(error)

		def decrypt(self, str_, keyID):
			proc = self.run(['--decrypt', '-q', '-u %s'%keyID], create_fhs=['stdin', 'stdout'])
			enc = self._addHeaderFooter(str_, 'MESSAGE')
			proc.handles['stdin'].write(enc)
			proc.handles['stdin'].close()

			output = proc.handles['stdout'].read()
			proc.handles['stdout'].close()

			try: proc.wait()
			except IOError: pass
			return output

		def sign(self, str_, keyID):
			proc = self.run(['-b', '-u %s'%keyID], create_fhs=['stdin', 'stdout', 'status', 'stderr'])
			proc.handles['stdin'].write(str_)
			try:
				proc.handles['stdin'].close()
			except IOError:
				pass

			output = proc.handles['stdout'].read()
			try:
				proc.handles['stdout'].close()
				proc.handles['stderr'].close()
			except IOError:
				pass

			stat = proc.handles['status']
			resp = self._read_response(stat)
			try:
				proc.handles['status'].close()
			except IOError:
				pass

			try: proc.wait()
			except IOError: pass
			if 'GOOD_PASSPHRASE' in resp or 'SIG_CREATED' in resp:
				return self._stripHeaderFooter(output)
			if 'KEYEXPIRED' in resp:
				return 'KEYEXPIRED'
			return 'BAD_PASSPHRASE'

		def verify(self, str_, sign):
			if str_ is None:
				return ''
			f = tmpfile()
			fd = f.fileno()
			f.write(str_)
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
			if 'GOODSIG' in resp:
				keyid = resp['GOODSIG'].split()[0]
			return keyid

		def get_keys(self, secret = False):
			if secret:
				opt = '--list-secret-keys'
			else:
				opt = '--list-keys'
			proc = self.run(['--with-colons', opt],
				create_fhs=['stdout'])
			output = proc.handles['stdout'].read()
			proc.handles['stdout'].close()

			try: proc.wait()
			except IOError: pass

			keys = {}
			lines = output.split('\n')
			for line in lines:
				sline = line.split(':')
				if (sline[0] == 'sec' and secret) or \
						(sline[0] == 'pub' and not secret):
					# decode escaped chars
					name = eval('"' + sline[9].replace('"', '\\"') + '"')
					# make it unicode instance
					keys[sline[4][8:]] = helpers.decode_string(name)
			return keys

		def get_secret_keys(self):
			return self.get_keys(True)

		def _stripHeaderFooter(self, data):
			"""
			Remove header and footer from data
			"""
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

		def _addHeaderFooter(self, data, type_):
			"""
			Add header and footer from data
			"""
			out = "-----BEGIN PGP %s-----\n" % type_
			out = out + "Version: PGP\n"
			out = out + "\n"
			out = out + data + "\n"
			out = out + "-----END PGP %s-----\n" % type_
			return out

# vim: set ts=3:
