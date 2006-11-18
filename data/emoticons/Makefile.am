emoticonsdir = $(pkgdatadir)/data/emoticons

emoticons_DATA = 

EMOTICONS_DIRS = **

EMOTICONS_FILES = **/{*.png,*.gif,emoticons.py}


install-data-local:
	@for d in $(EMOTICONS_DIRS);do \
		if test -d $$d;then \
			echo " $(mkinstalldirs) $(DESTDIR)$(pkgdatadir)/data/emoticons/$$d"; \
			$(mkinstalldirs) $(DESTDIR)$(pkgdatadir)/data/emoticons/$$d || exit 1; \
		fi; \
	done; \
	for f in $(EMOTICONS_FILES);do \
		if test -f $$f; then \
			echo " $(INSTALL_DATA) $$f $(DESTDIR)$(pkgdatadir)/data/emoticons/$$f"; \
			$(INSTALL_DATA) $$f $(DESTDIR)$(pkgdatadir)/data/emoticons/$$f || exit 1; \
		fi; \
	done; 

dist-hook:
	@for d in $(EMOTICONS_DIRS);do \
		if test -d $$d;then \
			echo " $(mkdir_p) $(distdir)/$$d"; \
			$(mkdir_p) $(distdir)/$$d || exit 1; \
		fi; \
	done; \
	for f in $(EMOTICONS_FILES);do \
		if test -f $$f; then \
			echo " cp -pR $(srcdir)/$$f $(distdir)/$$f"; \
			cp -pR $(srcdir)/$$f $(distdir)/$$f || exit 1; \
		fi; \
	done;

MAINTAINERCLEANFILES = Makefile.in
