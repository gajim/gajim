#!/bin/sh
if [ ! $PYTHON ]; then
       PYTHON="python3";
fi
cd "$(dirname $0)/src"
exec $PYTHON -OOt gajim.py "$@"
