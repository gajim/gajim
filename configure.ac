AC_INIT([Gajim - A Jabber Instant Messager],
		[0.12.3.1-dev],[http://trac.gajim.org/],[gajim])
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
PKG_CHECK_MODULES([PYGTK], [gtk+-2.0 >= 2.12.0 pygtk-2.0 >= 2.12.0])
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
*****************************"
