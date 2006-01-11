top_srcdir = ../src/
NAME = gajim
LANGS   := fr pt el pl es ru bg de nb cs nl pt_BR sv it eu sk no zh_CN
LANGDIR := $(foreach LANG, $(LANGS),$(LANG)/LC_MESSAGES/gajim.mo)

all: $(LANGDIR)

%.mo: %.po
	msgfmt $< -o $@

gajim.pot: ../src/*py ../src/common/*py ../src/gtkgui.glade.h
	intltool-update --pot --gettext-package=$(NAME)

clean:
	find . -name '*.mo' -exec rm {} \;
