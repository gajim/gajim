VERSION		?= 0.9

GAJIM_AP	= 0 # do we build Autopackage?

MODULES		= src src/common po
PREFIX		= /usr/local
DESTDIR		= 
OPTFLAGS	= 
export OPTFLAGS
LIBDIR		= /lib
export LIBDIR
MANDIR		= $(DESTDIR)$(PREFIX)/share/man

FIND		= find . \( -name '*.glade' -o -name '*.py' -o -name '*.xpm' -o -name '*.gif' -o -name '*.png' -o -name '*.wav' \)

FILES		= `$(FIND)`
DIRS		= `$(FIND) -exec dirname {} \; | sort -u`
FIND_PO		= find ./po \( -name '*.mo' \)
FILES_PO	= `$(FIND_PO) | sed -e 's/^\.\/po/\./g'`
DIRS_PO		= `$(FIND_PO) -exec dirname {} \; | sort -u | sed -e 's/^\.\/po/\./g'`
FIND_LIB	= find . -name '*.so'
FILES_LIB	= `$(FIND_LIB)`

SCRIPTS = \
	scripts/gajim \
	scripts/gajim-remote

all: translation trayicon gtkspell idle gajim.desktop

translation:
	${MAKE} -C po all

trayicon:
	${MAKE} -C src trayicon.so;

gtkspell:
	${MAKE} -C src gtkspell.so;

idle:
	${MAKE} -C src/common all;

clean:
	find . -name '*.pyc' -exec rm {} \;
	find . -name '*.pyo' -exec rm {} \;
	find . -name '*.mo' -exec rm {} \;
	rm -f gajim.desktop \;
	$(foreach sdir, $(MODULES), ${MAKE} -C $(sdir) clean;)

dist:
	rm -rf gajim-$(VERSION)
	mkdir gajim-$(VERSION)
	cp -r data src po gajim-$(VERSION)/
	cp AUTHORS gajim.1 gajim-remote.1 gajim.desktop.in COPYING Makefile Changelog README launch.sh gajim-$(VERSION)
	mkdir gajim-$(VERSION)/scripts
	for s in $(SCRIPTS) ; do \
		cp $$s gajim-$(VERSION)/scripts/; \
	done
	find gajim-$(VERSION) -name '.svn' -type d | xargs rm -rf
	find gajim-$(VERSION) -name '*.pyc' -exec rm {} \;
	find gajim-$(VERSION) -name '*.pyo' -exec rm {} \;
	find gajim-$(VERSION) -name '.*' -exec rm {} \;
	@echo tarring gajim-$(VERSION) ...
	@tar czf gajim-$(VERSION).tar.gz gajim-$(VERSION)/
	@tar cjf gajim-$(VERSION).tar.bz2 gajim-$(VERSION)/
	rm -rf gajim-$(VERSION)

install:
	# Remove the old po folder if it exists
	if [ -d $(DESTDIR)$(PREFIX)/share/gajim/po ] ; then \
		rm -rf $(DESTDIR)$(PREFIX)/share/gajim/po; \
	fi
	for d in $(DIRS) ; do \
		if [ ! -d $(DESTDIR)$(PREFIX)/share/gajim/$$d ] ; then \
			mkdir -p "$(DESTDIR)$(PREFIX)/share/gajim/$$d"; \
		fi; \
	done
	for f in $(FILES) ; do \
		DST=`dirname "$$f"`; \
		cp "$$f" "$(DESTDIR)$(PREFIX)/share/gajim/$$DST/"; \
	done
	rm "$(DESTDIR)$(PREFIX)/share/gajim/src/systraywin32.py"
	for d in $(DIRS_PO) ; do \
		if [ ! -d $(DESTDIR)$(PREFIX)/share/locale/$$d ] ; then \
			mkdir -p "$(DESTDIR)$(PREFIX)/share/locale/$$d"; \
		fi; \
	done
	for f in $(FILES_PO) ; do \
		DST=`dirname "$$f"`; \
		cp "./po/$$f" "$(DESTDIR)$(PREFIX)/share/locale/$$DST/"; \
	done
	cp COPYING "$(DESTDIR)$(PREFIX)/share/gajim/";
	mkdir -p "$(DESTDIR)$(PREFIX)/share/pixmaps";
	cp data/pixmaps/gajim.png "$(DESTDIR)$(PREFIX)/share/pixmaps/";
	cp data/pixmaps/gajim_about.png "$(DESTDIR)$(PREFIX)/share/pixmaps/";
	mkdir -p "$(DESTDIR)$(PREFIX)/share/applications";
	cp gajim.desktop "$(DESTDIR)$(PREFIX)/share/applications/";
	mkdir -p "$(MANDIR)/man1";
	cp gajim.1 "$(MANDIR)/man1";
	cp gajim-remote.1 "$(MANDIR)/man1";
	mkdir -p "$(DESTDIR)$(PREFIX)$(LIBDIR)/gajim";
	for f in $(FILES_LIB) ; do \
		cp "$$f" "$(DESTDIR)$(PREFIX)$(LIBDIR)/gajim/"; \
	done
	mkdir -p "$(DESTDIR)$(PREFIX)/bin";
	for s in $(SCRIPTS) ; do \
		BASE=`basename "$$s"`; \
		if [ $(GAJIM_AP) -ne 0 ] ; then \
			F=`cat "$$s" | sed -e 's!LIB!$(LIBDIR)!g'`; \
		else \
			F=`cat "$$s" | sed -e 's!PREFIX!$(PREFIX)!g' -e 's!LIB!$(LIBDIR)!g'`; \
		fi; \
		echo "$$F" > "$(DESTDIR)$(PREFIX)/bin/$$BASE"; \
		chmod +x "$(DESTDIR)$(PREFIX)/bin/$$BASE"; \
	done

gajim.desktop: gajim.desktop.in
	intltool-merge -d po gajim.desktop.in gajim.desktop

#
# show make params we accept
#
help:
	@echo Usage:
	@echo make		- builds all modules
	@echo make clean	- delete built modules and object files
	@echo make install	- install binaries into the official directories
	@echo make uninstall	- uninstall binaries from the official directories
	@echo make help		- prints this help
	@echo
	@echo make trayicon	- makes only trayicon module
	@echo make idle		- makes only idle detection module
	@echo make translation	- makes only translation \(mo files\)
	@echo make gtkspell	- makes only gtkspell detection module
	@echo make tags		- makes 'tags' file for use with ctags
	@echo

#
# uninstall application from official directories
#
uninstall:
	rm -rf	"$(DESTDIR)$(PREFIX)/share/gajim" # the main files are here
	rm -rf	"$(DESTDIR)$(PREFIX)/lib/gajim" # the .so files are here
	rm -f	"$(DESTDIR)$(PREFIX)/bin/gajim" # the bash script
	rm -f	"$(DESTDIR)$(PREFIX)/bin/gajim-remote" # remote-control script
	rm -f	"$(MANDIR)/man1/gajim.1" # the man page
	rm -f	"$(MANDIR)/man1/gajim-remote.1" # the man page
	rm -f	"$(DESTDIR)$(PREFIX)/share/pixmaps/gajim.png" # the icon
	rm -f	"$(DESTDIR)$(PREFIX)/share/pixmaps/gajim_about.png" # the icon
	rm -f	"$(DESTDIR)$(PREFIX)/share/applications/gajim.desktop" #the desktop
	find "$(DESTDIR)$(PREFIX)/share/locale" -name 'gajim.mo' -exec rm {} \; #the .mo files
	@echo done uninstalling

tags:
	-rm tags
	exuberant-ctags -R

.PHONY: all translation trayicon gtkspell idle clean dist install help\
	uninstall tags
