MODULES = common plugins/gtkgui
PREFIX = /usr
DESTDIR = /

FIND= find -regex '.*\.\(\(glade\)\|\(py\)\|\(xpm\)\|\(so\)\|\(mo\)\)'
FILES=`$(FIND)`
DIRS= `$(FIND) -exec dirname {} \; | sort -u`

SCRIPTS = \
	scripts/gajim

all:
	msgfmt Messages/fr/LC_MESSAGES/gajim.po -o Messages/fr/LC_MESSAGES/gajim.mo
	$(foreach sdir, $(MODULES), make -C $(sdir) all;)

clean:
	find -name *.pyc -exec rm {} \;
	$(foreach sdir, $(MODULES), make -C $(sdir) clean;)

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
	for s in $(SCRIPTS) ; do \
		BASE=`basename "$$s"`; \
		F=`cat "$$s" | sed -e 's!PREFIX!$(PREFIX)!g'`; \
		echo "$$F" > "$(DESTDIR)$(PREFIX)/bin/$$BASE"; \
		chmod +x "$(DESTDIR)$(PREFIX)/bin/$$BASE"; \
	done
