#!/bin/sh

aclocal -I ./m4 --force
autoconf 
autoheader 
automake --add-missing 
