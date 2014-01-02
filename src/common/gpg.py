## src/common/gpg.py
##
## Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005 Alex Mauer <hawke AT hawkesnest.net>
## Copyright (C) 2005-2006 Nikos Kouremenos <kourem AT gmail.com>
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

from common.gajim import HAVE_GPG
import os

if HAVE_GPG:
    from common import gnupg

    class GnuPG(gnupg.GPG):
        def __init__(self, use_agent=False):
            gnupg.GPG.__init__(self)
            self.decode_errors = 'replace'
            self.passphrase = None
            self.use_agent = use_agent
            self.always_trust = [] # list of keyID to always trust

        def _setup_my_options(self):
            self.options.armor = 1
            self.options.meta_interactive = 0
            self.options.extra_args.append('--no-secmem-warning')
            # disable photo viewer when verifying keys
            self.options.extra_args.append('--verify-options')
            self.options.extra_args.append('no-show-photo')
            if self.use_agent:
                self.options.extra_args.append('--use-agent')

        def encrypt(self, str_, recipients, always_trust=False):
            trust = always_trust
            if not trust:
                trust = True
                for key in recipients:
                    if key not in self.always_trust:
                        trust = False
            result = super(GnuPG, self).encrypt(str_, recipients,
                always_trust=trust, passphrase=self.passphrase)

            if result.status == 'invalid recipient':
                return '', 'NOT_TRUSTED'

            if result.ok:
                error = ''
            else:
                error = result.status

            return self._stripHeaderFooter(str(result)), error

        def decrypt(self, str_, keyID):
            data = self._addHeaderFooter(str_, 'MESSAGE')
            result = super(GnuPG, self).decrypt(data,
                passphrase=self.passphrase)

            return str(result)

        def sign(self, str_, keyID):
            result = super(GnuPG, self).sign(str_, keyid=keyID, detach=True,
                passphrase=self.passphrase)

            if result.fingerprint:
                return self._stripHeaderFooter(str(result))
            if result.status == 'key expired':
                return 'KEYEXPIRED'
            return 'BAD_PASSPHRASE'

        def verify(self, str_, sign):
            if str_ is None:
                return ''
            # Hash algorithm is not transfered in the signed presence stanza so try
            # all algorithms. Text name for hash algorithms from RFC 4880 - section 9.4
            hash_algorithms = ['SHA512', 'SHA384', 'SHA256', 'SHA224', 'SHA1', 'RIPEMD160']
            for algo in hash_algorithms:
                data = os.linesep.join(
                    ['-----BEGIN PGP SIGNED MESSAGE-----',
                     'Hash: ' + algo,
                     '',
                     str_,
                     self._addHeaderFooter(sign, 'SIGNATURE')]
                    )
                result = super(GnuPG, self).verify(data)
                if result.valid:
                    return result.key_id

            return ''

        def get_keys(self, secret=False):
            keys = {}
            result = super(GnuPG, self).list_keys(secret=secret)
            for key in result:
                # Take first not empty uid
                keys[key['keyid'][8:]] = [uid for uid in key['uids'] if uid][0]
            return keys

        def get_secret_keys(self):
            return self.get_keys(True)

        def _stripHeaderFooter(self, data):
            """
            Remove header and footer from data
            """
            if not data: return ''
            lines = data.splitlines()
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
            out = "-----BEGIN PGP %s-----" % type_ + os.linesep
            out = out + "Version: PGP" + os.linesep
            out = out + os.linesep
            out = out + data + os.linesep
            out = out + "-----END PGP %s-----" % type_ + os.linesep
            return out
