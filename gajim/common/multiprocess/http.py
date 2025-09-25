# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import hashlib
import logging
import math
import queue
import ssl
import threading
from collections.abc import Iterable
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import httpx
import truststore

from gajim.common.aes import AESGCMDecryptor
from gajim.common.aes import AESKeyData
from gajim.common.enum import FTState

MIN_CHUNK_SIZE = 1024 * 1024

log = logging.getLogger("gajim.http")


@dataclass
class TransferState:
    id: str
    state: FTState
    progress: float = 0


@dataclass
class TransferMetadata:
    id: str
    content_length: int
    content_type: str | None


@dataclass
class DownloadResult:
    hash_algo: str
    hash_value: str
    content_length: int
    content_type: str | None
    content: bytes | None = None


class InvalidHash(Exception):
    pass


class MaxContentLengthExceeded(Exception):
    pass


class ContentTypeNotAllowed(Exception):
    pass


class HTTPStatusError(Exception):
    pass


class CancelledError(Exception):
    pass


class NonDecryptor:

    def decrypt(self, data: bytes) -> bytes:
        return data

    def finalize(self) -> bytes:
        return b""


def get_header_values(headers: httpx.Headers) -> tuple[int, str | None]:
    try:
        content_length = max(int(headers["Content-Length"]), 0)
    except Exception:
        content_length = 0

    try:
        content_type = headers["Content-Type"]
    except Exception:
        content_type = None

    return content_length, content_type


def http_download(
    queue: queue.Queue[TransferState | TransferMetadata],
    event: threading.Event,
    ft_id: str,
    url: str,
    output: Path | None = None,
    with_progress: bool = False,
    max_content_length: int | None = None,
    allowed_content_types: Iterable[str] | None = None,
    hash_algo: str | None = None,
    hash_value: str | None = None,
    decryption_data: AESKeyData | None = None,
    proxy: str | None = None,
) -> DownloadResult:

    trust_env = True
    if proxy == "direct://":
        proxy = None
        trust_env = False

    hash_algo = hash_algo or "sha256"
    hash_obj = hashlib.new(hash_algo)

    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    client = httpx.Client(
        timeout=10,
        verify=ctx,
        http2=True,
        proxy=proxy,
        trust_env=trust_env,
        follow_redirects=True,
    )

    queue.put(TransferState(id=ft_id, state=FTState.STARTED))

    req = client.build_request("GET", url=url)
    resp = client.send(req, stream=True)

    if event.is_set():
        raise CancelledError

    content_length, content_type = get_header_values(resp.headers)

    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError:
        # https://github.com/encode/httpx/issues/1990
        raise HTTPStatusError(f"{resp.status_code} {resp.reason_phrase}")

    queue.put(
        TransferMetadata(
            id=ft_id, content_length=content_length, content_type=content_type
        )
    )

    if content_length == 0:
        raise OverflowError("No content length available")

    if max_content_length is not None:
        if content_length > max_content_length:
            raise MaxContentLengthExceeded(content_length)

    if allowed_content_types is not None:
        if content_type is None or content_type not in allowed_content_types:
            raise ContentTypeNotAllowed(content_type)

    received_length = 0
    chunk_size = math.ceil(content_length / 50)
    chunk_size = max(chunk_size, MIN_CHUNK_SIZE)

    match decryption_data:
        case AESKeyData():
            decryptor = AESGCMDecryptor(decryption_data)
        case _:
            decryptor = NonDecryptor()

    if output is None:
        file = BytesIO()
    else:
        file = output.open(mode="wb")

    queue.put(
        TransferState(id=ft_id, state=FTState.IN_PROGRESS, progress=0)
    )

    for data in resp.iter_bytes(chunk_size=chunk_size):
        if event.is_set():
            file.close()
            raise CancelledError

        received_length += len(data)
        if received_length > content_length:
            raise OverflowError(f"{received_length} > {content_length}")

        progress = round(received_length / content_length, 2)
        hash_obj.update(data)
        file.write(decryptor.decrypt(data))
        if with_progress:
            queue.put(
                TransferState(id=ft_id, state=FTState.IN_PROGRESS, progress=progress)
            )

    file.write(decryptor.finalize())
    if with_progress:
        queue.put(TransferState(id=ft_id, state=FTState.IN_PROGRESS, progress=1))

    content = None
    if isinstance(file, BytesIO):
        content = file.getvalue()

    file.close()

    digest = hash_obj.hexdigest()
    if hash_value is not None and digest != hash_value:
        raise InvalidHash(f"{digest} != {hash_value}")

    result = DownloadResult(
        hash_algo=hash_algo,
        hash_value=digest,
        content_length=content_length,
        content_type=content_type,
        content=content,
    )

    return result
