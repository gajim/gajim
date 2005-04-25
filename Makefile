VERSION		?= 0.6.1

MODULES		= src src/common po
PREFIX		= /usr
DESTDIR		= /

FIND		= find -regex '.*\.\(\(glade\)\|\(pyo\)\|\(xpm\)\|\(gif\)\|\(png\)\|\(mo\)\|\(wav\)\)'
FILES		= `$(FIND)`
DIRS		= `$(FIND) -exec dirname {} \; | sort -u`
FIND_LIB	= find -regex '.*\.\(so\)'
FILES_LIB	= `$(FIND_LIB)`
FIND_PY		= find -regex '.*\.\(py\)'
FILES_PY	= `$(FIND_PY)`

LANGS		= fr pt_BR
SCRIPTS = \
	scripts/gajim

all: translation trayicon idle pyo

translation:
	make -C po all

trayicon:
	make -C src all;

idle:
	make -C src/common all;

pyo:
	ST="import py_compile\n py_compile.compile('$$f')"
	for f in $(FILES_PY) ; do \
		python -OO -c "$$ST"; \
	done

clean:
	find -name *.pyc -exec rm {} \;
	find -name *.mo -exec rm {} \;
	$(foreach sdir, $(MODULES), make -C $(sdir) clean;)

dist:
	-rm -rf gajim-$(VERSION)
	mkdir gajim-$(VERSION)
	cp -r data src doc po gajim-$(VERSION)/
	cp AUTHORS gajim.1 gajim.xpm gajim.ico COPYING Makefile Changelog README gajim.py gajim-$(VERSION)
	-find gajim-$(VERSION) -name '.svn' -exec rm -rf {} \; 2> /dev/null
	find gajim-$(VERSION) -name '*.pyc' -exec rm {} \;
	find gajim-$(VERSION) -name '*.pyo' -exec rm {} \;
	find gajim-$(VERSION) -name '.*' -exec rm {} \;
	@echo tarring gajim-$(VERSION) ...
	@tar czf gajim-$(VERSION).tar.gz gajim-$(VERSION)/
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
