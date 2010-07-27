# -*- coding:utf-8 -*-
## src/common/jingle_xtls.py
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

import logging
log = logging.getLogger('gajim.c.jingle_xtls')

PYOPENSSL_PRESENT = False

try:
    import OpenSSL
    PYOPENSSL_PRESENT = True
    from OpenSSL import SSL, Context
except ImportError:
    log.info("PyOpenSSL not available")

def default_callback(connection, certificate, error_num, depth, return_code):
    log.info("certificate: %s" % certificate)
    return return_code

def get_context(fingerprint, verify_cb=None):
    """
    constructs and returns the context objects
    """
    ctx = SSL.Context(TLSv1_METHOD)
    ctx.set_verify(SSL.VERIFY_PEER|SSL.VERIFY_FAIL_IF_NO_PEER_CERT, verify_cb or default_callback)
    # TODO: set private key, set certificate, set verification path
    return ctx

