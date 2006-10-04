SUBDIRS = glade emoticons pixmaps iconsets 

desktopdir = $(datadir)/applications
desktop_in_files = gajim.desktop.in.in 
desktop_DATA = $(desktop_in_files:.desktop.in.in=.desktop)

soundsdir = $(pkgdatadir)/data/sounds
sounds_DATA = sounds/*.wav

otherdir = $(pkgdatadir)/data/others
other_DATA = other/servers.xml

man_MANS = gajim.1 gajim-remote.1

@INTLTOOL_DESKTOP_RULE@

EXTRA_DIST = $(desktop_in_files) \
			 $(sounds_DATA) \
			 $(other_DATA) \
			 $(man_MANS)

DISTCLEANFILES = $(desktop_DATA)

