CFLAGS=-g `pkg-config --cflags farsight-0.1 pygtk-2.0` -I /usr/include/python2.5 -I. -I farsight/
LDFLAGS=`pkg-config --libs farsight-0.1`

farsight.so: farsight.o farsightmodule.o
	$(CC) $(LDFLAGS) -shared $^ -o $@

farsight.c: farsight.defs farsight.override
	pygtk-codegen-2.0 \
		--prefix farsight \
		--override farsight.override \
		--register /usr/share/gst-python/0.10/defs/gst-types.defs \
		farsight.defs >$@

farsight.defs:
	python /usr/share/pygtk/2.0/codegen/h2def.py \
		farsight/farsight-codec.h \
		farsight/farsight-session.h \
		farsight/farsight-stream.h \
		>$@

clean:
	-rm farsight.c farsightmodule.o  farsight.o farsight.so

.PHONY: clean
