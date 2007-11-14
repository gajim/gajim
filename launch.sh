#!/bin/bash
BASE=`pwd`/`dirname $0`
OS=`uname -s`

if [ "x${OS}" == "xDarwin" ]; then
    export RESOURCEPATH="${BASE}/dist/Gajim.app/Contents/Resources"
fi

cd ${BASE}/src
exec -a gajim python -OOt gajim.py $@
