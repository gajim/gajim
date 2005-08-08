top_srcdir = ../src/
NAME = gajim
LANGS   := fr pt el pl es ru bg de
LANGDIR := $(foreach LANG, $(LANGS),$(LANG)/LC_MESSAGES/gajim.mo)

all: $(LANGDIR)

%.mo: %.po
	msgfmt $< -o $@

gajim.pot: ../src/*py ../src/common/*py ../src/gtkgui.glade.h
	intltool-update --pot --gettext-package=$(NAME)

clean:
	find . -name '*.mo' -exec rm {} \;
