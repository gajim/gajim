#!/usr/bin/env bash
  AM_ARGS="--add-missing --gnu --copy -Wno-portability"
  CONF_ARGS=""

  echo "[encoding: UTF-8]" > po/POTFILES.in \
  && for p in `ls gajim/data/gui/*.ui`; do echo "[type: gettext/glade]$p" >> \
  po/POTFILES.in; done \
  && ls -1 data/org.gajim.Gajim.appdata.xml.in data/org.gajim.Gajim.desktop.in.in data/gajim-remote.desktop.in.in \
  gajim/*.py gajim/common/*.py gajim/command_system/*.py gajim/command_system/implementation/*.py gajim/common/zeroconf/*.py gajim/plugins/*.py | grep -v ipython_view.py >> \
  po/POTFILES.in \
  && echo -e "data/org.gajim.Gajim.desktop.in\ndata/gajim-remote.desktop.in\ngajim/ipython_view.py" > po/POTFILES.skip  || exit 1
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

  if [ "$NO_AUTOTOOLS_RUN" ]; then
    exit 0
  fi

  intltoolize --force --automake \
  && aclocal -I ./m4 \
  && $LIBTOOLIZE --copy --force --automake \
  && autoheader \
  && autoconf \
  && automake ${AM_ARGS} \
  && ./configure ${CONF_ARGS} $@
