
#CLEANFILES = \
#	trayicon.c

INCLUDES = \
	$(PYTHON_INCLUDES) 


idlelib_LTLIBRARIES = idle.la
idlelibdir = $(libdir)/gajim

idle_la_LIBADD = $(XSCREENSAVER_LIBS) 

idle_la_SOURCES = idle.c

idle_la_LDFLAGS = \
	-module -avoid-version -no-undefined

idle_la_CFLAGS = $(XSCREENSAVER_CFLAGS)

