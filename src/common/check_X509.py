import logging
log = logging.getLogger('gajim.c.check_X509')

try:
    import OpenSSL.SSL
    import OpenSSL.crypto
    ver = OpenSSL.__version__
    if ver < '0.12':
        raise ImportError
    from pyasn1.type import univ, constraint, char, namedtype, tag
    from pyasn1.codec.der.decoder import decode
    from common.helpers import prep, InvalidFormat

    MAX = 64
    oid_xmppaddr = '1.3.6.1.5.5.7.8.5'
    oid_dnssrv   = '1.3.6.1.5.5.7.8.7'



    class DirectoryString(univ.Choice):
        componentType = namedtype.NamedTypes(
            namedtype.NamedType(
                'teletexString', char.TeletexString().subtype(
                    subtypeSpec=constraint.ValueSizeConstraint(1, MAX))),
            namedtype.NamedType(
                'printableString', char.PrintableString().subtype(
                    subtypeSpec=constraint.ValueSizeConstraint(1, MAX))),
            namedtype.NamedType(
                'universalString', char.UniversalString().subtype(
                    subtypeSpec=constraint.ValueSizeConstraint(1, MAX))),
            namedtype.NamedType(
                'utf8String', char.UTF8String().subtype(
                    subtypeSpec=constraint.ValueSizeConstraint(1, MAX))),
            namedtype.NamedType(
                'bmpString', char.BMPString().subtype(
                    subtypeSpec=constraint.ValueSizeConstraint(1, MAX))),
            namedtype.NamedType(
                'ia5String', char.IA5String().subtype(
                    subtypeSpec=constraint.ValueSizeConstraint(1, MAX))),
            namedtype.NamedType(
                'gString', univ.OctetString().subtype(
                    subtypeSpec=constraint.ValueSizeConstraint(1, MAX))),
            )

    class AttributeValue(DirectoryString):
        pass

    class AttributeType(univ.ObjectIdentifier):
        pass

    class AttributeTypeAndValue(univ.Sequence):
        componentType = namedtype.NamedTypes(
            namedtype.NamedType('type', AttributeType()),
            namedtype.NamedType('value', AttributeValue()),
            )

    class RelativeDistinguishedName(univ.SetOf):
        componentType = AttributeTypeAndValue()

    class RDNSequence(univ.SequenceOf):
        componentType = RelativeDistinguishedName()

    class Name(univ.Choice):
        componentType = namedtype.NamedTypes(
            namedtype.NamedType('', RDNSequence()),
            )

    class GeneralName(univ.Choice):
        componentType = namedtype.NamedTypes(
            namedtype.NamedType('otherName', univ.Sequence().subtype(
                implicitTag=tag.Tag(tag.tagClassContext,
                tag.tagFormatConstructed, 0x0))),
            namedtype.NamedType('rfc822Name', char.IA5String().subtype(
                implicitTag=tag.Tag(tag.tagClassContext,
                tag.tagFormatSimple, 1))),
            namedtype.NamedType('dNSName', char.IA5String().subtype(
                implicitTag=tag.Tag(tag.tagClassContext,
                tag.tagFormatSimple, 2))),
            namedtype.NamedType('x400Address', univ.Sequence().subtype(
                implicitTag=tag.Tag(tag.tagClassContext,
                tag.tagFormatConstructed, 0x3))),
            namedtype.NamedType('directoryName', Name().subtype(
                implicitTag=tag.Tag(tag.tagClassContext,
                tag.tagFormatConstructed, 0x4))),
            namedtype.NamedType('ediPartyName', univ.Sequence().subtype(
                implicitTag=tag.Tag(tag.tagClassContext,
                tag.tagFormatConstructed, 0x5))),
            namedtype.NamedType('uniformResourceIdentifier',
                char.IA5String().subtype(
                implicitTag=tag.Tag(tag.tagClassContext,
                tag.tagFormatSimple, 6))),
            namedtype.NamedType('iPAddress', univ.OctetString().subtype(
                implicitTag=tag.Tag(tag.tagClassContext,
                tag.tagFormatSimple, 7))),
            namedtype.NamedType('registeredID', univ.ObjectIdentifier().subtype(
                implicitTag=tag.Tag(tag.tagClassContext,
                tag.tagFormatSimple, 8))),
            )

    class GeneralNames(univ.SequenceOf):
        componentType = GeneralName()
        sizeSpec = univ.SequenceOf.sizeSpec + constraint.ValueSizeConstraint(1, MAX)

    def _parse_asn1(asn1):
        obj = decode(asn1, asn1Spec=GeneralNames())[0]
        r = {}
        for o in obj:
            name = o.getName()
            if name == 'dNSName':
                if name not in r:
                    r[name] = []
                r[name].append(str(o.getComponent()))
            if name == 'otherName':
                if name not in r:
                    r[name] = {}
                tag = str(tuple(o.getComponent())[0])
                val = str(tuple(o.getComponent())[1])
                if tag not in r[name]:
                    r[name][tag] = []
                r[name][tag].append(val)
            if name == 'uniformResourceIdentifier':
                r['uniformResourceIdentifier'] = True
        return r

    def check_certificate(cert, domain):
        cnt = cert.get_extension_count()
        if '.' in domain:
            compared_domain = domain.split('.', 1)[1]
        else:
            compared_domain = ''
        srv_domain = '_xmpp-client.' + domain
        compared_srv_domain = '_xmpp-client.' + compared_domain
        for i in range(0, cnt):
            ext = cert.get_extension(i)
            if ext.get_short_name() == 'subjectAltName':
                try:
                    r = _parse_asn1(ext.get_data())
                except:
                    log.error('Wrong data in certificate: subjectAltName=%s' % \
                        ext.get_data())
                    continue
                if 'otherName' in r:
                    if oid_xmppaddr in r['otherName']:
                        for host in r['otherName'][oid_xmppaddr]:
                            try:
                                host = prep(None, host, None)
                            except InvalidFormat:
                                continue
                            if host == domain:
                                return True
                    if oid_dnssrv in r['otherName']:
                        for host in r['otherName'][oid_dnssrv]:
                            if host.startswith('_xmpp-client.*.'):
                                if host.replace('*.', '', 1) == compared_srv_domain:
                                    return True
                                continue
                            if host == srv_domain:
                                return True
                if 'dNSName' in r:
                    for host in r['dNSName']:
                        if host.startswith('*.'):
                            if host[2:] == compared_domain:
                                return True
                            continue
                        if host == domain:
                            return True
                if r:
                    return False
                break

        subject = cert.get_subject()
        if subject.commonName == domain:
            return True
        return False
except ImportError:
    log.warning('Import of PyOpenSSL or pyasn1 failed. Cannot correctly check '
        'SSL certificate')

    def check_certificate(cert, domain):
        subject = cert.get_subject()
        if subject.commonName == domain:
            return True
        return False
