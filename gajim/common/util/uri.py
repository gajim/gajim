# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

import logging
import os
import sys
import webbrowser
from pathlib import Path
from urllib.parse import unquote
from urllib.parse import urlparse

from gi.repository import Gio
from gi.repository import GLib
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common import iana
from gajim.common.const import NONREGISTERED_URI_SCHEMES
from gajim.common.const import URIType
from gajim.common.const import XmppUriQuery
from gajim.common.dbus.file_manager import DBusFileManager
from gajim.common.structs import URI
from gajim.common.util.decorators import catch_exceptions
from gajim.common.util.jid import validate_jid

log = logging.getLogger('gajim.c.util.uri')


def is_known_uri_scheme(scheme: str) -> bool:
    '''
    `scheme` is lower-case
    '''
    if scheme in iana.URI_SCHEMES:
        return True
    if scheme in NONREGISTERED_URI_SCHEMES:
        return True
    return scheme in app.settings.get('additional_uri_schemes').split()


def parse_xmpp_uri_query(pct_iquerycomp: str) -> tuple[str, dict[str, str]]:
    '''
    Parses 'mess%61ge;b%6Fdy=Hello%20%F0%9F%8C%90%EF%B8%8F' into
    ('message', {'body': 'Hello 🌐️'}), empty string into ('', {}).
    '''
    # Syntax and terminology from
    # <https://rfc-editor.org/rfc/rfc5122#section-2.2>; the pct_ prefix means
    # percent encoding not being undone yet.

    if not pct_iquerycomp:
        return '', {}

    pct_iquerytype, _, pct_ipairs = pct_iquerycomp.partition(';')
    iquerytype = unquote(pct_iquerytype, errors='strict')
    if not pct_ipairs:
        return iquerytype, {}

    pairs: dict[str, str] = {}
    for pct_ipair in pct_ipairs.split(';'):
        pct_ikey, _, pct_ival = pct_ipair.partition('=')
        pairs[unquote(pct_ikey, errors='strict')] = unquote(pct_ival, errors='replace')
    return iquerytype, pairs


def parse_uri(uri: str) -> URI:
    try:
        urlparts = urlparse(uri)
    except Exception as err:
        return URI(URIType.INVALID, uri, data={'error': str(err)})

    if not urlparts.scheme:
        return URI(URIType.INVALID, uri, data={'error': 'Relative URI'})

    scheme = urlparts.scheme  # urlparse is expected to return it in lower case

    if not is_known_uri_scheme(scheme):
        return URI(URIType.INVALID, uri, data={'error': 'Unknown scheme'})

    if scheme in ('https', 'http'):
        if not urlparts.netloc:
            err = f'No host or empty host in an {scheme} URI'
            return URI(URIType.INVALID, uri, data={'error': err})
        return URI(URIType.WEB, uri)

    if scheme == 'xmpp':
        if not urlparts.path.startswith('/'):
            pct_jid = urlparts.path
        else:
            pct_jid = urlparts.path[1:]

        data: dict[str, str] = {}
        try:
            data['jid'] = unquote(pct_jid, errors='strict')
            validate_jid(data['jid'])
            qtype, qparams = parse_xmpp_uri_query(urlparts.query)
        except ValueError as err:
            data['error'] = str(err)
            return URI(URIType.INVALID, uri, data=data)

        return URI(URIType.XMPP, uri, query_type=qtype, query_params=qparams, data=data)

    if scheme == 'mailto':
        data: dict[str, str] = {}
        try:
            data['addr'] = unquote(urlparts.path, errors='strict')
            validate_jid(data['addr'], 'bare')  # meh, good enough
        except ValueError as err:
            data['error'] = str(err)
            return URI(URIType.INVALID, uri, data=data)
        return URI(URIType.MAIL, uri, data=data)

    if scheme == 'tel':
        # https://rfc-editor.org/rfc/rfc3966#section-3
        # TODO: extract number
        return URI(URIType.TEL, uri)

    if scheme == 'geo':
        # TODO: unify with .util.preview.split_geo_uri
        # https://rfc-editor.org/rfc/rfc5870#section-3.3
        lat, _, lon_alt = urlparts.path.partition(',')
        if not lat or not lon_alt:
            return URI(URIType.INVALID, uri, data={'error': 'No latitude or longitude'})
        lon, _, alt = lon_alt.partition(',')
        if not lon:
            return URI(URIType.INVALID, uri, data={'error': 'No longitude'})

        data = {'lat': lat, 'lon': lon, 'alt': alt}
        return URI(URIType.GEO, uri, data=data)

    if scheme == 'file':
        # https://rfc-editor.org/rfc/rfc8089.html#section-2
        data: dict[str, str] = {}
        try:
            data['netloc'] = urlparts.netloc
            path = Gio.File.new_for_uri(uri).get_path()
            assert path is not None
            data['path'] = path
        except Exception as err:
            data['error'] = str(err)
            return URI(URIType.INVALID, uri, data=data)
        return URI(URIType.FILE, uri, data=data)

    if scheme == 'about':
        # https://rfc-editor.org/rfc/rfc6694#section-2.1
        data: dict[str, str] = {}
        try:
            token = unquote(urlparts.path, errors='strict')
            if token == 'ambiguous-address':  # noqa: S105
                data['addr'] = unquote(urlparts.query, errors='strict')
                validate_jid(data['addr'], 'bare')
                return URI(URIType.AT, uri, data=data)
            raise Exception(f'Unrecognized about-token "{token}"')
        except Exception as err:
            data['error'] = str(err)
            return URI(URIType.INVALID, uri, data=data)

    return URI(URIType.OTHER, uri)


def _handle_message_qtype(jid: str, params: dict[str, str], account: str) -> None:
    body = params.get('body')
    # ^ For JOIN, this is a non-standard, but nice extension
    app.window.start_chat_from_jid(account, jid, message=body)


_xmpp_query_type_handlers = {
    XmppUriQuery.NONE: _handle_message_qtype,
    XmppUriQuery.MESSAGE: _handle_message_qtype,
    XmppUriQuery.JOIN: _handle_message_qtype,
}


@catch_exceptions
def open_uri(uri: URI | str, account: str | None = None) -> None:
    if not isinstance(uri, URI):
        uri = parse_uri(uri)

    if uri.type == URIType.FILE:
        opt_name = 'allow_open_file_uris'
        if app.settings.get(opt_name):
            open_file_uri(uri.source)
        else:
            log.info('Blocked opening a file URI, see %s option', opt_name)

    elif uri.type in (URIType.MAIL, URIType.TEL, URIType.WEB, URIType.OTHER):
        open_uri_externally(uri.source)

    elif uri.type == URIType.GEO:
        if Gio.AppInfo.get_default_for_uri_scheme('geo'):
            open_uri_externally(uri.source)
        else:
            open_uri(geo_provider_from_location(uri.data['lat'], uri.data['lon']))

    elif uri.type in (URIType.XMPP, URIType.AT):
        if account is None:
            log.warning('Account must be specified to open XMPP uri')
            return

        if uri.type == URIType.XMPP:
            jid = uri.data['jid']
        else:
            jid = uri.data['addr']

        qtype, qparams = XmppUriQuery.from_str(uri.query_type), uri.query_params
        if not qtype:
            log.info(
                'open_uri: can\'t "%s": ' 'unsupported query type in %s',
                uri.query_type,
                uri,
            )
            # From <rfc5122#section-2.5>:
            # > If the processing application does not understand [...] the
            # > specified query type, it MUST ignore the query component and
            # > treat the IRI/URI as consisting of, for example,
            # > <xmpp:example-node@example.com> rather than
            # > <xmpp:example-node@example.com?query>."
            qtype, qparams = XmppUriQuery.NONE, {}
        _xmpp_query_type_handlers[qtype](jid, qparams, account)

    elif uri.type == URIType.INVALID:
        log.warning('open_uri: Invalid %s', uri)
        # TODO: UI error instead

    else:
        log.error('open_uri: No handler for %s', uri)
        # TODO: this is a bug, so, `raise` maybe?


def open_uri_externally(uri: str) -> None:
    if sys.platform == 'win32':
        webbrowser.open(uri, new=2)
    else:
        try:
            Gio.AppInfo.launch_default_for_uri(uri)
        except GLib.Error as err:
            log.info(
                'open_uri_externally: ' "Couldn't launch default for %s: %s", uri, err
            )


def open_file_uri(uri: str) -> None:
    try:
        if sys.platform != 'win32':
            Gio.AppInfo.launch_default_for_uri(uri)
        else:
            os.startfile(uri, 'open')  # noqa: S606
    except Exception as err:
        log.info("Couldn't open file URI %s: %s", uri, err)


@catch_exceptions
def open_file(path: Path) -> None:
    if not path.exists():
        log.warning('Unable to open file, path %s does not exist', path)
        return

    open_file_uri(path.as_uri())


def open_directory(path: Path) -> None:
    return open_file(path)


def show_in_folder(path: Path) -> None:
    if not DBusFileManager().show_items_sync([path.as_uri()]):
        # Fall back to just opening the containing folder
        open_directory(path.parent)


def filesystem_path_from_uri(uri: str) -> Path | None:
    puri = parse_uri(uri)
    if puri.type != URIType.FILE:
        return None

    netloc = puri.data['netloc']
    if netloc and netloc.lower() != 'localhost' and sys.platform != 'win32':
        return None
    return Path(puri.data['path'])


def get_file_path_from_dnd_dropped_uri(text: str) -> Path | None:
    uri = text.strip('\r\n\x00')  # remove \r\n and NULL
    return filesystem_path_from_uri(uri)


def make_path_from_jid(base_path: Path, jid: JID) -> Path:
    assert jid.domain is not None
    domain = jid.domain[:50]

    if jid.localpart is None:
        return base_path / domain

    path = base_path / domain / jid.localpart[:50]
    if jid.resource is not None:
        return path / jid.resource[:30]
    return path


def geo_provider_from_location(lat: str, lon: str) -> str:
    return f'https://www.openstreetmap.org/?mlat={lat}&mlon={lon}&zoom=16'
