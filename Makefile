all:
	python setup.py build_ext -i
	mv idle.so common/
	msgfmt Messages/fr/LC_MESSAGES/gajim.po -o Messages/fr/LC_MESSAGES/gajim.mo
