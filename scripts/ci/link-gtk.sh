#!/bin/bash

cd gajim
mv gui gui_temp
cp -r gtk gui
mv -f gui_temp/__init__.py gui/__init__.py 
rm -r gui_temp
