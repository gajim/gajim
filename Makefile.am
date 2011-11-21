SUBDIRS = src data po icons plugins

ACLOCAL_AMFLAGS = -I m4

bin_SCRIPTS = scripts/gajim scripts/gajim-history-manager scripts/gajim-remote

EXTRA_DIST = \
	README.html \
	THANKS.artists \
	autogen.sh			\
	intltool-extract.in \
	intltool-merge.in 	\
	intltool-update.in	\
	gajim.nsi \
	setup_win32.py \
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
	python test/runtests.py
.PHONY: test

doc:
	epydoc --config=doc/epydoc.conf
.PHONY: doc
