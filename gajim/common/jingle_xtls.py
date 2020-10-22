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
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

import logging
from pathlib import Path

from OpenSSL import SSL, crypto

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.util import generate_id
from gajim.common import app
from gajim.common import configpaths

log = logging.getLogger('gajim.c.jingle_xtls')

# key-exchange id -> [callback, args], accept that session once key-exchange completes
pending_contents = {}

def key_exchange_pend(id_, cb, args):
    # args is a list
    pending_contents[id_] = [cb, args]

def approve_pending_content(id_):
    cb = pending_contents[id_][0]
    args = pending_contents[id_][1]
    cb(*args)

TYPE_RSA = crypto.TYPE_RSA
TYPE_DSA = crypto.TYPE_DSA

SELF_SIGNED_CERTIFICATE = 'localcert'
DH_PARAMS = 'dh_params.pem'
DEFAULT_DH_PARAMS = 'dh4096.pem'

def default_callback(connection, certificate, error_num, depth, return_code):
    log.info("certificate: %s", certificate)
    return return_code

def load_cert_file(cert_path, cert_store=None):
    """
    This is almost identical to the one in nbxmpp.tls_nb
    """
    if not cert_path.is_file():
        return None
    try:
        f = open(cert_path)
    except IOError as e:
        log.warning('Unable to open certificate file %s: %s', cert_path,
                    str(e))
        return None
    lines = f.readlines()
    i = 0
    begin = -1
    for line in lines:
        if 'BEGIN CERTIFICATE' in line:
            begin = i
        elif 'END CERTIFICATE' in line and begin > -1:
            cert = ''.join(lines[begin:i+2])
            try:
                x509cert = crypto.load_certificate(crypto.FILETYPE_PEM, cert)
                if cert_store:
                    cert_store.add_cert(x509cert)
                f.close()
                return x509cert
            except crypto.Error as exception_obj:
                log.warning('Unable to load a certificate from file %s: %s',
                            cert_path, exception_obj.args[0][0][2])
            except Exception:
                log.warning('Unknown error while loading certificate from file '
                            '%s', cert_path)
            begin = -1
        i += 1
    f.close()

def get_context(fingerprint, verify_cb=None, remote_jid=None):
    """
    constructs and returns the context objects
    """
    ctx = SSL.Context(SSL.SSLv23_METHOD)
    flags = (SSL.OP_NO_SSLv2 | SSL.OP_NO_SSLv3 | SSL.OP_SINGLE_DH_USE \
             | SSL.OP_NO_TICKET)
    ctx.set_options(flags)
    ctx.set_cipher_list(b'HIGH:!aNULL:!3DES')

    if fingerprint == 'server': # for testing purposes only
        ctx.set_verify(SSL.VERIFY_NONE|SSL.VERIFY_FAIL_IF_NO_PEER_CERT,
                       verify_cb or default_callback)
    elif fingerprint == 'client':
        ctx.set_verify(SSL.VERIFY_PEER, verify_cb or default_callback)

    cert_name = configpaths.get('MY_CERT') / SELF_SIGNED_CERTIFICATE
    ctx.use_privatekey_file(str(cert_name.with_suffix('.pkey')).encode('utf-8'))
    ctx.use_certificate_file(str(cert_name.with_suffix('.cert')).encode('utf-8'))

    # Try to load Diffie-Hellman parameters.
    # First try user DH parameters, if this fails load the default DH parameters
    dh_params_name = configpaths.get('MY_CERT') / DH_PARAMS
    try:
        with open(dh_params_name, "r"):
            ctx.load_tmp_dh(dh_params_name.encode('utf-8'))
    except FileNotFoundError as err:
        default_dh_params_name = (configpaths.get('DATA') / 'other' /
                                  DEFAULT_DH_PARAMS)
        try:
            with open(default_dh_params_name, "r"):
                ctx.load_tmp_dh(str(default_dh_params_name).encode('utf-8'))
        except FileNotFoundError as err:
            log.error('Unable to load default DH parameter file: %s, %s',
                      default_dh_params_name, err)
            raise

    if remote_jid:
        store = ctx.get_cert_store()
        path = configpaths.get('MY_PEER_CERTS').expanduser() / (remote_jid
                                                                + '.cert')
        if path.exists():
            load_cert_file(path, cert_store=store)
            log.debug('certificate file %s loaded fingerprint %s',
                      path, fingerprint)
    return ctx

def read_cert(certpath):
    certificate = ''
    with open(certpath, 'r') as certfile:
        for line in certfile.readlines():
            if not line.startswith('-'):
                certificate += line
    return certificate

def send_cert(con, jid_from, sid):
    certpath = configpaths.get('MY_CERT') / (SELF_SIGNED_CERTIFICATE
                                             + '.cert')
    certificate = read_cert(certpath)
    iq = nbxmpp.Iq('result', to=jid_from)
    iq.setAttr('id', sid)

    pubkey = iq.setTag('pubkeys')
    pubkey.setNamespace(Namespace.PUBKEY_PUBKEY)

    keyinfo = pubkey.setTag('keyinfo')
    name = keyinfo.setTag('name')
    name.setData('CertificateHash')
    cert = keyinfo.setTag('x509cert')
    cert.setData(certificate)

    con.send(iq)

def handle_new_cert(con, obj, jid_from):
    jid = app.get_jid_without_resource(jid_from)
    certpath = configpaths.get('MY_PEER_CERTS').expanduser() / (jid + '.cert')

    id_ = obj.getAttr('id')

    x509cert = obj.getTag('pubkeys').getTag('keyinfo').getTag('x509cert')

    cert = x509cert.getData()

    f = open(certpath, 'w')
    f.write('-----BEGIN CERTIFICATE-----\n')
    f.write(cert)
    f.write('-----END CERTIFICATE-----\n')
    f.close()

    approve_pending_content(id_)

def check_cert(jid, fingerprint):
    certpath = configpaths.get('MY_PEER_CERTS').expanduser() / (jid + '.cert')
    if certpath.exists():
        cert = load_cert_file(certpath)
        if cert:
            digest_algo = cert.get_signature_algorithm().decode('utf-8')\
                    .split('With')[0]
            if cert.digest(digest_algo) == fingerprint:
                return True
    return False

def send_cert_request(con, to_jid):
    iq = nbxmpp.Iq('get', to=to_jid)
    id_ = generate_id()
    iq.setAttr('id', id_)
    pubkey = iq.setTag('pubkeys')
    pubkey.setNamespace(Namespace.PUBKEY_PUBKEY)
    con.connection.send(iq)
    return str(id_)

# the following code is partly due to pyopenssl examples

def createKeyPair(type_, bits):
    """
    Create a public/private key pair.

    Arguments: type_ - Key type, must be one of TYPE_RSA and TYPE_DSA
               bits - Number of bits to use in the key
    Returns:   The public/private key pair in a PKey object
    """
    pkey = crypto.PKey()
    pkey.generate_key(type_, bits)
    return pkey

def createCertRequest(pkey, digest="sha256", **name):
    """
    Create a certificate request.

    Arguments: pkey   - The key to associate with the request
               digest - Digestion method to use for signing, default is sha256
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

    for (key, value) in name.items():
        setattr(subj, key, value)

    req.set_pubkey(pkey)
    req.sign(pkey, digest)
    return req

def createCertificate(req, issuerCert, issuerKey, serial, notBefore, notAfter, digest="sha256"):
    """
    Generate a certificate given a certificate request.

    Arguments: req        - Certificate request to use
               issuerCert - The certificate of the issuer
               issuerKey  - The private key of the issuer
               serial     - Serial number for the certificate
               notBefore  - Timestamp (relative to now) when the certificate
                            starts being valid
               notAfter   - Timestamp (relative to now) when the certificate
                            stops being valid
               digest     - Digest method to use for signing, default is sha256
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
    filepath : absolute path of certificate file, will be appended the '.pkey'
    and '.cert' extensions
    CN : common name
    """
    key = createKeyPair(TYPE_RSA, 4096)
    req = createCertRequest(key, CN=CN)
    cert = createCertificate(req, req, key, 0, 0, 60*60*24*365*5) # five years
    with open(filepath.with_suffix('.pkey'), 'wb') as f:
        filepath.with_suffix('.pkey').chmod(0o600)
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))
    with open(filepath.with_suffix('.cert'), 'wb') as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))


if __name__ == '__main__':
    make_certs(Path('selfcert'), 'gajim')
