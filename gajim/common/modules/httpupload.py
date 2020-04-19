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


import os
import io
from urllib.parse import urlparse
import mimetypes

from nbxmpp.namespaces import Namespace
from nbxmpp.util import is_error_result
from nbxmpp.util import convert_tls_error_flags
from gi.repository import GLib
from gi.repository import Soup

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.helpers import get_tls_error_phrase
from gajim.common.helpers import get_user_proxy
from gajim.common.const import FTState
from gajim.common.filetransfer import FileTransfer
from gajim.common.modules.base import BaseModule
from gajim.common.structs import OutgoingMessage
from gajim.common.connection_handlers_events import InformationEvent


class HTTPUpload(BaseModule):

    _nbxmpp_extends = 'HTTPUpload'

    def __init__(self, con):
        BaseModule.__init__(self, con)

        self.available = False
        self.component = None
        self.httpupload_namespace = None
        self.max_file_size = None  # maximum file size in bytes

        self._proxy_resolver = None
        self._queued_messages = {}
        self._session = Soup.Session()
        self._session.props.ssl_strict = False
        self._session.props.user_agent = 'Gajim %s' % app.version

    def _set_proxy_if_available(self):
        proxy = get_user_proxy(self._account)
        if proxy is None:
            self._proxy_resolver = None
            self._session.props.proxy_resolver = None
        else:
            self._proxy_resolver = proxy.get_resolver()
            self._session.props.proxy_resolver = self._proxy_resolver

    def pass_disco(self, info):
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
            size = GLib.format_size_full(self.max_file_size,
                                         GLib.FormatSizeFlags.IEC_UNITS)
            self._log.info('Component has a maximum file size of: %s', size)

        for ctrl in app.interface.msg_win_mgr.get_controls(acct=self._account):
            ctrl.update_actions()

    def check_file_before_transfer(self, path, encryption, contact,
                                   groupchat=False):
        if not path or not os.path.exists(path):
            return

        invalid_file = False
        stat = os.stat(path)

        if os.path.isfile(path):
            if stat[6] == 0:
                invalid_file = True
                msg = _('File is empty')
        else:
            invalid_file = True
            msg = _('File does not exist')

        if self.max_file_size is not None and \
                stat.st_size > self.max_file_size:
            invalid_file = True
            size = GLib.format_size_full(self.max_file_size,
                                         GLib.FormatSizeFlags.IEC_UNITS)
            msg = _('File is too large, '
                    'maximum allowed file size is: %s') % size

        if invalid_file:
            self._raise_information_event('open-file-error2', msg)
            return

        mime = mimetypes.MimeTypes().guess_type(path)[0]
        if not mime:
            mime = 'application/octet-stream'  # fallback mime type
        self._log.info("Detected MIME type of file: %s", mime)

        try:
            transfer = HTTPFileTransfer(self._account,
                                        self._cancel_upload,
                                        path,
                                        contact,
                                        mime,
                                        encryption,
                                        groupchat)
            app.interface.show_httpupload_progress(transfer)
        except Exception as error:
            self._log.exception('Error while loading file')
            self._raise_information_event('open-file-error2', str(error))
            return

        if encryption is not None:
            app.interface.encrypt_file(transfer,
                                       self._account,
                                       self._request_slot)
        else:
            self._request_slot(transfer)

    def _cancel_upload(self, transfer):
        message = self._queued_messages.get(id(transfer))
        if message is None:
            return
        self._session.cancel_message(message, Soup.Status.CANCELLED)

    @staticmethod
    def _raise_information_event(dialog_name, args=None):
        app.nec.push_incoming_event(InformationEvent(
            None, dialog_name=dialog_name, args=args))

    def _request_slot(self, transfer):
        transfer.set_preparing()
        self._log.info('Sending request for slot')
        self._nbxmpp('HTTPUpload').request_slot(
            jid=self.component,
            filename=transfer.filename,
            size=transfer.size,
            content_type=transfer.mime,
            callback=self._received_slot,
            user_data=transfer)

    def _received_slot(self, result, transfer):
        if is_error_result(result):
            transfer.set_error()

            if result.app_condition == 'file-too-large':
                size_text = GLib.format_size_full(
                    result.get_max_file_size(),
                    GLib.FormatSizeFlags.IEC_UNITS)

                error_text = _('File is too large, '
                               'maximum allowed file size is: %s' % size_text)
            else:
                error_text = str(result)
                self._log.warning(result)

            self._raise_information_event('request-upload-slot-error',
                                          error_text)
            return

        transfer.process_result(result)

        if (urlparse(transfer.put_uri).scheme != 'https' or
                urlparse(transfer.get_uri).scheme != 'https'):
            transfer.set_error()
            self._raise_information_event('unsecure-error')
            return

        self._log.info('Uploading file to %s', transfer.put_uri)
        self._log.info('Please download from %s', transfer.get_uri)

        self._upload_file(transfer)

    def _upload_file(self, transfer):
        transfer.set_started()

        message = Soup.Message.new('PUT', transfer.put_uri)
        message.connect('starting', self._check_certificate)

        # Set CAN_REBUILD so chunks get discarded after they are beeing
        # written to the network
        message.set_flags(Soup.MessageFlags.CAN_REBUILD |
                          Soup.MessageFlags.NO_REDIRECT)

        message.props.request_body.set_accumulate(False)

        message.props.request_headers.set_content_type(transfer.mime, None)
        message.props.request_headers.set_content_length(transfer.size)
        for name, value in transfer.headers:
            message.props.request_headers.append(name, value)

        message.connect('wrote-headers', self._on_wrote_headers, transfer)
        message.connect('wrote-chunk', self._on_wrote_chunk, transfer)

        self._queued_messages[id(transfer)] = message
        self._set_proxy_if_available()
        self._session.queue_message(message, self._on_finish, transfer)

    def _check_certificate(self, message):
        https_used, tls_certificate, tls_errors = message.get_https_status()
        if not https_used:
            self._log.warning('HTTPS was not used for upload')
            self._session.cancel_message(message, Soup.Status.CANCELLED)
            return

        tls_errors = convert_tls_error_flags(tls_errors)
        if app.cert_store.verify(tls_certificate, tls_errors):
            return

        for error in tls_errors:
            phrase = get_tls_error_phrase(error)
            self._log.warning('TLS verification failed: %s', phrase)
        self._session.cancel_message(message, Soup.Status.CANCELLED)
        self._raise_information_event('httpupload-error', phrase)

    def _on_finish(self, _session, message, transfer):
        self._queued_messages.pop(id(transfer), None)
        transfer.set_finished()

        if message.props.status_code == Soup.Status.CANCELLED:
            self._log.info('Upload cancelled')
            return

        if message.props.status_code in (Soup.Status.OK, Soup.Status.CREATED):
            self._log.info('Upload completed successfully')
            uri = transfer.get_transformed_uri()

            type_ = 'chat'
            if transfer.is_groupchat:
                type_ = 'groupchat'

            message = OutgoingMessage(account=self._account,
                                      contact=transfer.contact,
                                      message=uri,
                                      type_=type_,
                                      oob_url=uri)

            self._con.send_message(message)

        else:
            phrase = Soup.Status.get_phrase(message.props.status_code)
            self._log.error('Got unexpected http upload response code: %s',
                            phrase)
            self._raise_information_event('httpupload-response-error', phrase)

    def _on_wrote_chunk(self, message, transfer):
        transfer.update_progress()
        if transfer.is_complete:
            message.props.request_body.complete()
            return

        bytes_ = transfer.get_chunk()
        self._session.pause_message(message)
        GLib.idle_add(self._append, message, bytes_)

    def _append(self, message, bytes_):
        if message.props.status_code == Soup.Status.CANCELLED:
            return
        self._session.unpause_message(message)
        message.props.request_body.append(bytes_)

    @staticmethod
    def _on_wrote_headers(message, transfer):
        message.props.request_body.append(transfer.get_chunk())


class HTTPFileTransfer(FileTransfer):

    _state_descriptions = {
        FTState.ENCRYPTING: _('Encrypting file…'),
        FTState.PREPARING: _('Requesting HTTP File Upload Slot…'),
        FTState.STARTED: _('Uploading via HTTP File Upload…'),
    }

    def __init__(self,
                 account,
                 cancel_func,
                 path,
                 contact,
                 mime,
                 encryption,
                 groupchat):
        FileTransfer.__init__(self, account, cancel_func=cancel_func)

        self._path = path
        self._encryption = encryption
        self._groupchat = groupchat
        self._contact = contact
        self._mime = mime

        self.size = os.stat(path).st_size
        self.put_uri = None
        self.get_uri = None
        self._uri_transform_func = None

        self._stream = None
        self._data = None
        self._headers = {}

    @property
    def mime(self):
        return self._mime

    @property
    def contact(self):
        return self._contact

    @property
    def is_groupchat(self):
        return self._groupchat

    @property
    def encryption(self):
        return self._encryption

    @property
    def headers(self):
        return self._headers

    @property
    def path(self):
        return self._path

    def get_transformed_uri(self):
        if self._uri_transform_func is not None:
            return self._uri_transform_func(self.get_uri)
        return self.get_uri

    def set_uri_transform_func(self, func):
        self._uri_transform_func = func

    @property
    def filename(self):
        return os.path.basename(self._path)

    def set_error(self, text=''):
        self._close()
        super().set_error(text)

    def set_finished(self):
        self._close()
        super().set_finished()

    def set_encrypted_data(self, data):
        self._data = data

    def _close(self):
        if self._stream is not None:
            self._stream.close()

    def get_chunk(self):
        if self._stream is None:
            if self._encryption is None:
                self._stream = open(self._path, 'rb')
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

    def get_data(self):
        with open(self._path, 'rb') as file:
            data = file.read()
        return data

    def process_result(self, result):
        self.put_uri = result.put_uri
        self.get_uri = result.get_uri
        self._headers = result.headers


def get_instance(*args, **kwargs):
    return HTTPUpload(*args, **kwargs), 'HTTPUpload'
