#!/bin/sh
  intltoolize --force --automake \
  && aclocal -I ./m4 \
  && libtoolize --copy --force --automake \
  && autoheader \
  && automake --add-missing --gnu --copy \
  && autoconf \
  && ./configure $@
