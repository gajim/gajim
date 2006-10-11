#!/bin/sh
  echo "[encoding: UTF-8]" > po/POTFILES.in \
  && ls data/gajim.desktop.in.in data/glade/*.glade \
  src/*py src/common/*py src/common/zeroconf/*.py -1 -U >> \
  po/POTFILES.in || exit 1
  set -x
  intltoolize --force --automake \
  && aclocal -I ./m4 \
  && libtoolize --copy --force --automake \
  && autoheader \
  && autoconf  \
  && automake --add-missing --gnu --copy \
  && ./configure $@
