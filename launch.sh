#!/bin/bash
cd `dirname $0`/src
exec -a gajim python -t gajim.py $@
