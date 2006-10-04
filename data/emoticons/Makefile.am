emoticonsdir = $(pkgdatadir)/data/emoticons

emoticons_DATA = 

EMOTICONS_DIRS = **

EMOTICONS_FILES = **/{*.png,*.gif,emoticons.py}

# copy files recursively
install-data-local:
	@for d in $(EMOTICONS_DIRS);do \
		if test -d $$d;then \
			echo " $(mkinstalldirs) $(pkgdatadir)/data/emoticons/$$d"; \
			$(mkinstalldirs) $(pkgdatadir)/data/emoticons/$$d || exit 1; \
		fi; \
	done; \
	for f in $(EMOTICONS_FILES);do \
		if test -f $$f; then \
			echo " $(INSTALL_DATA) $$f $(pkgdatadir)/data/emoticons/$$f"; \
			$(INSTALL_DATA) $$f $(pkgdatadir)/data/emoticons/$$f || exit 1; \
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
