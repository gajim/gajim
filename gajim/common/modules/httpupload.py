# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# XEP-0363: HTTP File Upload

from __future__ import annotations

from typing import cast

import binascii
import os
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

from gi.repository import GLib
from gi.repository import GObject
from nbxmpp.errors import HTTPUploadStanzaError
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.structs import DiscoInfo
from nbxmpp.structs import HTTPUploadData
from nbxmpp.task import Task

from gajim.common import app
from gajim.common import types
from gajim.common.aes import AESKeyData
from gajim.common.const import FTState
from gajim.common.events import HTTPUploadError
from gajim.common.events import HTTPUploadStarted
from gajim.common.exceptions import FileError
from gajim.common.file_transfer_manager import FileTransfer as FileTransferM
from gajim.common.filetransfer import FileTransfer
from gajim.common.helpers import determine_proxy
from gajim.common.i18n import _
from gajim.common.modules.base import BaseModule
from gajim.common.multiprocess.http import CancelledError
from gajim.common.multiprocess.http import UploadResult
from gajim.common.structs import OutgoingMessage
from gajim.common.util.preview import guess_mime_type


class HTTPUpload(BaseModule):

    _nbxmpp_extends = 'HTTPUpload'

    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)

        self.available = False
        self.component: JID | None = None
        self.httpupload_namespace: str | None = None
        self.max_file_size: float | None = None  # max file size in bytes

        self._requests_in_progress: dict[int, FileTransferM[UploadResult]] = {}

        self._running_transfers: dict[
            tuple[str, JID], set[HTTPFileTransfer]] = defaultdict(set)

    def pass_disco(self, info: DiscoInfo) -> None:
        if not info.has_httpupload:
            return

        self.available = True
        self.httpupload_namespace = Namespace.HTTPUPLOAD_0
        self.component = info.jid
        self.max_file_size = info.httpupload_max_file_size

        self._log.info('Discovered component: %s', info.jid)

        if self.max_file_size is None:
            self._log.warning('Component does not provide maximum file size')
        else:
            size = GLib.format_size_full(int(self.max_file_size),
                                         GLib.FormatSizeFlags.IEC_UNITS)
            self._log.info('Component has a maximum file size of: %s', size)

    def get_running_transfers(self,
                              contact: types.ChatContactT
                              ) -> set[HTTPFileTransfer] | None:

        return self._running_transfers.get((contact.account, contact.jid))

    def send_file(self, contact: types.ChatContactT, path: Path) -> None:
        encryption = contact.settings.get('encryption') or None

        try:
            transfer = self._make_transfer(
                path,
                encryption,
                contact)
        except FileError as error:
            event = HTTPUploadError(
                contact.account,
                contact.jid,
                _('Could not open file (%s)') % str(error))
            app.ged.raise_event(event)
            return

        transfer.connect('cancel', self._on_cancel_upload)
        transfer.connect('state-changed', self._on_http_upload_state_changed)

        event = HTTPUploadStarted(
            contact.account,
            contact.jid,
            transfer)
        app.ged.raise_event(event)

        transfer.set_preparing()
        self._log.info('Sending request for slot')
        self._nbxmpp('HTTPUpload').request_slot(
            jid=self.component,
            filename=transfer.filename,
            size=transfer.size,
            content_type=transfer.mime,
            callback=self._received_slot,
            user_data=transfer
        )

    def _make_transfer(self,
                       path: Path,
                       encryption: str | None,
                       contact: types.ChatContactT,
                       ) -> HTTPFileTransfer:

        if not path or not path.exists():
            raise FileError(_('Could not access file'))

        invalid_file = False
        msg = ''
        stat = path.stat()

        if os.path.isfile(path):
            if stat[6] == 0:
                invalid_file = True
                msg = _('File is empty')
        else:
            invalid_file = True
            msg = _('File does not exist')

        if (self.max_file_size is not None and
                stat.st_size > self.max_file_size):
            invalid_file = True
            size = GLib.format_size_full(int(self.max_file_size),
                                         GLib.FormatSizeFlags.IEC_UNITS)
            msg = _('File is too large, '
                    'maximum allowed file size is: %s') % size

        if invalid_file:
            raise FileError(msg)

        mime = guess_mime_type(path)
        if not mime:
            mime = 'application/octet-stream'  # fallback mime type
        self._log.info('Detected MIME type of file: %s', mime)

        transfer = HTTPFileTransfer(self._account,
                                    str(path),
                                    contact,
                                    mime,
                                    encryption,
                                    contact.is_groupchat)

        key = (contact.account, contact.jid)
        self._running_transfers[key].add(transfer)

        return transfer

    def _on_http_upload_state_changed(self,
                                      transfer: HTTPFileTransfer,
                                      _signal_name: str,
                                      state: FTState
                                      ) -> None:

        if state.is_finished:
            uri = transfer.get_transformed_uri()

            message = OutgoingMessage(account=transfer.account,
                                      contact=transfer.contact,
                                      text=uri,
                                      oob_url=uri)

            self._client.send_message(message)

    def _on_cancel_upload(self,
                          transfer: HTTPFileTransfer,
                          _signal_name: str
                          ) -> None:

        transfer.set_cancelled()

        key = (transfer.account, transfer.contact.jid)
        self._running_transfers[key].discard(transfer)

        obj = self._requests_in_progress.get(id(transfer))
        if obj is None:
            return

        obj.cancel()

    @staticmethod
    def _uri_is_acceptable(uri: str | None) -> bool:
        if not uri:
            return False

        parts = urlparse(uri)
        if parts.scheme not in ("http", "https"):
            return False

        # Remove port
        domain = parts.netloc.split(":", maxsplit=1)[0]
        if domain.endswith(".onion"):
            return True

        return parts.scheme != "http"

    def _received_slot(self, task: Task) -> None:
        transfer = cast(HTTPFileTransfer, task.get_user_data())

        try:
            result = cast(HTTPUploadData, task.finish())
        except HTTPUploadStanzaError as error:

            if error.app_condition == 'file-too-large':
                size = error.get_max_file_size()
                if size is not None:
                    size_text = GLib.format_size_full(
                        int(size), GLib.FormatSizeFlags.IEC_UNITS
                    )
                else:
                    size_text = 'Unknown'

                error_text = _('File is too large, '
                               'maximum allowed file size is: %s') % size_text
                transfer.set_error('file-too-large', error_text)
            else:
                transfer.set_error('misc', str(error))
            return

        except Exception as error:
            transfer.set_error('misc', str(error))
            return

        transfer.process_result(result)

        if (not self._uri_is_acceptable(transfer.put_uri) or
                not self._uri_is_acceptable(transfer.get_uri)):
            transfer.set_error('unsecure')
            return

        self._log.info('Uploading file to %s', transfer.put_uri)
        self._log.info('Please download from %s', transfer.get_uri)

        self._upload_file(transfer)

    def _upload_file(self, transfer: HTTPFileTransfer) -> None:
        transfer.set_started()

        assert transfer.put_uri is not None
        obj = app.ftm.http_upload(
            transfer.put_uri,
            transfer.mime,
            transfer.path,
            transfer.headers,
            with_progress=True,
            encryption_data=transfer.get_encryption_data(),
            proxy=determine_proxy(self._account),
            user_data=transfer,
            callback=self._on_finish,
        )
        if obj is None:
            return

        obj.connect('notify::progress', self._on_upload_progress)

        self._requests_in_progress[id(transfer)] = obj

    def _on_finish(self, ftobj: FileTransferM[UploadResult]) -> None:

        transfer = cast(HTTPFileTransfer, ftobj.get_user_data())

        self._requests_in_progress.pop(id(transfer), None)

        key = (transfer.account, transfer.contact.jid)
        self._running_transfers[key].discard(transfer)

        try:
            ftobj.raise_for_error()
        except CancelledError:
            self._log.info('Upload cancelled')

        except Exception as error:
            self._log.error(error)
            transfer.set_error('http-response', str(error))

        else:
            transfer.set_finished()
            self._log.info('Upload completed successfully')

    def _on_upload_progress(
        self,
        ftobj: FileTransferM[UploadResult],
        _param: GObject.ParamSpec
    ) -> None:

        transfer = cast(HTTPFileTransfer, ftobj.get_user_data())
        transfer.set_progress(ftobj.progress)


class HTTPFileTransfer(FileTransfer):

    _state_descriptions = {
        FTState.ENCRYPTING: _('Encrypting file…'),
        FTState.PREPARING: _('Requesting HTTP File Upload Slot…'),
        FTState.STARTED: _('Uploading via HTTP File Upload…'),
    }

    _errors = {
        'unsecure': _('The server returned an insecure transport (HTTP).'),
        'encryption-not-available': _('There is no encryption method available '
                                      'for the chosen encryption.'),
        'unknown': _('Unknown error.')
    }

    def __init__(self,
                 account: str,
                 path: str,
                 contact: types.ChatContactT,
                 mime: str,
                 encryption: str | None,
                 groupchat: bool
                 ) -> None:

        FileTransfer.__init__(self, account)

        self._path = Path(path)
        self._encryption = encryption
        self._groupchat = groupchat
        self._contact = contact
        self._mime = mime

        self.put_uri: str | None = None
        self.get_uri: str | None = None

        self._data: bytes | None = None
        self._headers: dict[str, str] = {}

        self._aes_key_data = None
        if encryption:
            self._aes_key_data = AESKeyData.init()

    @property
    def size(self) -> int:
        size = self._path.stat().st_size
        if self._encryption:
            return size + 16
        return size

    @size.setter
    def size(self, size: int) -> None:
        # Backwards compatibility with plugins
        pass

    @property
    def mime(self) -> str:
        return self._mime

    @property
    def contact(self) -> types.ChatContactT:
        return self._contact

    @property
    def is_groupchat(self) -> bool:
        return self._groupchat

    @property
    def encryption(self) -> str | None:
        return self._encryption

    @property
    def headers(self) -> dict[str, str]:
        return self._headers

    @property
    def path(self) -> Path:
        return self._path

    def get_encryption_data(self) -> AESKeyData | None:
        return self._aes_key_data

    def get_transformed_uri(self) -> str:
        assert self.get_uri is not None
        if self._aes_key_data is not None:
            fragment = binascii.hexlify(
                self._aes_key_data.iv + self._aes_key_data.key).decode()
            return f'aesgcm{self.get_uri[5:]}#{fragment}'

        return self.get_uri

    @property
    def filename(self) -> str:
        return self._path.name

    def set_error(self, domain: str, text: str = '') -> None:
        if not text:
            text = self._errors.get(domain) or self._errors['unknown']

        super().set_error(domain, text)

    def process_result(self, result: HTTPUploadData) -> None:
        self.put_uri = result.put_uri
        self.get_uri = result.get_uri
        self._headers = result.headers
