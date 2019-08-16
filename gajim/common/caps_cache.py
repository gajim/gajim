# Copyright (C) 2007 Tomasz Melcer <liori AT exroot.org>
#                    Travis Shirk <travis AT pobox.com>
# Copyright (C) 2007-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
#                    Jonathan Schleifer <js-gajim AT webkeks.org>
# Copyright (C) 2008-2009 Stephan Erb <steve-e AT h3c.de>
#
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

"""
Module containing all XEP-115 (Entity Capabilities) related classes

Basic Idea:
CapsCache caches features to hash relationships. The cache is queried
through ClientCaps objects which are hold by contact instances.
"""

import logging

from nbxmpp import (NS_XHTML_IM, NS_ESESSION, NS_CHATSTATES,
    NS_JINGLE_ICE_UDP, NS_JINGLE_RTP_AUDIO, NS_JINGLE_RTP_VIDEO,
    NS_JINGLE_FILE_TRANSFER_5)
# Features where we cannot safely assume that the other side supports them
FEATURE_BLACKLIST = [NS_CHATSTATES, NS_XHTML_IM, NS_ESESSION,
    NS_JINGLE_ICE_UDP, NS_JINGLE_RTP_AUDIO, NS_JINGLE_RTP_VIDEO,
    NS_JINGLE_FILE_TRANSFER_5]

log = logging.getLogger('gajim.c.caps_cache')

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
    if not supported_features and cache_item.status in (NEW, QUERIED, FAKED):
        # assume feature is supported, if we don't know yet, what the client
        # is capable of
        return requested_feature not in FEATURE_BLACKLIST
    return False

def get_client_identity(client_caps):
    lookup_item = client_caps.get_cache_lookup_strategy()
    cache_item = lookup_item(capscache)

    for identity in cache_item.identities:
        if identity.category == 'client':
            return identity.type

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


################################################################################
### Internal classes of this module
################################################################################

class AbstractClientCaps:
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
        To be implemented by subclasses
        """
        raise NotImplementedError

    def get_cache_lookup_strategy(self):
        return self._lookup_in_cache

    def _lookup_in_cache(self, caps_cache):
        """
        To be implemented by subclasses
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
        connection.get_module('Discovery').disco_contact(
            jid, '%s#%s' % (self._node, self._hash))


class OldClientCaps(AbstractClientCaps):
    """
    Old XEP-115 implementation. Kept around for background compatibility
    """
    def __init__(self, caps_hash, node):
        AbstractClientCaps.__init__(self, caps_hash, node)
        self._hash_method = 'old'

    def _lookup_in_cache(self, caps_cache):
        return caps_cache[('old', self._node + '#' + self._hash)]

    def _discover(self, connection, jid):
        connection.get_module('Discovery').disco_contact(jid)


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
        connection.get_module('Discovery').disco_contact(jid)


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


class CapsCache:
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

        class CacheItem:
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
                return self._identities

            def _set_identities(self, value):
                self._identities = value

            identities = property(_get_identities, _set_identities)

            def set_and_store(self, info):
                self.identities = info.identities
                self.features = info.features
                if self.hash_method != 'no':
                    self._logger.add_caps_entry(self.hash_method, self.hash, info)
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
        data = self.logger.load_caps_data()
        for key, item in data.items():
            x = self[key]
            x.identities = item.identities
            x.features = item.features
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
        hash_ = client_caps._hash
        key = (hash_method, hash_)
        if key in self.__cache:
            del self.__cache[key]
