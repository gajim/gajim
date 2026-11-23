# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/\>
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import hashlib
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from pathlib import Path

from gajim.common.multiprocess.http import http_request
from gajim.common.multiprocess.http import HTTPResult
from gajim.common.multiprocess.http import InvalidHash


class _EmptyResponseHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass


class ZeroContentLengthTest(unittest.TestCase):
    def setUp(self) -> None:
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _EmptyResponseHandler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        host, port = self._server.server_address[:2]
        self._url = f"http://{host}:{port}/empty.txt"
        self._dir = tempfile.TemporaryDirectory()
        self._output = Path(self._dir.name) / "empty.txt"

    def tearDown(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._dir.cleanup()

    def _request(self, hash_value: str | None) -> HTTPResult:
        return http_request(
            threading.Event(),
            "test",
            "GET",
            self._url,
            5,
            output=self._output,
            hash_value=hash_value,
            proxy="direct://",
        )

    def test_empty_response_without_hash(self) -> None:
        result = self._request(None)
        self.assertEqual(result.content_length, 0)

    def test_empty_response_with_empty_hash(self) -> None:
        result = self._request(hashlib.sha256(b"").hexdigest())
        self.assertEqual(result.content_length, 0)

    def test_empty_response_with_wrong_hash(self) -> None:
        with self.assertRaises(InvalidHash):
            self._request("0" * 64)


if __name__ == "__main__":
    unittest.main()
