# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import Literal

import hashlib
import io
import math
import queue
import threading
from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import MutableMapping
from dataclasses import dataclass
from functools import partial
from io import BytesIO
from pathlib import Path

import niquests

from gajim.common.aes import AESGCMDecryptor
from gajim.common.aes import AESGCMEncryptor
from gajim.common.aes import AESKeyData
from gajim.common.enum import FTState

MIN_CHUNK_SIZE = 1024 * 100  # 100 KB
DEFAULT_MAX_CONTENT_LENGTH = 1024 * 1024 * 10  # 10 MB
NO_CONTENT_LENGTH_MAX_DOWNLOAD = 1024 * 1024  # 1 MB
USER_AGENT = "Gajim 2.x"


@dataclass
class TransferState:
    id: str
    state: FTState
    total: int | None = None
    progress: int = 0


@dataclass
class TransferMetadata:
    id: str
    content_length: int | None
    content_type: str | None


@dataclass
class HTTPResult:
    hash_algo: str
    req_hash_value: str
    resp_hash_value: str
    content_length: int | None
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


def get_header_values(
    headers: MutableMapping[str, str],
) -> tuple[int | None, str | None]:
    try:
        content_length = max(int(headers["Content-Length"]), 0)
    except Exception:
        content_length = None

    try:
        content_type = headers["Content-Type"]
    except Exception:
        content_type = None

    return content_length, content_type


def get_chunk_size(content_length: int | None) -> int:
    if content_length is None:
        return MIN_CHUNK_SIZE
    return max(math.ceil(content_length / 100), MIN_CHUNK_SIZE)


def resolve_proxies(proxy: str | None) -> tuple[bool, dict[str, str] | None]:
    match proxy:
        case None:
            return True, None
        case "direct://":
            return False, None
        case _:
            return True, {"http": proxy, "https": proxy}


def _upload_progress(
    ft_id: str,
    queue: queue.Queue[TransferState | TransferMetadata],
    req: niquests.PreparedRequest,
) -> None:
    assert req.upload_progress is not None
    queue.put(
        TransferState(
            id=ft_id,
            state=FTState.IN_PROGRESS,
            total=req.upload_progress.content_length,
            progress=req.upload_progress.total,
        )
    )


class FileWrapper(Iterable[bytes]):
    def __init__(
        self,
        file: Path | bytes,
        aes_key_data: AESKeyData | None,
        hash_algo: str,
        event: threading.Event,
    ) -> None:
        if isinstance(file, bytes):
            self._file = io.BytesIO(file)
            self._size = len(file)
        else:
            self._file = open(file, mode="rb")
            self._size = file.stat().st_size

        self._seek_pos = 0

        self._event = event
        self._hash = hashlib.new(hash_algo)

        match aes_key_data:
            case AESKeyData():
                self._encryptor = AESGCMEncryptor(aes_key_data)
                self._size += 16
            case _:
                self._encryptor = NonEncryptor()

        self._chunk_size = get_chunk_size(self._size)

    def __len__(self) -> int:
        return self._size

    def get_hash(self) -> str:
        return self._hash.hexdigest()

    def __iter__(self) -> Iterator[bytes]:
        while data := self._file.read(self._chunk_size):
            if self._event.is_set():
                self._file.close()
                raise CancelledError("HTTP Request was cancelled")

            self._hash.update(data)
            data = self._encryptor.encrypt(data)
            yield data

        data = self._encryptor.finalize()
        self._hash.update(data)

        self._file.close()
        if not data:
            return

        yield data


def http_request(
    event: threading.Event,
    ft_id: str,
    method: Literal["GET", "POST", "PUT"],
    url: str,
    timeout: int,
    *,
    queue: queue.Queue[TransferState | TransferMetadata] | None = None,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    content_type: str | None = None,
    input_: Path | bytes = b"",
    with_req_progress: bool = False,
    output: Path | None = None,
    with_resp_progress: bool = False,
    max_content_length: int = DEFAULT_MAX_CONTENT_LENGTH,
    max_download_size: int = 0,
    allowed_content_types: Iterable[str] | None = None,
    hash_algo: str = "sha256",
    hash_value: str | None = None,
    encryption_data: AESKeyData | None = None,
    decryption_data: AESKeyData | None = None,
    proxy: str | None = None,
) -> HTTPResult:

    if queue is not None:
        queue.put(TransferState(id=ft_id, state=FTState.STARTED))

    input_file = FileWrapper(input_, encryption_data, hash_algo, event)

    if headers is None:
        headers = {}

    if content_type is not None:
        headers["Content-Type"] = content_type

    hooks = None
    if with_req_progress and queue is not None:
        hooks = {"on_upload": [partial(_upload_progress, ft_id, queue)]}

    read_file_generator = None
    if input_:
        read_file_generator = input_file

    req = niquests.Request(
        method,
        url,
        headers=headers,
        data=read_file_generator,
        params=params,
        hooks=hooks,
    )

    session = niquests.Session(
        timeout=(10, timeout),
        headers={
            "User-Agent": USER_AGENT,
        },
    )

    session.trust_env, proxies = resolve_proxies(proxy)
    prepared_req = session.prepare_request(req)
    resp = session.send(prepared_req, stream=True, proxies=proxies)

    if event.is_set():
        raise CancelledError("HTTP Request was cancelled")

    try:
        resp.raise_for_status()
    except niquests.HTTPError as error:
        raise HTTPStatusError(str(error))

    content_length, content_type = get_header_values(resp.headers)

    if queue is not None:
        queue.put(
            TransferMetadata(
                id=ft_id, content_length=content_length, content_type=content_type
            )
        )

    if content_length == 0:
        return HTTPResult(
            hash_algo=hash_algo,
            req_hash_value=input_file.get_hash(),
            resp_hash_value="",
            content_length=content_length,
            content_type=content_type,
            content=b"",
        )

    if content_length is not None:
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

    if with_resp_progress and queue is not None:
        queue.put(
            TransferState(
                id=ft_id, state=FTState.IN_PROGRESS, total=content_length, progress=0
            )
        )

    resp_hash_obj = hashlib.new(hash_algo)
    max_bytes_downloaded = content_length or NO_CONTENT_LENGTH_MAX_DOWNLOAD

    try:
        with file_method() as output_file:
            for data in resp.iter_content(chunk_size=-1):
                assert resp.download_progress is not None
                if event.is_set():
                    raise CancelledError("HTTP Request was cancelled")

                if (
                    max_bytes_downloaded >= 0
                    and resp.download_progress.total > max_bytes_downloaded
                ):
                    raise OverflowError(
                        f"{resp.download_progress.total} > {max_bytes_downloaded}"
                    )

                resp_hash_obj.update(data)
                output_file.write(decryptor.decrypt(data))

                if with_resp_progress and queue is not None:
                    queue.put(
                        TransferState(
                            id=ft_id,
                            state=FTState.IN_PROGRESS,
                            total=content_length,
                            progress=resp.download_progress.total,
                        )
                    )

                if resp.download_progress.total >= max_download_size > 0:
                    break

            data = decryptor.finalize()
            output_file.write(data)
            resp_hash_obj.update(data)

            content = b""
            if isinstance(output_file, BytesIO):
                content = output_file.getvalue()

    except Exception as error:
        raise ValueError(str(error))

    resp_digest = resp_hash_obj.hexdigest()
    if hash_value is not None and resp_digest != hash_value:
        raise InvalidHash(f"{resp_digest} != {hash_value}")

    result = HTTPResult(
        hash_algo=hash_algo,
        req_hash_value=input_file.get_hash(),
        resp_hash_value=resp_digest,
        content_length=content_length,
        content_type=content_type,
        content=content,
    )

    return result
