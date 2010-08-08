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

import os

import logging
log = logging.getLogger('gajim.c.jingle_xtls')

PYOPENSSL_PRESENT = False

try:
    import OpenSSL
    PYOPENSSL_PRESENT = True
except ImportError:
    log.info("PyOpenSSL not available")

if PYOPENSSL_PRESENT:
    from OpenSSL import SSL
    from OpenSSL.SSL import Context
    from OpenSSL import crypto

SELF_SIGNED_CERTIFICATE = 'localcert'
    
def default_callback(connection, certificate, error_num, depth, return_code):
    log.info("certificate: %s" % certificate)
    return return_code

def load_cert_file(cert_path, cert_store):
    """
    This is almost identical to the one in common.xmpp.tls_nb
    """
    if not os.path.isfile(cert_path):
        return
    try:
        f = open(cert_path)
    except IOError, e:
        log.warning('Unable to open certificate file %s: %s' % \
                (cert_path, str(e)))
        return
    lines = f.readlines()
    i = 0
    begin = -1
    for line in lines:
        if 'BEGIN CERTIFICATE' in line:
            begin = i
        elif 'END CERTIFICATE' in line and begin > -1:
            cert = ''.join(lines[begin:i+2])
            try:
                x509cert = OpenSSL.crypto.load_certificate(
                        OpenSSL.crypto.FILETYPE_PEM, cert)
                cert_store.add_cert(x509cert)
            except OpenSSL.crypto.Error, exception_obj:
                log.warning('Unable to load a certificate from file %s: %s' %\
                            (cert_path, exception_obj.args[0][0][2]))
            except:
                log.warning('Unknown error while loading certificate from file '
                            '%s' % cert_path)
            begin = -1
        i += 1

def get_context(fingerprint, verify_cb=None):
    """
    constructs and returns the context objects
    """
    ctx = SSL.Context(SSL.TLSv1_METHOD)

    if fingerprint == 'server': # for testing purposes only
        ctx.set_verify(SSL.VERIFY_PEER|SSL.VERIFY_FAIL_IF_NO_PEER_CERT, verify_cb or default_callback)
    elif fingerprint == 'client':
        ctx.set_verify(SSL.VERIFY_PEER, verify_cb or default_callback)
        
    ctx.use_privatekey_file (os.path.expanduser('~/certs/' + SELF_SIGNED_CERTIFICATE + '.pkey'))
    ctx.use_certificate_file(os.path.expanduser('~/certs/' + SELF_SIGNED_CERTIFICATE + '.cert'))
    store = ctx.get_cert_store()
    for f in os.listdir(os.path.expanduser('~/certs/')):
        load_cert_file(os.path.join(os.path.expanduser('~/certs'), f), store)
    return ctx

# the following code is partly due to pyopenssl examples

TYPE_RSA = crypto.TYPE_RSA
TYPE_DSA = crypto.TYPE_DSA

def createKeyPair(type, bits):
    """
    Create a public/private key pair.

    Arguments: type - Key type, must be one of TYPE_RSA and TYPE_DSA
               bits - Number of bits to use in the key
    Returns:   The public/private key pair in a PKey object
    """
    pkey = crypto.PKey()
    pkey.generate_key(type, bits)
    return pkey

def createCertRequest(pkey, digest="md5", **name):
    """
    Create a certificate request.

    Arguments: pkey   - The key to associate with the request
               digest - Digestion method to use for signing, default is md5
               **name - The name of the subject of the request, possible
                        arguments are:
                          C     - Country name
                          ST    - State or province name
                          L     - Locality name
                          O     - Organization name
                          OU    - Organizational unit name
                          CN    - Common name
                          emailAddress - E-mail address
    Returns:   The certificate request in an X509Req object
    """
    req = crypto.X509Req()
    subj = req.get_subject()

    for (key,value) in name.items():
        setattr(subj, key, value)

    req.set_pubkey(pkey)
    req.sign(pkey, digest)
    return req

def createCertificate(req, (issuerCert, issuerKey), serial, (notBefore, notAfter), digest="md5"):
    """
    Generate a certificate given a certificate request.

    Arguments: req        - Certificate reqeust to use
               issuerCert - The certificate of the issuer
               issuerKey  - The private key of the issuer
               serial     - Serial number for the certificate
               notBefore  - Timestamp (relative to now) when the certificate
                            starts being valid
               notAfter   - Timestamp (relative to now) when the certificate
                            stops being valid
               digest     - Digest method to use for signing, default is md5
    Returns:   The signed certificate in an X509 object
    """
    cert = crypto.X509()
    cert.set_serial_number(serial)
    cert.gmtime_adj_notBefore(notBefore)
    cert.gmtime_adj_notAfter(notAfter)
    cert.set_issuer(issuerCert.get_subject())
    cert.set_subject(req.get_subject())
    cert.set_pubkey(req.get_pubkey())
    cert.sign(issuerKey, digest)
    return cert

def make_certs(filepath, CN):
    """
    make self signed certificates
    filepath : absolute path of certificate file, will be appended the '.pkey' and '.cert' extensions
    CN : common name
    """
    key = createKeyPair(TYPE_RSA, 1024)
    req = createCertRequest(key, CN=CN)
    cert = createCertificate(req, (req, key), 0, (0, 60*60*24*365*5)) # five years
    open(filepath + '.pkey', 'w').write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))
    open(filepath + '.cert', 'w').write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))


if __name__ == '__main__':
    make_certs('./selfcert', 'gajim')
