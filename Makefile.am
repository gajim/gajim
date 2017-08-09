SUBDIRS = gajim data po icons plugins

ACLOCAL_AMFLAGS = -I m4

bin_SCRIPTS = scripts/gajim scripts/gajim-history-manager scripts/gajim-remote

EXTRA_DIST = \
	THANKS.artists \
	autogen.sh			\
	intltool-extract.in \
	intltool-merge.in 	\
	intltool-update.in	\
	win \
	scripts/gajim.in
	
DISTCLEANFILES = 		\
	intltool-extract 	\
	intltool-merge 		\
	intltool-update		\
	scripts/gajim		\
	scripts/gajim-remote	\
	scripts/gajim-histrory-manager

MAINTAINERCLEANFILES = \
	configure \
	Makefile.in \
	intltool-extract.in \
	intltool-update.in \
	intltool-merge.in \
	ltmain.sh \
	missing \
	mkinstalldirs \
	install-sh \
	compile \
	depcomp \
	config.guess \
	config.log \
	config.sub \
	config.status \
	aclocal.m4 \
	libtool \
	po/POTFILES.in \
	m4/intltool.m4

MAINTAINERCLEANDIRS = \
	autom4te.cache \
	build \
	dist


test:
	${PYTHON} test/runtests.py
.PHONY: test

test_nogui:
	${PYTHON} test/runtests.py -n
.PHONY: test_nogui

doc:
	epydoc --config=doc/epydoc.conf
.PHONY: doc
