LANGS   := fr pt el pl
LANGDIR := $(foreach lang, $(LANGS), $(subst ,/LC_MESSAGES/gajim.mo, $(lang)))

all: $(LANGDIR)

%.mo: %.po
	msgfmt $< -o $@

clean:
	find -name '*.mo' -exec rm {} \;
