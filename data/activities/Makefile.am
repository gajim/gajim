activitiesdir = $(pkgdatadir)/data/activities

activities_DATA = 

ACTIVITIES_DIRS = **/**

ACTIVITIES_FILES = **/**/{*.png,*.gif}


install-data-local:
	@for d in $$(cd $(srcdir); echo $(ACTIVITIES_DIRS));do \
		if test -d $(srcdir)/$$d;then \
			echo " $(mkinstalldirs) $(DESTDIR)$(pkgdatadir)/data/activities/$$d"; \
			$(mkinstalldirs) $(DESTDIR)$(pkgdatadir)/data/activities/$$d || exit 1; \
		fi; \
	done; \
	for f in $$(cd $(srcdir); echo $(ACTIVITIES_FILES));do \
		if test -f $(srcdir)/$$f; then \
			echo " $(INSTALL_DATA) $(srcdir)/$$f $(DESTDIR)$(pkgdatadir)/data/activities/$$f"; \
			$(INSTALL_DATA) $(srcdir)/$$f $(DESTDIR)$(pkgdatadir)/data/activities/$$f || exit 1; \
		fi; \
	done; 

dist-hook:
	@for d in $$(cd $(srcdir); echo $(ACTIVITIES_DIRS));do \
		if test -d $(srcdir)/$$d;then \
			echo " $(mkdir_p) $(distdir)/$$d"; \
			$(mkdir_p) $(distdir)/$$d || exit 1; \
		fi; \
	done; \
	for f in $$(cd $(srcdir); echo $(ACTIVITIES_FILES));do \
		if test -f $(srcdir)/$$f; then \
			echo " cp -pR $(srcdir)/$$f $(distdir)/$$f"; \
			cp -pR $(srcdir)/$$f $(distdir)/$$f || exit 1; \
		fi; \
	done;

MAINTAINERCLEANFILES = Makefile.in
