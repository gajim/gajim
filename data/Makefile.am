SUBDIRS = pixmaps
@INTLTOOL_DESKTOP_RULE@

appstreamdir = $(datadir)/metainfo/
appstream_in_files = org.gajim.Gajim.appdata.xml.in
appstream_DATA = $(appstream_in_files:.xml.in=.xml)
@INTLTOOL_XML_RULE@

desktopdir = $(datadir)/applications
desktop_in_files = org.gajim.Gajim.desktop.in.in gajim-remote.desktop.in.in
desktop_DATA = $(desktop_in_files:.desktop.in.in=.desktop)

installdefsdir = $(gajim_srcdir)/common
installdefs_DATA = defs.py


man_MANS = gajim.1 gajim-remote.1 gajim-history-manager.1


EXTRA_DIST = $(appstream_in_files) \
			 $(desktop_in_files) \
			 $(man_MANS) \
			 defs.py.in


DISTCLEANFILES = $(desktop_DATA) \
				 $(installdefs_DATA)

CLEANFILES = $(appstream_DATA) \
			 org.gajim.Gajim.desktop \
			 gajim-remote.desktop

MAINTAINERCLEANFILES = Makefile.in
