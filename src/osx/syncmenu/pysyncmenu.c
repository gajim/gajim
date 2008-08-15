/*
## src/osx/syncmenu/pysyncmenu.c
##
## Copyright (C) 2007 Yann Leboulanger <asterix AT lagaule.org>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
## 
 */

#include <errno.h>
#include <string.h>
#include <Python.h>
#include <pygobject.h>
#include "sync-menu.h"


PyDoc_STRVAR(pysync_menu_takeover_menu__doc__,
"Receives: a GtkMenuShell\n"
"Returns:\n");

static PyObject *pysync_menu_takeover_menu(PyObject *s, PyObject *args)
{
    PyObject *obj = NULL;

    if (!PyArg_ParseTuple(args, "O:GtkMenuShell", &obj))
    {
        PyErr_SetString(PyExc_TypeError, "Failed to process parameter1");
        return NULL;
    }

    Py_INCREF(obj);

    GtkMenuShell* menu = pyg_boxed_get(obj, GtkMenuShell);
    if (!menu)
    {
        PyErr_SetString(PyExc_TypeError, "Failed to process parameter2");
        return NULL;
    }

    sync_menu_takeover_menu(menu);

    Py_INCREF(Py_None);
    return Py_None;
}

static PyMethodDef syncmenuModuleMethods[] =
{
    {"takeover_menu", (PyCFunction)pysync_menu_takeover_menu,
     METH_VARARGS, pysync_menu_takeover_menu__doc__},
    {NULL}
};

PyDoc_STRVAR(modsyncmenu__doc__,
             "GTK+ Integration for the Mac OS X Menubar.\n");

void initsyncmenu(void)
{
  if (!Py_InitModule3("syncmenu", syncmenuModuleMethods, modsyncmenu__doc__))
  {
      PyErr_SetString(PyExc_ImportError,
                      "Py_InitModule3(\"syncmenu\") failed");
      return;
  }
}
