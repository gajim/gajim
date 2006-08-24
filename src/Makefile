# Set the C flags to include the GTK+ and Python libraries
PYTHON ?= python
PYTHONVER = `$(PYTHON) -c 'import sys; print sys.version[:3]'`
gtk_CFLAGS = `pkg-config --cflags gtk+-2.0 pygtk-2.0` -fPIC -I/usr/include/python$(PYTHONVER) -I.
gtk_LDFLAGS = `pkg-config --libs gtk+-2.0 pygtk-2.0` -lpython$(PYTHONVER)

all: trayicon.so gtkspell.so

# Build the shared objects
trayicon.so: trayicon.o eggtrayicon.o trayiconmodule.o
	$(CC) -shared $^ -o $@ $(LDFLAGS) $(gtk_LDFLAGS)

gtkspell.so:
	$(CC) $(OPTFLAGS) $(CFLAGS) $(LDFLAGS) $(gtk_CFLAGS) $(gtk_LDFLAGS) `pkg-config --libs --cflags gtkspell-2.0` -shared gtkspellmodule.c $^ -o $@

# The path to the GTK+ python types
DEFS=`pkg-config --variable=defsdir pygtk-2.0`

%.o: %.c
	$(CC) -o $@ -c $< $(CFLAGS) $(gtk_CFLAGS)

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
