MODULES = common plugins/gtkgui

all:
	msgfmt Messages/fr/LC_MESSAGES/gajim.po -o Messages/fr/LC_MESSAGES/gajim.mo
	for dir in ${MODULES}; do \
	  (cd $$dir; make all); \
	done

clean:
	find -name *.pyc -exec rm {} \;
	for dir in ${MODULES}; do \
	  (cd $$dir; make clean); \
	done
