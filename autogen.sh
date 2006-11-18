#!/usr/bin/env bash
  echo "[encoding: UTF-8]" > po/POTFILES.in \
  && ls -1 -U data/gajim.desktop.in.in data/glade/*.glade \
  src/*py src/common/*py src/common/zeroconf/*.py >> \
  po/POTFILES.in || exit 1
  if test -z `which pkg-config 2>/dev/null`;then
    echo "***Error: pkg-config not found***"
	echo "See README.html for build requirements."
	exit 1
  fi
  set -x
  intltoolize --force --automake \
  && aclocal -I ./m4 \
  && libtoolize --copy --force --automake \
  && autoheader \
  && autoconf  \
  && automake --add-missing --gnu --copy \
  && ./configure $@
