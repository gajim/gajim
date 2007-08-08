#include <pygobject.h>
#include <stdio.h>
 
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
 
	// farsight_add_constants(m, 'FARSIGHT_TYPE_');

	if (PyErr_Occurred ()) {
		PyErr_Print();
	}
}
