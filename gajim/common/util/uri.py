# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import NamedTuple

import logging
import os
import sys
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import ParseResult
from urllib.parse import unquote
from urllib.parse import urlparse

from gi.repository import Gio
from gi.repository import GLib
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common import iana
from gajim.common.const import NONREGISTERED_URI_SCHEMES
from gajim.common.dbus.file_manager import DBusFileManager
from gajim.common.regex import IRI_RX
from gajim.common.util.decorators import catch_exceptions

log = logging.getLogger('gajim.c.util.uri')


@dataclass
class Uri:
    scheme: str
    uri: str

    @classmethod
    def from_urlparts(cls, urlparts: ParseResult, uri: str) -> Uri:
        if urlparts.scheme in ('http', 'https'):
            if not urlparts.netloc:
                raise ValueError(f'No host or empty host in an {urlparts.scheme} URI')
        return cls(scheme=urlparts.scheme, uri=uri)


@dataclass
class InvalidUri(Uri):
    error: str


@dataclass
class XmppIri(Uri):
    jid: JID
    action: str
    params: dict[str, str]

    @classmethod
    def from_urlparts(cls, urlparts: ParseResult, uri: str) -> XmppIri:
        urlparts = urlparse(uri)
        if urlparts.scheme != 'xmpp':
            raise ValueError('Invalid scheme: %s' % urlparts.scheme)

        if urlparts.path.startswith('/'):
            raise ValueError('Authority component not supported: %s' % uri)

        if not urlparts.path:
            raise ValueError('No path component found: %s' % uri)

        jid = JID.from_iri(f'xmpp:{urlparts.path}')
        qtype, qparams = parse_xmpp_uri_query(urlparts.query)
        return cls(scheme='xmpp', uri=uri, jid=jid, action=qtype, params=qparams)

    @classmethod
    def from_string(cls, uri: str) -> XmppIri:
        urlparts = urlparse(uri)
        return XmppIri.from_urlparts(urlparts, uri)


@dataclass
class MailUri(Uri):
    addr: str

    @classmethod
    def from_urlparts(cls, urlparts: ParseResult, uri: str) -> MailUri:
        if urlparts.path.startswith('/'):
            raise ValueError('Authority component not supported: %s' % uri)

        if not urlparts.path:
            raise ValueError('No path component found: %s' % uri)

        return cls(scheme=urlparts.scheme, uri=uri, addr=urlparts.path)


@dataclass
class GeoUri(Uri):
    lat: str
    lon: str
    alt: str

    @classmethod
    def from_urlparts(cls, urlparts: ParseResult, uri: str) -> GeoUri:
        lat, _, lon_alt = urlparts.path.partition(',')
        if not lat or not lon_alt:
            raise ValueError('No latitude or longitude')

        lon, _, alt = lon_alt.partition(',')
        if not lon:
            raise ValueError('No longitude')

        return cls(scheme=urlparts.scheme, uri=uri, lat=lat, lon=lon, alt=alt)


@dataclass
class FileUri(Uri):
    netloc: str
    path: str

    @classmethod
    def from_urlparts(cls, urlparts: ParseResult, uri: str) -> FileUri:
        path = Gio.File.new_for_uri(uri).get_path()
        assert path is not None
        return cls(scheme=urlparts.scheme, uri=uri, netloc=urlparts.netloc, path=path)


UriT = Uri | InvalidUri | XmppIri | MailUri | GeoUri | FileUri


SCHEME_CLASS_MAP = {
    'xmpp': XmppIri,
    'mailto': MailUri,
    'geo': GeoUri,
    'file': FileUri
}


def is_known_uri_scheme(scheme: str) -> bool:
    '''
    `scheme` is lower-case
    '''
    if not scheme:
        return False
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


def parse_uri(uri: str) -> UriT:
    try:
        urlparts = urlparse(uri)
    except Exception as error:
        return InvalidUri(scheme='', uri=uri, error=str(error))

    scheme = urlparts.scheme

    if not is_known_uri_scheme(scheme):
        return InvalidUri(scheme='', uri=uri, error='Unknown scheme')

    uri_class = SCHEME_CLASS_MAP.get(scheme, Uri)
    try:
        return uri_class.from_urlparts(urlparts, uri)
    except Exception as error:
        return InvalidUri(scheme='', uri=uri, error=str(error))


@catch_exceptions
def open_uri(uri: UriT | str) -> None:
    if isinstance(uri, str):
        uri = parse_uri(uri)

    match uri:
        case InvalidUri():
            log.warning('Failed to open uri: %s', uri.error)

        case XmppIri():
            app.window.open_xmpp_iri(uri)

        case GeoUri():
            if Gio.AppInfo.get_default_for_uri_scheme('geo'):
                open_uri_externally(uri.uri)
            else:
                open_uri(geo_provider_from_location(uri.lat, uri.lon))

        case Uri():
            open_uri_externally(uri.uri)


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
    if not isinstance(puri, FileUri):
        return None

    if puri.netloc and puri.netloc.lower() != 'localhost' and sys.platform != 'win32':
        return None
    return Path(puri.path)


def get_file_path_from_dnd_dropped_uri(text: str) -> Path | None:
    uri = text.strip('\r\n\x00')  # remove \r\n and NULL
    return filesystem_path_from_uri(uri)


def get_file_path_from_uri(uri: str) -> Path | None:
    """Prepare URI by:
    - removing invalid characters
    - parsing and checking the URI for validity
    - checking if the path is a file
    - checking if the file is accessible (path.is_file() calls Path.stat())
    """
    path = get_file_path_from_dnd_dropped_uri(uri)
    if path is None:
        return None

    try:
        is_file = path.is_file()
    except OSError:
        log.exception("Could not access file: %s", path)
        return None

    if not is_file:
        return None

    return path


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


class Coords(NamedTuple):
    location: str
    lat: str
    lon: str


def split_geo_uri(uri: str) -> Coords:
    # Example:
    # geo:37.786971,-122.399677,122.3;CRS=epsg:32718;U=20;mapcolors=abc
    # Assumption is all coordinates are CRS=WGS-84

    # Remove "geo:"
    coords = uri[4:]

    # Remove arguments
    if ';' in coords:
        coords, _ = coords.split(';', maxsplit=1)

    # Split coords
    coords = coords.split(',')
    if len(coords) not in (2, 3):
        raise ValueError('Invalid geo uri: invalid coord count')

    # Remoove coord-c (altitude)
    if len(coords) == 3:
        coords.pop(2)

    lat, lon = coords
    if float(lat) < -90 or float(lat) > 90:
        raise ValueError('Invalid geo_uri: invalid latitude %s' % lat)

    if float(lon) < -180 or float(lon) > 180:
        raise ValueError('Invalid geo_uri: invalid longitude %s' % lon)

    location = ','.join(coords)
    return Coords(location=location, lat=lat, lon=lon)


def get_geo_choords(uri: str) -> Coords | None:
    if not IRI_RX.fullmatch(uri):
        # urlparse removes whitespace (and who knows what else) from URLs,
        # so can't be used for validation.
        return None

    try:
        urlparts = urlparse(uri)
    except Exception:
        return None

    if urlparts.scheme != 'geo':
        return None

    try:
        return split_geo_uri(uri)
    except Exception as err:
        log.info('Bad geo URI %s: %s', uri, err)
        return None
