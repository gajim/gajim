# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.


import logging
from pathlib import Path

from gi.repository import GLib
from gi.repository import Gio

from gajim.common import configpaths

from gajim.common.helpers import get_random_string_16
from gajim.common.helpers import write_file_async


log = logging.getLogger('gajim.c.cert_store')


class CertificateStore:
    def __init__(self):
        self._path = Path(configpaths.get('CERT_STORE'))
        self._certs = []

        self._load_certificates()

    def _get_random_path(self):
        filename = get_random_string_16()
        path = self._path / filename
        if path.exists():
            return self._get_random_path()
        return path

    def _load_certificates(self):
        for path in self._path.iterdir():
            if path.is_dir():
                continue
            try:
                cert = Gio.TlsCertificate.new_from_file(str(path))
            except GLib.Error as error:
                log.warning('Can\'t load certificate: %s, %s', path, error)
                continue

            log.info('Loaded: %s', path.stem)
            self._certs.append(cert)

        log.info('%s Certificates loaded', len(self._certs))

    def get_certificates(self):
        return list(self._certs)

    def add_certificate(self, certificate):
        log.info('Add certificate to trust store')
        pem = certificate.props.certificate_pem
        path = self._get_random_path()
        write_file_async(path,
                         pem.encode(),
                         self._on_certificate_write_finished,
                         path)

    @staticmethod
    def _on_certificate_write_finished(data, error, path):
        if data is None:
            log.error('Can\'t store certificate: %s', error)
            return

        log.info('Certificate stored: %s', path)
