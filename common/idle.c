/*      common/idle.c
 *
 * Gajim Team:
 *      - Yann Le Boulanger <asterix@lagaule.org>
 *      - Vincent Hanquez <tab@snarc.org>
 *
 *      Copyright (C) 2003-2005 Gajim Team
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published
 * by the Free Software Foundation; version 2 only.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
*/

#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/extensions/scrnsaver.h>
#include <gdk/gdkx.h>
#include <python2.3/Python.h>

#include <gtk/gtk.h>

static PyObject * idle_init(PyObject *self, PyObject *args)
{
	gtk_init (NULL, NULL);
	Py_INCREF(Py_None);
	return Py_None;
}

static PyObject * idle_getIdleSec(PyObject *self, PyObject *args)
{
	static XScreenSaverInfo *mit_info = NULL;
	int idle_time, event_base, error_base;

	gtk_init (NULL, NULL);
	if (XScreenSaverQueryExtension(GDK_DISPLAY(), &event_base, &error_base))
	{
		if (mit_info == NULL)
			mit_info = XScreenSaverAllocInfo();
		XScreenSaverQueryInfo(GDK_DISPLAY(), GDK_ROOT_WINDOW(), mit_info);
		idle_time = (mit_info->idle) / 1000;
	}
	else
		idle_time = 0;
	return Py_BuildValue("i", idle_time);
}

static PyObject * idle_close(PyObject *self, PyObject *args)
{
	gtk_main_quit ();
	Py_INCREF(Py_None);
	return Py_None;
}

static PyMethodDef idleMethods[] =
{
	{"init",  idle_init, METH_VARARGS, "init gtk"},
	{"getIdleSec",  idle_getIdleSec, METH_VARARGS, "Give the idle time in secondes"},
	{"close",  idle_close, METH_VARARGS, "close gtk"},
	{NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC
initidle(void)
{
	    (void) Py_InitModule("idle", idleMethods);
}
