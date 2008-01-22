SUBDIRS = farsight

INCLUDES = \
	$(PYTHON_INCLUDES) 
if BUILD_IDLE
idlelib_LTLIBRARIES = idle.la
idlelibdir = $(libdir)/gajim

idle_la_LIBADD = $(XSCRNSAVER_LIBS) 

idle_la_SOURCES = idle.c

idle_la_LDFLAGS = \
	-module -avoid-version

idle_la_CFLAGS = $(XSCRNSAVER_CFLAGS) $(PYTHON_INCLUDES)
endif

DISTCLEANFILES = 

EXTRA_DIST = 

MAINTAINERCLEANFILES = Makefile.in
