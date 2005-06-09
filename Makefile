VERSION		?= 0.7.1

GAJIM_AP	= 0
MODULES		= src src/common po
PREFIX		= /usr
DESTDIR		= /

FIND		= find . \( -name '*.glade' -o -name '*.py' -o -name '*.xpm' -o -name '*.gif' -o -name '*.png' -o -name '*.mo' -o -name '*.wav' \)

FILES		= `$(FIND)`
DIRS		= `$(FIND) -exec dirname {} \; | sort -u`
FIND_LIB	= find . -name '*.so'
FILES_LIB	= `$(FIND_LIB)`

SCRIPTS = \
	scripts/gajim

all: translation trayicon gtkspell idle

translation:
	${MAKE} -C po all

trayicon:
	${MAKE} -C src trayicon.so;

gtkspell:
	${MAKE} -C src gtkspell.so;

idle:
	${MAKE} -C src/common all;

clean:
	find . -name *.pyc -exec rm {} \;
	find . -name *.pyo -exec rm {} \;
	find . -name *.mo -exec rm {} \;
	$(foreach sdir, $(MODULES), ${MAKE} -C $(sdir) clean;)

dist:
	rm -rf gajim-$(VERSION)
	mkdir gajim-$(VERSION)
	cp -r data src doc po gajim-$(VERSION)/
	cp AUTHORS gajim.1 gajim.ico gajim.desktop gajim.pot COPYING Makefile Changelog README launch.sh gajim-$(VERSION)
	mkdir gajim-$(VERSION)/scripts
	cp scripts/gajim gajim-$(VERSION)/scripts/
	find gajim-$(VERSION) -name '.svn' -type d | xargs rm -rf
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
	cp COPYING "$(DESTDIR)$(PREFIX)/share/gajim/";
	mkdir -p "$(DESTDIR)$(PREFIX)/share/pixmaps";
	cp data/pixmaps/gajim.png "$(DESTDIR)$(PREFIX)/share/pixmaps/";
	cp data/pixmaps/gajim_about.png "$(DESTDIR)$(PREFIX)/share/pixmaps/";
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
		if [ $(GAJIM_AP) -ne 0 ] ; then \
			F=`cat "$$s"`; \
		else \
			F=`cat "$$s" | sed -e 's!PREFIX!$(PREFIX)!g'`; \
		fi; \
		echo "$$F" > "$(DESTDIR)$(PREFIX)/bin/$$BASE"; \
		chmod +x "$(DESTDIR)$(PREFIX)/bin/$$BASE"; \
	done
