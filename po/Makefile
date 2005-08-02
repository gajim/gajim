top_srcdir = ../src/
NAME = gajim
LANGS   := fr pt el pl es ru bg de
LANGDIR := $(foreach lang, $(LANGS), $(subst ,/LC_MESSAGES/gajim.mo, $(lang)))

all: $(LANGDIR)

%.mo: %.po
	msgfmt $< -o $@

gajim.pot: ../src/*py ../src/common/*py
	 intltool-update --pot --gettext-package=$(NAME)

clean:
	find . -name '*.mo' -exec rm {} \;
