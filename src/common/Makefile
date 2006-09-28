# Set the C flags to include the GTK+ and Python libraries
PYTHON ?= python
PYTHONVER = `$(PYTHON) -c 'import sys; print sys.version[:3]'`

HAVE_XSCRNSAVER = $(shell pkg-config --exists xscrnsaver && echo 'YES')

ifeq ($(HAVE_XSCRNSAVER),YES)
# We link with libXScrnsaver from modular X.Org X11
x_CFLAGS = `pkg-config --cflags xscrnsaver` -fpic -I/usr/include/python$(PYTHONVER) -I.
x_LDFLAGS = `pkg-config --libs xscrnsaver` -lpython$(PYTHONVER)
else
# # We link with libXScrnsaver from monolithic X.Org X11
x_CFLAGS = -fpic -I/usr/include/python$(PYTHONVER) -I.
x_LDFLAGS = -L/usr/X11R6$(LIBDIR) -lX11 -lXss -lXext -lpython$(PYTHONVER)
endif

all: idle.so

idle.so:
	$(CC) $(OPTFLAGS) $(CFLAGS) $(x_CFLAGS) -shared idle.c $^ -o $@ $(LDFLAGS) $(x_LDFLAGS)

clean:
	rm -f *.so
	rm -rf build
