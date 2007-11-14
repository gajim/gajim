GTKPATH="/Library/Frameworks/GTK+.framework/Versions/Current/bin"

export MACOSX_DEPLOYMENT_TARGET=10.4
INCLUDES = $(PYTHON_INCLUDES)

GTKLDFLAGS=`$(GTKPATH)/pkg-config --libs gtk+-2.0 pygobject-2.0` 
GTKCFLAGS=`$(GTKPATH)/pkg-config --cflags gtk+-2.0 pygobject-2.0`

if BUILD_COCOA
syncmenulib_LTLIBRARIES = syncmenu.la
syncmenulibdir = $(libdir)/gajim
syncmenu_la_SOURCES = sync-menu.c pysyncmenu.c
syncmenu_la_LDFLAGS = -module -avoid-version $(GTKLDFLAGS)
syncmenu_la_CFLAGS = $(GTKCFLAGS) -Wall -g $(INCLUDES)
endif

DISTCLEANFILES = 

EXTRA_DIST = 

MAINTAINERCLEANFILES = Makefile.in
