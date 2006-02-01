# Set the C flags to include the GTK+ and Python libraries
PYTHONVER = `python -c 'import sys; print sys.version[:3]'`

HAVE_XSCRNSAVER = $(shell pkg-config --exists xscrnsaver && echo 'YES')

ifeq ($(HAVE_XSCRNSAVER),YES)
# We link with libXScrnsaver from modular X.Org X11
CFLAGS = `pkg-config --cflags gtk+-2.0 pygtk-2.0 xscrnsaver` -fpic -I/usr/include/python$(PYTHONVER) -I.
LDFLAGS = `pkg-config --libs gtk+-2.0 pygtk-2.0 xscrnsaver`
else
# # We link with libXScrnsaver from monolithic X.Org X11
CFLAGS = `pkg-config --cflags gtk+-2.0 pygtk-2.0` -fpic -I/usr/include/python$(PYTHONVER) -I.
LDFLAGS = `pkg-config --libs gtk+-2.0 pygtk-2.0` -L/usr/X11R6$(LIBDIR) -lX11 -lXss -lXext
endif

all: idle.so

idle.so:
	$(CC) $(OPTFLAGS) $(CFLAGS) $(LDFLAGS) -shared idle.c $^ -o $@

clean:
	rm -f *.so
	rm -rf build
