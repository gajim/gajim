# Set the C flags to include the GTK+ and Python libraries
PYTHONVER = `python -c 'import sys; print sys.version[:3]'`
CFLAGS = `pkg-config --cflags gtk+-2.0 pygtk-2.0` -fpic -I/usr/include/python$(PYTHONVER) -I.
LDFLAGS = `pkg-config --libs gtk+-2.0 pygtk-2.0`

all: idle.so

idle.so:
	$(CC) $(CFLAGS) $(LDFLAGS) -shared idle.c $^ -o $@ -L/usr/X11R6/lib -lX11 -lXss -lXext

clean:
	rm -f *.so
	rm -rf build
