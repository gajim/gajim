#import "nsapp.h"
#include <notify.h>

#include <AppKit/NSSound.h>

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#include <Python.h>


#define GAJIM_POOL_ALLOC \
     NSAutoreleasePool *gajim_pool = [[NSAutoreleasePool alloc] init];
#define GAJIM_POOL_FREE [gajim_pool release];


static PyObject *netChangedCB = NULL;
static NSFileHandle* netNotifyFH = nil;
static int netNotifyToken = -1;


@implementation NSApplication (Gajim)

- (void) initGUI
{
    [NSBundle loadNibNamed:@"Gajim" owner:NSApp];
}

+ (void) netNotifyCB: (NSNotification*) notif
{
    NSLog(@"Network changed notification");

    if (netChangedCB)
    {
        PyObject_CallObject(netChangedCB, NULL);
    }

	[[notif object] readInBackgroundAndNotify];		
}

- (BOOL) initNetNotify
{
    int fd = 0;

    if (notify_register_file_descriptor(
                "com.apple.system.config.network_change", &fd, 0,
                &netNotifyToken) != NOTIFY_STATUS_OK)
    {
        return FALSE;
    }

    netNotifyFH = [[NSFileHandle alloc] initWithFileDescriptor: fd];
    [[NSNotificationCenter defaultCenter] addObserver: [self class] 
           selector: @selector(netNotifyCB:) 
           name: NSFileHandleReadCompletionNotification 
           object: netNotifyFH];
    [netNotifyFH readInBackgroundAndNotify];	

    return TRUE;
}

- (void) initGajim
{
    GAJIM_POOL_ALLOC

    [self initGUI];
    [self initNetNotify];

    [NSApp setDelegate:self];
    [NSApp finishLaunching];

    GAJIM_POOL_FREE
}

- (void) orderFrontStandardAboutPanel: (id)sender
{
    PyRun_SimpleString("\n\
import gobject\n\
import dialogs\n\
def doAbout():\n\
	dialogs.AboutDialog()\n\
	return None\n\
gobject.idle_add(doAbout)\n\
");
}

- (NSApplicationTerminateReply)applicationShouldTerminate:(NSApplication *)sender
{
/*
    PyRun_SimpleString("\n\
import gajim\n\
import gobject\n\
def doQuit():\n\
	gajim.interface.roster.on_quit_menuitem_activate(None)\n\
	return None\n\
gobject.idle_add(doQuit)\n\
");
*/
    return NSTerminateNow;
}

- (BOOL) application:(NSApplication *)theApplication 
            openFile:(NSString *)filename
{
    NSLog(@"openFile");
    NSLog(filename);
    return YES;
}

- (void)application:(NSApplication *)sender openFiles:(NSArray *)filenames
{
    NSLog(@"openFiles");

    NSEnumerator* iter = [filenames objectEnumerator];
    NSString* str;
    while ((str = [iter nextObject]))
    {
        NSLog(str);
    }
    return;
}

- (BOOL)applicationOpenUntitledFile:(NSApplication *)theApplication
{
    NSLog(@"openUntitledFile");
    return YES;
}

- (BOOL)applicationShouldOpenUntitledFile:(NSApplication *)sender
{
    NSLog(@"shouldOpenUntitledFile");
    return YES;
}

@end


static PyObject * nsapp_init(PyObject *self, PyObject *args)
{
    [NSApp initGajim];

	Py_INCREF(Py_None);
	return Py_None;
}

static PyObject * nsapp_setNetworkCB(PyObject *self, PyObject *args)
{
    PyArg_UnpackTuple(args, "netcb", 1, 1, &netChangedCB);

	Py_INCREF(Py_None);
	return Py_None;
}

static PyObject * nsapp_requestUserAttention(PyObject *self, PyObject *args)
{
    GAJIM_POOL_ALLOC
    [NSApp requestUserAttention:NSInformationalRequest];
    GAJIM_POOL_FREE

	Py_INCREF(Py_None);
	return Py_None;
}

static PyObject * nsapp_playFile(PyObject *self, PyObject *args)
{
    GAJIM_POOL_ALLOC

    const char* cstr = NULL;

    if (!PyArg_ParseTuple(args, "s", &cstr))
    {
        return NULL;
    }

    NSSound* snd = [[NSSound alloc] initWithContentsOfFile:
                                      [[NSString alloc] initWithUTF8String: cstr]
                                    byReference: YES];
    if (!snd)
    {
        Py_INCREF(Py_None);
        return Py_None;
    }

    if (![snd play])
    {
        Py_INCREF(Py_None);
        return Py_None;
    }

    GAJIM_POOL_FREE

	return Py_BuildValue("b", 1);
}

static PyObject * nsapp_getBundlePath(PyObject *self, PyObject *args)
{
    GAJIM_POOL_ALLOC

    NSBundle* bundle = [NSBundle mainBundle];
    if (!bundle)
    {
        Py_INCREF(Py_None);
        return Py_None;
    }

    NSString* nspath = [bundle bundlePath];
    if (!nspath)
    {
        Py_INCREF(Py_None);
        return Py_None;
    }

    const char* path = [nspath UTF8String];
    PyObject* pypath = Py_BuildValue("s", path);

    GAJIM_POOL_FREE

    return pypath;
}

static PyMethodDef nsappMethods[] =
{
	{"init", nsapp_init, METH_VARARGS, "init nsapp"},
    {"setNetworkCB", nsapp_setNetworkCB, METH_VARARGS,
     "Callback to call when the network state changes"},
    {"getBundlePath", nsapp_getBundlePath, METH_VARARGS,
     "Get the path to the bundle we were run from"},
    {"playFile", nsapp_playFile, METH_VARARGS,
     "Play a sound file"},
    {"requestUserAttention", nsapp_requestUserAttention, METH_VARARGS,
     "Sends a request for the users attention to the window manager"},
	{NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC initnsapp(void)
{
    (void) Py_InitModule("nsapp", nsappMethods);
}
