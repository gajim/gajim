SUBDIRS = data src po
bin_SCRIPTS = scripts/gajim

commonfilesdir = $(pkgdatadir)
commonfiles_DATA = COPYING	\
				   README 	\
				   ChangeLog \
				   THANKS	\
				   AUTHORS

EXTRA_DIST =			\
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
