# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import os
from dataclasses import dataclass

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import algorithms
from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers.modes import GCM


@dataclass
class AESKeyData:
    key: bytes
    iv: bytes

    @classmethod
    def init(cls, key_size: int = 32, iv_size: int = 12) -> AESKeyData:
        key = os.urandom(key_size)
        iv = os.urandom(iv_size)
        return cls(key=key, iv=iv)


class AESGCMDecryptor:
    def __init__(self, data: AESKeyData) -> None:

        self._cipher = Cipher(
            algorithms.AES(data.key), GCM(data.iv), backend=default_backend()
        ).decryptor()
        self._cache = b""

    def decrypt(self, data: bytes) -> bytes:
        self._cache += data
        # Never use the last 16 bytes, because it could be the auth tag
        ciphertext = self._cache[:-16]
        self._cache = data[-16:]
        return self._cipher.update(ciphertext)

    def finalize(self) -> bytes:
        return self._cipher.finalize_with_tag(self._cache)


class AESGCMEncryptor:
    def __init__(self, data: AESKeyData) -> None:

        self._cipher = Cipher(
            algorithms.AES(data.key), GCM(data.iv), backend=default_backend()
        ).encryptor()

    def encrypt(self, data: bytes) -> bytes:
        return self._cipher.update(data)

    def finalize(self) -> bytes:
        return self._cipher.finalize() + self._cipher.tag
