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

#ifndef _WIN32
	#include <X11/Xlib.h>
	#include <X11/Xutil.h>
	#include <X11/extensions/scrnsaver.h>
	#include <gdk/gdkx.h>
	#include <gtk/gtk.h>
#else
	#define _WIN32_WINNT 0x0500
	#include <windows.h>
	#define EXPORT __declspec(dllexport)
#endif

#include <Python.h>

#ifdef _WIN32
	typedef BOOL (WINAPI *GETLASTINPUTINFO)(LASTINPUTINFO *);
	static HMODULE g_user32 = NULL;
	static GETLASTINPUTINFO g_GetLastInputInfo = NULL;
#endif


static PyObject * idle_init(PyObject *self, PyObject *args)
{
#ifndef _WIN32
	gtk_init (NULL, NULL);
#else
	g_user32 = LoadLibrary("user32.dll");
	if (g_user32) {
		g_GetLastInputInfo = (GETLASTINPUTINFO)GetProcAddress(g_user32, "GetLastInputInfo");
	}
#endif
	Py_INCREF(Py_None);
	return Py_None;
}

static PyObject * idle_getIdleSec(PyObject *self, PyObject *args)
{
#ifndef _WIN32
	static XScreenSaverInfo *mit_info = NULL;
	int idle_time, event_base, error_base;
#else
	int idle_time = 0;
#endif

#ifndef _WIN32
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
#else
	if (g_GetLastInputInfo != NULL) {
		LASTINPUTINFO lii;
		memset(&lii, 0, sizeof(lii));
		lii.cbSize = sizeof(lii);
		if (g_GetLastInputInfo(&lii)) {
			idle_time = lii.dwTime;
		}
		idle_time = (GetTickCount() - idle_time) / 1000;
	}									
#endif
	return Py_BuildValue("i", idle_time);
}

static PyObject * idle_close(PyObject *self, PyObject *args)
{
#ifndef _WIN32
	gtk_main_quit ();
#else
	if (g_user32 != NULL)
		FreeLibrary(g_user32);
#endif
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
