# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging
from pathlib import Path

from gi.repository import Gio
from gi.repository import GLib

from gajim.common import configpaths
from gajim.common.helpers import get_random_string
from gajim.common.helpers import write_file_async

log = logging.getLogger('gajim.c.cert_store')


class CertificateStore:
    def __init__(self):
        self._path = configpaths.get('CERT_STORE')
        self._certs: list[Gio.TlsCertificate] = []

        self._load_certificates()

    def _get_random_path(self) -> Path:
        filename = get_random_string()
        path = self._path / filename
        if path.exists():
            return self._get_random_path()
        return path

    def _load_certificates(self) -> None:
        for path in self._path.iterdir():
            if path.is_dir():
                continue
            try:
                cert = Gio.TlsCertificate.new_from_file(str(path))
            except GLib.Error as error:
                log.warning("Can't load certificate: %s, %s", path, error)
                continue

            log.info('Loaded: %s', path.stem)
            self._certs.append(cert)

        log.info('%s Certificates loaded', len(self._certs))

    def get_certificates(self):
        return list(self._certs)

    def add_certificate(self, certificate: Gio.TlsCertificate) -> None:
        log.info('Add certificate to trust store')
        self._certs.append(certificate)
        pem = certificate.props.certificate_pem
        path = self._get_random_path()
        write_file_async(path,
                         pem.encode(),
                         self._on_certificate_write_finished,
                         path)

    def verify(self,
               certificate: Gio.TlsCertificate,
               tls_errors: set[Gio.TlsCertificateFlags]):

        if Gio.TlsCertificateFlags.UNKNOWN_CA in tls_errors:
            for trusted_certificate in self._certs:
                if trusted_certificate.is_same(certificate):
                    tls_errors.remove(Gio.TlsCertificateFlags.UNKNOWN_CA)
                    break

        if not tls_errors:
            return True
        return False

    @staticmethod
    def _on_certificate_write_finished(_successful: bool,
                                       error: GLib.Error | None,
                                       path: Path):
        if error is not None:
            log.error("Can't store certificate: %s", error.message)
            return

        log.info('Certificate stored: %s', path)
