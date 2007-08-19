#!/usr/bin/python

import sys, dl, gst, gobject
sys.setdlopenflags(dl.RTLD_NOW | dl.RTLD_GLOBAL)
import farsight
from socket import *

TYPE_CANDIDATE=0
TYPE_CODEC=1
TYPE_READY_BYTE=2

MODE_DUPLEX=0
MODE_AUDIO=1
MODE_VIDEO=2

send_sock = 0
recv_sock = 0
serv_addr = None
audio_stream = None
video_stream = None

def stream_error(stream, error, debug):
	pass
	#print "stream_error: stream=%r error=%s" % (stream, error)

def session_error(session, error, debug):
	pass
	#print "session_error: session=%r error=%s" % (session, error)

def new_active_candidate_pair(stream, native, remote):
	pass
	#print "new_active_candidate_pair: native %s, remote %s" % (native, remote)
	#send_codecs(stream.get_local_codecs())

def codec_changed(stream, codec_id):
	#print "codec_changed: codec_id=%d, stream=%r" % (codec_id, stream)
	pass

def native_candidates_prepared(stream):
	return
	print "native_candidates_prepared: stream=%r" % stream
	for info in stream.get_native_candidate_list():
		print "Local transport candidate: %s %d %s %s %s %d pref %f" % (
			info['candidate_id'], info['component'],
			(info['proto']==farsight.NETWORK_PROTOCOL_TCP) and "TCP" or "UDP",
			info['proto_subtype'], info['ip'], info['port'], info['preference']);

def show_element(e):
	return 
	print 'element: ...'

def state_changed(stream, state, dir):
	if state==farsight.STREAM_STATE_DISCONNECTED:
		#print "state_changed: disconnected"
		pass
	elif state==farsight.STREAM_STATE_CONNECTING:
		#print "state_changed: connecting"
		pass
	elif state==farsight.STREAM_STATE_CONNECTED:
		#print "state_changed: connectied"
		#print "WW: stream.signal_native_candidates_prepared()"
		#print "WW: stream.start()"
		stream.signal_native_candidates_prepared()
		stream.start()

def send_codecs(codecs):
	global send_sock, serv_addr
	for codec in codecs:
		if 'channels' not in codec: codec['channels']=1
		s="%d %d %s %d %d %d " % (TYPE_CODEC, codec['media_type'],
			codec['encoding_name'], codec['id'], codec['clock_rate'],
			codec['channels'])
		print s
	s="%d %d %s %d %d %d " % (TYPE_CODEC, codec['media_type'], 'LAST', 0, 0, 0)
	print s

def send_candidate(type, trans):
	global send_sock, serv_addr
	s="%d %d %s %s %d %s %s" % (TYPE_CANDIDATE,
		type, trans['candidate_id'], trans['ip'], trans['port'],
		trans['username'], trans['password'])
	print s

def new_native_candidate(stream, candidate_id):
	candidate=stream.get_native_candidate(candidate_id)
	trans=candidate[0]

	#print "New native candidate: <id: %s, component: %d, ip: %s port: %d proto: %d, proto_subtype: %s, proto_profile: %s, preference: %f, type: %d, username: %s, password: %s>" % (
	#	trans['candidate_id'], trans['component'], trans['ip'], trans['port'], trans['proto'],
	#	trans['proto_subtype'], trans['proto_profile'], trans['preference'], trans['type'],
	#	trans['username'], trans['password'])

	type=stream.get_property("media-type")

	send_candidate(type, trans)

remote_codecs_audio = []
remote_codecs_video = []
def add_remote_codec(stream, pt, encoding_name, media_type, clock_rate, channels):
	global remote_codecs_audio, remote_codecs_video
	if encoding_name=="LAST":
		if media_type==farsight.MEDIA_TYPE_AUDIO:
			#print "WW: set_remote_codecs(remote_codecs_audio), %r" % (remote_codecs_audio,)
			stream.set_remote_codecs(remote_codecs_audio)
		else:
			stream.set_remote_codecs(remote_codecs_video)
	else:
		codec={'id': pt, 'encoding_name': encoding_name, 'media_type': media_type,
			'clock_rate': clock_rate, 'channels': channels}
		if media_type==farsight.MEDIA_TYPE_AUDIO:
			remote_codecs_audio.append(codec)
		elif media_type==farsight.MEDIA_TYPE_VIDEO:
			remote_codecs_video.append(codec)

		#for codec in remote_codecs_audio:
		#	print "added audio codec: %d: %s/%d found" % (codec['id'], codec['encoding_name'], codec['clock_rate'])
		#for codec in remote_codecs_video:
		#	print "added video codec: %d: %s/%d found" % (codec['id'], codec['encoding_name'], codec['clock_rate'])

def add_remote_candidate(stream, id, ip, port, username, password):
	if not stream: return

	trans={'candidate_id': id, 'component': 1, 'ip': ip, 'port': port, 'proto': farsight.NETWORK_PROTOCOL_UDP,
		'proto_subtype': 'RTP', 'proto_profile': 'AVP', 'preference': 1.0,
		'type': farsight.CANDIDATE_TYPE_LOCAL, 'username': username, 'password': password}

	#print "WW: add_remote_candidate(%r)" % ([trans],)
	stream.add_remote_candidate([trans]);

def receive_loop(ch, cond, *data):
	#print 'receive_loop called!'
	global recv_sock, serv_addr, audio_stream, remote_stream
	#print "waiting for msg from %r" % (serv_addr,)
	buf=raw_input()
	#buf,a = recv_sock.recvfrom(1500)
	#print "got message! ",buf
	msg = buf.split(' ')
	type = int(msg.pop(0))
	#print msg
	if type==TYPE_CANDIDATE:
		media_type, id, ip, port, username, password = msg[:6]
		media_type=int(media_type)
		port=int(port)
		#print "Received %d %s %s %d %s %s" % (media_type, id, ip, port, username, password)
		if media_type==farsight.MEDIA_TYPE_AUDIO:
			add_remote_candidate(audio_stream, id, ip, port, username, password)
		elif media_type==farsight.MEDIA_TYPE_VIDEO:
			add_remote_candidate(video_stream, id, ip, port, username, password)
	elif type==TYPE_CODEC:
		media_type, encoding_name, pt, clock_rate, channels=msg[:5]
		media_type=int(media_type)
		pt=int(pt)
		clock_rate=int(clock_rate)
		channels=int(channels)

		#print "Received %d %s %d %d %d" % (media_type, encoding_name, pt, clock_rate, channels)

		if media_type==farsight.MEDIA_TYPE_AUDIO:
			add_remote_codec(audio_stream, pt, encoding_name, media_type, clock_rate, channels)
		elif media_type==farsight.MEDIA_TYPE_VIDEO:
			add_remote_codec(video_stream, pt, encoding_name, media_type, clock_rate, channels)
	elif type==TYPE_READY_BYTE:
		#print "got ready byte"
		pass
	return True

def set_xoverlay(bus, message, xid):
	print "set_xoverlay: called"
	if message!=gst.MESSAGE_ELEMENT: return gst.BUS_PASS

	if not message.structure.has_name('prepare-xwindow-id'): return gst.BUS_PASS

	print "set_xoverlay: setting x overlay window id"
	message.set_xwindow_id(xid)

	return gst.BUS_DROP

def main():
	global audio_stream, remote_stream
	#if len(sys.argv)<4 or len(sys.argv)>6:
	#	#print 'usage: %s remoteip remoteport localport [mode] [xid]' % sys.argv[0]
	#	return -1

	#if len(sys.argv)>=5:
	#	mode = int(sys.argv[4])
	#else:
	mode = MODE_DUPLEX

	#setup_send(sys.argv[1], int(sys.argv[2]))
	#print "Sending to %s %d listening on port %d" % (sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))

	#recv_chan=setup_recv(int(sys.argv[3]))

	#do_handshake(recv_chan)

	gobject.io_add_watch(0, gobject.IO_IN, receive_loop)

	session = setup_rtp_session()

	if mode==MODE_AUDIO or mode==MODE_VIDEO:
		audio_stream = setup_rtp_stream(session, farsight.MEDIA_TYPE_AUDIO)
	if mode==MODE_VIDEO or mode==MODE_DUPLEX:
		video_stream = setup_rtp_stream(session, farsight.MEDIA_TYPE_VIDEO)

	if audio_stream:
		audio_stream.set_active_codec(8)

		alsasrc = gst.element_factory_make('audiotestsrc', 'src')
		alsasink= gst.element_factory_make('alsasink', 'alsasink')

		alsasink.set_property('sync', False)
		alsasink.set_property('latency-time', 20000)
		alsasink.set_property('buffer-time', 80000)
		alsasrc.set_property('blocksize', 320)
		#alsasrc.set_property('latency-time', 20000)
		alsasrc.set_property('is-live', True)

		#print "WW: set_sink(%r)" % (alsasink,)
		audio_stream.set_sink(alsasink)
		#print "WW: set_source(%r)" % (alsasrc,)
		audio_stream.set_source(alsasrc)
	
	#if video_stream: assert False

	gobject.MainLoop().run()
	#print 'bu!'

def setup_rtp_session():
	session = farsight.farsight_session_factory_make('rtp')

	session.connect('error', session_error)
	return session

def setup_rtp_stream(session, type):
	stream = session.create_stream(type, farsight.STREAM_DIRECTION_BOTH)

	stream.set_property('transmitter', 'libjingle')

	stream.connect('error', stream_error)
	stream.connect('new-active-candidate-pair', new_active_candidate_pair)
	stream.connect('codec-changed', codec_changed)
	stream.connect('native-candidates-prepared', native_candidates_prepared)
	stream.connect('state-changed', state_changed)
	stream.connect('new-native-candidate', new_native_candidate)

	possible_codecs = stream.get_local_codecs()

	#for codec in possible_codecs:
	#	print "codec: %d: %s/%d found" % (codec['id'], codec['encoding_name'], codec['clock_rate'])
	
	send_codecs(possible_codecs)

	stream.prepare_transports()

	return stream


main()
