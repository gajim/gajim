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
Handles Jingle RTP sessions (XEP 0167)
"""

import gobject
import socket

import xmpp
import farsight, gst
from glib import GError

import gajim

from jingle_transport import JingleTransportICEUDP
from jingle_content import contents, JingleContent, JingleContentSetupException


class JingleRTPContent(JingleContent):
	def __init__(self, session, media, transport=None):
		if transport is None:
			transport = JingleTransportICEUDP()
		JingleContent.__init__(self, session, transport)
		self.media = media
		self._dtmf_running = False
		self.farsight_media = {'audio': farsight.MEDIA_TYPE_AUDIO,
								'video': farsight.MEDIA_TYPE_VIDEO}[media]

		self.candidates_ready = False # True when local candidates are prepared

		self.callbacks['session-initiate'] += [self.__on_remote_codecs]
		self.callbacks['content-add'] += [self.__on_remote_codecs]
		self.callbacks['description-info'] += [self.__on_remote_codecs]
		self.callbacks['content-accept'] += [self.__on_remote_codecs,
			self.__on_content_accept]
		self.callbacks['session-accept'] += [self.__on_remote_codecs,
			self.__on_content_accept]
		self.callbacks['session-accept-sent'] += [self.__on_content_accept]
		self.callbacks['content-accept-sent'] += [self.__on_content_accept]
		self.callbacks['session-terminate'] += [self.__stop]
		self.callbacks['session-terminate-sent'] += [self.__stop]

	def setup_stream(self):
		# pipeline and bus
		self.pipeline = gst.Pipeline()
		bus = self.pipeline.get_bus()
		bus.add_signal_watch()
		bus.connect('message', self._on_gst_message)

		# conference
		self.conference = gst.element_factory_make('fsrtpconference')
		self.conference.set_property('sdes-cname', self.session.ourjid)
		self.pipeline.add(self.conference)
		self.funnel = None

		self.p2psession = self.conference.new_session(self.farsight_media)

		participant = self.conference.new_participant(self.session.peerjid)
		# FIXME: Consider a workaround, here...
		# pidgin and telepathy-gabble don't follow the XEP, and it won't work
		# due to bad controlling-mode
		params = {'controlling-mode': self.session.weinitiate, 'debug': False}
		stun_server = gajim.config.get('stun_server')
		if stun_server:
			try:
				ip = socket.getaddrinfo(stun_server, 0, socket.AF_UNSPEC,
					socket.SOCK_STREAM)[0][4][0]
			except socket.gaierror, (errnum, errstr):
				log.warn('Lookup of stun ip failed: %s' % errstr)
			else:
				params['stun-ip'] =  ip

		self.p2pstream = self.p2psession.new_stream(participant,
			farsight.DIRECTION_RECV, 'nice', params)

	def is_ready(self):
		return (JingleContent.is_ready(self) and self.candidates_ready
			and self.p2psession.get_property('codecs-ready'))

	def make_bin_from_config(self, config_key, pipeline, text):
		pipeline = pipeline % gajim.config.get(config_key)
		try:
			bin = gst.parse_bin_from_description(pipeline, True)
			return bin
		except GError, error_str:
			self.session.connection.dispatch('ERROR',
				(_("%s configuration error") % text.capitalize(),
					_("Couldn't setup %s. Check your configuration.\n\n"
						"Pipeline was:\n%s\n\n"
						"Error was:\n%s") % (text, pipeline, error_str)))
			raise JingleContentSetupException

	def add_remote_candidates(self, candidates):
		JingleContent.add_remote_candidates(self, candidates)
		# FIXME: connectivity should not be etablished yet
		# Instead, it should be etablished after session-accept!
		if self.sent:
			self.p2pstream.set_remote_candidates(candidates)

	def batch_dtmf(self, events):
		"""
		Send several DTMF tones
		"""
		if self._dtmf_running:
			raise Exception # TODO: Proper exception
		self._dtmf_running = True
		self._start_dtmf(events.pop(0))
		gobject.timeout_add(500, self._next_dtmf, events)

	def _next_dtmf(self, events):
		self._stop_dtmf()
		if events:
			self._start_dtmf(events.pop(0))
			gobject.timeout_add(500, self._next_dtmf, events)
		else:
			self._dtmf_running = False

	def _start_dtmf(self, event):
		if event in ('*', '#'):
			event = {'*': farsight.DTMF_EVENT_STAR,
				'#': farsight.DTMF_EVENT_POUND}[event]
		else:
			event = int(event)
		self.p2psession.start_telephony_event(event, 2,
			farsight.DTMF_METHOD_RTP_RFC4733)

	def _stop_dtmf(self):
		self.p2psession.stop_telephony_event(farsight.DTMF_METHOD_RTP_RFC4733)

	def _fill_content(self, content):
		content.addChild(xmpp.NS_JINGLE_RTP + ' description',
			attrs={'media': self.media}, payload=self.iter_codecs())

	def _setup_funnel(self):
		self.funnel = gst.element_factory_make('fsfunnel')
		self.pipeline.add(self.funnel)
		self.funnel.set_state(gst.STATE_PLAYING)
		self.sink.set_state(gst.STATE_PLAYING)
		self.funnel.link(self.sink)

	def _on_src_pad_added(self, stream, pad, codec):
		if not self.funnel:
			self._setup_funnel()
		pad.link(self.funnel.get_pad('sink%d'))

	def _on_gst_message(self, bus, message):
		if message.type == gst.MESSAGE_ELEMENT:
			name = message.structure.get_name()
			if name == 'farsight-new-active-candidate-pair':
				pass
			elif name == 'farsight-recv-codecs-changed':
				pass
			elif name == 'farsight-codecs-changed':
				if self.is_ready():
					self.session.on_session_state_changed(self)
				# TODO: description-info
			elif name == 'farsight-local-candidates-prepared':
				self.candidates_ready = True
				if self.is_ready():
					self.session.on_session_state_changed(self)
			elif name == 'farsight-new-local-candidate':
				candidate = message.structure['candidate']
				self.transport.candidates.append(candidate)
				if self.candidates_ready:
					# FIXME: Is this case even possible?
					self.send_candidate(candidate)
			elif name == 'farsight-component-state-changed':
				state = message.structure['state']
				print message.structure['component'], state
				if state == farsight.STREAM_STATE_FAILED:
					reason = xmpp.Node('reason')
					reason.setTag('failed-transport')
					self.session._session_terminate(reason)
			elif name == 'farsight-error':
				print 'Farsight error #%d!' % message.structure['error-no']
				print 'Message: %s' % message.structure['error-msg']
				print 'Debug: %s' % message.structure['debug-msg']
			else:
				print name

	def __on_content_accept(self, stanza, content, error, action):
		if self.accepted:
			if self.transport.remote_candidates:
				self.p2pstream.set_remote_candidates(self.transport.remote_candidates)
				self.transport.remote_candidates = []
			# TODO: farsight.DIRECTION_BOTH only if senders='both'
			self.p2pstream.set_property('direction', farsight.DIRECTION_BOTH)
			self.session.content_negociated(self.media)

	def __on_remote_codecs(self, stanza, content, error, action):
		"""
		Get peer codecs from what we get from peer
		"""

		codecs = []
		for codec in content.getTag('description').iterTags('payload-type'):
			c = farsight.Codec(int(codec['id']), codec['name'],
				self.farsight_media, int(codec['clockrate']))
			if 'channels' in codec:
				c.channels = int(codec['channels'])
			else:
				c.channels = 1
			c.optional_params = [(str(p['name']), str(p['value'])) for p in \
				codec.iterTags('parameter')]
			codecs.append(c)

		if codecs:
			# FIXME: Handle this case:
			# glib.GError: There was no intersection between the remote codecs and
			# the local ones
			self.p2pstream.set_remote_codecs(codecs)

	def iter_codecs(self):
		codecs = self.p2psession.get_property('codecs')
		for codec in codecs:
			attrs = {'name': codec.encoding_name,
				'id': codec.id,
				'channels': codec.channels}
			if codec.clock_rate:
				attrs['clockrate'] = codec.clock_rate
			if codec.optional_params:
				payload = (xmpp.Node('parameter', {'name': name, 'value': value})
					for name, value in codec.optional_params)
			else:
				payload = ()
			yield xmpp.Node('payload-type', attrs, payload)

	def __stop(self, *things):
		self.pipeline.set_state(gst.STATE_NULL)

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
		vol must be between 0 ans 1
		"""
		self.mic_volume.set_property('volume', vol)

	def setup_stream(self):
		JingleRTPContent.setup_stream(self)

		# Configure SPEEX
		# Workaround for psi (not needed since rev
		# 147aedcea39b43402fe64c533d1866a25449888a):
		#  place 16kHz before 8kHz, as buggy psi versions will take in
		#  account only the first codec

		codecs = [farsight.Codec(farsight.CODEC_ID_ANY, 'SPEEX',
			farsight.MEDIA_TYPE_AUDIO, 16000),
			farsight.Codec(farsight.CODEC_ID_ANY, 'SPEEX',
			farsight.MEDIA_TYPE_AUDIO, 8000)]
		self.p2psession.set_codec_preferences(codecs)

		# the local parts
		# TODO: Add queues?
		src_bin = self.make_bin_from_config('audio_input_device',
			'%s ! audioconvert', _("audio input"))

		self.sink = self.make_bin_from_config('audio_output_device',
			'audioconvert ! %s', _("audio output"))

		self.mic_volume = src_bin.get_by_name('gajim_vol')
		self.set_mic_volume(0)

		# link gst elements
		self.pipeline.add(self.sink, src_bin)

		src_bin.get_pad('src').link(self.p2psession.get_property(
			'sink-pad'))
		self.p2pstream.connect('src-pad-added', self._on_src_pad_added)

		# The following is needed for farsight to process ICE requests:
		self.pipeline.set_state(gst.STATE_PLAYING)


class JingleVideo(JingleRTPContent):
	def __init__(self, session, transport=None):
		JingleRTPContent.__init__(self, session, 'video', transport)
		self.setup_stream()

	def setup_stream(self):
		# TODO: Everything is not working properly:
		# sometimes, one window won't show up,
		# sometimes it'll freeze...
		JingleRTPContent.setup_stream(self)

		# the local parts
		src_bin = self.make_bin_from_config('video_input_device',
			'%s ! videoscale ! ffmpegcolorspace', _("video input"))
		#caps = gst.element_factory_make('capsfilter')
		#caps.set_property('caps', gst.caps_from_string('video/x-raw-yuv, width=320, height=240'))

		self.pipeline.add(src_bin)#, caps)
		#src_bin.link(caps)

		self.sink = self.make_bin_from_config('video_output_device',
			'videoscale ! ffmpegcolorspace ! %s', _("video output"))
		self.pipeline.add(self.sink)

		src_bin.get_pad('src').link(self.p2psession.get_property('sink-pad'))
		self.p2pstream.connect('src-pad-added', self._on_src_pad_added)

		# The following is needed for farsight to process ICE requests:
		self.pipeline.set_state(gst.STATE_PLAYING)


def get_content(desc):
	if desc['media'] == 'audio':
		return JingleAudio
	elif desc['media'] == 'video':
		return JingleVideo

contents[xmpp.NS_JINGLE_RTP] = get_content

# vim: se ts=3:
