# -*- coding:utf-8 -*-
## src/common/caps_cache.py
##
## Copyright (C) 2007 Tomasz Melcer <liori AT exroot.org>
##                    Travis Shirk <travis AT pobox.com>
## Copyright (C) 2007-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
##                    Jonathan Schleifer <js-gajim AT webkeks.org>
## Copyright (C) 2008-2009 Stephan Erb <steve-e AT h3c.de>
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

"""
Module containing all XEP-115 (Entity Capabilities) related classes

Basic Idea:
CapsCache caches features to hash relationships. The cache is queried
through ClientCaps objects which are hold by contact instances.
"""

import base64
import hashlib

import logging
log = logging.getLogger('gajim.c.caps_cache')

from nbxmpp import (NS_XHTML_IM, NS_RECEIPTS, NS_ESESSION, NS_CHATSTATES,
    NS_JINGLE_ICE_UDP, NS_JINGLE_RTP_AUDIO, NS_JINGLE_RTP_VIDEO, NS_CAPS,
    NS_JINGLE_FILE_TRANSFER)
# Features where we cannot safely assume that the other side supports them
FEATURE_BLACKLIST = [NS_CHATSTATES, NS_XHTML_IM, NS_RECEIPTS, NS_ESESSION,
    NS_JINGLE_ICE_UDP, NS_JINGLE_RTP_AUDIO, NS_JINGLE_RTP_VIDEO,
    NS_JINGLE_FILE_TRANSFER]

# Query entry status codes
NEW = 0
QUERIED = 1
CACHED = 2 # got the answer
FAKED = 3 # allow NullClientCaps to behave as it has a cached item

################################################################################
### Public API of this module
################################################################################

capscache = None
def initialize(logger):
    """
    Initialize this module
    """
    global capscache
    capscache = CapsCache(logger)

def client_supports(client_caps, requested_feature):
    lookup_item = client_caps.get_cache_lookup_strategy()
    cache_item = lookup_item(capscache)

    supported_features = cache_item.features
    if requested_feature in supported_features:
        return True
    elif not supported_features and cache_item.status in (NEW, QUERIED, FAKED):
        # assume feature is supported, if we don't know yet, what the client
        # is capable of
        return requested_feature not in FEATURE_BLACKLIST
    else:
        return False

def create_suitable_client_caps(node, caps_hash, hash_method, fjid=None):
    """
    Create and return a suitable ClientCaps object for the given node,
    caps_hash, hash_method combination.
    """
    if not node or not caps_hash:
        if fjid:
            client_caps = NoClientCaps(fjid)
        else:
            # improper caps, ignore client capabilities.
            client_caps = NullClientCaps()
    elif not hash_method:
        client_caps = OldClientCaps(caps_hash, node)
    else:
        client_caps = ClientCaps(caps_hash, node, hash_method)
    return client_caps

def compute_caps_hash(identities, features, dataforms=[], hash_method='sha-1'):
    """
    Compute caps hash according to XEP-0115, V1.5

    dataforms are nbxmpp.DataForms objects as common.dataforms don't allow several
    values without a field type list-multi
    """
    def sort_identities_func(i1, i2):
        cat1 = i1['category']
        cat2 = i2['category']
        if cat1 < cat2:
            return -1
        if cat1 > cat2:
            return 1
        type1 = i1.get('type', '')
        type2 = i2.get('type', '')
        if type1 < type2:
            return -1
        if type1 > type2:
            return 1
        lang1 = i1.get('xml:lang', '')
        lang2 = i2.get('xml:lang', '')
        if lang1 < lang2:
            return -1
        if lang1 > lang2:
            return 1
        return 0

    def sort_dataforms_func(d1, d2):
        f1 = d1.getField('FORM_TYPE')
        f2 = d2.getField('FORM_TYPE')
        if f1 and f2 and (f1.getValue() < f2.getValue()):
            return -1
        return 1

    S = ''
    from functools import cmp_to_key
    identities.sort(key=cmp_to_key(sort_identities_func))
    for i in identities:
        c = i['category']
        type_ = i.get('type', '')
        lang = i.get('xml:lang', '')
        name = i.get('name', '')
        S += '%s/%s/%s/%s<' % (c, type_, lang, name)
    features.sort()
    for f in features:
        S += '%s<' % f
    dataforms.sort(key=cmp_to_key(sort_dataforms_func))
    for dataform in dataforms:
        # fields indexed by var
        fields = {}
        for f in dataform.getChildren():
            fields[f.getVar()] = f
        form_type = fields.get('FORM_TYPE')
        if form_type:
            S += form_type.getValue() + '<'
            del fields['FORM_TYPE']
        for var in sorted(fields.keys()):
            S += '%s<' % var
            values = sorted(fields[var].getValues())
            for value in values:
                S += '%s<' % value

    if hash_method == 'sha-1':
        hash_ = hashlib.sha1(S.encode('utf-8'))
    elif hash_method == 'md5':
        hash_ = hashlib.md5(S.encode('utf-8'))
    else:
        return ''
    return base64.b64encode(hash_.digest()).decode('utf-8')


################################################################################
### Internal classes of this module
################################################################################

class AbstractClientCaps(object):
    """
    Base class representing a client and its capabilities as advertised by a
    caps tag in a presence
    """
    def __init__(self, caps_hash, node):
        self._hash = caps_hash
        self._node = node
        self._hash_method = None

    def get_discover_strategy(self):
        return self._discover

    def _discover(self, connection, jid):
        """
        To be implemented by subclassess
        """
        raise NotImplementedError

    def get_cache_lookup_strategy(self):
        return self._lookup_in_cache

    def _lookup_in_cache(self, caps_cache):
        """
        To be implemented by subclassess
        """
        raise NotImplementedError

    def get_hash_validation_strategy(self):
        return self._is_hash_valid

    def _is_hash_valid(self, identities, features, dataforms):
        """
        To be implemented by subclassess
        """
        raise NotImplementedError


class ClientCaps(AbstractClientCaps):
    """
    The current XEP-115 implementation
    """
    def __init__(self, caps_hash, node, hash_method):
        AbstractClientCaps.__init__(self, caps_hash, node)
        assert hash_method != 'old'
        self._hash_method = hash_method

    def _lookup_in_cache(self, caps_cache):
        return caps_cache[(self._hash_method, self._hash)]

    def _discover(self, connection, jid):
        connection.discoverInfo(jid, '%s#%s' % (self._node, self._hash))

    def _is_hash_valid(self, identities, features, dataforms):
        computed_hash = compute_caps_hash(identities, features,
                        dataforms=dataforms, hash_method=self._hash_method)
        return computed_hash == self._hash


class OldClientCaps(AbstractClientCaps):
    """
    Old XEP-115 implemtation. Kept around for background competability
    """
    def __init__(self, caps_hash, node):
        AbstractClientCaps.__init__(self, caps_hash, node)
        self._hash_method = 'old'

    def _lookup_in_cache(self, caps_cache):
        return caps_cache[('old', self._node + '#' + self._hash)]

    def _discover(self, connection, jid):
        connection.discoverInfo(jid)

    def _is_hash_valid(self, identities, features, dataforms):
        return True

class NoClientCaps(AbstractClientCaps):
    """
    For clients that don't support XEP-0115
    """
    def __init__(self, fjid):
        AbstractClientCaps.__init__(self, fjid, fjid)
        self._hash_method = 'no'

    def _lookup_in_cache(self, caps_cache):
        return caps_cache[('no', self._node)]

    def _discover(self, connection, jid):
        connection.discoverInfo(jid)

    def _is_hash_valid(self, identities, features, dataforms):
        return True

class NullClientCaps(AbstractClientCaps):
    """
    This is a NULL-Object to streamline caps handling if a client has not
    advertised any caps or has advertised them in an improper way

    Assumes (almost) everything is supported.
    """
    _instance = None
    def __new__(cls, *args, **kwargs):
        """
        Make it a singleton.
        """
        if not cls._instance:
            cls._instance = super(NullClientCaps, cls).__new__(
                    cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        AbstractClientCaps.__init__(self, None, None)
        self._hash_method = 'dummy'

    def _lookup_in_cache(self, caps_cache):
        # lookup something which does not exist to get a new CacheItem created
        cache_item = caps_cache[('dummy', '')]
        # Mark the item as cached so that protocol/caps.py does not update it
        cache_item.status = FAKED
        return cache_item

    def _discover(self, connection, jid):
        pass

    def _is_hash_valid(self, identities, features, dataforms):
        return False


class CapsCache(object):
    """
    This object keeps the mapping between caps data and real disco features they
    represent, and provides simple way to query that info
    """
    def __init__(self, logger=None):
        # our containers:
        # __cache is a dictionary mapping: pair of hash method and hash maps
        #   to CapsCacheItem object
        # __CacheItem is a class that stores data about particular
        #   client (hash method/hash pair)
        self.__cache = {}

        class CacheItem(object):
            # __names is a string cache; every string long enough is given
            #   another object, and we will have plenty of identical long
            #   strings. therefore we can cache them
            __names = {}

            def __init__(self, hash_method, hash_, logger):
                # cached into db
                self.hash_method = hash_method
                self.hash = hash_
                self._features = []
                self._identities = []
                self._logger = logger

                self.status = NEW
                self._recently_seen = False

            def _get_features(self):
                return self._features

            def _set_features(self, value):
                self._features = []
                for feature in value:
                    self._features.append(self.__names.setdefault(feature, feature))

            features = property(_get_features, _set_features)

            def _get_identities(self):
                list_ = []
                for i in self._identities:
                    # transforms it back in a dict
                    d = dict()
                    d['category'] = i[0]
                    if i[1]:
                        d['type'] = i[1]
                    if i[2]:
                        d['xml:lang'] = i[2]
                    if i[3]:
                        d['name'] = i[3]
                    list_.append(d)
                return list_

            def _set_identities(self, value):
                self._identities = []
                for identity in value:
                    # dict are not hashable, so transform it into a tuple
                    t = (identity['category'], identity.get('type'),
                            identity.get('xml:lang'), identity.get('name'))
                    self._identities.append(self.__names.setdefault(t, t))

            identities = property(_get_identities, _set_identities)

            def set_and_store(self, identities, features):
                self.identities = identities
                self.features = features
                if self.hash_method != 'no':
                    self._logger.add_caps_entry(self.hash_method, self.hash,
                        identities, features)
                self.status = CACHED

            def update_last_seen(self):
                if not self._recently_seen:
                    self._recently_seen = True
                    if self.hash_method != 'no':
                        self._logger.update_caps_time(self.hash_method,
                            self.hash)

            def is_valid(self):
                """
                Returns True if identities and features for this cache item
                are known.
                """
                return self.status in (CACHED, FAKED)

        self.__CacheItem = CacheItem
        self.logger = logger

    def initialize_from_db(self):
        self._remove_outdated_caps()
        for hash_method, hash_, identities, features in \
        self.logger.iter_caps_data():
            x = self[(hash_method, hash_)]
            x.identities = identities
            x.features = features
            x.status = CACHED

    def _remove_outdated_caps(self):
        """
        Remove outdated values from the db
        """
        self.logger.clean_caps_table()

    def __getitem__(self, caps):
        if caps in self.__cache:
            return self.__cache[caps]

        hash_method, hash_ = caps

        x = self.__CacheItem(hash_method, hash_, self.logger)
        self.__cache[(hash_method, hash_)] = x
        return x

    def query_client_of_jid_if_unknown(self, connection, jid, client_caps):
        """
        Start a disco query to determine caps (node, ver, exts). Won't query if
        the data is already in cache
        """
        lookup_cache_item = client_caps.get_cache_lookup_strategy()
        q = lookup_cache_item(self)

        if q.status == NEW:
            # do query for bare node+hash pair
            # this will create proper object
            q.status = QUERIED
            discover = client_caps.get_discover_strategy()
            discover(connection, jid)
        else:
            q.update_last_seen()

    def forget_caps(self, client_caps):
        hash_method = client_caps._hash_method
        hash = client_caps._hash
        key = (hash_method, hash)
        if key in self.__cache:
            del self.__cache[key]
