## setup_osx.py
##
## Copyright (C) 2007 James Newton <redshodan AT gmail.com>
## Copyright (C) 2007-2008 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

"""
Usage:
    python setup_osx.py [build | dist]
"""

from setuptools import setup
import sys, glob, os, commands, types
from os import system, unlink, symlink, getcwd, mkdir, utime
from shutil import move, copy, copytree, rmtree

###
### Globals
###

GTK_DIR="/Library/Frameworks/GTK+.framework/Versions/Current"
NAME = 'Gajim'
VERSION = '0.12.1'
DESCRIPTION = 'A full featured Jabber client'
AUTHOR = 'Gajim Development Team'
URL = 'http://www.gajim.org/'
DOWNLOAD_URL = 'http://www.gajim.org/downloads.php'
LICENSE = 'GPL'
PWD = getcwd()
APP_RS = "dist/Gajim.app/Contents/Resources"

GAJIM_SCRIPT = \
'#!/bin/bash \n\
export DYLD_LIBRARY_PATH=%s/lib \n\
export PATH=%s/bin:$PATH \n\
export PYTHONPATH=%s/lib/python2.5/site-packages:%s/lib/python2.5/site-packages/gtk-2.0 \n\
exec ${0}.bin \n\
' % (GTK_DIR, GTK_DIR, GTK_DIR, GTK_DIR)

GAJIM_REMOTE_SCRIPT = \
'#!/bin/bash \n\
export DYLD_LIBRARY_PATH=%s/lib \n\
TOPDIR=${0%%/MacOS/gajim-remote} \n\
echo "${TOPDIR}" | grep -e "^/" \n\
[ $? -ne 0 ] && TOPDIR=`pwd`/${TOPDIR} \n\
export RESOURCEPATH=${TOPDIR}/Resources \n\
export PYTHONHOME=${RESOURCEPATH}/lib/python2.5 \n\
export PYTHONPATH=${RESOURCEPATH}/lib/python2.5/lib-dynload:${RESOURCEPATH}/lib/python2.5/site-packages.zip:${PYTHONPATH} \n\
cd ${RESOURCEPATH} \n\
exec ${TOPDIR}/MacOS/Python ${RESOURCEPATH}/gajim-remote.py $* \n\
' % GTK_DIR

###
### Functions
###

def check(ret):
	if isinstance(ret, list):
		if ret[0] != 0:
			raise Exception("Command failed: " + ret[1])
	elif isinstance(ret, int):
		if ret != 0:
			raise Exception("Command failed")
	return


def force(func):
	try:
		func()
	except Exception:
		pass
	return


def writeScript(filename, contents):
	script = open(filename, "w+")
	script.write(contents)
	script.close()
	system("chmod +x %s" % filename)
	return


def cleanup():
	force(lambda:rmtree("build"))
	force(lambda:rmtree("dist"))

def stageInstall():
	check(system("make DATADIR=%s/build/inst LIBDIR=%s/build/inst prefix=%s/build/inst DOCDIR=%s/build/inst/share/doc install" % (PWD, PWD, PWD, PWD)))
	force(lambda:unlink("src/osx/growl/_growl.so"))
	force(lambda:unlink("src/osx/growl/_growlImage.so"))
	force(lambda:unlink("src/osx/idle.so"))
	force(lambda:unlink("src/osx/nsapp.so"))
	force(lambda:unlink("src/osx/syncmenu.so"))
	force(lambda:unlink("src/gtkspell.so"))
	symlink("%s/build/inst/lib/gajim/_growl.so" % PWD, "src/osx/growl/_growl.so")
	symlink("%s/build/inst/lib/gajim/_growlImage.so" % PWD,
		 "src/osx/growl/_growlImage.so")
	symlink("%s/build/inst/lib/gajim/idle.so" % PWD, "src/osx/idle.so")
	symlink("%s/build/inst/lib/gajim/nsapp.so" % PWD, "src/osx/nsapp.so")
	symlink("%s/build/inst/lib/gajim/syncmenu.so" % PWD, "src/osx/syncmenu.so")
	if os.path.isfile("build/inst/lib/gajim/gtkspell.so"):
		symlink("%s/build/inst/lib/gajim/gtkspell.so" % PWD, "src/gtkspell.so")
	return


def buildApp():
	sys.path.append('src')
	sys.path.append(GTK_DIR + "/lib/python2.5/site-packages")
	sys.path.append(GTK_DIR + "/lib/python2.5/site-packages/gtk-2.0")
	OPTIONS = {'argv_emulation':True,
			   'excludes':'docutils,Crypto,dbus,OpenSSL,cairo,gtk,gobject,atk,pangocairo',
			   'iconfile':'data/pixmaps/gajim.icns',
			   'includes':'osx,ConfigParser,compiler,UserString,history_manager',
			   'plist':{'LSMinimumSystemVersion':'10.4.0',
						'NSHumanReadableCopyright':'GNU General Public License',
						'CFBundleIdentifier':'org.gajim',
						'NSMainNibFile':'Gajim',
						},
			   }
	setup(
		name = NAME, version = VERSION, description = DESCRIPTION,
		author = AUTHOR, url = URL, download_url = DOWNLOAD_URL,
		license = LICENSE,
		app=['src/gajim.py'],
		data_files=['data/nibs/Gajim.nib'],
		options={'py2app': OPTIONS},
		setup_requires=['py2app'],
		)
	return


def setupPrep():
	copy("src/osx/prep_py2app.py", APP_RS)
	move("dist/Gajim.app/Contents/Resources/__boot__.py",
		 "dist/Gajim.app/Contents/Resources/__boot__.py.org")
	new = open("dist/Gajim.app/Contents/Resources/__boot__.py", "w+")
	org = open("dist/Gajim.app/Contents/Resources/__boot__.py.org")
	for line in org:
		new.write(line)
		if (('site.addsitedir' in line) and ('Python' in line)):
			new.write("    import prep_py2app\n")
	new.close()
	org.close()
	unlink("dist/Gajim.app/Contents/Resources/__boot__.py.org")
	return


def finishApp():
	# setup gajim dirs
	copytree("build/inst/share/gajim/data", APP_RS + "/data")
	copy("data/pixmaps/gajim.icns", APP_RS + "/data/pixmaps")
	copytree("build/inst/share/locale", APP_RS + "/locale")
	copytree("build/inst/share/man", APP_RS + "/man")
	force(lambda:unlink("dist/Gajim.app/Contents/data"))
	symlink("Resources/data", "dist/Gajim.app/Contents/data")
	copy("src/gajim-remote.py", "dist/Gajim.app/Contents/Resources")
	# Nuke libs that are in the framework
	move("dist/Gajim.app/Contents/Frameworks/Python.framework",
		 "dist/Gajim.app/Contents/Python.framework")
	rmtree("dist/Gajim.app/Contents/Frameworks")
	mkdir("dist/Gajim.app/Contents/Frameworks")
	move("dist/Gajim.app/Contents/Python.framework",
		 "dist/Gajim.app/Contents/Frameworks/Python.framework")
	# Adjust the running of the app
	move("dist/Gajim.app/Contents/MacOS/Gajim",
		 "dist/Gajim.app/Contents/MacOS/Gajim.bin")
	writeScript("dist/Gajim.app/Contents/MacOS/Gajim", GAJIM_SCRIPT)
	setupPrep()
	# Setup the gajim-remote script
	writeScript("dist/Gajim.app/Contents/MacOS/gajim-remote",
				GAJIM_REMOTE_SCRIPT)
	# Touch the top dir so Finder knows to update its idea of this bundle
	utime("dist/Gajim.app", None)
	return


def distApp():
	force(lambda:rmtree("dist/Gajim"))
	force(lambda:rmtree("dist/Gajim.tar.bz2"))
	mkdir("dist/Gajim")
	check(system("tar -cf - -C dist Gajim.app | tar -xf - -C dist/Gajim"))
	copy("README.osx", "dist/Gajim/README")
	copy("TODO.osx", "dist/Gajim/TODO")
	check(system("tar -C dist -jcf dist/Gajim-OSX-`date | awk '{printf(\"%s-%s-%s\", $6, $2, $3);}'`.tar.bz2 Gajim"))
	rmtree("dist/Gajim")
	return



###
### Start
###
if ((len(sys.argv) != 2) or ((sys.argv[1] != "build") and
	(sys.argv[1] != "dist"))):
	print "usage: python setup_osx.py [build]"
	print "   or: python setup_osx.py [dist]"
	sys.exit(1)
elif sys.argv[1] == "build":
	sys.argv[1] = "py2app"
	sys.argv.append('--use-pythonpath')
	cleanup()
	stageInstall()
	buildApp()
	finishApp()
elif sys.argv[1] == "dist":
	distApp()

# vim: se ts=3:
