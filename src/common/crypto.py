# common crypto functions (mostly specific to XEP-0116, but useful elsewhere)
# -*- coding:utf-8 -*-
## src/common/crypto.py
##
## Copyright (C) 2007 Brendan Taylor <whateley AT gmail.com>
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

import sys
import os
import math

from hashlib import sha256 as SHA256

# convert a large integer to a big-endian bitstring
def encode_mpi(n):
    if n >= 256:
        return encode_mpi(n / 256) + chr(n % 256)
    else:
        return chr(n)

# convert a large integer to a big-endian bitstring, padded with \x00s to
# a multiple of 16 bytes
def encode_mpi_with_padding(n):
    return pad_to_multiple(encode_mpi(n), 16, '\x00', True)

# pad 'string' to a multiple of 'multiple_of' with 'char'.
# pad on the left if 'left', otherwise pad on the right.
def pad_to_multiple(string, multiple_of, char, left):
    mod = len(string) % multiple_of
    if mod == 0:
        return string
    else:
        padding = (multiple_of - mod) * char

    if left:
        return padding + string
    else:
        return string + padding

# convert a big-endian bitstring to an integer
def decode_mpi(s):
    if len(s) == 0:
        return 0
    else:
        return 256 * decode_mpi(s[:-1]) + ord(s[-1])

def sha256(string):
    sh = SHA256()
    sh.update(string)
    return sh.digest()

base28_chr = "acdefghikmopqruvwxy123456789"

def sas_28x5(m_a, form_b):
    sha = sha256(m_a + form_b + 'Short Authentication String')
    lsb24 = decode_mpi(sha[-3:])
    return base28(lsb24)

def base28(n):
    if n >= 28:
        return base28(n / 28) + base28_chr[n % 28]
    else:
        return base28_chr[n]

def add_entropy_sources_OpenSSL():
    # Other possibly variable data. This are very low quality sources of
    # entropy, but some of them are installation dependent and can be hard
    # to guess for the attacker.
    # Data available on all platforms Unix, Windows
    sources = [sys.argv, sys.builtin_module_names,
        sys.copyright, sys.getfilesystemencoding(), sys.hexversion,
        sys.modules, sys.path, sys.version, sys.api_version,
        os.environ, os.getcwd(), os.getpid()]

    for s in sources:
        OpenSSL.rand.add(str(s).encode('utf-8'), 1)

    # On Windows add the current contents of the screen to the PRNG state.
    if os.name == 'nt':
        OpenSSL.rand.screen()
    # The /proc filesystem on POSIX systems contains many random variables:
    # memory statistics, interrupt counts, network packet counts
    if os.name == 'posix':
        dirs = ['/proc', '/proc/net', '/proc/self']
        for d in dirs:
            if os.access(d, os.R_OK):
               for filename in os.listdir(d):
                  OpenSSL.rand.add(filename.encode('utf-8'), 0)
                  try:
                     with open(d + os.sep + filename, "r") as fp:
                         # Limit the ammount of read bytes, in case a memory
                         # file was opened
                         OpenSSL.rand.add(str(fp.read(5000)).encode('utf-8'),
                             1)
                  except:
                      # Ignore all read and access errors
                      pass

PYOPENSSL_PRNG_PRESENT = False
try:
    import OpenSSL.rand
    PYOPENSSL_PRNG_PRESENT = True
except ImportError:
    # PyOpenSSL PRNG not available
    pass

def random_bytes(bytes_):
    if PYOPENSSL_PRNG_PRESENT:
        OpenSSL.rand.add(os.urandom(bytes_), bytes_)
        return OpenSSL.rand.bytes(bytes_)
    else:
        return os.urandom(bytes_)

def generate_nonce():
    return random_bytes(8)

# generate a random number between 'bottom' and 'top'
def srand(bottom, top):
    # minimum number of bytes needed to represent that range
    bytes = int(math.ceil(math.log(top - bottom, 256)))

    # in retrospect, this is horribly inadequate.
    return (decode_mpi(random_bytes(bytes)) % (top - bottom)) + bottom

# a faster version of (base ** exp) % mod
#               taken from <http://lists.danga.com/pipermail/yadis/2005-September/001445.html>
def powmod(base, exp, mod):
    square = base % mod
    result = 1

    while exp > 0:
        if exp & 1: # exponent is odd
            result = (result * square) % mod

        square = (square * square) % mod
        exp /= 2

    return result
