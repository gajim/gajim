SUBDIRS = gui emoticons pixmaps iconsets moods activities
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

soundsdir = $(pkgdatadir)/data/sounds
sounds_DATA = $(srcdir)/sounds/*.wav

otherdir = $(pkgdatadir)/data/other
other_DATA = other/servers.xml other/dh4096.pem
# other/cacert.pem is used only on Windows. On Unix platforms
# use CA certificates installed in /etc/ssl/certs

man_MANS = gajim.1 gajim-remote.1 gajim-history-manager.1


EXTRA_DIST = $(appstream_in_files) \
			 $(desktop_in_files) \
			 $(sounds_DATA) \
			 $(other_DATA) \
			 $(man_MANS) \
			 defs.py.in


DISTCLEANFILES = $(desktop_DATA) \
				 $(installdefs_DATA)

CLEANFILES = $(appstream_DATA) \
			 org.gajim.Gajim.desktop \
			 gajim-remote.desktop

MAINTAINERCLEANFILES = Makefile.in
