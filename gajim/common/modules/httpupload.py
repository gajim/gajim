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

import nbxmpp
from nbxmpp import NS_HTTPUPLOAD
from gi.repository import GLib
from gi.repository import Soup

from gajim.common import app
from gajim.common import ged
from gajim.common.i18n import _
from gajim.common.nec import NetworkIncomingEvent
from gajim.common.helpers import get_tls_error_phrase
from gajim.common.modules.base import BaseModule
from gajim.common.connection_handlers_events import InformationEvent
from gajim.common.connection_handlers_events import MessageOutgoingEvent
from gajim.common.connection_handlers_events import GcMessageOutgoingEvent

NS_HTTPUPLOAD_0 = NS_HTTPUPLOAD + ':0'


class HTTPUpload(BaseModule):
    def __init__(self, con):
        BaseModule.__init__(self, con)

        self.available = False
        self.component = None
        self.httpupload_namespace = None
        self.max_file_size = None  # maximum file size in bytes

        self._allowed_headers = ['Authorization', 'Cookie', 'Expires']
        self._text = []
        self._queued_messages = {}
        self._session = Soup.Session()
        self._session.props.ssl_strict = False
        self._session.props.user_agent = 'Gajim %s' % app.version

        # pylint: disable=line-too-long
        self.register_events([
            ('stanza-message-outgoing', ged.OUT_PREGUI, self._handle_outgoing_stanza),
            ('gc-stanza-message-outgoing', ged.OUT_PREGUI, self._handle_outgoing_stanza),
        ])
        # pylint: enable=line-too-long

    def pass_disco(self, info):
        if NS_HTTPUPLOAD_0 in info.features:
            self.httpupload_namespace = NS_HTTPUPLOAD_0
        elif NS_HTTPUPLOAD in info.features:
            self.httpupload_namespace = NS_HTTPUPLOAD
        else:
            return

        self.component = info.jid
        self._log.info('Discovered component: %s', info.jid)

        for form in info.dataforms:
            form_type = form.vars.get('FORM_TYPE')
            if (form_type is None or
                    form_type.value != self.httpupload_namespace):
                continue
            size = form.vars.get('max-file-size')
            if size is not None:
                try:
                    self.max_file_size = float(size.value)
                except Exception:
                    self._log.info('Invalid file size: %s', size.value)
                    size = None
                break

        if self.max_file_size is None:
            self._log.warning('Component does not provide maximum file size')
        else:
            self._log.info('Component has a maximum file size of: %s MiB',
                           self.max_file_size / (1024 * 1024))

        self.available = True

        for ctrl in app.interface.msg_win_mgr.get_controls(acct=self._account):
            ctrl.update_actions()

    def _handle_outgoing_stanza(self, event):
        if event.conn.name != self._account:
            return
        body = event.msg_iq.getTagData('body')
        if body and body in self._text:
            self._text.remove(body)
            # Add oob information before sending message to recipient,
            #  to distinguish HTTP File Upload Link from pasted URL
            oob = event.msg_iq.addChild('x', namespace=nbxmpp.NS_X_OOB)
            oob.addChild('url').setData(body)
            event.additional_data.set_value('gajim', 'oob_url', body)

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
            file = File(path,
                        contact,
                        self._account,
                        mime,
                        encryption,
                        groupchat)
            app.interface.show_httpupload_progress(file)
        except Exception as error:
            self._log.exception('Error while loading file')
            self._raise_information_event('open-file-error2', str(error))
            return

        if encryption is not None:
            app.interface.encrypt_file(file, self._account, self._request_slot)
        else:
            self._request_slot(file)

    def cancel_upload(self, file):
        message = self._queued_messages.get(id(file))
        if message is None:
            return
        self._session.cancel_message(message, Soup.Status.CANCELLED)

    @staticmethod
    def _raise_progress_event(status, file, seen=None, total=None):
        app.nec.push_incoming_event(HTTPUploadProgressEvent(
            None, status=status, file=file, seen=seen, total=total))

    @staticmethod
    def _raise_information_event(dialog_name, args=None):
        app.nec.push_incoming_event(InformationEvent(
            None, dialog_name=dialog_name, args=args))

    def _request_slot(self, file):
        GLib.idle_add(self._raise_progress_event, 'request', file)
        iq = self._build_request(file)
        self._log.info("Sending request for slot")
        self._con.connection.SendAndCallForResponse(
            iq, self._received_slot, {'file': file})

    def _build_request(self, file):
        iq = nbxmpp.Iq(typ='get', to=self.component)
        id_ = app.get_an_id()
        iq.setID(id_)
        if self.httpupload_namespace == NS_HTTPUPLOAD:
            # experimental namespace
            request = iq.setTag(name="request",
                                namespace=self.httpupload_namespace)
            request.addChild('filename', payload=os.path.basename(file.path))
            request.addChild('size', payload=file.size)
            request.addChild('content-type', payload=file.mime)
        else:
            attr = {'filename': os.path.basename(file.path),
                    'size': file.size,
                    'content-type': file.mime}
            iq.setTag(name="request",
                      namespace=self.httpupload_namespace,
                      attrs=attr)
        return iq

    @staticmethod
    def _get_slot_error_message(stanza):
        tmp = stanza.getTag('error').getTag('file-too-large')

        if tmp is not None:
            max_file_size = float(tmp.getTag('max-file-size').getData())
            return _('File is too large, maximum allowed file size is: %s') % \
                GLib.format_size_full(max_file_size,
                                      GLib.FormatSizeFlags.IEC_UNITS)

        return stanza.getErrorMsg()

    def _received_slot(self, _con, stanza, file):
        self._log.info("Received slot")
        if stanza.getType() == 'error':
            self._raise_progress_event('close', file)
            self._raise_information_event('request-upload-slot-error',
                                          self._get_slot_error_message(stanza))
            self._log.error(stanza)
            return

        try:
            if self.httpupload_namespace == NS_HTTPUPLOAD:
                file.put_uri = stanza.getTag('slot').getTag('put').getData()
                file.get_uri = stanza.getTag('slot').getTag('get').getData()
            else:
                slot = stanza.getTag('slot')
                file.put_uri = slot.getTagAttr('put', 'url')
                file.get_uri = slot.getTagAttr('get', 'url')
                for header in slot.getTag('put').getTags('header'):
                    name = header.getAttr('name')
                    if name not in self._allowed_headers:
                        raise ValueError('Not allowed header')
                    data = header.getData()
                    if '\n' in data:
                        raise ValueError('Newline in header data')
                    file.append_header(name, data)
        except Exception:
            self._log.error("Got invalid stanza: %s", stanza)
            self._log.exception('Error')
            self._raise_progress_event('close', file)
            self._raise_information_event('request-upload-slot-error2')
            return

        if (urlparse(file.put_uri).scheme != 'https' or
                urlparse(file.get_uri).scheme != 'https'):
            self._raise_progress_event('close', file)
            self._raise_information_event('unsecure-error')
            return

        self._log.info('Uploading file to %s', file.put_uri)
        self._log.info('Please download from %s', file.get_uri)

        self._upload_file(file)

    def _upload_file(self, file):
        self._raise_progress_event('upload', file)

        message = Soup.Message.new('PUT', file.put_uri)
        message.connect('starting', self._check_certificate)

        # Set CAN_REBUILD so chunks get discarded after they are beeing
        # written to the network
        message.set_flags(Soup.MessageFlags.CAN_REBUILD)
        message.props.request_body.set_accumulate(False)

        message.props.request_headers.set_content_type(file.mime, None)
        message.props.request_headers.set_content_length(file.size)
        for name, value in file.headers:
            message.props.request_headers.append(name, value)

        message.connect('wrote-headers', self._on_wrote_headers, file)
        message.connect('wrote-chunk', self._on_wrote_chunk, file)

        self._queued_messages[id(file)] = message
        self._session.queue_message(message, self._on_finish, file)

    def _check_certificate(self, message):
        https_used, _tls_certificate, tls_errors = message.get_https_status()
        if not https_used:
            self._log.warning('HTTPS was not used for upload')
            self._session.cancel_message(message, Soup.Status.CANCELLED)
            return

        if not app.config.get_per('accounts',
                                  self._account,
                                  'httpupload_verify'):
            return

        if tls_errors:
            phrase = get_tls_error_phrase(tls_errors)
            self._log.warning('TLS verification failed: %s')
            self._session.cancel_message(message, Soup.Status.CANCELLED)
            self._raise_information_event('httpupload-error', phrase)
            return

    def _on_finish(self, _session, message, file):
        self._raise_progress_event('close', file)

        self._queued_messages.pop(id(file), None)
        file.set_finished()

        if message.props.status_code == Soup.Status.CANCELLED:
            self._log.info('Upload cancelled')
            return

        if message.props.status_code in (Soup.Status.OK, Soup.Status.CREATED):
            self._log.info('Upload completed successfully')
            uri = file.get_transformed_uri()
            self._text.append(uri)

            if file.is_groupchat:
                app.nec.push_outgoing_event(
                    GcMessageOutgoingEvent(None,
                                           account=self._account,
                                           jid=file.contact.jid,
                                           message=uri,
                                           automatic_message=False))
            else:
                app.nec.push_outgoing_event(
                    MessageOutgoingEvent(None,
                                         account=self._account,
                                         jid=file.contact.jid,
                                         message=uri,
                                         type_='chat',
                                         automatic_message=False))

        else:
            phrase = Soup.Status.get_phrase(message.props.status_code)
            self._log.error('Got unexpected http upload response code: %s',
                            phrase)
            self._raise_information_event('httpupload-response-error', phrase)

    def _on_wrote_chunk(self, message, file):
        self._raise_progress_event('update', file, file.seen, file.size)
        if file.is_complete:
            message.props.request_body.complete()
            return

        bytes_ = file.get_chunk()
        self._session.pause_message(message)
        GLib.idle_add(self._append, message, bytes_)

    def _append(self, message, bytes_):
        if message.props.status_code == Soup.Status.CANCELLED:
            return
        self._session.unpause_message(message)
        message.props.request_body.append(bytes_)

    @staticmethod
    def _on_wrote_headers(message, file):
        message.props.request_body.append(file.get_chunk())


class File:
    def __init__(self,
                 path,
                 contact,
                 account,
                 mime,
                 encryption,
                 groupchat):

        self._path = path
        self._encryption = encryption
        self._groupchat = groupchat
        self._contact = contact
        self._account = account
        self._mime = mime

        self.size = os.stat(path).st_size
        self.put_uri = None
        self.get_uri = None
        self._uri_transform_func = None

        self._stream = None
        self._data = None
        self._seen = 0
        self._headers = {}

    @property
    def account(self):
        return self._account

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

    def get_transformed_uri(self):
        if self._uri_transform_func is not None:
            return self._uri_transform_func(self.get_uri)
        return self.get_uri

    @property
    def seen(self):
        return self._seen

    @property
    def path(self):
        return self._path

    @property
    def is_complete(self):
        return self._seen >= self.size

    def append_header(self, name, value):
        self._headers[name] = value

    def set_uri_transform_func(self, func):
        self._uri_transform_func = func

    def set_finished(self):
        self._close()

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


class HTTPUploadProgressEvent(NetworkIncomingEvent):
    name = 'httpupload-progress'


def get_instance(*args, **kwargs):
    return HTTPUpload(*args, **kwargs), 'HTTPUpload'
