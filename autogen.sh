#!/usr/bin/env bash
  gajimversion="0.16-alpha2"
  if [ -d ".hg" ]; then
    node=$(hg  tip --template "{node}")
    hgversion="-${node:0:12}"
  else
    hgversion=""
  fi
  echo "define([AC_PACKAGE_VERSION], [${gajimversion}${hgversion}])" > m4/hgversion.m4

  AM_ARGS="--add-missing --gnu --copy -Wno-portability"
  CONF_ARGS=""

  echo "[encoding: UTF-8]" > po/POTFILES.in \
  && for p in `ls data/gui/*.ui`; do echo "[type: gettext/glade]$p" >> \
  po/POTFILES.in; done \
  && ls -1 data/gajim.desktop.in.in \
  src/*.py src/common/*.py src/command_system/*.py src/command_system/implementation/*.py src/common/zeroconf/*.py src/plugins/*.py | grep -v ipython_view.py >> \
  po/POTFILES.in \
  && echo -e "data/gajim.desktop.in\nsrc/ipython_view.py" > po/POTFILES.skip  || exit 1
  if [ $(find plugins/ -name '*.py' | wc -l) -gt 0 ];then
    ls -1 plugins/*/*.py plugins/*/*.ui >> po/POTFILES.skip
  fi
  if test -z `which pkg-config 2>/dev/null`;then
    echo "***Error: pkg-config not found***"
	echo "See README.html for build requirements."
	exit 1
  fi

  which glibtoolize >/dev/null 2>&1 && LIBTOOLIZE="glibtoolize" || LIBTOOLIZE="libtoolize"

  mkdir -p config

  intltoolize --force --automake \
  && aclocal -I ./m4 \
  && $LIBTOOLIZE --copy --force --automake \
  && autoheader \
  && autoconf \
  && automake ${AM_ARGS} \
  && ./configure ${CONF_ARGS} $@
