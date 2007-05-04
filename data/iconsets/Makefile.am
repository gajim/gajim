iconsetdir = $(pkgdatadir)/data/iconsets

iconset_DATA = 

ICONSET_DIRS = **/{16x16,32x32,48x48} \
			   transports/**/{16x16,32x32,48x48}

ICONSET_FILES = **/{16x16,32x32,48x48}/{*.gif,*.png} \
			   transports/**/{16x16,32x32,48x48}/{*.gif,*.png}

install-data-local:
	@for d in $$(cd $(srcdir); echo $(ICONSET_DIRS));do \
		if test -d $(srcdir)/$$d;then \
			echo " $(mkinstalldirs) $(DESTDIR)$(pkgdatadir)/data/iconsets/$$d"; \
			$(mkinstalldirs) $(DESTDIR)$(pkgdatadir)/data/iconsets/$$d || exit 1; \
		fi; \
	done
	for f in $$(cd $(srcdir); echo $(ICONSET_FILES));do \
		if test -f $(srcdir)/$$f; then \
			echo " $(INSTALL_DATA) $(srcdir)/$$f $(DESTDIR)$(pkgdatadir)/data/iconsets/$$f"; \
			$(INSTALL_DATA) $(srcdir)/$$f $(DESTDIR)$(pkgdatadir)/data/iconsets/$$f || exit 1; \
		fi; \
	done; 

dist-hook:
	@for d in $$(cd $(srcdir); echo $(ICONSET_DIRS));do \
		if test -d $(srcdir)/$$d;then \
			echo " $(mkdir_p) $(distdir)/$$d"; \
			$(mkdir_p) $(distdir)/$$d || exit 1; \
		fi; \
	done
	for f in $$(cd $(srcdir); echo $(ICONSET_FILES));do \
		if test -f $(srcdir)/$$f; then \
			echo " cp -pR $(srcdir)/$$f $(distdir)/$$f"; \
			cp -pR $(srcdir)/$$f $(distdir)/$$f || exit 1; \
		fi; \
	done;

MAINTAINERCLEANFILES = Makefile.in
