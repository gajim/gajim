##
## Copyright (C) 2006 Gajim Team
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 2 only.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
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

# * figure out why it doesn't work with pidgin:
#     That's maybe a bug in pidgin:
#       http://xmpp.org/extensions/xep-0176.html#protocol-checks

import xmpp
import helpers

from jingle_session import JingleSession, JingleStates
from jingle_rtp import JingleAudio, JingleVideo
from jingle_ft import JingleFileTransfer
import gajim

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

    def delete_jingle_session(self, sid):
        """
        Remove a jingle session from a jingle stanza dispatcher
        """
        if sid in self._sessions:
            #FIXME: Move this elsewhere?
            for content in self._sessions[sid].contents.values():
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
        jid = helpers.get_full_jid_from_iq(stanza)
        id = stanza.getID()

        if (jid, id) in self.__iq_responses.keys():
            self.__iq_responses[(jid, id)].on_stanza(stanza)
            del self.__iq_responses[(jid, id)]
            raise xmpp.NodeProcessed

        jingle = stanza.getTag('jingle')
        # a jingle element is not necessary in iq-result stanza
        # don't check for that
        if jingle:
            sid = jingle.getAttr('sid')
        else:
            sid = None
            for sesn in self._sessions.values():
                if id in sesn.iq_ids:
                    sesn.on_stanza(stanza)
            return

        # do we need to create a new jingle object
        if sid not in self._sessions:
            #TODO: tie-breaking and other things...
            newjingle = JingleSession(con=self, weinitiate=False, jid=jid,
                iq_id=id, sid=sid)
            self._sessions[sid] = newjingle

        # we already have such session in dispatcher...
        self._sessions[sid].collect_iq_id(id)
        self._sessions[sid].on_stanza(stanza)
        # Delete invalid/unneeded sessions
        if sid in self._sessions and self._sessions[sid].state == JingleStates.ended:
            self.delete_jingle_session(sid)

        raise xmpp.NodeProcessed

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

    def start_video(self, jid):
        if self.get_jingle_session(jid, media='video'):
            return self.get_jingle_session(jid, media='video').sid
        jingle = self.get_jingle_session(jid, media='audio')
        if jingle:
            jingle.add_content('video', JingleVideo(jingle))
        else:
            jingle = JingleSession(self, weinitiate=True, jid=jid)
            self._sessions[jingle.sid] = jingle
            jingle.add_content('video', JingleVideo(jingle))
            jingle.start_session()
        return jingle.sid

    def start_file_transfer(self, jid, file_props):
        logger.info("start file transfer with file: %s" % file_props)
        jingle = self.get_jingle_session(jid, media='file')
        contact = gajim.contacts.get_contact_with_highest_priority(self.name,
                                                                   gajim.get_jid_without_resource(jid))
        if contact is None:
            return
        use_security = contact.supports(xmpp.NS_JINGLE_XTLS)
        if jingle:
            file_props['sid'] = jingle.sid
            c = JingleFileTransfer(jingle, file_props=file_props,
                use_security=use_security)
            jingle.add_content('file' + helpers.get_random_string_16(), c)
            jingle.on_session_state_changed(c)
        else:
            jingle = JingleSession(self, weinitiate=True, jid=jid)
            self.__sessions__[jingle.sid] = jingle
            file_props['sid'] = jingle.sid
            c = JingleFileTransfer(jingle, file_props=file_props,
                use_security=use_security)
            jingle.add_content('file' + helpers.get_random_string_16(), c)
            jingle.start_session()
        return c.transport.sid


    def iter_jingle_sessions(self, jid, sid=None, media=None):
        if sid:
            return (session for session in self._sessions.values() if session.sid == sid)
        sessions = (session for session in self._sessions.values() if session.peerjid == jid)
        if media:
            if media not in ('audio', 'video', 'file'):
                return tuple()
            else:
                return (session for session in sessions if session.get_content(media))
        else:
            return sessions


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
