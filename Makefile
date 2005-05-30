VERSION		?= 0.7

MODULES		= src src/common po
PREFIX		= /usr
DESTDIR		= /

FIND		= find -regex '.*\.\(\(glade\)\|\(py\)\|\(xpm\)\|\(gif\)\|\(png\)\|\(mo\)\|\(wav\)\)'
FILES		= `$(FIND)`
DIRS		= `$(FIND) -exec dirname {} \; | sort -u`
FIND_LIB	= find -regex '.*\.\(so\)'
FILES_LIB	= `$(FIND_LIB)`

SCRIPTS = \
	scripts/gajim

all: translation trayicon gtkspell idle

translation:
	make -C po all

trayicon:
	make -C src trayicon.so;

gtkspell:
	make -C src gtkspell.so;

idle:
	make -C src/common all;

clean:
	find -name *.pyc -exec rm {} \;
	find -name *.pyo -exec rm {} \;
	find -name *.mo -exec rm {} \;
	$(foreach sdir, $(MODULES), make -C $(sdir) clean;)

dist:
	-rm -rf gajim-$(VERSION)
	mkdir gajim-$(VERSION)
	cp -r data src doc po scripts gajim-$(VERSION)/
	cp AUTHORS gajim.1 gajim.xpm gajim.ico gajim.desktop gajim.pot COPYING Makefile Changelog README launch.sh gajim-$(VERSION)
	-find gajim-$(VERSION) -name '.svn' -exec rm -rf {} \; 2> /dev/null
	find gajim-$(VERSION) -name '*.pyc' -exec rm {} \;
	find gajim-$(VERSION) -name '*.pyo' -exec rm {} \;
	find gajim-$(VERSION) -name '.*' -exec rm {} \;
	@echo tarring gajim-$(VERSION) ...
	@tar czf gajim-$(VERSION).tar.gz gajim-$(VERSION)/
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
	cp COPYING "$(DESTDIR)$(PREFIX)/share/gajim/";
	mkdir -p "$(DESTDIR)$(PREFIX)/share/applications";
	cp gajim.desktop "$(DESTDIR)$(PREFIX)/share/applications/";
	mkdir -p "$(DESTDIR)$(PREFIX)/share/man/man1";
	cp gajim.1 "$(DESTDIR)$(PREFIX)/share/man/man1";
	mkdir -p "$(DESTDIR)$(PREFIX)/lib/gajim";
	for f in $(FILES_LIB) ; do \
		cp "$$f" "$(DESTDIR)$(PREFIX)/lib/gajim/"; \
	done
	mkdir -p "$(DESTDIR)$(PREFIX)/bin";
	for s in $(SCRIPTS) ; do \
		BASE=`basename "$$s"`; \
		F=`cat "$$s" | sed -e 's!PREFIX!$(PREFIX)!g'`; \
		echo "$$F" > "$(DESTDIR)$(PREFIX)/bin/$$BASE"; \
		chmod +x "$(DESTDIR)$(PREFIX)/bin/$$BASE"; \
	done
