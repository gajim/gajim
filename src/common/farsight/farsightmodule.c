#include <pygobject.h>
#include <stdio.h>

#include <farsight/farsight-codec.h>
#include <farsight/farsight-stream.h>
#include <farsight/farsight-transmitter.h>
 
void farsight_register_classes (PyObject *d); 
extern PyMethodDef farsight_functions[];
 
DL_EXPORT(void)
initfarsight(void)
{
	PyObject *m, *d;
 
	init_pygobject ();
 
	m = Py_InitModule ("farsight", farsight_functions);
	d = PyModule_GetDict (m);
 
	farsight_register_classes (d);
 
	PyModule_AddIntConstant(m, "MEDIA_TYPE_AUDIO", FARSIGHT_MEDIA_TYPE_AUDIO);
	PyModule_AddIntConstant(m, "MEDIA_TYPE_VIDEO", FARSIGHT_MEDIA_TYPE_VIDEO);
	PyModule_AddIntConstant(m, "STREAM_DIRECTION_NONE", FARSIGHT_STREAM_DIRECTION_NONE);
	PyModule_AddIntConstant(m, "STREAM_DIRECTION_SENDONLY", FARSIGHT_STREAM_DIRECTION_SENDONLY);
	PyModule_AddIntConstant(m, "STREAM_DIRECTION_RECEIVEONLY", FARSIGHT_STREAM_DIRECTION_RECEIVEONLY);
	PyModule_AddIntConstant(m, "STREAM_DIRECTION_BOTH", FARSIGHT_STREAM_DIRECTION_BOTH);
	PyModule_AddIntConstant(m, "STREAM_STATE_DISCONNECTED", FARSIGHT_STREAM_STATE_DISCONNECTED);
	PyModule_AddIntConstant(m, "STREAM_STATE_CONNECTING", FARSIGHT_STREAM_STATE_CONNECTING);
	PyModule_AddIntConstant(m, "STREAM_STATE_CONNECTED", FARSIGHT_STREAM_STATE_CONNECTED);
	PyModule_AddIntConstant(m, "STREAM_ERROR_EOS", FARSIGHT_STREAM_ERROR_EOS);
	PyModule_AddIntConstant(m, "STREAM_UNKNOWN_ERROR", FARSIGHT_STREAM_UNKNOWN_ERROR);
	PyModule_AddIntConstant(m, "STREAM_ERROR_UNKNOWN", FARSIGHT_STREAM_UNKNOWN_ERROR);
	PyModule_AddIntConstant(m, "STREAM_ERROR_TIMEOUT", FARSIGHT_STREAM_ERROR_TIMEOUT);
	PyModule_AddIntConstant(m, "STREAM_ERROR_NETWORK", FARSIGHT_STREAM_ERROR_NETWORK);
	PyModule_AddIntConstant(m, "STREAM_ERROR_PIPELINE_SETUP", FARSIGHT_STREAM_ERROR_PIPELINE_SETUP);
	PyModule_AddIntConstant(m, "STREAM_ERROR_RESOURCE", FARSIGHT_STREAM_ERROR_RESOURCE);
	PyModule_AddIntConstant(m, "DTMF_EVENT_0", FARSIGHT_DTMF_EVENT_0);
	PyModule_AddIntConstant(m, "DTMF_EVENT_1", FARSIGHT_DTMF_EVENT_1);
	PyModule_AddIntConstant(m, "DTMF_EVENT_2", FARSIGHT_DTMF_EVENT_2);
	PyModule_AddIntConstant(m, "DTMF_EVENT_3", FARSIGHT_DTMF_EVENT_3);
	PyModule_AddIntConstant(m, "DTMF_EVENT_4", FARSIGHT_DTMF_EVENT_4);
	PyModule_AddIntConstant(m, "DTMF_EVENT_5", FARSIGHT_DTMF_EVENT_5);
	PyModule_AddIntConstant(m, "DTMF_EVENT_6", FARSIGHT_DTMF_EVENT_6);
	PyModule_AddIntConstant(m, "DTMF_EVENT_7", FARSIGHT_DTMF_EVENT_7);
	PyModule_AddIntConstant(m, "DTMF_EVENT_8", FARSIGHT_DTMF_EVENT_8);
	PyModule_AddIntConstant(m, "DTMF_EVENT_9", FARSIGHT_DTMF_EVENT_9);
	PyModule_AddIntConstant(m, "DTMF_EVENT_STAR", FARSIGHT_DTMF_EVENT_STAR);
	PyModule_AddIntConstant(m, "DTMF_EVENT_POUND", FARSIGHT_DTMF_EVENT_POUND);
	PyModule_AddIntConstant(m, "DTMF_EVENT_A", FARSIGHT_DTMF_EVENT_A);
	PyModule_AddIntConstant(m, "DTMF_EVENT_B", FARSIGHT_DTMF_EVENT_B);
	PyModule_AddIntConstant(m, "DTMF_EVENT_C", FARSIGHT_DTMF_EVENT_C);
	PyModule_AddIntConstant(m, "DTMF_EVENT_D", FARSIGHT_DTMF_EVENT_D);
	PyModule_AddIntConstant(m, "DTMF_METHOD_AUTO", FARSIGHT_DTMF_METHOD_AUTO);
	PyModule_AddIntConstant(m, "DTMF_METHOD_RTP_RFC4733", FARSIGHT_DTMF_METHOD_RTP_RFC4733);
	PyModule_AddIntConstant(m, "DTMF_METHOD_SOUND", FARSIGHT_DTMF_METHOD_SOUND);
	PyModule_AddIntConstant(m, "TRANSMITTER_STATE_DISCONNECTED", FARSIGHT_TRANSMITTER_STATE_DISCONNECTED);
	PyModule_AddIntConstant(m, "TRANSMITTER_STATE_CONNECTING", FARSIGHT_TRANSMITTER_STATE_CONNECTING);
	PyModule_AddIntConstant(m, "TRANSMITTER_STATE_CONNECTED", FARSIGHT_TRANSMITTER_STATE_CONNECTED);
	PyModule_AddIntConstant(m, "CANDIDATE_TYPE_LOCAL", FARSIGHT_CANDIDATE_TYPE_LOCAL);
	PyModule_AddIntConstant(m, "CANDIDATE_TYPE_DERIVED", FARSIGHT_CANDIDATE_TYPE_DERIVED);
	PyModule_AddIntConstant(m, "CANDIDATE_TYPE_RELAY", FARSIGHT_CANDIDATE_TYPE_RELAY);
	PyModule_AddIntConstant(m, "NETWORK_PROTOCOL_UDP", FARSIGHT_NETWORK_PROTOCOL_UDP);
	PyModule_AddIntConstant(m, "NETWORK_PROTOCOL_TCP", FARSIGHT_NETWORK_PROTOCOL_TCP);

	if (PyErr_Occurred ()) {
		PyErr_Print();
	}
}
