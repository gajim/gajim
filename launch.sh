#!/bin/sh
cd "$(dirname $0)/src"
exec python -m cProfile gajim.py "$@"
