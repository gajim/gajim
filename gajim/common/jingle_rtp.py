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
Handles Jingle RTP sessions (XEP 0167)
"""

import logging
import socket
from collections import deque

import nbxmpp
from nbxmpp.namespaces import Namespace

from gi.repository import GLib

try:
    from gi.repository import Farstream
    from gi.repository import Gst
except Exception:
    pass

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.jingle_transport import JingleTransportICEUDP
from gajim.common.jingle_content import contents
from gajim.common.jingle_content import JingleContent
from gajim.common.jingle_content import JingleContentSetupException
from gajim.common.connection_handlers_events import InformationEvent
from gajim.common.jingle_session import FailedApplication


log = logging.getLogger('gajim.c.jingle_rtp')


class JingleRTPContent(JingleContent):
    def __init__(self, session, media, transport=None):
        if transport is None:
            transport = JingleTransportICEUDP(None)
        JingleContent.__init__(self, session, transport, None)
        self.media = media
        self._dtmf_running = False
        self.farstream_media = {
            'audio': Farstream.MediaType.AUDIO,
            'video': Farstream.MediaType.VIDEO}[media]

        self.pipeline = None
        self.src_bin = None
        self.stream_failed_once = False

        self.candidates_ready = False # True when local candidates are prepared

        # TODO
        self.conference = None
        self.funnel = None
        self.p2psession = None
        self.p2pstream = None

        self.callbacks['session-initiate'] += [self.__on_remote_codecs]
        self.callbacks['content-add'] += [self.__on_remote_codecs]
        self.callbacks['description-info'] += [self.__on_remote_codecs]
        self.callbacks['content-accept'] += [self.__on_remote_codecs]
        self.callbacks['session-accept'] += [self.__on_remote_codecs]
        self.callbacks['session-terminate'] += [self.__stop]
        self.callbacks['session-terminate-sent'] += [self.__stop]

    def setup_stream(self, on_src_pad_added):
        # pipeline and bus
        self.pipeline = Gst.Pipeline()
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message', self._on_gst_message)

        # conference
        self.conference = Gst.ElementFactory.make('fsrtpconference', None)
        self.pipeline.add(self.conference)
        self.funnel = None

        self.p2psession = self.conference.new_session(self.farstream_media)

        participant = self.conference.new_participant()
        # FIXME: Consider a workaround, here...
        # pidgin and telepathy-gabble don't follow the XEP, and it won't work
        # due to bad controlling-mode

        params = {'controlling-mode': self.session.weinitiate, 'debug': False}
        if app.config.get('use_stun_server'):
            stun_server = app.config.get('stun_server')
            if not stun_server and self.session.connection._stun_servers:
                stun_server = self.session.connection._stun_servers[0]['host']
            if stun_server:
                try:
                    ip = socket.getaddrinfo(stun_server, 0, socket.AF_UNSPEC,
                                            socket.SOCK_STREAM)[0][4][0]
                except socket.gaierror as e:
                    log.warning('Lookup of stun ip failed: %s', str(e))
                else:
                    params['stun-ip'] = ip

        self.p2pstream = self.p2psession.new_stream(participant,
                                                    Farstream.StreamDirection.BOTH)
        self.p2pstream.connect('src-pad-added', on_src_pad_added)
        self.p2pstream.set_transmitter_ht('nice', params)

    def is_ready(self):
        return JingleContent.is_ready(self) and self.candidates_ready

    def make_bin_from_config(self, config_key, pipeline, text):
        pipeline = pipeline % app.config.get(config_key)
        try:
            gst_bin = Gst.parse_bin_from_description(pipeline, True)
            return gst_bin
        except GLib.GError as e:
            app.nec.push_incoming_event(
                InformationEvent(
                    None, conn=self.session.connection, level='error',
                    pri_txt=_('%s configuration error') % text.capitalize(),
                    sec_txt=_('Couldn’t set up %(text)s. Check your '
                    'configuration.\n\nPipeline was:\n%(pipeline)s\n\n'
                    'Error was:\n%(error)s') % {'text': text,
                    'pipeline': pipeline, 'error': str(e)}))
            raise JingleContentSetupException

    def add_remote_candidates(self, candidates):
        JingleContent.add_remote_candidates(self, candidates)
        # FIXME: connectivity should not be established yet
        # Instead, it should be established after session-accept!
        if self.sent:
            self.p2pstream.add_remote_candidates(candidates)

    def batch_dtmf(self, events):
        """
        Send several DTMF tones
        """
        if self._dtmf_running:
            raise Exception("There is a DTMF batch already running")
        events = deque(events)
        self._dtmf_running = True
        self._start_dtmf(events.popleft())
        GLib.timeout_add(500, self._next_dtmf, events)

    def _next_dtmf(self, events):
        self._stop_dtmf()
        if events:
            self._start_dtmf(events.popleft())
            GLib.timeout_add(500, self._next_dtmf, events)
        else:
            self._dtmf_running = False

    def _start_dtmf(self, event):
        if event in ('*', '#'):
            event = {'*': Farstream.DTMFEvent.STAR,
                     '#': Farstream.DTMFEvent.POUND}[event]
        else:
            event = int(event)
        self.p2psession.start_telephony_event(event, 2)

    def _stop_dtmf(self):
        self.p2psession.stop_telephony_event()

    def _fill_content(self, content):
        content.addChild(Namespace.JINGLE_RTP + ' description',
                         attrs={'media': self.media},
                         payload=list(self.iter_codecs()))

    def _setup_funnel(self):
        self.funnel = Gst.ElementFactory.make('funnel', None)
        self.pipeline.add(self.funnel)
        self.funnel.link(self.sink)
        self.sink.set_state(Gst.State.PLAYING)
        self.funnel.set_state(Gst.State.PLAYING)

    def _on_src_pad_added(self, stream, pad, codec):
        if not self.funnel:
            self._setup_funnel()
        pad.link(self.funnel.get_request_pad('sink_%u'))

    def _on_gst_message(self, bus, message):
        if message.type == Gst.MessageType.ELEMENT:
            name = message.get_structure().get_name()
            log.debug('gst element message: %s: %s', name, message)
            if name == 'farstream-new-active-candidate-pair':
                pass
            elif name == 'farstream-recv-codecs-changed':
                pass
            elif name == 'farstream-codecs-changed':
                if self.sent and self.p2psession.props.codecs_without_config:
                    self.send_description_info()
                    if self.transport.remote_candidates:
                        # those lines MUST be done after we get info on our
                        # codecs
                        self.p2pstream.add_remote_candidates(
                            self.transport.remote_candidates)
                        self.transport.remote_candidates = []
                        self.p2pstream.set_property('direction',
                                                    Farstream.StreamDirection.BOTH)

            elif name == 'farstream-local-candidates-prepared':
                self.candidates_ready = True
                if self.is_ready():
                    self.session.on_session_state_changed(self)
            elif name == 'farstream-new-local-candidate':
                candidate = self.p2pstream.parse_new_local_candidate(message)[1]
                self.transport.candidates.append(candidate)
                if self.sent:
                    # FIXME: Is this case even possible?
                    self.send_candidate(candidate)
            elif name == 'farstream-component-state-changed':
                state = message.get_structure().get_value('state')
                if state == Farstream.StreamState.FAILED:
                    reason = nbxmpp.Node('reason')
                    reason.setTag('failed-transport')
                    self.session.remove_content(self.creator, self.name, reason)
            elif name == 'farstream-error':
                log.error('Farstream error #%d!\nMessage: %s',
                          message.get_structure().get_value('error-no'),
                          message.get_structure().get_value('error-msg'))
        elif message.type == Gst.MessageType.ERROR:
            # TODO: Fix it to fallback to videotestsrc anytime an error occur,
            # or raise an error, Jingle way
            # or maybe one-sided stream?
            gerror_msg = message.get_structure().get_value('gerror')
            debug_msg = message.get_structure().get_value('debug')
            log.error(gerror_msg)
            log.error(debug_msg)
            if not self.stream_failed_once:
                app.nec.push_incoming_event(
                    InformationEvent(
                        None, dialog_name='gstreamer-error',
                        kwargs={'error': gerror_msg, 'debug': debug_msg}))

            sink_pad = self.p2psession.get_property('sink-pad')

            # Remove old source
            self.src_bin.get_static_pad('src').unlink(sink_pad)
            self.src_bin.set_state(Gst.State.NULL)
            self.pipeline.remove(self.src_bin)

            if not self.stream_failed_once:
                # Add fallback source
                self.src_bin = self.get_fallback_src()
                self.pipeline.add(self.src_bin)
                self.src_bin.get_static_pad('src').link(sink_pad)
                self.stream_failed_once = True
            else:
                reason = nbxmpp.Node('reason')
                reason.setTag('failed-application')
                self.session.remove_content(self.creator, self.name, reason)

            # Start playing again
            self.pipeline.set_state(Gst.State.PLAYING)

    @staticmethod
    def get_fallback_src():
        return Gst.ElementFactory.make('fakesrc', None)

    def on_negotiated(self):
        if self.accepted:
            if self.p2psession.get_property('codecs'):
                # those lines MUST be done after we get info on our codecs
                if self.transport.remote_candidates:
                    self.p2pstream.add_remote_candidates(
                        self.transport.remote_candidates)
                    self.transport.remote_candidates = []
                    # TODO: Farstream.StreamDirection.BOTH only if senders='both'
#                    self.p2pstream.set_property('direction',
#                        Farstream.StreamDirection.BOTH)
        JingleContent.on_negotiated(self)

    def __on_remote_codecs(self, stanza, content, error, action):
        """
        Get peer codecs from what we get from peer
        """

        codecs = []
        for codec in content.getTag('description').iterTags('payload-type'):
            if not codec['id'] or not codec['name'] or not codec['clockrate']:
                # ignore invalid payload-types
                continue
            c = Farstream.Codec.new(int(codec['id']), codec['name'],
                                    self.farstream_media, int(codec['clockrate']))
            if 'channels' in codec:
                c.channels = int(codec['channels'])
            else:
                c.channels = 1
            for p in codec.iterTags('parameter'):
                c.add_optional_parameter(p['name'], str(p['value']))
            codecs.append(c)

        if codecs:
            try:
                self.p2pstream.set_remote_codecs(codecs)
            except GLib.Error:
                raise FailedApplication

    def iter_codecs(self):
        codecs = self.p2psession.props.codecs_without_config
        for codec in codecs:
            attrs = {
                'name': codec.encoding_name,
                'id': codec.id,
            }
            if codec.channels > 0:
                attrs['channels'] = codec.channels
            if codec.clock_rate:
                attrs['clockrate'] = codec.clock_rate
            if codec.optional_params:
                payload = [nbxmpp.Node('parameter',
                                       {'name': p.name, 'value': p.value})
                           for p in codec.optional_params]
            else:
                payload = []
            yield nbxmpp.Node('payload-type', attrs, payload)

    def __stop(self, *things):
        self.pipeline.set_state(Gst.State.NULL)

    def __del__(self):
        self.__stop()

    def destroy(self):
        JingleContent.destroy(self)
        self.p2pstream.disconnect_by_func(self._on_src_pad_added)
        self.pipeline.get_bus().disconnect_by_func(self._on_gst_message)


class JingleAudio(JingleRTPContent):
    """
    Jingle VoIP sessions consist of audio content transported over an ICE UDP
    protocol
    """

    def __init__(self, session, transport=None):
        JingleRTPContent.__init__(self, session, 'audio', transport)
        self.setup_stream()

    def set_mic_volume(self, vol):
        """
        vol must be between 0 and 1
        """
        self.mic_volume.set_property('volume', vol)

    def set_out_volume(self, vol):
        """
        vol must be between 0 and 1
        """
        self.out_volume.set_property('volume', vol)

    def setup_stream(self):
        JingleRTPContent.setup_stream(self, self._on_src_pad_added)

        # list of codecs that are explicitly allowed
        allow_codecs = [
            Farstream.Codec.new(Farstream.CODEC_ID_ANY, 'OPUS',
                                Farstream.MediaType.AUDIO, 48000),
            Farstream.Codec.new(Farstream.CODEC_ID_ANY, 'SPEEX',
                                Farstream.MediaType.AUDIO, 32000),
            Farstream.Codec.new(Farstream.CODEC_ID_ANY, 'G722',
                                Farstream.MediaType.AUDIO, 8000),
            Farstream.Codec.new(Farstream.CODEC_ID_ANY, 'SPEEX',
                                Farstream.MediaType.AUDIO, 16000),
            Farstream.Codec.new(Farstream.CODEC_ID_ANY, 'PCMA',
                                Farstream.MediaType.AUDIO, 8000),
            Farstream.Codec.new(Farstream.CODEC_ID_ANY, 'PCMU',
                                Farstream.MediaType.AUDIO, 8000),
            Farstream.Codec.new(Farstream.CODEC_ID_ANY, 'SPEEX',
                                Farstream.MediaType.AUDIO, 8000),
            Farstream.Codec.new(Farstream.CODEC_ID_ANY, 'AMR',
                                Farstream.MediaType.AUDIO, 8000),
            ]

        # disable all other codecs
        disable_codecs = []
        codecs_without_config = self.p2psession.props.codecs_without_config
        allowed_encoding_names = [c.encoding_name for c in allow_codecs] + ['telephone-event']
        for codec in codecs_without_config:
            if codec.encoding_name not in allowed_encoding_names:
                disable_codecs.append(Farstream.Codec.new(Farstream.CODEC_ID_DISABLE,
                                                          codec.encoding_name,
                                                          Farstream.MediaType.AUDIO,
                                                          codec.clock_rate))

        self.p2psession.set_codec_preferences(allow_codecs + disable_codecs)

        # the local parts
        # TODO: Add queues?
        self.src_bin = self.make_bin_from_config('audio_input_device',
                                                 '%s ! audioconvert',
                                                 _("audio input"))

        self.sink = self.make_bin_from_config('audio_output_device',
                                              'audioconvert ! volume name=gajim_out_vol ! %s',
                                              _("audio output"))

        self.mic_volume = self.src_bin.get_by_name('gajim_vol')
        self.out_volume = self.sink.get_by_name('gajim_out_vol')

        # link gst elements
        self.pipeline.add(self.sink)
        self.pipeline.add(self.src_bin)

        self.src_bin.get_static_pad('src').link(self.p2psession.get_property(
            'sink-pad'))

        # The following is needed for farstream to process ICE requests:
        self.pipeline.set_state(Gst.State.PLAYING)


class JingleVideo(JingleRTPContent):
    def __init__(self, session, transport=None):
        JingleRTPContent.__init__(self, session, 'video', transport)
        self.setup_stream()

    def setup_stream(self):
        # TODO: Everything is not working properly:
        # sometimes, one window won't show up,
        # sometimes it'll freeze...
        JingleRTPContent.setup_stream(self, self._on_src_pad_added)
        bus = self.pipeline.get_bus()
        bus.enable_sync_message_emission()

    def do_setup(self, self_display_sink, other_sink):
        if app.config.get('video_see_self'):
            tee = '! tee name=split ! queue name=self-display-queue split. ! queue name=network-queue'
        else:
            tee = ''

        self.src_bin = self.make_bin_from_config('video_input_device',
                                                 '%%s %s' % tee,
                                                 _("video input"))
        self.pipeline.add(self.src_bin)
        if app.config.get('video_see_self'):
            self.pipeline.add(self_display_sink)
            self_display_queue = self.src_bin.get_by_name('self-display-queue')
            self_display_queue.get_static_pad('src').link_maybe_ghosting(self_display_sink.get_static_pad('sink'))
        self.pipeline.set_state(Gst.State.PLAYING)

        self.sink = other_sink
        self.pipeline.add(self.sink)

        self.src_bin.get_static_pad('src').link(self.p2psession.get_property(
            'sink-pad'))

        # The following is needed for farstream to process ICE requests:
        self.pipeline.set_state(Gst.State.PLAYING)

        if log.getEffectiveLevel() == logging.DEBUG:
            Gst.debug_bin_to_dot_file(self.pipeline, Gst.DebugGraphDetails.ALL, 'video-graph')

    def get_fallback_src(self):
        # TODO: Use avatar?
        pipeline = 'videotestsrc is-live=true ! video/x-raw,framerate=10/1 ! videoconvert'
        return Gst.parse_bin_from_description(pipeline, True)

def get_content(desc):
    if desc['media'] == 'audio':
        return JingleAudio
    if desc['media'] == 'video':
        return JingleVideo

contents[Namespace.JINGLE_RTP] = get_content
