/*      common/idle.c
 *
 * Gajim Team:
 *      - Yann Le Boulanger <asterix@lagaule.org>
 *
 * Copyright (C) 2003-2004 Yann Le Boulanger <asterix@lagaule.org>
 *                         Vincent Hanquez <tab@snarc.org>
 * Copyright (C) 2005-2006 Yann Le Boulanger <asterix@lagaule.org>
 *                    Nikos Kouremenos <nkour@jabber.org>
 *
 * This file is part of Gajim.
 *
 * Gajim is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published
 * by the Free Software Foundation; version 3 only.
 *
 * Gajim is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public Licens
 * along with Gajim.  If not, see <http://www.gnu.org/licenses/>.
*/

#ifndef _WIN32
	#include <X11/Xlib.h>
	#include <X11/Xutil.h>
	#include <X11/extensions/scrnsaver.h>
#endif

#include <Python.h>

#ifndef _WIN32
	Display *display;
#endif


static PyObject * idle_init(PyObject *self, PyObject *args)
{
#ifndef _WIN32
	display = XOpenDisplay(NULL);
#endif
	Py_INCREF(Py_None);
	return Py_None;
}

static PyObject * idle_getIdleSec(PyObject *self, PyObject *args)
{
#ifndef _WIN32
	static XScreenSaverInfo *mit_info = NULL;
	int idle_time, event_base, error_base;
#endif

#ifndef _WIN32
	if (XScreenSaverQueryExtension(display, &event_base, &error_base))
	{
		if (mit_info == NULL)
			mit_info = XScreenSaverAllocInfo();
		XScreenSaverQueryInfo(display, RootWindow(display, 0), mit_info);
		idle_time = (mit_info->idle) / 1000;
	}
	else
		idle_time = 0;
#endif
	return Py_BuildValue("i", idle_time);
}

static PyObject * idle_close(PyObject *self, PyObject *args)
{
#ifndef _WIN32
	XCloseDisplay(display);
#endif
	Py_INCREF(Py_None);
	return Py_None;
}

static PyMethodDef idleMethods[] =
{
	{"init",  idle_init, METH_VARARGS, "init idle"},
	{"getIdleSec",  idle_getIdleSec, METH_VARARGS, "Give the idle time in secondes"},
	{"close",  idle_close, METH_VARARGS, "close idle"},
	{NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC
initidle(void)
{
	    (void) Py_InitModule("idle", idleMethods);
}
