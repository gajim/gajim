# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import sys
import unicodedata
from collections.abc import Callable
from pathlib import Path

from gi.repository import Gio
from gi.repository import GLib
from nbxmpp.protocol import JID

WIN_PATH_BLACKLIST = ["\\", "/", ":", "*", "?", "？", '"', "<", ">", "|", "\0"]
WIN_RESERVED_FILENAMES = [
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
]


def sanitize_filename(filename: str, max_length: int = 50) -> str:
    """
    Sanitize filename of:
     - characters used to obfuscate file names/extensions
     - elements not allowed on Windows
       https://docs.microsoft.com/en-us/windows/win32/fileio/naming-a-file
     - shorten to max length
    """

    # Remove right-to-left override U+202E (commonly used to spoof extensions)
    filename = filename.replace("\u202e", "")

    if sys.platform == "win32":
        filename = sanitize_windows_filename(filename)

    extension = Path(filename).suffix[:10]
    filename = Path(filename).stem

    if max_length > 0:
        final_length = max_length - len(extension)
        filename = filename[:final_length]

    return f"{filename}{extension}"


def sanitize_windows_filename(filename: str) -> str:
    filename = "".join(char for char in filename if char not in WIN_PATH_BLACKLIST)
    filename = "".join(char for char in filename if ord(char) > 31)

    filename = unicodedata.normalize("NFKD", filename)
    filename = filename.rstrip(". ")
    filename = filename.strip()

    if all(char == "." for char in filename):
        filename = f"__{filename}"
    if filename.upper() in WIN_RESERVED_FILENAMES:
        filename = f"__{filename}"
    if len(filename) == 0:
        filename = "__"

    return filename


def make_path_from_jid(base_path: Path, jid: JID) -> Path:
    assert jid.domain is not None
    domain = jid.domain[:50]

    if jid.localpart is None:
        return base_path / domain

    path = base_path / domain / sanitize_filename(jid.localpart)
    if jid.resource is not None:
        return path / sanitize_filename(jid.resource, max_length=30)
    return path


def write_file_async(
    path: Path,
    data: bytes,
    callback: Callable[[bool, GLib.Error | None, Any], Any],
    user_data: Any | None = None,
):

    def _on_write_finished(
        outputstream: Gio.OutputStream, result: Gio.AsyncResult, _data: bytes
    ) -> None:
        try:
            successful, _bytes_written = outputstream.write_all_finish(result)
        except GLib.Error as error:
            callback(False, error, user_data)
        else:
            callback(successful, None, user_data)

    def _on_file_created(file: Gio.File, result: Gio.AsyncResult) -> None:
        try:
            outputstream = file.create_finish(result)
        except GLib.Error as error:
            callback(False, error, user_data)
            return

        # Pass data as user_data to the callback, because
        # write_all_async() takes no reference to the data
        # and python gc collects it before the data is written
        outputstream.write_all_async(
            data, GLib.PRIORITY_DEFAULT, None, _on_write_finished, data
        )

    file = Gio.File.new_for_path(str(path))
    file.create_async(
        Gio.FileCreateFlags.PRIVATE, GLib.PRIORITY_DEFAULT, None, _on_file_created
    )


def load_file_async(
    path: Path,
    callback: Callable[[bytes | None, GLib.Error | None, Any], Any],
    user_data: Any | None = None,
) -> None:

    def _on_load_finished(file: Gio.File, result: Gio.AsyncResult) -> None:

        try:
            _, contents, _ = file.load_contents_finish(result)
        except GLib.Error as error:
            callback(None, error, user_data)
        else:
            # "contents" may be an empty bytes object
            callback(contents or None, None, user_data)

    file = Gio.File.new_for_path(str(path))
    file.load_contents_async(None, _on_load_finished)
