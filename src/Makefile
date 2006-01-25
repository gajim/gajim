# Set the C flags to include the GTK+ and Python libraries
PYTHONVER = `python -c 'import sys; print sys.version[:3]'`
HAVE_XSCRNSAVER = $(shell pkg-config --exists xscrnsaver && echo 'YES')

ifeq ($(HAVE_XSCRNSAVER),YES)
# We link with libXScrnsaver from modular X.Org X11
CFLAGS = `pkg-config --cflags gtk+-2.0 pygtk-2.0 xscrnsaver` -fpic -I/usr/include/python$(PYTHONVER) -I.
LDFLAGS = `pkg-config --libs gtk+-2.0 pygtk-2.0 xscrnsaver`
else
# We link with libXScrnsaver from monolithic X.Org X11
CFLAGS = `pkg-config --cflags gtk+-2.0 pygtk-2.0` -fpic -I/usr/include/python$(PYTHONVER) -I.
LDFLAGS = `pkg-config --libs gtk+-2.0 pygtk-2.0` -L/usr/X11R6$(LIBDIR) -lX11 -lXss -lXext
endif

all: trayicon.so gtkspell.so

# Build the shared objects
trayicon.so: trayicon.o eggtrayicon.o trayiconmodule.o
	$(CC) $(LDFLAGS) -shared $^ -o $@

gtkspell.so:
	$(CC) $(OPTFLAGS) $(CFLAGS) $(LDFLAGS) `pkg-config --libs --cflags gtkspell-2.0` -shared gtkspellmodule.c $^ -o $@

# The path to the GTK+ python types
DEFS=`pkg-config --variable=defsdir pygtk-2.0`

# Generate the C wrapper from the defs and our override file
trayicon.c: trayicon.defs trayicon.override
	pygtk-codegen-2.0 --prefix trayicon \
	--register $(DEFS)/gdk-types.defs \
	--register $(DEFS)/gtk-types.defs \
	--override trayicon.override \
	trayicon.defs > $@


# A rule to clean the generated files
clean:
	rm -f trayicon.so *.o trayicon.c gtkspell.so *~  

.PHONY: clean
