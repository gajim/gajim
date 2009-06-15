/* -*- Mode: C; c-basic-offset: 4 -*-
 * src/trayiconmodule.c
 *
 * Copyright (C) 2004-2005 Yann Leboulanger <asterix AT lagaule.org>
 *
 * This file is part of Gajim.
 *
 * Gajim is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published
 * by the Free Software Foundation; version 3 only.
 *
 * Gajim is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with Gajim. If not, see <http://www.gnu.org/licenses/>.
 */

/* include this first, before NO_IMPORT_PYGOBJECT is defined */
#include <pygobject.h>

void trayicon_register_classes (PyObject *d);

extern PyMethodDef trayicon_functions[];

DL_EXPORT(void)
inittrayicon(void)
{
    PyObject *m, *d;

    init_pygobject ();

    m = Py_InitModule ("trayicon", trayicon_functions);
    d = PyModule_GetDict (m);

    trayicon_register_classes (d);

    if (PyErr_Occurred ()) {
	Py_FatalError ("can't initialise module trayicon :(");
    }
}
