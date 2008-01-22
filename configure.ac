AC_INIT([Gajim - A Jabber Instant Messager],
		[0.11.1.5],[http://trac.gajim.org/],[gajim])
AC_PREREQ([2.59])
AM_INIT_AUTOMAKE([1.8])
AC_CONFIG_HEADER(config.h)
AC_CONFIG_MACRO_DIR([m4])
AM_MAINTAINER_MODE

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

FARSIGHT_CFLAGS=`$PKG_CONFIG --cflags farsight-0.1`
AC_SUBST(FARSIGHT_CFLAGS)

dnl ****
dnl pygtk and gtk+
dnl ****
PKG_CHECK_MODULES([PYGTK], [gtk+-2.0 >= 2.6.0 pygtk-2.0 >= 2.6.0])
AC_SUBST(PYGTK_CFLAGS)
AC_SUBST(PYGTK_LIBS)
PYGTK_DEFS=`$PKG_CONFIG --variable=defsdir pygtk-2.0`
AC_SUBST(PYGTK_DEFS)

dnl *****
dnl dbus
dnl *****
AC_ARG_ENABLE([remote], 
  [  --disable-remote        enable remote control via DBus [default auto]],
  enable_remote=$enableval, enable_remote=auto)

if test "x$enable_remote" = "xauto"; then
	 PKG_CHECK_EXISTS([dbus-1],enable_remote=yes,enable_remote=no)
fi

if test "x$enable_remote" = "xyes";then
	PKG_CHECK_MODULES([DBUS], [dbus-1 >= 0.60])
	AC_SUBST(DBUS_CFLAGS)
	AC_SUBST(DBUS_LIBS)
	have_remote=true
else
	have_remote=false
fi
AM_CONDITIONAL(BUILD_REMOTE_CONTROL, $have_remote)

dnl ****
dnl gtkspell
dnl ****
AC_ARG_ENABLE(gtkspell, 
  [  --disable-gtkspell      build spell checking support [default auto]],
  enable_gtkspell=$enableval, enable_gtkspell=auto)

if test "x$enable_gtkspell" = "xauto";then
	PKG_CHECK_EXISTS([gtkspell-2.0], [enable_gtkspell=yes], [enable_gtkspell=no])
fi
if test "x$enable_gtkspell" = "xyes";then
	PKG_CHECK_MODULES([GTKSPELL], [gtkspell-2.0])
	AC_SUBST(GTKSPELL_CFLAGS)
	AC_SUBST(GTKSPELL_LIBS)
	have_gtkspell=true
else
	have_gtkspell=false
fi
AM_CONDITIONAL(BUILD_GTKSPELL, $have_gtkspell)


dnl ****
dnl xscreensaver
dnl ****
AC_ARG_ENABLE([idle],
  [  --disable-idle          build idle module [default auto]],
  enable_idle=$enableval, enable_idle=yes)

if test "x$enable_idle" = "xyes";then 
	PKG_CHECK_EXISTS([xscrnsaver], [have_xscrnsaver=yes], [have_xscrnsaver=no])

	if test "x$have_xscrnsaver" = "xyes";then
		PKG_CHECK_MODULES([XSCRNSAVER], xscrnsaver)
		AC_SUBST(XSCRNSAVER_LIBS)
		have_idle=true
	else
		# Checks for libraries.
		LIBS=-L$x_libraries
		AC_CHECK_LIB([X11], [XOpenDisplay])
		AC_CHECK_LIB([Xext], [XMissingExtension])
		AC_CHECK_LIB([Xss], [XScreenSaverAllocInfo])
		XSCRNSAVER_LIBS="$LIBS"
		AC_SUBST([XSCRNSAVER_LIBS])
		if test "x$XSCRNSAVER_LIBS" = "x-L";then 
			have_idle=false
		else
			have_idle=true
		fi
	fi
else
	have_idle=false
fi
AM_CONDITIONAL(BUILD_IDLE, $have_idle)

AM_PATH_PYTHON([2.4])
if test "x$PYTHON" = "x:"; then
	AC_MSG_ERROR([Python not found])
fi

dnl ****
dnl tray icon
dnl ****
AC_ARG_ENABLE(trayicon,
  [  --disable-trayicon      build trayicon module [default yes]],
  enable_trayicon=$enableval, enable_trayicon=yes)
test "x$enable_trayicon" = "xyes" && have_trayicon=true || have_trayicon=false
AM_CONDITIONAL(BUILD_TRAYICON, $have_trayicon)

ACLOCAL_AMFLAGS="\${ACLOCAL_FLAGS}"
AC_SUBST(ACLOCAL_AMFLAGS)

AM_CHECK_PYTHON_HEADERS(,[AC_MSG_ERROR(could not find Python headers)])
AC_SUBST([PYTHON_INCLUDES])

AS_AC_EXPAND(DATADIR, "${datadir}")

AS_AC_EXPAND(LIBDIR, ${libdir})

AS_AC_EXPAND(DOCDIR, "${docdir}")

AC_SUBST(VERSION)
AC_SUBST(PACKAGE)
AC_SUBST(DATADIR)
AC_SUBST(LIBDIR)
AS_AC_EXPAND(DATADIR, "${DATADIR}")
AC_SUBST(DOCDIR)
AS_AC_EXPAND(DOCDIR, "${DOCDIR}")

AC_CONFIG_FILES([ 
	Makefile
	data/Makefile
	data/glade/Makefile
	data/emoticons/Makefile
	data/pixmaps/Makefile
	data/iconsets/Makefile
	data/gajim.desktop.in
	data/defs.py
	src/Makefile
	src/common/Makefile
	src/common/farsight/Makefile
	scripts/gajim
	scripts/gajim-remote
	po/Makefile.in
])
AC_OUTPUT
echo " 
***************************** 
  Build features:
    spell check ...... ${have_gtkspell}
    idle module ...... ${have_idle}
    remote control ... ${have_remote}
    trayicon ......... ${have_trayicon}
*****************************"
