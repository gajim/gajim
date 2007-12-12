/*****
    This is a modified form of idler.c. The original copyright notice follows.
 **/

/*****************************************
  * idler.c
  *
  * Uses IOKit to figure out the idle time of the system. The idle time
  * is stored as a property of the IOHIDSystem class; the name is
  * HIDIdleTime. Stored as a 64-bit int, measured in ns.
  *
  * The program itself just prints to stdout the time that the computer
has
  * been idle in seconds.
  *
  * Compile with gcc -Wall -framework IOKit -framework Carbon idler.c -o
  * idler
  *
  * Copyright (c) 2003, Stanford University
  * All rights reserved.
  *
  * Redistribution and use in source and binary forms, with or without
  * modification, are permitted provided that the following conditions
are
  * met:
  * Redistributions of source code must retain the above copyright
notice,
  * this list of conditions and the following disclaimer.
  *
  * Redistributions in binary form must reproduce the above copyright
notice,
  * this list of conditions and the following disclaimer in the
documentation
  * and/or other materials provided with the distribution.
  *
  * Neither the name of Stanford University nor the names of its
contributors
  * may be used to endorse or promote products derived from this software
  * without specific prior written permission.
  *
  * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS
  * IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO,
  * THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
PARTICULAR
  * PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR
  * CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
  * EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
  * PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
  * PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY
OF
  * LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
  * NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
  * SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
  */

#include <CoreFoundation/CoreFoundation.h>
#include <CoreServices/CoreServices.h>
#include <IOKit/IOKitLib.h>

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#include <Python.h>

/* 10^9 --  number of ns in a second */
#define NS_SECONDS 1000000000


static mach_port_t __idle_osx_master_port;
io_registry_entry_t __idle_osx_service;


static PyObject * idle_init(PyObject *self, PyObject *args)
{
    io_iterator_t iter;
    CFMutableDictionaryRef hid_match;

    IOMasterPort(MACH_PORT_NULL, &__idle_osx_master_port);

    /* Get IOHIDSystem */
    hid_match = IOServiceMatching("IOHIDSystem");
    IOServiceGetMatchingServices(__idle_osx_master_port, hid_match, &iter);
    if (iter == 0) {
        printf("Error accessing IOHIDSystem\n");
    }

    __idle_osx_service = IOIteratorNext(iter);
    if (__idle_osx_service == 0) {
        printf("Iterator's empty!\n");
    }

    IOObjectRelease(iter);

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * idle_getIdleSec(PyObject *self, PyObject *args)
{
    CFMutableDictionaryRef properties = 0;
    CFTypeRef obj = NULL;
    uint64_t tHandle = 0;

    if (IORegistryEntryCreateCFProperties(__idle_osx_service, &properties,
                                          kCFAllocatorDefault, 0) ==
        KERN_SUCCESS && properties != NULL)
    {
        obj = CFDictionaryGetValue(properties, CFSTR("HIDIdleTime"));
        CFRetain(obj);
    }
    else
    {
        printf("Couldn't grab properties of system\n");
    }

    if (obj)
    {
        CFTypeID type = CFGetTypeID(obj);

        if (type == CFDataGetTypeID())
        {
            CFDataGetBytes((CFDataRef) obj,
                           CFRangeMake(0, sizeof(tHandle)),
                           (UInt8*) &tHandle);
        }
        else if (type == CFNumberGetTypeID())
        {
            CFNumberGetValue((CFNumberRef)obj,
                             kCFNumberSInt64Type,
                             &tHandle);
        }
        else
        {
            printf("%d: unsupported type\n", (int)type);
        }

        CFRelease(obj);

        // essentially divides by 10^9
        tHandle >>= 30;
    }
    else
    {
        printf("Can't find idle time\n");
    }

    CFRelease((CFTypeRef)properties);
    return Py_BuildValue("L", tHandle);
}

static PyObject * idle_close(PyObject *self, PyObject *args)
{
    /* Release our resources */
    IOObjectRelease(__idle_osx_service);

	Py_INCREF(Py_None);
	return Py_None;
}

static PyMethodDef idleMethods[] =
{
	{"init",  idle_init, METH_VARARGS, "init idle"},
	{"getIdleSec",  idle_getIdleSec, METH_VARARGS, "Get idle time in seconds"},
	{"close",  idle_close, METH_VARARGS, "close idle"},
	{NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC initidle(void)
{
    (void) Py_InitModule("idle", idleMethods);
}
