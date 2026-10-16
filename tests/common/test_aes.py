# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from gajim.common import aes


class AESTest(unittest.TestCase):
    def test_encrypt_decrypt(self):

        key_data = aes.AESKeyData.init()
        encryptor = aes.AESGCMEncryptor(key_data)

        plaintext_before = "mLMSAD09JASdj?ASdÖADsPASJdü=)SDü=S"
        ciphertext = encryptor.encrypt(plaintext_before.encode())
        ciphertext += encryptor.finalize()

        decryptor = aes.AESGCMDecryptor(key_data)
        decrypted_bytes = decryptor.decrypt(ciphertext)
        decrypted_bytes += decryptor.finalize()

        plaintext_after = decrypted_bytes.decode()

        self.assertEqual(plaintext_before, plaintext_after)

    def test_encrypt_decrypt_streamed(self):
        # Make sure chunk size is below 16 bytes to test auth tag split
        chunk_size = 10

        key_data = aes.AESKeyData.init()
        encryptor = aes.AESGCMEncryptor(key_data)

        plaintext_before = "mLMSAD09JASdj?ASdÖADsPASJdü=)SDü=Ss"

        ciphertext = b""
        for i in range(0, len(plaintext_before), chunk_size):
            ciphertext += encryptor.encrypt(
                plaintext_before[i : i + chunk_size].encode()
            )

        ciphertext += encryptor.finalize()

        decryptor = aes.AESGCMDecryptor(key_data)

        decrypted_bytes = b""
        for i in range(0, len(ciphertext), chunk_size):
            decrypted_bytes += decryptor.decrypt(ciphertext[i : i + chunk_size])

        decrypted_bytes += decryptor.finalize()

        plaintext_after = decrypted_bytes.decode()

        self.assertEqual(plaintext_before, plaintext_after)
