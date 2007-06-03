emoticonsdir = $(pkgdatadir)/data/emoticons

emoticons_DATA = 

EMOTICONS_DIRS = **

EMOTICONS_FILES = **/{*.png,*.gif,emoticons.py}


install-data-local:
	@for d in $$(cd $(srcdir); echo $(EMOTICONS_DIRS));do \
		if test -d $(srcdir)/$$d;then \
			echo " $(mkinstalldirs) $(DESTDIR)$(pkgdatadir)/data/emoticons/$$d"; \
			$(mkinstalldirs) $(DESTDIR)$(pkgdatadir)/data/emoticons/$$d || exit 1; \
		fi; \
	done; \
	for f in $$(cd $(srcdir); echo $(EMOTICONS_FILES));do \
		if test -f $(srcdir)/$$f; then \
			echo " $(INSTALL_DATA) $(srcdir)/$$f $(DESTDIR)$(pkgdatadir)/data/emoticons/$$f"; \
			$(INSTALL_DATA) $(srcdir)/$$f $(DESTDIR)$(pkgdatadir)/data/emoticons/$$f || exit 1; \
		fi; \
	done; 

dist-hook:
	@for d in $$(cd $(srcdir); echo $(EMOTICONS_DIRS));do \
		if test -d $(srcdir)/$$d;then \
			echo " $(mkdir_p) $(distdir)/$$d"; \
			$(mkdir_p) $(distdir)/$$d || exit 1; \
		fi; \
	done; \
	for f in $$(cd $(srcdir); echo $(EMOTICONS_FILES));do \
		if test -f $(srcdir)/$$f; then \
			echo " cp -pR $(srcdir)/$$f $(distdir)/$$f"; \
			cp -pR $(srcdir)/$$f $(distdir)/$$f || exit 1; \
		fi; \
	done;

MAINTAINERCLEANFILES = Makefile.in
