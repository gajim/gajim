# Set the C flags to include the GTK+ and Python libraries
PYTHONVER = `python -V 2>&1 | awk '{print $$2}' | cut -f1,2 -d.`
CFLAGS = `pkg-config --cflags gtk+-2.0 pygtk-2.0` -fpic -I/usr/include/python$(PYTHONVER) -I.
LDFLAGS = `pkg-config --libs gtk+-2.0 pygtk-2.0`

all: idle.so

idle.so:
	$(CC) $(CFLAGS) $(LDFLAGS) -shared idle.c $^ -o $@

clean:
	rm -f *.so
	rm -rf build
