# Copyright (C) 2006 Jean-Marie Traissard <jim AT lapin.org>
#                    Tomasz Melcer <liori AT exroot.org>
# Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
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
Atom (rfc 4287) feed parser, used to read data from atom-over-pubsub transports
and services. Very simple. Actually implements only atom:entry.
Implement more features if you need
"""

# XEP-0277: Microblogging over XMPP

# Module is disabled for now because Gajim lacks a good UI for that
# register the module in connection.py with register_module() to activate again

import logging
import time

import nbxmpp

from gajim.common.const import PEPEventType
from gajim.common.exceptions import StanzaMalformed
from gajim.common.modules.pep import AbstractPEPModule, AbstractPEPData

log = logging.getLogger('gajim.c.m.atom')


class AtomData(AbstractPEPData):

    type_ = PEPEventType.ATOM

    def __init__(self, atom):
        self.data = atom

    def get_entry(self):
        return self.data


class Atom(AbstractPEPModule):

    name = 'atom'
    namespace = 'urn:xmpp:microblog:0'
    pep_class = AtomData
    store_publish = False
    _log = log

    def _extract_info(self, item):
        entry = item.getTag('entry', namespace=nbxmpp.NS_ATOM)
        if entry is None:
            StanzaMalformed('no entry node')

        return OldEntry(node=entry) or None

    def _build_node(self, data):
        raise NotImplementedError


class PersonConstruct(nbxmpp.Node):
    """
    Not used for now, as we don't need authors/contributors
    in pubsub.com feeds. They rarely exist there
    """

    def __init__(self, node):
        ''' Create person construct from node. '''
        nbxmpp.Node.__init__(self, node=node)

    def get_name(self):
        return self.getTagData('name')

    name = property(
        get_name, None, None,
        '''Conveys a human-readable name for the person. Should not be None,
        although some badly generated atom feeds don't put anything here
        (this is non-standard behavior, still pubsub.com sometimes
        does that.)''')

    def get_uri(self):
        return self.getTagData('uri')

    uri = property(
        get_uri, None, None,
        '''Conveys an IRI associated with the person.
        Might be None when not set.''')

    def get_email(self):
        return self.getTagData('email')

    email = property(
        get_email, None, None,
        '''Conveys an e-mail address associated with the person.
        Might be None when not set.''')


class Entry(nbxmpp.Node):
    def __init__(self, node=None):
        nbxmpp.Node.__init__(self, 'entry', node=node)

    def __repr__(self):
        return '<Atom:Entry object of id="%r">' % self.getAttr('id')


class OldEntry(nbxmpp.Node):
    """
    Parser for feeds from pubsub.com. They use old Atom 0.3 format with their
    extensions
    """

    def __init__(self, node=None):
        ''' Create new Atom 0.3 entry object. '''
        nbxmpp.Node.__init__(self, 'entry', node=node)

    def __repr__(self):
        return '<Atom0.3:Entry object of id="%r">' % self.getAttr('id')

    def get_feed_title(self):
        """
        Return title of feed, where the entry was created.
        The result is the feed name concatenated with source-feed title
        """
        if self.parent is not None:
            main_feed = self.parent.getTagData('title')
        else:
            main_feed = None

        if self.getTag('feed') is not None:
            source_feed = self.getTag('feed').getTagData('title')
        else:
            source_feed = None

        if main_feed is not None and source_feed is not None:
            return '%s: %s' % (main_feed, source_feed)
        if main_feed is not None:
            return main_feed
        if source_feed is not None:
            return source_feed
        return ''

    feed_title = property(
        get_feed_title, None, None,
        ''' Title of feed. It is built from entry''s original feed title
        and title of feed which delivered this entry. ''')

    def get_feed_link(self):
        """
        Get source link
        """
        try:
            link = self.getTag('feed').getTags('link', {'rel': 'alternate'})
            return link[1].getData()
        except Exception:
            return None

    feed_link = property(
        get_feed_link, None, None,
        ''' Link to main webpage of the feed. ''')

    def get_title(self):
        """
        Get an entry's title
        """
        return self.getTagData('title')

    title = property(
        get_title, None, None,
        ''' Entry's title. ''')

    def get_uri(self):
        """
        Get the uri the entry points to (entry's first link element with
        rel='alternate' or without rel attribute)
        """
        for element in self.getTags('link'):
            if 'rel' in element.attrs and element.attrs['rel'] != 'alternate':
                continue
            try:
                return element.attrs['href']
            except AttributeError:
                pass
        return None

    uri = property(
        get_uri, None, None,
        ''' URI that is pointed by the entry. ''')

    def get_updated(self):
        """
        Get the time the entry was updated last time

        This should be standarized, but pubsub.com sends it in human-readable
        format. We won't try to parse it.
        (Atom 0.3 uses the word «modified» for that).

        If there's no time given in the entry, we try with <published>
        and <issued> elements.
        """
        for name in ('updated', 'modified', 'published', 'issued'):
            date = self.getTagData(name)
            if date is not None:
                break

        if date is None:
            # it is not in the standard format
            return time.asctime()

        return date

    updated = property(
        get_updated, None, None,
        ''' Last significant modification time. ''')

    feed_tagline = ''
