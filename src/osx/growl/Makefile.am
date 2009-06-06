OBJC = gcc

export MACOSX_DEPLOYMENT_TARGET=10.4
INCLUDES = \
	$(PYTHON_INCLUDES) 

if BUILD_CARBON
_growllib_LTLIBRARIES = _growl.la
_growllibdir = $(pkglibdir)

_growl_la_LIBADD = $(CARBON_LIBS) 

_growl_la_SOURCES = _growl.c

_growl_la_LDFLAGS = \
	-module -avoid-version -Xcompiler -isysroot -Xcompiler /Developer/SDKs/MacOSX10.4u.sdk -Xcompiler -arch -Xcompiler ppc -Xcompiler -arch -Xcompiler i386

_growl_la_CFLAGS = -Xcompiler -isysroot -Xcompiler /Developer/SDKs/MacOSX10.4u.sdk -Xcompiler -arch -Xcompiler ppc -Xcompiler -arch -Xcompiler i386 $(PYTHON_INCLUDES)
endif

if BUILD_COCOA
_growlImagelib_LTLIBRARIES = _growlImage.la
_growlImagelibdir = $(pkglibdir)

_growlImage_la_LIBADD = $(COCOA_LIBS) 

_growlImage_la_SOURCES = _growlImage.m

_growlImage_la_LDFLAGS = \
	-module -avoid-version -Xcompiler -isysroot -Xcompiler /Developer/SDKs/MacOSX10.4u.sdk -Xcompiler -arch -Xcompiler ppc -Xcompiler -arch -Xcompiler i386

_growlImage_la_CFLAGS = -Xcompiler -isysroot -Xcompiler /Developer/SDKs/MacOSX10.4u.sdk -Xcompiler -arch -Xcompiler ppc -Xcompiler -arch -Xcompiler i386 $(PYTHON_INCLUDES)

AM_OBJCFLAGS = $(_growlImage_la_CFLAGS)
endif

DISTCLEANFILES = 

EXTRA_DIST = 

MAINTAINERCLEANFILES = Makefile.in
