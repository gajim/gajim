#!/usr/bin/python
# hack
import sys, dl, gst, gobject
sys.setdlopenflags(dl.RTLD_NOW | dl.RTLD_GLOBAL)
import farsight

FARSIGHT_MEDIA_TYPE_AUDIO=0
FARSIGHT_STREAM_DIRECTION_BOTH=3
FARSIGHT_NETWORK_PROTOCOL_UDP=0
FARSIGHT_CANDIDATE_TYPE_LOCAL=0

# callbacks
def stream_error(stream, error, debug):
	print "stream error: stream=%r, error=%s" % (stream, error)

def session_error(stream, error, debug):
	print "session error: session=%r, error=%s" % (session, error)

def new_active_candidate_pair(stream, native_candidate, remote_candidate):
	print "new-native-canditate-pair: stream=%r" % (stream,)

def codec_changed(stream, codec_id):
	print "codec-changed: stream=%r, codec=%d" % (stream, codec_id)

def native_candidates_prepared(stream):
	print "preparation-complete: stream=%r" % (stream,)

	transport_candidates = stream.get_native_candidate_list()
	for candidate in candidates:
		print "Local transport candidate: %s %d %s %s %s:%d, pref %f" % \
			(candidate.candidate_id, candidate.component,
			 "UDP" if candidate.proto==FARSIGHT_NETWORK_PROTOCOL_UDP else "TCP",
			 candidate.proto_subtype, candidate.ip, candidate.port,
			 candidate.preference)

def state_changed(stream, state, dir):
	print "state-changed: stream=%r, %d, %d" % (stream, state, dir)

# setups
def setup_rtp_session():
	session = farsight.farsight_session_factory_make("rtp")

	# no error checking
	# no protocol details printed

	session.connect('error', session_error)

	return session

def setup_rtp_stream(session):
	stream = session.create_stream(FARSIGHT_MEDIA_TYPE_AUDIO, FARSIGHT_STREAM_DIRECTION_BOTH)
	stream.transmitter = "rawudp"
	stream.connect("error", stream_error);
	stream.connect("new-active-candidate-pair", new_active_candidate_pair);
	stream.connect("codec-changed", codec_changed);
	stream.connect("native-candidates-prepared", native_candidates_prepared);
	stream.connect("state-changed", state_changed);

	possible_codecs=stream.get_local_codecs()

	for codec in possible_codecs:
		print "codec: %d: %s/%d found" % (codec['id'], codec['encoding_name'], codec['clock_rate'])

	stream.prepare_transports()

	return stream

# main
def main():
	if len(sys.argv)!=3:
		print >>sys.stderr, "usage: test remoteip remoteport"
		return

	session = setup_rtp_session()
	stream = setup_rtp_stream(session)

	stream.set_remote_candidate_list([
		{'candidate_id': 'L1',
		 'component': 1,
		 'ip': sys.argv[1],
		 'port': int(sys.argv[2]),
		 'proto': FARSIGHT_NETWORK_PROTOCOL_UDP,
		 'proto_subtype': 'RTP',
		 'proto_profile': 'AVP',
		 'preference': 1.0,
		 'type': FARSIGHT_CANDIDATE_TYPE_LOCAL}])

	stream.set_remote_codecs(stream.get_local_codecs())

	gobject.MainLoop().run()


main()
