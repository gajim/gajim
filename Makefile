VERSION		= 0.51

MODULES		= common plugins/gtkgui
PREFIX		= /usr
DESTDIR		= /

FIND		= find -regex '.*\.\(\(glade\)\|\(py\)\|\(xpm\)\|\(gif\)\|\(png\)\|\(mo\)\|\(wav\)\)'
FILES		= `$(FIND)`
DIRS		= `$(FIND) -exec dirname {} \; | sort -u`
FIND_LIB	= find -regex '.*\.\(so\)'
FILES_LIB	= `$(FIND_LIB)`

SCRIPTS = \
	scripts/gajim

all:
	msgfmt Messages/fr/LC_MESSAGES/gajim.po -o Messages/fr/LC_MESSAGES/gajim.mo
	$(foreach sdir, $(MODULES), make -C $(sdir) all;)

clean:
	find -name *.pyc -exec rm {} \;
	$(foreach sdir, $(MODULES), make -C $(sdir) clean;)

# FIXME -- olé gorito
dist:
	-rm -rf gajim-$(VERSION)
	mkdir gajim-$(VERSION)
	cp -r plugins debian scripts common Core doc Messages sounds gajim-$(VERSION)/
	cp setup_win32.py gajim.iss AUTHORS gajim.1 gajim.xpm gajim.ico COPYING Makefile gajim.py gajim-$(VERSION)
	-find gajim-$(VERSION) -name '.svn' -exec rm -rf {} \; 2> /dev/null
	find gajim-$(VERSION) -name '*.pyc' -exec rm {} \;
	find gajim-$(VERSION) -name '*.pyo' -exec rm {} \;
	find gajim-$(VERSION) -name '.*' -exec rm {} \;
	@echo tarring gajim-$(VERSION) ...
	@tar cjf gajim-$(VERSION).tar.bz2 gajim-$(VERSION)/
	rm -rf gajim-$(VERSION)

install:
	for d in $(DIRS) ; do \
		if [ ! -d $(DESTDIR)$(PREFIX)/share/gajim/$$d ] ; then \
			mkdir -p "$(DESTDIR)$(PREFIX)/share/gajim/$$d"; \
		fi; \
	done
	for f in $(FILES) ; do \
		DST=`dirname "$$f"`; \
		cp "$$f" "$(DESTDIR)$(PREFIX)/share/gajim/$$DST/"; \
	done
	rm "$(DESTDIR)$(PREFIX)/share/gajim/setup_win32.py";
	mkdir -p "$(DESTDIR)$(PREFIX)/lib/gajim";
	for f in $(FILES_LIB) ; do \
		cp "$$f" "$(DESTDIR)$(PREFIX)/lib/gajim/"; \
	done
	for s in $(SCRIPTS) ; do \
		BASE=`basename "$$s"`; \
		F=`cat "$$s" | sed -e 's!PREFIX!$(PREFIX)!g'`; \
		echo "$$F" > "$(DESTDIR)$(PREFIX)/bin/$$BASE"; \
		chmod +x "$(DESTDIR)$(PREFIX)/bin/$$BASE"; \
	done
