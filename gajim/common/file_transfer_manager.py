# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast
from typing import Generic
from typing import Literal
from typing import overload
from typing import TypeVar

import logging
import multiprocessing as mp
import queue
import threading
from collections import defaultdict
from collections.abc import Callable
from collections.abc import Iterable
from concurrent.futures import Future
from functools import partial
from pathlib import Path
from urllib.parse import urlparse

from gi.repository import GLib
from gi.repository import GObject
from nbxmpp.structs import ProxyData

from gajim.common import app
from gajim.common.aes import AESKeyData
from gajim.common.enum import FTState
from gajim.common.helpers import determine_proxy
from gajim.common.helpers import get_uuid
from gajim.common.multiprocess.http import DownloadResult
from gajim.common.multiprocess.http import http_download
from gajim.common.multiprocess.http import http_upload
from gajim.common.multiprocess.http import TransferMetadata
from gajim.common.multiprocess.http import TransferState
from gajim.common.multiprocess.http import UploadResult
from gajim.common.util.http import get_aes_key_data

log = logging.getLogger("gajim.c.ftm")

_T = TypeVar("_T")
QueueT = queue.Queue[TransferState | TransferMetadata]


class FileTransferManager:
    def __init__(self) -> None:
        self._transfers: dict[
            str, FileTransfer[UploadResult] | FileTransfer[DownloadResult]
        ] = {}
        self._manager = mp.Manager()
        self._queue: QueueT = self._manager.Queue()
        GLib.timeout_add(100, self._poll_queue)

    def get_transfer(
        self, id_: str
    ) -> FileTransfer[UploadResult] | FileTransfer[DownloadResult] | None:
        return self._transfers.get(id_)

    def _poll_queue(self) -> bool:
        messages: dict[str, list[TransferState | TransferMetadata]] = defaultdict(list)
        while not self._queue.empty():
            try:
                state = self._queue.get_nowait()
            except Exception:
                pass

            else:
                messages[state.id].append(state)

        for transfer_id, states in messages.items():
            obj = self._transfers.get(transfer_id)
            if obj is None:
                log.error("Unable to find transfer object with id: %s", transfer_id)

            else:
                try:
                    obj.process_multiple_states(states)
                except Exception:
                    log.exception("Failed to process states")

        return GLib.SOURCE_CONTINUE

    def http_download(
        self,
        url: str,
        id_: str | None = None,
        output: Path | None = None,
        with_progress: bool = False,
        max_content_length: int | None = None,
        allowed_content_types: Iterable[str] | None = None,
        hash_algo: str | None = None,
        hash_value: str | None = None,
        proxy: ProxyData | None = None,
        user_data: Any = None,
        callback: Callable[[FileTransfer[DownloadResult]], Any] | None = None,
    ) -> FileTransfer[DownloadResult] | None:

        if id_ is None:
            id_ = get_uuid()

        obj = self._transfers.get(id_)
        if obj is not None:
            return cast(FileTransfer[DownloadResult], obj)

        if proxy is None:
            proxy = determine_proxy()

        urlparts = urlparse(url)

        decryption_data = None
        if urlparts.scheme == "aesgcm":
            decryption_data = get_aes_key_data(urlparts.fragment)
            # Don’t send fragment to the server, it would leak the AES key
            urlparts = urlparts._replace(scheme="https", fragment="")

        event = self._manager.Event()

        try:
            future = app.process_pool.submit(
                http_download,
                self._queue,
                event,
                id_,
                urlparts.geturl(),
                output=output,
                with_progress=with_progress,
                max_content_length=max_content_length,
                allowed_content_types=allowed_content_types,
                hash_algo=hash_algo,
                hash_value=hash_value,
                decryption_data=decryption_data,
                proxy=None if proxy is None else proxy.get_uri(),
            )
        except Exception as error:
            log.exception(error)
            return None

        future.add_done_callback(
            partial(
                GLib.idle_add,
                self._on_download_finished,
                id_,
            )
        )

        obj = FileTransfer[DownloadResult](
            self, id_, event, output=output, user_data=user_data
        )
        if callback is not None:
            obj.connect("finished", callback)
        self._transfers[id_] = obj
        return obj

    def _on_download_finished(self, id_: str, future: Future[DownloadResult]) -> None:
        obj = cast(FileTransfer[DownloadResult] | None, self._transfers.get(id_))
        if obj is None:
            log.error("Unable to find transfer object with id: %s", id_)
            return

        self._poll_queue()

        try:
            download_result = future.result()
        except Exception as error:
            output = obj.get_output_path()
            if output is not None:
                output.unlink(missing_ok=True)
            obj.set_exception(error)

        else:
            obj.set_result(download_result)
            obj.set_finished()

        del self._transfers[id_]

    def http_upload(
        self,
        url: str,
        content_type: str,
        input_: Path | bytes,
        headers: dict[str, str] | None = None,
        id_: str | None = None,
        with_progress: bool = False,
        encryption_data: AESKeyData | None = None,
        proxy: ProxyData | None = None,
        user_data: Any = None,
        callback: Callable[[FileTransfer[UploadResult]], Any] | None = None,
    ) -> FileTransfer[UploadResult] | None:

        if id_ is None:
            id_ = get_uuid()

        obj = self._transfers.get(id_)
        if obj is not None:
            return cast(FileTransfer[UploadResult], obj)

        if proxy is None:
            proxy = determine_proxy()

        event = self._manager.Event()

        try:
            future = app.process_pool.submit(
                http_upload,
                self._queue,
                event,
                id_,
                url,
                content_type,
                input_,
                headers=headers,
                with_progress=with_progress,
                encryption_data=encryption_data,
                proxy=None if proxy is None else proxy.get_uri(),
            )
        except Exception as error:
            log.exception(error)
            return None

        future.add_done_callback(
            partial(
                GLib.idle_add,
                self._on_upload_finished,
                id_,
            )
        )

        obj = FileTransfer[UploadResult](self, id_, event, user_data=user_data)
        if callback is not None:
            obj.connect("finished", callback)
        self._transfers[id_] = obj
        return obj

    def _on_upload_finished(self, id_: str, future: Future[UploadResult]) -> None:
        obj = cast(FileTransfer[UploadResult] | None, self._transfers.get(id_))
        if obj is None:
            log.error("Unable to find transfer object with id: %s", id_)
            return

        self._poll_queue()

        try:
            upload_result = future.result()
        except Exception as error:
            obj.set_exception(error)

        else:
            obj.set_result(upload_result)
            obj.set_finished()

        del self._transfers[id_]


class FileTransfer(Generic[_T], GObject.Object):
    __gtype_name__ = "FileTransfer"

    __gsignals__ = {
        "finished": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(
        self,
        manager: FileTransferManager,
        id_: str,
        event: threading.Event,
        output: Path | None = None,
        user_data: Any = None,
    ) -> None:
        super().__init__()

        self._id = id_
        self._state = FTState.CREATED
        self._progress = 0

        self._event = event
        self._output = output
        self._manager = manager
        self._result = None
        self._exception = None
        self._metadata = None
        self._user_data = user_data

    def cancel(self) -> None:
        self._event.set()

    @GObject.Property(type=str, flags=GObject.ParamFlags.READABLE)
    def id(self) -> str:
        return self._id

    @GObject.Property(type=int, flags=GObject.ParamFlags.READABLE)
    def state(self) -> int:
        return self._state

    @GObject.Property(type=float, flags=GObject.ParamFlags.READABLE)
    def progress(self) -> float:
        return self._progress

    def process_multiple_states(
        self, states: list[TransferState | TransferMetadata]
    ) -> None:
        # Process multiple state changes and notify only once for
        # each changed property

        old_state = self._state
        old_progress = self._progress

        for state in states:
            match state:
                case TransferMetadata():
                    self._metadata = state
                case TransferState():
                    self._state = state.state
                    if self._state == FTState.IN_PROGRESS:
                        self._progress = state.progress

        if self._state != old_state:
            self.notify("state")
        if self._progress != old_progress:
            self.notify("progress")

    def set_finished(self) -> None:
        self._state = FTState.FINISHED
        self.notify("state")
        self.emit("finished")
        self.run_dispose()

    def is_finished(self) -> bool:
        return self._state == FTState.FINISHED

    def set_user_data(self, user_data: Any) -> None:
        self._user_data = user_data

    def get_user_data(self) -> Any:
        return self._user_data

    def get_metadata(self) -> TransferMetadata | None:
        return self._metadata

    def set_result(self, result: _T) -> None:
        self._result = result

    @overload
    def get_result(self, *, raise_if_empty: Literal[False]) -> _T | None: ...

    @overload
    def get_result(self, *, raise_if_empty: Literal[True]) -> _T: ...

    @overload
    def get_result(self) -> _T: ...

    def get_result(self, *, raise_if_empty: bool = True) -> _T | None:
        self.raise_for_error()
        if raise_if_empty:
            if self._result is None:
                raise ValueError("No result available")

            if isinstance(self._result, DownloadResult) and not self._result.content:
                raise ValueError("No content received")

        return self._result

    def set_exception(self, exception: Exception | None) -> None:
        self._exception = exception
        self._state = FTState.ERROR
        self.notify("state")
        self.emit("finished")
        self.run_dispose()

    def raise_for_error(self) -> None:
        if self._exception is not None:
            raise self._exception

    def get_output_path(self) -> Path | None:
        return self._output
