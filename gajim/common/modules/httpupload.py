# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# XEP-0363: HTTP File Upload

from __future__ import annotations

from typing import cast

import mimetypes
import os
import tempfile
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

from gi.repository import Gio
from gi.repository import GLib
from nbxmpp.const import HTTPRequestError
from nbxmpp.errors import HTTPUploadStanzaError
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.http import HTTPRequest
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.structs import DiscoInfo
from nbxmpp.structs import HTTPUploadData
from nbxmpp.task import Task
from nbxmpp.util import convert_tls_error_flags

from gajim.common import app
from gajim.common import types
from gajim.common.const import FTState
from gajim.common.events import HTTPUploadError
from gajim.common.events import HTTPUploadStarted
from gajim.common.exceptions import FileError
from gajim.common.filetransfer import FileTransfer
from gajim.common.helpers import get_random_string
from gajim.common.helpers import get_tls_error_phrases
from gajim.common.i18n import _
from gajim.common.modules.base import BaseModule
from gajim.common.structs import OutgoingMessage
from gajim.common.util.http import create_http_request


class HTTPUpload(BaseModule):

    _nbxmpp_extends = 'HTTPUpload'

    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)

        self.available = False
        self.component: JID | None = None
        self.httpupload_namespace: str | None = None
        self.max_file_size: float | None = None  # max file size in bytes

        self._requests_in_progress: dict[int, HTTPRequest] = {}

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
        self._start_transfer(transfer)

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

        mime = mimetypes.MimeTypes().guess_type(path)[0]
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

            type_ = 'chat'
            if transfer.is_groupchat:
                type_ = 'groupchat'

            message = OutgoingMessage(account=transfer.account,
                                      contact=transfer.contact,
                                      text=uri,
                                      type_=type_,
                                      oob_url=uri)

            self._client.send_message(message)

    def _on_cancel_upload(self,
                          transfer: HTTPFileTransfer,
                          _signal_name: str
                          ) -> None:

        transfer.set_cancelled()

        key = (transfer.account, transfer.contact.jid)
        self._running_transfers[key].discard(transfer)

        request = self._requests_in_progress.get(id(transfer))
        if request is None:
            return

        request.cancel()

    def _start_transfer(self, transfer: HTTPFileTransfer) -> None:
        if transfer.encryption is not None and not transfer.is_encrypted:
            transfer.set_encrypting()
            if transfer.encryption == 'OMEMO':
                self._client.get_module('OMEMO').encrypt_file(
                    transfer, self._start_transfer)
                return

            plugin = app.plugin_manager.encryption_plugins[transfer.encryption]
            if hasattr(plugin, 'encrypt_file'):
                plugin.encrypt_file(transfer,
                                    self._account,
                                    self._start_transfer)
            else:
                transfer.set_error('encryption-not-available')

            return

        transfer.set_preparing()
        self._log.info('Sending request for slot')
        self._nbxmpp('HTTPUpload').request_slot(
            jid=self.component,
            filename=transfer.filename,
            size=transfer.size,
            content_type=transfer.mime,
            callback=self._received_slot,
            user_data=transfer)

    def _received_slot(self, task: Task) -> None:
        transfer = cast(HTTPFileTransfer, task.get_user_data())

        try:
            result = task.finish()
        except (StanzaError,
                HTTPUploadStanzaError,
                MalformedStanzaError) as error:

            if error.app_condition == 'file-too-large':
                size_text = GLib.format_size_full(
                    error.get_max_file_size(),
                    GLib.FormatSizeFlags.IEC_UNITS)

                error_text = _('File is too large, '
                               'maximum allowed file size is: %s') % size_text
                transfer.set_error('file-too-large', error_text)

            else:
                transfer.set_error('misc', str(error))

            return

        transfer.process_result(result)

        if (urlparse(transfer.put_uri).scheme != 'https' or
                urlparse(transfer.get_uri).scheme != 'https'):
            transfer.set_error('unsecure')
            return

        self._log.info('Uploading file to %s', transfer.put_uri)
        self._log.info('Please download from %s', transfer.get_uri)

        self._upload_file(transfer)

    def _upload_file(self, transfer: HTTPFileTransfer) -> None:
        transfer.set_started()

        assert transfer.put_uri is not None
        request = create_http_request(self._account)
        request.set_user_data(transfer)
        request.connect('accept-certificate', self._accept_certificate)
        request.connect('request-progress', self._on_request_progress)

        request.set_request_body_from_path(transfer.mime, transfer.payload_path)

        for name, value in transfer.headers.items():
            request.get_request_headers().append(name, value)

        request.send('PUT', transfer.put_uri, callback=self._on_finish)

        self._requests_in_progress[id(transfer)] = request

    def _accept_certificate(self,
                            request: HTTPRequest,
                            _certificate: Gio.TlsCertificate,
                            certificate_errors: Gio.TlsCertificateFlags,
                            ) -> bool:

        transfer = request.get_user_data()
        phrases = get_tls_error_phrases(
            convert_tls_error_flags(certificate_errors))
        self._log.warning(
            'TLS verification failed: %s (0x%02x)', phrases, certificate_errors)

        transfer.set_error('tls-verification-failed', phrases[0])
        return False

    def _on_finish(self, request: HTTPRequest) -> None:
        transfer = request.get_user_data()

        self._requests_in_progress.pop(id(transfer), None)

        key = (transfer.account, transfer.contact.jid)
        self._running_transfers[key].discard(transfer)

        if not request.is_complete():
            error = request.get_error_string()
            if request.get_error() == HTTPRequestError.CANCELLED:
                self._log.info('Upload cancelled')
            else:
                if not error:
                    error = _('Upload could not be completed.')
                transfer.set_error('http-response', error)
            return

        transfer.set_finished()
        self._log.info('Upload completed successfully')

    def _on_request_progress(self,
                             request: HTTPRequest,
                             progress: float
                             ) -> None:

        transfer = request.get_user_data()
        transfer.set_progress(progress)


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
                 contact: types.ContactT,
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
        self._uri_transform_func: Callable[[str], str] | None = None

        self._data: bytes | None = None
        self._headers: dict[str, str] = {}

        self._is_encrypted = False
        self._temp_path = self._get_temp_path()

    @property
    def size(self) -> int:
        if self._encryption is not None and not self._is_encrypted:
            raise ValueError('File size unknown at this point')
        return self.payload_path.stat().st_size

    @size.setter
    def size(self, size: int) -> None:
        # Backwards compatibility with plugins
        pass

    @property
    def mime(self) -> str:
        return self._mime

    @property
    def contact(self) -> types.ContactT:
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

    @property
    def payload_path(self) -> Path:
        if self._encryption is not None:
            return self._temp_path
        return self._path

    @property
    def is_encrypted(self) -> bool:
        return self._is_encrypted

    def get_transformed_uri(self) -> str:
        if self._uri_transform_func is not None:
            return self._uri_transform_func(self.get_uri)
        return self.get_uri

    def set_uri_transform_func(self, func: Callable[[str], str]) -> None:
        self._uri_transform_func = func

    @property
    def filename(self) -> str:
        return self._path.name

    @staticmethod
    def _get_temp_path() -> Path:
        tempdir = tempfile.gettempdir()
        return Path(tempdir) / get_random_string(16)

    def set_error(self, domain: str, text: str = '') -> None:
        if not text:
            text = self._errors.get(domain) or self._errors['unknown']

        super().set_error(domain, text)
        self._cleanup()

    def set_finished(self) -> None:
        super().set_finished()
        self._cleanup()

    def set_encrypted_data(self, data: bytes) -> None:
        self._temp_path.write_bytes(data)
        self._is_encrypted = True

    def get_data(self) -> bytes:
        return self._path.read_bytes()

    def process_result(self, result: HTTPUploadData) -> None:
        self.put_uri = result.put_uri
        self.get_uri = result.get_uri
        self._headers = result.headers

    def _cleanup(self) -> None:
        if self._temp_path.exists():
            self._temp_path.unlink()
