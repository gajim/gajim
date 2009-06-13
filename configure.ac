AC_INIT([Gajim - A Jabber Instant Messager],
		[0.12.1.5-svn],[http://trac.gajim.org/],[gajim])
AC_PREREQ([2.59])

AC_CONFIG_HEADER(config.h)
AC_CONFIG_AUX_DIR(config)
AC_CONFIG_MACRO_DIR([m4])

AM_INIT_AUTOMAKE([1.8])
AM_MAINTAINER_MODE

dnl Make Objective-C work with automake
AM_CONDITIONAL([am__fastdepOBJC], false)

IT_PROG_INTLTOOL([0.35.0])
PKG_PROG_PKG_CONFIG([0.19])

AM_DISABLE_STATIC
AC_ENABLE_SHARED(yes)
AC_ENABLE_STATIC(no)

AC_ISC_POSIX
AC_PROG_CC
AC_PROG_INSTALL
AC_PROG_MAKE_SET
AC_PROG_LIBTOOL
AC_C_CONST
AC_CHECK_HEADERS([libintl.h])
AC_PATH_X


GETTEXT_PACKAGE=gajim
AC_SUBST([GETTEXT_PACKAGE])
AC_DEFINE_UNQUOTED([GETTEXT_PACKAGE],["$GETTEXT_PACKAGE"], [Gettext package])
AM_GLIB_GNU_GETTEXT
AM_NLS


dnl ****
dnl pygtk and gtk+
dnl ****
PKG_CHECK_MODULES([PYGTK], [gtk+-2.0 >= 2.8.0 pygtk-2.0 >= 2.8.0])
AC_SUBST(PYGTK_CFLAGS)
AC_SUBST(PYGTK_LIBS)
PYGTK_DEFS=`$PKG_CONFIG --variable=defsdir pygtk-2.0`
AC_SUBST(PYGTK_DEFS)

AM_PATH_PYTHON([2.5])
if test "x$PYTHON" = "x:"; then
	AC_MSG_ERROR([Python not found])
fi

dnl ****
dnl tray icon
dnl ****
AC_ARG_ENABLE(trayicon,
  [  --disable-trayicon      do not build trayicon module [default yes]],
  enable_trayicon=$enableval, enable_trayicon=yes)
test "x$enable_trayicon" = "xyes" && have_trayicon=true || have_trayicon=false
AM_CONDITIONAL(BUILD_TRAYICON, $have_trayicon)

dnl ****
dnl Cocoa
dnl ****
AC_ARG_ENABLE([cocoa],
  [  --disable-cocoa         do not build cocoa integration [default auto]],
  enable_cocoa=$enableval, enable_cocoa=yes)

if test "x$enable_cocoa" = "xyes";then 
  dnl There is no pkgconfig for cocoa; lets do a header check
  temp_save_cflags="$CFLAGS"
  CFLAGS="$CFLAGS -ObjC"
  AC_CHECK_HEADER(Cocoa/Cocoa.h, [have_cocoa=true], [have_cocoa=false])
  AC_CHECK_HEADER(AppKit/AppKit.h, [have_appkit=true], [have_appkit=false])
  CFLAGS="$temp_save_cflags"

  if test "x$have_cocoa" = "xtrue";then
     COCOA_LIBS="$COCOA_LIBS -Xlinker -framework -Xlinker Cocoa"
  fi
  if test "x$have_appkit" = "xtrue";then
     COCOA_LIBS="$COCOA_LIBS -Xlinker -framework -Xlinker AppKit"
  fi
  if test "x$COCOA_LIBS" != "x";then
	 AC_SUBST(COCOA_LIBS)
     true
  fi
fi
AM_CONDITIONAL(BUILD_COCOA, $have_cocoa)

dnl ****
dnl Carbon
dnl ****
AC_ARG_ENABLE([carbon],
  [  --disable-carbon        do not build with carbon [default auto]],
  enable_carbon=$enableval, enable_carbon=yes)

if test "x$enable_carbon" = "xyes";then 
  dnl There is no pkgconfig for carbon; lets do a header check
  AC_CHECK_HEADER(Carbon/Carbon.h, [have_carbon=true], [have_carbon=false])
  AC_CHECK_HEADER(IOKit/IOKitLib.h, [have_iokit=true], [have_iokit=false])

  if test "x$have_carbon" = "xtrue";then
     CARBON_LIBS="$CARBON_LIBS -Xlinker -framework -Xlinker Carbon"
  fi
  if test "x$have_iokit" = "xtrue";then
     CARBON_LIBS="$CARBON_LIBS -Xlinker -framework -Xlinker IOKit"
  fi
  if test "x$CARBON_LIBS" != "x";then
	 AC_SUBST(CARBON_LIBS)
     have_idle_osx=true
     dnl Disable custom trayicon
     have_trayicon=gtk+
     AM_CONDITIONAL(BUILD_TRAYICON, false)
     dnl Hack to work around failure in gettext package detection on OS/X
     if test "x$GMSGFMT" = "x";then
        AC_SUBST(GMSGFMT, msgfmt)
        AC_SUBST(MSGFMT, msgfmt)
        AC_SUBST(XGETTEXT, xgettext)
     fi
  else
	 have_carbon=false
     have_idle_osx=false
  fi
fi
AM_CONDITIONAL(BUILD_IDLE_OSX, $have_carbon)
AM_CONDITIONAL(BUILD_CARBON, $have_carbon)

ACLOCAL_AMFLAGS="\${ACLOCAL_FLAGS}"
AC_SUBST(ACLOCAL_AMFLAGS)

AM_CHECK_PYTHON_HEADERS(,[AC_MSG_ERROR(could not find Python headers)])
AC_SUBST([PYTHON_INCLUDES])

AS_AC_EXPAND(DATADIR, "${datadir}")
AS_AC_EXPAND(LIBDIR, "${libdir}")
AS_AC_EXPAND(DOCDIR, "${docdir}")
AS_AC_EXPAND(LOCALEDIR, "${localedir}")

AC_SUBST(VERSION)
AC_SUBST(PACKAGE)

AC_CONFIG_FILES([ 
	Makefile
	data/Makefile
	data/glade/Makefile
	data/emoticons/Makefile
	data/pixmaps/Makefile
	data/iconsets/Makefile
	data/moods/Makefile
	data/activities/Makefile
	data/gajim.desktop.in
	data/defs.py
	src/Makefile
	src/osx/Makefile
	src/osx/growl/Makefile
	src/osx/syncmenu/Makefile
	scripts/gajim
	scripts/gajim-remote:scripts/gajim.in
	scripts/gajim-history-manager:scripts/gajim.in
	po/Makefile.in
])
AC_OUTPUT
echo " 
***************************** 
  Build features:
    trayicon ......... ${have_trayicon}
    idle module OSX .. ${have_idle_osx}
    cocoa (OSX)....... ${have_cocoa}
*****************************"
