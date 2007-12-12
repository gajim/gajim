#!/bin/bash
BASE=`pwd`/`dirname $0`
OS=`uname -s`

if [ "x${OS}" == "xDarwin" ]; then
    export RESOURCEPATH="${BASE}/dist/Gajim.app/Contents/Resources"
    GTK_DIR="/Library/Frameworks/GTK+.framework/Versions/Current"
    export PATH="${GTK_DIR}/bin:$PATH"
    export PYTHONPATH="${GTK_DIR}/lib/python2.5/site-packages:${GTK_DIR}/lib/python2.5/site-packages/gtk-2.0:${PYTHONPATH}"
    unset GTK_DIR
fi

cd ${BASE}/src
exec -a gajim python -OOt gajim.py $@
