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


# Handles the jingle signalling protocol


# TODO:
# * things in XEP 0176, including:
#      - http://xmpp.org/extensions/xep-0176.html#protocol-restarts
#      - http://xmpp.org/extensions/xep-0176.html#fallback
# * XEP 0177 (raw udp)

# * UI:
#   - make state and codec information available to the user
#   - video integration
#   * config:
#     - codecs

from __future__ import annotations

from typing import Any

import logging

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.structs import IqProperties
from nbxmpp.structs import StanzaHandler

from gajim.common import helpers
from gajim.common import types
from gajim.common.file_props import FileProp
from gajim.common.jingle_ft import JingleFileTransfer
from gajim.common.jingle_rtp import JingleAudio
from gajim.common.jingle_rtp import JingleVideo
from gajim.common.jingle_session import JingleSession
from gajim.common.jingle_session import JingleStates
from gajim.common.jingle_transport import JingleTransportIBB
from gajim.common.jingle_transport import JingleTransportSocks5
from gajim.common.modules.base import BaseModule

logger = logging.getLogger('gajim.c.m.jingle')


class Jingle(BaseModule):
    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='iq',
                          typ='result',
                          callback=self._on_jingle_iq),
            StanzaHandler(name='iq',
                          typ='error',
                          callback=self._on_jingle_iq),
            StanzaHandler(name='iq',
                          typ='set',
                          ns=Namespace.JINGLE,
                          callback=self._on_jingle_iq),
        ]

        # dictionary: sessionid => JingleSession object
        self._sessions: dict[str, JingleSession] = {}

        # dictionary: (jid, iq stanza id) => JingleSession object,
        # one time callbacks
        self.__iq_responses: dict[tuple[str, str], JingleSession] = {}
        self.files: list[dict[str, Any]] = []

    def delete_jingle_session(self, sid: str) -> None:
        '''
        Remove a jingle session from a jingle stanza dispatcher
        '''
        if sid in self._sessions:
            # FIXME: Move this elsewhere?
            for content in list(self._sessions[sid].contents.values()):
                content.destroy()
            self._sessions[sid].callbacks = []
            del self._sessions[sid]

    def _on_jingle_iq(self,
                      _con: types.xmppClient,
                      stanza: Iq,
                      _properties: IqProperties
                      ) -> None:
        '''
        The jingle stanza dispatcher

        Route jingle stanza to proper JingleSession object, or create one if it
        is a new session.

        TODO: Also check if the stanza isn't an error stanza, if so route it
        adequately.
        '''
        # get data
        try:
            jid = helpers.get_full_jid_from_iq(stanza)
        except helpers.InvalidFormat:
            logger.warning('Invalid JID: %s, ignoring it', stanza.getFrom())
            return
        id_ = stanza.getID()
        if (jid, id_) in self.__iq_responses:
            self.__iq_responses[(jid, id_)].on_stanza(stanza)
            del self.__iq_responses[(jid, id_)]
            raise nbxmpp.NodeProcessed
        jingle = stanza.getTag('jingle')
        # a jingle element is not necessary in iq-result stanza
        # don't check for that
        if jingle:
            sid = jingle.getAttr('sid')
        else:
            sid = None
            for sesn in self._sessions.values():
                if id_ in sesn.iq_ids:
                    sesn.on_stanza(stanza)
            return

        # do we need to create a new jingle object
        if sid not in self._sessions:
            # TODO: tie-breaking and other things...
            newjingle = JingleSession(self._con, weinitiate=False, jid=jid,
                                      iq_id=id_, sid=sid)
            self._sessions[sid] = newjingle
        # we already have such session in dispatcher...
        self._sessions[sid].collect_iq_id(id_)
        self._sessions[sid].on_stanza(stanza)
        # Delete invalid/unneeded sessions
        if (sid in self._sessions and
                self._sessions[sid].state == JingleStates.ENDED):
            self.delete_jingle_session(sid)
        raise nbxmpp.NodeProcessed

    def start_audio(self, jid: str) -> str:
        audio_session = self.get_jingle_session(jid, media='audio')
        if audio_session is not None:
            return audio_session.sid
        jingle = self.get_jingle_session(jid, media='video')
        if jingle:
            jingle.add_content('voice', JingleAudio(jingle))
        else:
            jingle = JingleSession(self._con, weinitiate=True, jid=jid)
            self._sessions[jingle.sid] = jingle
            jingle.add_content('voice', JingleAudio(jingle))
            jingle.start_session()
        return jingle.sid

    def start_video(self, jid: str) -> str:
        video_session = self.get_jingle_session(jid, media='video')
        if video_session is not None:
            return video_session.sid
        jingle = self.get_jingle_session(jid, media='audio')
        if jingle:
            video = JingleVideo(jingle)
            jingle.add_content('video', video)
        else:
            jingle = JingleSession(self._con, weinitiate=True, jid=jid)
            self._sessions[jingle.sid] = jingle
            video = JingleVideo(jingle)
            jingle.add_content('video', video)
            jingle.start_session()
        return jingle.sid

    def start_audio_video(self, jid: str) -> str:
        video_session = self.get_jingle_session(jid, media='video')
        if video_session is not None:
            return video_session.sid

        audio_session = self.get_jingle_session(jid, media='audio')
        video_session = self.get_jingle_session(jid, media='video')
        if audio_session and video_session:
            return audio_session.sid
        if audio_session:
            video = JingleVideo(audio_session)
            audio_session.add_content('video', video)
            return audio_session.sid
        if video_session:
            audio = JingleAudio(video_session)
            video_session.add_content('audio', audio)
            return video_session.sid

        jingle_session = JingleSession(self._con, weinitiate=True, jid=jid)
        self._sessions[jingle_session.sid] = jingle_session
        audio = JingleAudio(jingle_session)
        video = JingleVideo(jingle_session)
        jingle_session.add_content('audio', audio)
        jingle_session.add_content('video', video)
        jingle_session.start_session()
        return jingle_session.sid

    def start_file_transfer(self,
                            jid: str,
                            file_props: FileProp,
                            request: bool = False
                            ) -> str | None:
        logger.info('start file transfer with file: %s', file_props)
        contact = self._con.get_module('Contacts').get_contact(jid)
        jingle = JingleSession(self._con,
                               weinitiate=True,
                               jid=jid,
                               werequest=request)
        # this is a file transfer
        jingle.session_type_ft = True
        self._sessions[jingle.sid] = jingle
        file_props.sid = jingle.sid

        if contact.supports(Namespace.JINGLE_BYTESTREAM):
            transport = JingleTransportSocks5()
        elif contact.supports(Namespace.JINGLE_IBB):
            transport = JingleTransportIBB()
        else:
            logger.error('No suitable transport method available for %s',
                         contact.jid)
            return None

        senders = 'initiator'
        if request:
            senders = 'responder'
        transfer = JingleFileTransfer(jingle,
                                      transport=transport,
                                      file_props=file_props,
                                      senders=senders)
        file_props.transport_sid = transport.sid
        file_props.algo = self.__hash_support(contact)
        jingle.add_content('file' + helpers.get_random_string(), transfer)
        jingle.start_session()
        return transfer.transport.sid

    @staticmethod
    def __hash_support(contact: types.ResourceContact) -> str | None:
        if contact.supports(Namespace.HASHES_2):
            if contact.supports(Namespace.HASHES_BLAKE2B_512):
                return 'blake2b-512'
            if contact.supports(Namespace.HASHES_BLAKE2B_256):
                return 'blake2b-256'
            if contact.supports(Namespace.HASHES_SHA3_512):
                return 'sha3-512'
            if contact.supports(Namespace.HASHES_SHA3_256):
                return 'sha3-256'
            if contact.supports(Namespace.HASHES_SHA512):
                return 'sha-512'
            if contact.supports(Namespace.HASHES_SHA256):
                return 'sha-256'
        return None

    def get_jingle_sessions(self,
                            jid: str | None,
                            sid: str | None = None,
                            media: str | None = None
                            ) -> list[JingleSession]:
        if sid:
            return [se for se in self._sessions.values() if se.sid == sid]

        sessions = [se for se in self._sessions.values() if se.peerjid == jid]
        if media:
            if media not in ('audio', 'video', 'file'):
                return []
            return [se for se in sessions if se.get_content(media)]
        return sessions

    def set_file_info(self, file_: dict[str, Any]) -> None:
        # Saves information about the files we have transferred
        # in case they need to be requested again.
        self.files.append(file_)

    def get_file_info(self,
                      peerjid: str,
                      hash_: str | None = None,
                      name: str | None = None,
                      _account: str | None = None
                      ) -> dict[str, Any] | None:
        if hash_:
            for file in self.files:  # DEBUG
                # if f['hash'] == '1294809248109223':
                if file['hash'] == hash_ and file['peerjid'] == peerjid:
                    return file
        elif name:
            for file in self.files:
                if file['name'] == name and file['peerjid'] == peerjid:
                    return file
        return None

    def get_jingle_session(self,
                           jid: str,
                           sid: str | None = None,
                           media: str | None = None
                           ) -> JingleSession | None:
        if sid is not None:
            if sid in self._sessions:
                return self._sessions[sid]
            return None
        if media is not None:
            if media not in ('audio', 'video', 'file'):
                return None
            for session in self._sessions.values():
                if session.peerjid == jid and session.get_content(media):
                    return session
        return None
