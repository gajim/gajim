# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Literal

import hashlib
import io
import logging
import math
import queue
import ssl
import threading
from collections.abc import Iterable
from dataclasses import dataclass
from functools import partial
from io import BytesIO
from pathlib import Path

import httpx
import truststore

from gajim.common.aes import AESGCMDecryptor
from gajim.common.aes import AESGCMEncryptor
from gajim.common.aes import AESKeyData
from gajim.common.enum import FTState

MIN_CHUNK_SIZE = 1024 * 100  # 100 KB
DEFAULT_MAX_CONTENT_LENGTH = 1024 * 1024 * 10  # 10 MB
USER_AGENT = "Gajim 2.x"

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
class HTTPResult:
    hash_algo: str
    req_hash_value: str
    resp_hash_value: str
    content_length: int
    content_type: str | None
    content: bytes


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


class NonEncryptor:

    def encrypt(self, data: bytes) -> bytes:
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


def http_request(
    queue: queue.Queue[TransferState | TransferMetadata],
    event: threading.Event,
    ft_id: str,
    method: Literal["GET", "POST", "PUT"],
    url: str,
    timeout: int,
    *,
    headers: dict[str, str] | None = None,
    content_type: str | None = None,
    input_: Path | bytes = b"",
    with_req_progress: bool = False,
    output: Path | None = None,
    with_resp_progress: bool = False,
    max_content_length: int = DEFAULT_MAX_CONTENT_LENGTH,
    allowed_content_types: Iterable[str] | None = None,
    hash_algo: str = "sha256",
    hash_value: str | None = None,
    encryption_data: AESKeyData | None = None,
    decryption_data: AESKeyData | None = None,
    proxy: str | None = None,
) -> HTTPResult:

    trust_env = True
    if proxy == "direct://":
        proxy = None
        trust_env = False

    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    client = httpx.Client(
        timeout=timeout,
        verify=ctx,
        http2=True,
        proxy=proxy,
        trust_env=trust_env,
        follow_redirects=True,
    )

    queue.put(TransferState(id=ft_id, state=FTState.STARTED))

    if isinstance(input_, bytes):
        req_content_size = len(input_)
        input_file = io.BytesIO(input_)
    else:
        req_content_size = input_.stat().st_size
        input_file = input_.open(mode="rb")

    match encryption_data:
        case AESKeyData():
            encryptor = AESGCMEncryptor(encryption_data)
            req_content_size += 16
        case _:
            encryptor = NonEncryptor()

    default_headers = {
        "User-Agent": USER_AGENT,
    }

    if content_type is not None:
        default_headers.update(
            {
                "Content-Type": content_type,
                "Content-Length": str(req_content_size),
            }
        )

    if headers is not None:
        headers.update(default_headers)
    else:
        headers = default_headers

    req_hash_obj = hashlib.new(hash_algo)

    def _read_file_generator() -> Iterable[bytes]:
        if with_req_progress:
            queue.put(TransferState(id=ft_id, state=FTState.IN_PROGRESS, progress=0))

        chunk_size = math.ceil(req_content_size / 100)
        chunk_size = max(chunk_size, MIN_CHUNK_SIZE)

        uploaded = 0
        while data := input_file.read(chunk_size):
            if event.is_set():
                input_file.close()
                raise CancelledError

            req_hash_obj.update(data)
            data = encryptor.encrypt(data)
            uploaded += len(data)
            progress = round(uploaded / req_content_size, 2)
            if with_req_progress:
                queue.put(
                    TransferState(
                        id=ft_id, state=FTState.IN_PROGRESS, progress=progress
                    )
                )
            yield data

        yield encryptor.finalize()
        if with_req_progress:
            queue.put(TransferState(id=ft_id, state=FTState.IN_PROGRESS, progress=1))
        input_file.close()

    read_file_generator = None
    if input_:
        read_file_generator = _read_file_generator()

    req = client.build_request(
        method, url=url, content=read_file_generator, headers=headers
    )
    resp = client.send(req, stream=True)

    if event.is_set():
        raise CancelledError

    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError:
        # https://github.com/encode/httpx/issues/1990
        raise HTTPStatusError(f"{resp.status_code} {resp.reason_phrase}")

    content_length, content_type = get_header_values(resp.headers)

    queue.put(
        TransferMetadata(
            id=ft_id, content_length=content_length, content_type=content_type
        )
    )

    if content_length == 0:
        return HTTPResult(
            hash_algo=hash_algo,
            req_hash_value=req_hash_obj.hexdigest(),
            resp_hash_value="",
            content_length=content_length,
            content_type=content_type,
            content=b"",
        )

    if max_content_length >= 0 and content_length > max_content_length:
        raise MaxContentLengthExceeded(content_length)

    if allowed_content_types is not None:
        if content_type is None or content_type not in allowed_content_types:
            raise ContentTypeNotAllowed(content_type)

    match decryption_data:
        case AESKeyData():
            decryptor = AESGCMDecryptor(decryption_data)
        case _:
            decryptor = NonDecryptor()

    if output is None:
        file_method = BytesIO
    else:
        file_method = partial(output.open, mode="wb")

    if with_resp_progress:
        queue.put(TransferState(id=ft_id, state=FTState.IN_PROGRESS, progress=0))

    resp_hash_obj = hashlib.new(hash_algo)

    with file_method() as output_file:

        chunk_size = math.ceil(content_length / 100)
        chunk_size = max(chunk_size, MIN_CHUNK_SIZE)

        for data in resp.iter_bytes(chunk_size=chunk_size):
            if event.is_set():
                raise CancelledError

            if resp.num_bytes_downloaded > content_length:
                raise OverflowError(f"{resp.num_bytes_downloaded} > {content_length}")

            progress = round(resp.num_bytes_downloaded / content_length, 2)
            resp_hash_obj.update(data)
            output_file.write(decryptor.decrypt(data))
            if with_resp_progress:
                queue.put(
                    TransferState(
                        id=ft_id, state=FTState.IN_PROGRESS, progress=progress
                    )
                )

        output_file.write(decryptor.finalize())
        if with_resp_progress:
            queue.put(TransferState(id=ft_id, state=FTState.IN_PROGRESS, progress=1))

        content = b""
        if isinstance(output_file, BytesIO):
            content = output_file.getvalue()

    resp_digest = resp_hash_obj.hexdigest()
    if hash_value is not None and resp_digest != hash_value:
        raise InvalidHash(f"{resp_digest} != {hash_value}")

    result = HTTPResult(
        hash_algo=hash_algo,
        req_hash_value=req_hash_obj.hexdigest(),
        resp_hash_value=resp_digest,
        content_length=content_length,
        content_type=content_type,
        content=content,
    )

    return result
