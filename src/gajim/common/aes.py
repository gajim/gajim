# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import secrets
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
        key = secrets.token_bytes(key_size)
        iv = secrets.token_bytes(iv_size)
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
        if len(self._cache) > 16:
            ciphertext = self._cache[:-16]
            self._cache = self._cache[-16:]
        else:
            ciphertext = b""
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
