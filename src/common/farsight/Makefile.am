CLEANFILES = \
	farsight.c

INCLUDES = \
	$(PYTHON_INCLUDES) 
farsightlib_LTLIBRARIES = farsight.la
farsightlibdir = $(libdir)/gajim

farsight_la_LIBADD = $(FARSIGHT_LIBS)

farsight_la_SOURCES = \
	farsightmodule.c

nodist_farsight_la_SOURCES = farsight.c

farsight_la_LDFLAGS = \
	-module -avoid-version

farsight_la_CFLAGS = $(FARSIGHT_CFLAGS) $(PYGTK_CFLAGS) $(PYTHON_INCLUDES) -I farsight/

farsight.c: farsight.defs farsight.override
	pygtk-codegen-2.0 \
		--prefix farsight \
		--override farsight.override \
		--register /usr/share/gst-python/0.10/defs/gst-types.defs \
		farsight.defs >$@

farsight.defs:
	python /usr/share/pygtk/2.0/codegen/h2def.py \
		farsight/farsight-codec.h \
		farsight/farsight-session.h \
		farsight/farsight-stream.h \
		>$@

DISTCLEANFILES = 

EXTRA_DIST = 

MAINTAINERCLEANFILES = Makefile.in
