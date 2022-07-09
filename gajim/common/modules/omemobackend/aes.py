# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of OMEMO Gajim Plugin.
#
# OMEMO Gajim Plugin is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# OMEMO Gajim Plugin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OMEMO Gajim Plugin. If not, see <http://www.gnu.org/licenses/>.


import os
import logging
from collections import namedtuple

from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers import algorithms
from cryptography.hazmat.primitives.ciphers.modes import GCM
from cryptography.hazmat.backends import default_backend

log = logging.getLogger('gajim.p.omemo')

EncryptionResult = namedtuple('EncryptionResult', 'payload key iv')

IV_SIZE = 12


def _decrypt(key, iv, tag, data):
    decryptor = Cipher(
        algorithms.AES(key),
        GCM(iv, tag=tag),
        backend=default_backend()).decryptor()
    return decryptor.update(data) + decryptor.finalize()


def aes_decrypt(_key, iv, payload):
    if len(_key) >= 32:
        # XEP-0384
        log.debug('XEP Compliant Key/Tag')
        data = payload
        key = _key[:16]
        tag = _key[16:]
    else:
        # Legacy
        log.debug('Legacy Key/Tag')
        data = payload[:-16]
        key = _key
        tag = payload[-16:]

    return _decrypt(key, iv, tag, data).decode()


def aes_decrypt_file(key, iv, payload):
    data = payload[:-16]
    tag = payload[-16:]
    return _decrypt(key, iv, tag, data)


def _encrypt(data, key_size, iv_size=IV_SIZE):
    if isinstance(data, str):
        data = data.encode()
    key = os.urandom(key_size)
    iv = os.urandom(iv_size)
    encryptor = Cipher(
        algorithms.AES(key),
        GCM(iv),
        backend=default_backend()).encryptor()

    payload = encryptor.update(data) + encryptor.finalize()
    return key, iv, encryptor.tag, payload


def aes_encrypt(plaintext):
    key, iv, tag, payload = _encrypt(plaintext, 16)
    key += tag
    return EncryptionResult(payload=payload, key=key, iv=iv)


def aes_encrypt_file(data):
    key, iv, tag, payload, = _encrypt(data, 32)
    payload += tag
    return EncryptionResult(payload=payload, key=key, iv=iv)


def get_new_key():
    return os.urandom(16)


def get_new_iv():
    return os.urandom(IV_SIZE)
