
INCLUDES = \
	$(PYTHON_INCLUDES) 
if BUILD_IDLE
idlelib_LTLIBRARIES = idle.la
idlelibdir = $(libdir)/gajim

idle_la_LIBADD = $(XSCREENSAVER_LIBS) 

idle_la_SOURCES = idle.c

idle_la_LDFLAGS = \
	-module -avoid-version

idle_la_CFLAGS = $(XSCREENSAVER_CFLAGS) $(PYTHON_INCLUDES)
endif

DISTCLEANFILES = 

EXTRA_DIST = 

MAINTAINERCLEANFILES = Makefile.in
