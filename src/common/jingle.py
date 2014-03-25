##
## Copyright (C) 2006 Gajim Team
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
"""
Handles the jingle signalling protocol
"""

#TODO:
# * things in XEP 0176, including:
#      - http://xmpp.org/extensions/xep-0176.html#protocol-restarts
#      - http://xmpp.org/extensions/xep-0176.html#fallback
# * XEP 0177 (raw udp)

# * UI:
#   - make state and codec informations available to the user
#   - video integration
#   * config:
#     - codecs

import nbxmpp
from common import helpers
from common import gajim

from common.jingle_session import JingleSession, JingleStates
if gajim.HAVE_FARSTREAM:
    from common.jingle_rtp import JingleAudio, JingleVideo
from common.jingle_ft import JingleFileTransfer
from common.jingle_transport import JingleTransportSocks5, JingleTransportIBB

import logging
logger = logging.getLogger('gajim.c.jingle')

class ConnectionJingle(object):
    """
    This object depends on that it is a part of Connection class.
    """

    def __init__(self):
        # dictionary: sessionid => JingleSession object
        self._sessions = {}

        # dictionary: (jid, iq stanza id) => JingleSession object,
        # one time callbacks
        self.__iq_responses = {}
        self.files = []

    def delete_jingle_session(self, sid):
        """
        Remove a jingle session from a jingle stanza dispatcher
        """
        if sid in self._sessions:
            #FIXME: Move this elsewhere?
            for content in list(self._sessions[sid].contents.values()):
                content.destroy()
            self._sessions[sid].callbacks = []
            del self._sessions[sid]

    def _JingleCB(self, con, stanza):
        """
        The jingle stanza dispatcher

        Route jingle stanza to proper JingleSession object, or create one if it
        is a new session.

        TODO: Also check if the stanza isn't an error stanza, if so route it
        adequatelly.
        """
        # get data
        try:
            jid = helpers.get_full_jid_from_iq(stanza)
        except helpers.InvalidFormat:
            logger.warn('Invalid JID: %s, ignoring it' % stanza.getFrom())
            return
        id_ = stanza.getID()
        if (jid, id_) in self.__iq_responses.keys():
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
            #TODO: tie-breaking and other things...
            newjingle = JingleSession(con=self, weinitiate=False, jid=jid,
                iq_id=id_, sid=sid)
            self._sessions[sid] = newjingle
        # we already have such session in dispatcher...
        self._sessions[sid].collect_iq_id(id_)
        self._sessions[sid].on_stanza(stanza)
        # Delete invalid/unneeded sessions
        if sid in self._sessions and \
        self._sessions[sid].state == JingleStates.ended:
            self.delete_jingle_session(sid)
        raise nbxmpp.NodeProcessed

    def start_audio(self, jid):
        if self.get_jingle_session(jid, media='audio'):
            return self.get_jingle_session(jid, media='audio').sid
        jingle = self.get_jingle_session(jid, media='video')
        if jingle:
            jingle.add_content('voice', JingleAudio(jingle))
        else:
            jingle = JingleSession(self, weinitiate=True, jid=jid)
            self._sessions[jingle.sid] = jingle
            jingle.add_content('voice', JingleAudio(jingle))
            jingle.start_session()
        return jingle.sid

    def start_video(self, jid, in_xid, out_xid):
        if self.get_jingle_session(jid, media='video'):
            return self.get_jingle_session(jid, media='video').sid
        jingle = self.get_jingle_session(jid, media='audio')
        if jingle:
            jingle.add_content('video', JingleVideo(jingle, in_xid=in_xid,
                out_xid=out_xid))
        else:
            jingle = JingleSession(self, weinitiate=True, jid=jid)
            self._sessions[jingle.sid] = jingle
            jingle.add_content('video', JingleVideo(jingle, in_xid=in_xid,
                out_xid=out_xid))
            jingle.start_session()
        return jingle.sid

    def start_file_transfer(self, jid, file_props, request=False):
        logger.info("start file transfer with file: %s" % file_props)
        contact = gajim.contacts.get_contact_with_highest_priority(self.name,
            gajim.get_jid_without_resource(jid))
        if gajim.contacts.is_gc_contact(self.name,jid):
            gcc = jid.split('/')
            if len(gcc) == 2:
                contact = gajim.contacts.get_gc_contact(self.name, gcc[0], gcc[1])
        if contact is None:
            return
        use_security = contact.supports(nbxmpp.NS_JINGLE_XTLS)
        jingle = JingleSession(self, weinitiate=True, jid=jid, werequest=request)
        # this is a file transfer
        jingle.session_type_FT = True
        self._sessions[jingle.sid] = jingle
        file_props.sid = jingle.sid
        if contact.supports(nbxmpp.NS_JINGLE_BYTESTREAM):
            transport = JingleTransportSocks5()
        elif contact.supports(nbxmpp.NS_JINGLE_IBB):
            transport = JingleTransportIBB()
        c = JingleFileTransfer(jingle, transport=transport,
            file_props=file_props, use_security=use_security)
        file_props.algo = self.__hash_support(contact)
        jingle.add_content('file' + helpers.get_random_string_16(), c)
        jingle.start_session()
        return c.transport.sid

    def __hash_support(self, contact):
        if contact.supports(nbxmpp.NS_HASHES):
            if contact.supports(nbxmpp.NS_HASHES_SHA512):
                return 'sha-512'
            elif contact.supports(nbxmpp.NS_HASHES_SHA256):
                return 'sha-256'
            elif contact.supports(nbxmpp.NS_HASHES_SHA1):
                return 'sha-1'
            elif contact.supports(nbxmpp.NS_HASHES_MD5):
                return 'md5'
        return None

    def iter_jingle_sessions(self, jid, sid=None, media=None):
        if sid:
            return (session for session in self._sessions.values() if \
                session.sid == sid)
        sessions = (session for session in self._sessions.values() if \
            session.peerjid == jid)
        if media:
            if media not in ('audio', 'video', 'file'):
                return tuple()
            else:
                return (session for session in sessions if \
                    session.get_content(media))
        else:
            return sessions

    def set_file_info(self, file_):
        # Saves information about the files we have transfered in case they need
        # to be requested again.
        self.files.append(file_)

    def get_file_info(self, peerjid, hash_=None, name=None, account=None):
        if hash_:
            for f in self.files: # DEBUG
                #if f['hash'] == '1294809248109223':
                if f['hash'] == hash_ and f['peerjid'] == peerjid:
                    return f
        elif name:
            for f in self.files:
                if f['name'] == name and f['peerjid'] == peerjid:
                    return f

    def get_jingle_session(self, jid, sid=None, media=None):
        if sid:
            if sid in self._sessions:
                return self._sessions[sid]
            else:
                return None
        elif media:
            if media not in ('audio', 'video', 'file'):
                return None
            for session in self._sessions.values():
                if session.peerjid == jid and session.get_content(media):
                    return session
        return None
