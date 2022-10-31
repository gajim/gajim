# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

# XEP-0363: HTTP File Upload

from __future__ import annotations

from typing import cast
from typing import Callable
from typing import Optional

import os
import io
from urllib.parse import urlparse
import mimetypes
from collections import defaultdict
from pathlib import Path

from nbxmpp.errors import StanzaError
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import HTTPUploadStanzaError
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.structs import DiscoInfo
from nbxmpp.structs import HTTPUploadData
from nbxmpp.task import Task
from nbxmpp.util import convert_tls_error_flags

from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Soup

from gajim.common import app
from gajim.common import types
from gajim.common.events import HTTPUploadError
from gajim.common.events import HTTPUploadStarted
from gajim.common.i18n import _
from gajim.common.helpers import get_tls_error_phrase
from gajim.common.helpers import get_account_proxy
from gajim.common.const import FTState
from gajim.common.filetransfer import FileTransfer
from gajim.common.modules.base import BaseModule
from gajim.common.exceptions import FileError
from gajim.common.structs import OutgoingMessage


class HTTPUpload(BaseModule):

    _nbxmpp_extends = 'HTTPUpload'

    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)

        self.available = False
        self.component: Optional[JID] = None
        self.httpupload_namespace: Optional[str] = None
        self.max_file_size: Optional[float] = None  # max file size in bytes

        self._proxy_resolver: Optional[Gio.SimpleProxyResolver] = None
        self._queued_messages: dict[int, Soup.Message] = {}
        self._session = Soup.Session()
        self._session.props.ssl_strict = False
        self._session.props.user_agent = f'Gajim {app.version}'

        self._running_transfers: dict[
            tuple[str, JID], set[HTTPFileTransfer]] = defaultdict(set)

    def _set_proxy_if_available(self) -> None:
        proxy = get_account_proxy(self._account)
        if proxy is None:
            self._proxy_resolver = None
            self._session.props.proxy_resolver = None
        else:
            self._proxy_resolver = proxy.get_resolver()
            self._session.props.proxy_resolver = self._proxy_resolver

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
                              ) -> Optional[set[HTTPFileTransfer]]:

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
                       encryption: Optional[str],
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
                                      message=uri,
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

        message = self._queued_messages.get(id(transfer))
        if message is None:
            return

        self._session.cancel_message(message, Soup.Status.CANCELLED)

    def _start_transfer(self, transfer: HTTPFileTransfer) -> None:
        if transfer.encryption is not None and not transfer.is_encrypted:
            transfer.set_encrypting()
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
                               'maximum allowed file size is: %s' % size_text)
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
        message = Soup.Message.new('PUT', transfer.put_uri)
        message.connect('starting', self._check_certificate, transfer)

        # Set CAN_REBUILD so chunks get discarded after they have been
        # written to the network
        message.set_flags(Soup.MessageFlags.CAN_REBUILD |
                          Soup.MessageFlags.NO_REDIRECT)

        assert message.props.request_body is not None
        message.props.request_body.set_accumulate(False)

        assert message.props.request_headers is not None
        message.props.request_headers.set_content_type(transfer.mime, None)
        message.props.request_headers.set_content_length(transfer.size)
        for name, value in transfer.headers.items():
            message.props.request_headers.append(name, value)

        message.connect('wrote-headers', self._on_wrote_headers, transfer)
        message.connect('wrote-chunk', self._on_wrote_chunk, transfer)

        self._queued_messages[id(transfer)] = message
        self._set_proxy_if_available()
        self._session.queue_message(message, self._on_finish, transfer)

    def _check_certificate(self,
                           message: Soup.Message,
                           transfer: HTTPFileTransfer
                           ) -> None:
        https_used, tls_certificate, tls_errors = message.get_https_status()
        if not https_used:
            self._log.warning('HTTPS was not used for upload')
            transfer.set_error('unsecure')
            self._session.cancel_message(message, Soup.Status.CANCELLED)
            return

        tls_errors = convert_tls_error_flags(tls_errors)
        if app.cert_store.verify(tls_certificate, tls_errors):
            return

        phrase = ''
        for error in tls_errors:
            phrase = get_tls_error_phrase(error)
            self._log.warning('TLS verification failed: %s', phrase)

        transfer.set_error('tls-verification-failed', phrase)
        self._session.cancel_message(message, Soup.Status.CANCELLED)

    def _on_finish(self,
                   _session: Soup.Session,
                   message: Soup.Message,
                   transfer: HTTPFileTransfer
                   ) -> None:

        self._queued_messages.pop(id(transfer), None)

        key = (transfer.account, transfer.contact.jid)
        self._running_transfers[key].discard(transfer)

        if message.props.status_code == Soup.Status.CANCELLED:
            self._log.info('Upload cancelled')
            return

        if message.props.status_code in (Soup.Status.OK, Soup.Status.CREATED):
            self._log.info('Upload completed successfully')
            transfer.set_finished()

        else:
            phrase = Soup.Status.get_phrase(message.props.status_code)
            self._log.error('Got unexpected http upload response code: %s',
                            phrase)
            transfer.set_error('http-response', phrase)

    def _on_wrote_chunk(self,
                        message: Soup.Message,
                        transfer: HTTPFileTransfer
                        ) -> None:
        transfer.update_progress()
        if transfer.is_complete:
            assert message.props.request_body is not None
            message.props.request_body.complete()
            return

        bytes_ = transfer.get_chunk()
        assert bytes_ is not None
        self._session.pause_message(message)
        GLib.idle_add(self._append, message, bytes_)

    def _append(self, message: Soup.Message, bytes_: bytes) -> None:
        if message.props.status_code == Soup.Status.CANCELLED:
            return
        self._session.unpause_message(message)
        assert message.props.request_body is not None
        message.props.request_body.append(bytes_)

    @staticmethod
    def _on_wrote_headers(message: Soup.Message,
                          transfer: HTTPFileTransfer
                          ) -> None:
        bytes_ = transfer.get_chunk()
        assert bytes_ is not None
        assert message.props.request_body is not None
        message.props.request_body.append(bytes_)


class HTTPFileTransfer(FileTransfer):

    _state_descriptions = {
        FTState.ENCRYPTING: _('Encrypting file…'),
        FTState.PREPARING: _('Requesting HTTP File Upload Slot…'),
        FTState.STARTED: _('Uploading via HTTP File Upload…'),
    }

    _errors = {
        'unsecure': _('The server returned an insecure transport (HTTP).'),
        'encryption-not-available': _('There is no encryption method available '
                                      'for the chosen encryption.')
    }

    def __init__(self,
                 account: str,
                 path: str,
                 contact: types.ContactT,
                 mime: str,
                 encryption: Optional[str],
                 groupchat: bool
                 ) -> None:

        FileTransfer.__init__(self, account)

        self._path = path
        self._encryption = encryption
        self._groupchat = groupchat
        self._contact = contact
        self._mime = mime

        self.size = os.stat(path).st_size
        self.put_uri: Optional[str] = None
        self.get_uri: Optional[str] = None
        self._uri_transform_func: Optional[Callable[[str], str]] = None

        self._stream = None
        self._data: Optional[bytes] = None
        self._headers: dict[str, str] = {}

        self._is_encrypted = False

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
    def encryption(self) -> Optional[str]:
        return self._encryption

    @property
    def headers(self) -> dict[str, str]:
        return self._headers

    @property
    def path(self) -> str:
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
        return os.path.basename(self._path)

    def set_error(self, domain: str, text: str = '') -> None:
        if not text:
            text = self._errors[domain]

        self._close()
        super().set_error(domain, text)

    def set_finished(self) -> None:
        self._close()
        super().set_finished()

    def set_encrypted_data(self, data: bytes) -> None:
        self._data = data
        self._is_encrypted = True

    def _close(self) -> None:
        if self._stream is not None:
            self._stream.close()

    def get_chunk(self) -> Optional[bytes]:
        if self._stream is None:
            if self._encryption is None:
                self._stream = open(self._path, 'rb')  # pylint: disable=consider-using-with  # noqa: E501
            else:
                self._stream = io.BytesIO(self._data)

        data = self._stream.read(16384)
        if not data:
            self._close()
            return None
        self._seen += len(data)
        if self.is_complete:
            self._close()
        return data

    def get_data(self) -> bytes:
        with open(self._path, 'rb') as file:
            data = file.read()
        return data

    def process_result(self, result: HTTPUploadData) -> None:
        self.put_uri = result.put_uri
        self.get_uri = result.get_uri
        self._headers = result.headers
