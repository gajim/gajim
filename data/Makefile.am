SUBDIRS = glade emoticons pixmaps iconsets moods activities
@INTLTOOL_DESKTOP_RULE@

desktopdir = $(datadir)/applications
desktop_in_files = gajim.desktop.in.in 
desktop_DATA = $(desktop_in_files:.desktop.in.in=.desktop)

installdefsdir = $(pkgdatadir)/src/common
installdefs_DATA = defs.py

soundsdir = $(pkgdatadir)/data/sounds
sounds_DATA = $(srcdir)/sounds/*.wav

otherdir = $(pkgdatadir)/data/other
other_DATA = other/servers.xml other/cacerts.pem

if BUILD_REMOTE_CONTROL
OPTIONAL_MAN = gajim-remote.1
else
OPTIONAL_MAN =
endif

man_MANS = gajim.1 $(OPTIONAL_MAN)


EXTRA_DIST = $(desktop_in_files) \
			 $(sounds_DATA) \
			 $(other_DATA) \
			 $(man_MANS) \
			 defs.py.in


DISTCLEANFILES = $(desktop_DATA) \
				 $(installdefs_DATA)

CLEANFILES = gajim.desktop 

MAINTAINERCLEANFILES = Makefile.in
