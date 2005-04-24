# Set the C flags to include the GTK+ and Python libraries
PYTHONVER = `python -V 2>&1 | awk '{print $$2}' | cut -f1,2 -d.`
CFLAGS = `pkg-config --cflags gtk+-2.0 pygtk-2.0` -fpic -I/usr/include/python$(PYTHONVER) -I.
LDFLAGS = `pkg-config --libs gtk+-2.0 pygtk-2.0`

# Build the shared object
trayicon.so: trayicon.o eggtrayicon.o trayiconmodule.o
	$(CC) $(LDFLAGS) -shared $^ -o $@


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
	rm -f trayicon.so *.o trayicon.c *~ 

.PHONY: clean
