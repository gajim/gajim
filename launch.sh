#!/bin/sh
cd "$(dirname $0)/src"
exec python -t gajim.py $@
