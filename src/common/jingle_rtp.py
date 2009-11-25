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
''' Handles Jingle RTP sessions (XEP 0167). '''


import gobject

import xmpp
import farsight, gst

from jingle_transport import JingleTransportICEUDP
from jingle_content import contents, JingleContent

# TODO: Will that be even used?
def get_first_gst_element(elements):
	''' Returns, if it exists, the first available element of the list. '''
	for name in elements:
		factory = gst.element_factory_find(name)
		if factory:
			return factory.create()


class JingleRTPContent(JingleContent):
	def __init__(self, session, media, transport=None):
		if transport is None:
			transport = JingleTransportICEUDP()
		JingleContent.__init__(self, session, transport)
		self.media = media
		self._dtmf_running = False
		self.farsight_media = {'audio': farsight.MEDIA_TYPE_AUDIO,
								'video': farsight.MEDIA_TYPE_VIDEO}[media]
		self.got_codecs = False

		self.candidates_ready = False # True when local candidates are prepared

		self.callbacks['session-initiate'] += [self.__getRemoteCodecsCB]
		self.callbacks['content-add'] += [self.__getRemoteCodecsCB]
		self.callbacks['content-accept'] += [self.__getRemoteCodecsCB,
			self.__contentAcceptCB]
		self.callbacks['session-accept'] += [self.__getRemoteCodecsCB,
			self.__contentAcceptCB]
		self.callbacks['session-accept-sent'] += [self.__contentAcceptCB]
		self.callbacks['content-accept-sent'] += [self.__contentAcceptCB]
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
		self.conference.set_property("sdes-cname", self.session.ourjid)
		self.pipeline.add(self.conference)
		self.funnel = None

		self.p2psession = self.conference.new_session(self.farsight_media)

		participant = self.conference.new_participant(self.session.peerjid)
		#FIXME: Consider a workaround, here... 
		# pidgin and telepathy-gabble don't follow the XEP, and it won't work
		# due to bad controlling-mode
		params = {'controlling-mode': self.session.weinitiate,# 'debug': False}
			'stun-ip': '69.0.208.27', 'debug': False}

		self.p2pstream = self.p2psession.new_stream(participant,
			farsight.DIRECTION_RECV, 'nice', params)

	def is_ready(self):
		return (JingleContent.is_ready(self) and self.candidates_ready
			and self.p2psession.get_property('codecs-ready'))

	def add_remote_candidates(self, candidates):
		JingleContent.add_remote_candidates(self, candidates)
		#FIXME: connectivity should not be etablished yet
		# Instead, it should be etablished after session-accept!
		if self.sent:
			self.p2pstream.set_remote_candidates(candidates)

	def batch_dtmf(self, events):
		if self._dtmf_running:
			raise Exception #TODO: Proper exception
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

	def _fillContent(self, content):
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
				#TODO: description-info
			elif name == 'farsight-local-candidates-prepared':
				self.candidates_ready = True
				if self.is_ready():
					self.session.on_session_state_changed(self)
			elif name == 'farsight-new-local-candidate':
				candidate = message.structure['candidate']
				self.transport.candidates.append(candidate)
				if self.candidates_ready:
					#FIXME: Is this case even possible?
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

	def __contentAcceptCB(self, stanza, content, error, action):
		if self.accepted:
			if self.transport.remote_candidates:
				self.p2pstream.set_remote_candidates(self.transport.remote_candidates)
				self.transport.remote_candidates = []
			#TODO: farsight.DIRECTION_BOTH only if senders='both'
			self.p2pstream.set_property('direction', farsight.DIRECTION_BOTH)
			self.session.content_negociated(self.media)

	def __getRemoteCodecsCB(self, stanza, content, error, action):
		''' Get peer codecs from what we get from peer. '''
		if self.got_codecs:
			return

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

		if len(codecs) > 0:
			#FIXME: Handle this case:
			# glib.GError: There was no intersection between the remote codecs and
			# the local ones
			self.p2pstream.set_remote_codecs(codecs)
			self.got_codecs = True

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
			else:	payload = ()
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
	''' Jingle VoIP sessions consist of audio content transported
	over an ICE UDP protocol. '''
	def __init__(self, session, transport=None):
		JingleRTPContent.__init__(self, session, 'audio', transport)
		self.setup_stream()


	''' Things to control the gstreamer's pipeline '''
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
		# TODO: use gconfaudiosink?
		# sink = get_first_gst_element(['alsasink', 'osssink', 'autoaudiosink'])
		self.sink = gst.element_factory_make('alsasink')
		self.sink.set_property('sync', False)
		#sink.set_property('latency-time', 20000)
		#sink.set_property('buffer-time', 80000)

		# TODO: use gconfaudiosrc?
		src_mic = gst.element_factory_make('alsasrc')
		src_mic.set_property('blocksize', 320)

		self.mic_volume = gst.element_factory_make('volume')
		self.mic_volume.set_property('volume', 1)

		# link gst elements
		self.pipeline.add(self.sink, src_mic, self.mic_volume)
		src_mic.link(self.mic_volume)

		self.mic_volume.get_pad('src').link(self.p2psession.get_property(
			'sink-pad'))
		self.p2pstream.connect('src-pad-added', self._on_src_pad_added)

		# The following is needed for farsight to process ICE requests:
		self.pipeline.set_state(gst.STATE_PLAYING)


class JingleVideo(JingleRTPContent):
	def __init__(self, session, transport=None):
		JingleRTPContent.__init__(self, session, 'video', transport)
		self.setup_stream()

	''' Things to control the gstreamer's pipeline '''
	def setup_stream(self):
		#TODO: Everything is not working properly:
		# sometimes, one window won't show up,
		# sometimes it'll freeze...
		JingleRTPContent.setup_stream(self)
		# the local parts
		src_vid = gst.element_factory_make('videotestsrc')
		src_vid.set_property('is-live', True)
		videoscale = gst.element_factory_make('videoscale')
		caps = gst.element_factory_make('capsfilter')
		caps.set_property('caps', gst.caps_from_string('video/x-raw-yuv, width=320, height=240'))
		colorspace = gst.element_factory_make('ffmpegcolorspace')

		self.pipeline.add(src_vid, videoscale, caps, colorspace)
		gst.element_link_many(src_vid, videoscale, caps, colorspace)

		self.sink = gst.element_factory_make('xvimagesink')
		self.pipeline.add(self.sink)

		colorspace.get_pad('src').link(self.p2psession.get_property('sink-pad'))
		self.p2pstream.connect('src-pad-added', self._on_src_pad_added)

		# The following is needed for farsight to process ICE requests:
		self.pipeline.set_state(gst.STATE_PLAYING)


def get_content(desc):
	if desc['media'] == 'audio':
		return JingleAudio
	elif desc['media'] == 'video':
		return JingleVideo
	else:
		return None

contents[xmpp.NS_JINGLE_RTP] = get_content
