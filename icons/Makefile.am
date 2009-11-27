iconsdir = $(pkgdatadir)/icons

icons_DATA = 

ICONS_DIRS = **/**/**

ICONS_FILES = **/**/**/{*.png,*.svg}


install-data-local:
	@for d in $$(cd $(srcdir); echo $(ICONS_DIRS));do \
		if test -d $(srcdir)/$$d;then \
			echo " $(mkinstalldirs) $(DESTDIR)$(pkgdatadir)/icons/$$d"; \
			$(mkinstalldirs) $(DESTDIR)$(pkgdatadir)/icons/$$d || exit 1; \
		fi; \
	done; \
	for f in $$(cd $(srcdir); echo $(ICONS_FILES));do \
		if test -f $(srcdir)/$$f; then \
			echo " $(INSTALL_DATA) $(srcdir)/$$f $(DESTDIR)$(pkgdatadir)/icons/$$f"; \
			$(INSTALL_DATA) $(srcdir)/$$f $(DESTDIR)$(pkgdatadir)/icons/$$f || exit 1; \
		fi; \
	done; 

dist-hook:
	@for d in $$(cd $(srcdir); echo $(ICONS_DIRS));do \
		if test -d $(srcdir)/$$d;then \
			echo " $(mkdir_p) $(distdir)/$$d"; \
			$(mkdir_p) $(distdir)/$$d || exit 1; \
		fi; \
	done; \
	for f in $$(cd $(srcdir); echo $(ICONS_FILES));do \
		if test -f $(srcdir)/$$f; then \
			echo " cp -pR $(srcdir)/$$f $(distdir)/$$f"; \
			cp -pR $(srcdir)/$$f $(distdir)/$$f || exit 1; \
		fi; \
	done;

MAINTAINERCLEANFILES = Makefile.in
