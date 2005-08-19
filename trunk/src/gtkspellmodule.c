#include <Python.h>
#include <gtk/gtk.h>
#include <gtkspell/gtkspell.h>
#include "pygobject.h"

typedef struct {
    PyObject_HEAD
    GtkSpell *spell;
} gtkspell_SpellObject;

extern PyTypeObject gtkspell_SpellType;

static PyTypeObject *_PyGtkTextView_Type;
#define PyGtkTextView_Type (*_PyGtkTextView_Type)


static PyObject *
_wrap_gtkspell_new_attach (PyTypeObject *type, PyObject *args, PyObject *kwds)
{
	gtkspell_SpellObject *self;
	PyObject *pytextview;
	GtkTextView *textview;
        GtkSpell *spell;
        char *language = NULL;
        GError *error = NULL;

	if (!PyArg_ParseTuple(args, "O!|z:gtkspell.Spell.__new__",
                              &PyGtkTextView_Type, &pytextview, &language))
            return NULL;

	textview = GTK_TEXT_VIEW(((PyGObject *)pytextview)->obj);
        spell = gtkspell_new_attach(textview, language, &error);

        if (pyg_error_check(&error))
            return NULL;
        if (!spell) {
            PyErr_SetString(PyExc_RuntimeError, "unable to create and attach a Spell object");
            return NULL;
        }

	self = (gtkspell_SpellObject *)type->tp_alloc(type, 0);
        self->spell = spell;
	return (PyObject *)self;
}

static PyObject *
_wrap_gtkspell_set_language (gtkspell_SpellObject *self, PyObject *args, PyObject *kwds)
{
	gchar *lang;
	gboolean result;
	
	char *argnames[] = {"language", NULL};
	PyArg_ParseTupleAndKeywords (args, kwds, "s", argnames, &lang);

	result = gtkspell_set_language (self->spell, lang, NULL);	

	if (!result) {
		/*there are no specific errors in GtkSpell yet*/
       		PyErr_SetString(PyExc_RuntimeError, "Error setting language");
		return NULL;
	}

	Py_INCREF(Py_None);
	return Py_None;
}

static PyObject *
_wrap_gtkspell_recheck_all (gtkspell_SpellObject *self)
{
	gtkspell_recheck_all ((GtkSpell *)self->spell);

        Py_INCREF(Py_None);
        return Py_None;
	
}

static PyObject *
_wrap_gtkspell_get_from_text_view (PyObject *junk, PyObject *args, PyObject *kwds)
{
	PyObject *pytextview;
        GtkTextView *textview;
       	gtkspell_SpellObject *self; 
      
	char *argnames[] = {"textview", NULL};
        PyArg_ParseTupleAndKeywords (args, kwds, "O", argnames, &pytextview);

        textview = GTK_TEXT_VIEW(((PyGObject *)pytextview)->obj);

	self = (gtkspell_SpellObject *)PyType_GenericAlloc((PyTypeObject *)&gtkspell_SpellType, 1);
        if (self != NULL) {
                self->spell = gtkspell_get_from_text_view(textview);
                if (self->spell == NULL) {
                        Py_DECREF(self);
                        return NULL;
                }
        }
        return (PyObject *)self;
}

static PyObject *
_wrap_gtkspell_detach (gtkspell_SpellObject *self)
{
	gtkspell_detach(self->spell);
        self->spell = NULL;
	Py_INCREF(Py_None);
	return Py_None;
}


static PyMethodDef gtkspell_methods[] = {
        {"set_language", (PyCFunction)_wrap_gtkspell_set_language,
         METH_KEYWORDS, "Set the language"},
        {"recheck_all", (PyCFunction)_wrap_gtkspell_recheck_all,
         METH_NOARGS, "Recheck the spelling in the entire buffer"},
        {"detach", (PyCFunction)_wrap_gtkspell_detach,
         METH_NOARGS, "Detaches a Spell object from a TextView"},
        { NULL, NULL, 0 }
};


PyTypeObject gtkspell_SpellType = {
    PyObject_HEAD_INIT(NULL)
    0,                            /*ob_size*/
    "gtkspell.Spell",             /*tp_name*/
    sizeof(gtkspell_SpellObject), /*tp_basicsize*/
    0,                            /*tp_itemsize*/
    0, 				  /*tp_dealloc*/
    0,                            /*tp_print*/
    0,                            /*tp_getattr*/
    0,                            /*tp_setattr*/
    0,                            /*tp_compare*/
    0,                            /*tp_repr*/
    0,                            /*tp_as_number*/
    0,                            /*tp_as_sequence*/
    0,                            /*tp_as_mapping*/
    0,                            /*tp_hash */
    0,                            /*tp_call*/
    0,                            /*tp_str*/
    0,                            /*tp_getattro*/
    0,                            /*tp_setattro*/
    0,                            /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT,           /*tp_flags*/
    "GtkSpell object",            /* tp_doc */
    0,		               /* tp_traverse */
    0,		               /* tp_clear */
    0,		               /* tp_richcompare */
    0,		               /* tp_weaklistoffset */
    0,		               /* tp_iter */
    0,		               /* tp_iternext */
    gtkspell_methods,          /* tp_methods */
    0,             	       /* tp_members */
    0,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    0,       			/* tp_init */
    0,       			/* tp_alloc */
    _wrap_gtkspell_new_attach,  /* tp_new */
};

static PyMethodDef gtkspell_functions[] = {        
    {"get_from_text_view", (PyCFunction)_wrap_gtkspell_get_from_text_view,
     METH_KEYWORDS, "Retrieves the Spell object attach"},
    { NULL, NULL, 0, NULL }
};

DL_EXPORT(void)
initgtkspell(void)
{
    PyObject *m, *module;
        
    init_pygobject();

    if ((module = PyImport_ImportModule("gtk")) != NULL) {
        PyObject *moddict = PyModule_GetDict(module);

        _PyGtkTextView_Type = (PyTypeObject *)PyDict_GetItemString(moddict, "TextView");
        if (_PyGtkTextView_Type == NULL) {
            PyErr_SetString(PyExc_ImportError,
                            "cannot import name TextView from gtk");
            return;
        }
    } else {
        PyErr_SetString(PyExc_ImportError,
                        "could not import gtk");
        return;
    }


    m = Py_InitModule3 ("gtkspell", gtkspell_functions, "GtkSpell bindings");

    if (PyType_Ready(&gtkspell_SpellType) < 0)
        return;

    Py_INCREF(&gtkspell_SpellType);
    PyModule_AddObject(m, "Spell", (PyObject *)&gtkspell_SpellType);

    if (PyErr_Occurred ()) {
        PyErr_Print();
        Py_FatalError ("can't initialise module gtkspell");
    }
}
