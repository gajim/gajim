SUBDIRS = data src po

ACLOCAL_AMFLAGS = -I m4

bin_SCRIPTS = scripts/gajim

commonfilesdir = $(pkgdatadir)
commonfiles_DATA = COPYING	\
				   README 	\
				   ChangeLog \
				   THANKS	\
				   AUTHORS

EXTRA_DIST = \
	$(commonfiles_DATA) \
	autogen.sh			\
	intltool-extract.in \
	intltool-merge.in 	\
	intltool-update.in	\
	scripts/gajim.in
	
DISTCLEANFILES = 		\
	intltool-extract 	\
	intltool-merge 		\
	intltool-update		\
	scripts/gajim

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
	config.sub \
	aclocal.m4 \
	libtool
