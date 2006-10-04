SUBDIRS = common

CLEANFILES = \
	trayicon.c
INCLUDES = \
	$(PYTHON_INCLUDES) 

gtkspelllib_LTLIBRARIES = gtkspell.la
gtkspelllibdir = $(libdir)/gajim

gtkspell_la_LIBADD = \
	$(GTKSPELL_LIBS) $(PYGTK_LIBS) 

gtkspell_la_SOURCES = \
	gtkspellmodule.c

gtkspell_la_LDFLAGS = \
	-module -avoid-version -no-undefined

gtkspell_la_CFLAGS = $(GTKSPELL_CFLAGS) $(PYGTK_CFLAGS)

trayiconlib_LTLIBRARIES = trayicon.la
trayiconlibdir = $(libdir)/gajim
trayicon_la_LIBADD = $(PYGTK_LIBS)
trayicon_la_SOURCES = \
					  eggtrayicon.c \
					  trayiconmodule.c
nodist_trayicon_la_SOURCES = \
					trayicon.c
trayicon_la_LDFLAGS = \
	-module -avoid-version -no-undefined
trayicon_la_CFLAGS = $(PYGTK_CFLAGS)

trayicon.c: trayicon.defs trayicon.override
	    pygtk-codegen-2.0 --prefix trayicon \
		    --register $(PYGTK_DEFS)/gdk-types.defs \
		    --register $(PYGTK_DEFS)/gtk-types.defs \
		    --override trayicon.override \
		    trayicon.defs > $@

gajimsrcdir = $(pkgdatadir)/src
gajimsrc_DATA = *.py 

gajimsrc1dir = $(pkgdatadir)/src/common
gajimsrc1_DATA = \
				common/*.py 

gajimsrc2dir = $(pkgdatadir)/src/common/xmpp
gajimsrc2_DATA = \
				common/xmpp/*.py 

gajimsrc3dir = $(pkgdatadir)/src/common/zeroconf
gajimsrc3_DATA = \
				common/zeroconf/*.py 

EXTRA_DIST = $(gajimsrc_DATA) \
			$(gajimsrc1_DATA) \
			$(gajimsrc2_DATA) \
			$(gajimsrc3_DATA) \
			gtkspellmodule.c \
			eggtrayicon.c \
			trayiconmodule.c \
			eggtrayicon.h \
			trayicon.defs \
			trayicon.override

