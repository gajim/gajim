SUBDIRS = growl syncmenu

ACLOCAL_AMFLAGS = -I ../m4

OBJC = gcc

export MACOSX_DEPLOYMENT_TARGET=10.4
INCLUDES = \
	$(PYTHON_INCLUDES) 

if BUILD_IDLE_OSX
idlelib_LTLIBRARIES = idle.la
idlelibdir = $(pkglibdir)

idle_la_LIBADD = $(CARBON_LIBS) 

idle_la_SOURCES = idle.c

idle_la_LDFLAGS = \
	-module -avoid-version -Xcompiler -isysroot -Xcompiler /Developer/SDKs/MacOSX10.4u.sdk -Xcompiler -arch -Xcompiler ppc -Xcompiler -arch -Xcompiler i386

idle_la_CFLAGS = -Xcompiler -isysroot -Xcompiler /Developer/SDKs/MacOSX10.4u.sdk -Xcompiler -arch -Xcompiler ppc -Xcompiler -arch -Xcompiler i386 $(PYTHON_INCLUDES)
endif

if BUILD_COCOA
nsapplib_LTLIBRARIES = nsapp.la
nsapplibdir = $(pkglibdir)

nsapp_la_LIBADD = $(COCOA_LIBS) 

nsapp_la_SOURCES = nsapp.m

nsapp_la_LDFLAGS = \
	-module -avoid-version -Xcompiler -isysroot -Xcompiler /Developer/SDKs/MacOSX10.4u.sdk -Xcompiler -arch -Xcompiler ppc -Xcompiler -arch -Xcompiler i386

nsapp_la_CFLAGS = -Xcompiler -isysroot -Xcompiler /Developer/SDKs/MacOSX10.4u.sdk -Xcompiler -arch -Xcompiler ppc -Xcompiler -arch -Xcompiler i386 $(PYTHON_INCLUDES)

AM_OBJCFLAGS = $(nsapp_la_CFLAGS)
endif

DISTCLEANFILES = 

EXTRA_DIST = 

MAINTAINERCLEANFILES = Makefile.in
