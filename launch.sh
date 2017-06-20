#!/bin/sh
if [ ! $PYTHON ]; then
       PYTHON="python3";
fi
cd "$(dirname $0)/gajim"
exec $PYTHON -OOt gajim.py "$@"
