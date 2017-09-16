SUBDIRS = gui emoticons iconsets moods activities
@INTLTOOL_DESKTOP_RULE@

soundsdir = $(gajim_srcdir)/data/sounds
sounds_DATA = $(srcdir)/sounds/*.wav

styledir = $(gajim_srcdir)/data/style
style_DATA = $(srcdir)/style/*.css

otherdir = $(gajim_srcdir)/data/other
other_DATA = other/servers.xml other/dh4096.pem
# other/cacert.pem is used only on Windows. On Unix platforms
# use CA certificates installed in /etc/ssl/certs

EXTRA_DIST = $(sounds_DATA) \
			 $(style_DATA) \
			 $(other_DATA)

MAINTAINERCLEANFILES = Makefile.in
