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


# Handles Jingle contents (XEP 0166)


from __future__ import annotations

from typing import Any
from typing import Callable
from typing import TYPE_CHECKING

import nbxmpp
from nbxmpp.namespaces import Namespace

from gajim.common import app
from gajim.common.file_props import FileProp

if TYPE_CHECKING:
    from gajim.common.jingle_session import JingleSession
    from gajim.common.jingle_transport import JingleTransport


contents: dict[str, Any] = {}


def get_jingle_content(node: nbxmpp.Node):
    namespace = node.getNamespace()
    if namespace in contents:
        return contents[namespace](node)


class JingleContentSetupException(Exception):
    '''
    Exception that should be raised when a content fails to setup.
    '''


class JingleContent:
    '''
    An abstraction of content in Jingle sessions
    '''

    def __init__(self,
                 session: JingleSession,
                 transport: JingleTransport | None,
                 senders: str | None
                 ) -> None:

        self.session = session
        self.transport = transport
        # will be filled by JingleSession.add_content()
        # don't uncomment these lines, we will catch more buggy code then
        # (a JingleContent not added to session shouldn't send anything)
        self.creator: str | None = None
        self.name: str | None = None
        self.accepted = False
        self.sent = False
        self.negotiated = False

        self.media: str | None = None

        self.senders = senders
        if self.senders is None:
            self.senders = 'both'

        # Used for stream direction, attribute 'senders'
        self.allow_sending = True

        # These were found by the Politie
        self.file_props: FileProp | None = None

        self.callbacks: dict[str, list[Callable[
            [nbxmpp.Node, nbxmpp.Node, nbxmpp.Node | None, str],
            None]]] = {
            # these are called when *we* get stanzas
            'content-accept': [self.__on_transport_info,
                               self.__on_content_accept],
            'content-add': [self.__on_transport_info],
            'content-modify': [],
            'content-reject': [],
            'content-remove': [],
            'description-info': [],
            'security-info': [],
            'session-accept': [self.__on_transport_info,
                               self.__on_content_accept],
            'session-info': [],
            'session-initiate': [self.__on_transport_info],
            'session-terminate': [],
            'transport-info': [self.__on_transport_info],
            'transport-replace': [self.__on_transport_replace],
            'transport-accept': [self.__on_transport_replace],
            'transport-reject': [],
            'iq-result': [],
            'iq-error': [],
            # these are called when *we* sent these stanzas
            'content-accept-sent': [self.__fill_jingle_stanza,
                                    self.__on_content_accept],
            'content-add-sent': [self.__fill_jingle_stanza],
            'session-initiate-sent': [self.__fill_jingle_stanza],
            'session-accept-sent': [self.__fill_jingle_stanza,
                                    self.__on_content_accept],
            'session-terminate-sent': [],
        }

    def is_ready(self) -> bool:
        return self.accepted and not self.sent

    def __on_content_accept(self,
                            stanza: nbxmpp.Node,
                            content: nbxmpp.Node,
                            error: nbxmpp.Node | None,
                            action: str
                            ) -> None:
        self.on_negotiated()

    def on_negotiated(self) -> None:
        if self.accepted:
            self.negotiated = True
            self.session.content_negotiated(self.media)

    def add_remote_candidates(self, candidates):
        '''
        Add a list of candidates to the list of remote candidates
        '''
        self.transport.remote_candidates = candidates

    def on_stanza(self,
                  stanza: nbxmpp.Node,
                  content: nbxmpp.Node | None,
                  error: nbxmpp.Node | None,
                  action: str
                  ) -> None:
        '''
        Called when something related to our content was sent by peer
        '''
        if action in self.callbacks:
            for callback in self.callbacks[action]:
                callback(stanza, content, error, action)

    def __on_transport_replace(self,
                               stanza: nbxmpp.Node,
                               content: nbxmpp.Node,
                               error: nbxmpp.Node | None,
                               action: str
                               ) -> None:
        content.addChild(node=self.transport.make_transport())

    def __on_transport_info(self,
                            stanza: nbxmpp.Node,
                            content: nbxmpp.Node,
                            error: nbxmpp.Node | None,
                            action: str
                            ) -> None:
        '''
        Got a new transport candidate
        '''
        candidates = self.transport.parse_transport_stanza(
            content.getTag('transport'))
        if candidates:
            self.add_remote_candidates(candidates)

    def __content(self,
                  payload: list[nbxmpp.Node] | None = None
                  ) -> nbxmpp.Node:
        '''
        Build a XML content-wrapper for our data
        '''
        if payload is None:
            payload = []
        return nbxmpp.Node('content',
                           attrs={'name': self.name,
                                  'creator': self.creator,
                                  'senders': self.senders},
                           payload=payload)

    def send_candidate(self, candidate: dict[str, Any]) -> None:
        '''
        Send a transport candidate for a previously defined transport.
        '''
        content = self.__content()
        content.addChild(node=self.transport.make_transport([candidate]))
        self.session.send_transport_info(content)

    def send_error_candidate(self) -> None:
        '''
        Sends a candidate-error when we can't connect to a candidate.
        '''
        content = self.__content()
        tp = self.transport.make_transport(add_candidates=False)
        tp.addChild(name='candidate-error')
        content.addChild(node=tp)
        self.session.send_transport_info(content)

    def send_description_info(self) -> None:
        content = self.__content()
        self._fill_content(content)
        self.session.send_description_info(content)

    def __fill_jingle_stanza(self,
                             stanza: nbxmpp.Node,
                             content: nbxmpp.Node,
                             error: nbxmpp.Node | None,
                             action: str
                             ) -> None:
        '''
        Add our things to session-initiate stanza
        '''
        self._fill_content(content)
        self.sent = True
        content.addChild(node=self.transport.make_transport())

    def _fill_content(self, content: nbxmpp.Node) -> None:
        description_node = nbxmpp.simplexml.Node(
            tag=Namespace.JINGLE_FILE_TRANSFER_5 + ' description')
        file_tag = description_node.setTag('file')
        if self.file_props.name:
            node = nbxmpp.simplexml.Node(tag='name')
            node.addData(self.file_props.name)
            file_tag.addChild(node=node)
        if self.file_props.date:
            node = nbxmpp.simplexml.Node(tag='date')
            node.addData(self.file_props.date)
            file_tag.addChild(node=node)
        if self.file_props.size:
            node = nbxmpp.simplexml.Node(tag='size')
            node.addData(self.file_props.size)
            file_tag.addChild(node=node)
        if self.file_props.type_ == 'r':
            if self.file_props.hash_:
                file_tag.addChild('hash', attrs={'algo': self.file_props.algo},
                                  namespace=Namespace.HASHES_2,
                                  payload=self.file_props.hash_)
        else:
            # if the file is less than 10 mb, then it is small
            # lets calculate it right away
            if self.file_props.size < 10000000 and not self.file_props.hash_:
                hash_data = self._compute_hash()
                if hash_data:
                    file_tag.addChild(node=hash_data)
                pjid = app.get_jid_without_resource(self.session.peerjid)
                file_info = {'name': self.file_props.name,
                             'file-name': self.file_props.file_name,
                             'hash': self.file_props.hash_,
                             'size': self.file_props.size,
                             'date': self.file_props.date,
                             'peerjid': pjid
                             }
                self.session.connection.get_module('Jingle').set_file_info(
                    file_info)
        desc = file_tag.setTag('desc')
        if self.file_props.desc:
            desc.setData(self.file_props.desc)
        content.addChild(node=description_node)

    def destroy(self) -> None:
        self.callbacks = None
        del self.session.contents[(self.creator, self.name)]
