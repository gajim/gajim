AC_INIT([Gajim],[0.11.0],[http://trac.gajim.org/newticket],[gajim])
AM_INIT_AUTOMAKE([1.9])
AC_CONFIG_HEADER(config.h)

AM_MAINTAINER_MODE

IT_PROG_INTLTOOL([0.35.0])


AM_DISABLE_STATIC
AC_ENABLE_SHARED(yes)
AC_ENABLE_STATIC(no)

AC_ISC_POSIX
AC_PROG_CC
AC_PROG_INSTALL
AC_PROG_MAKE_SET
AC_PROG_LIBTOOL
AC_PATH_X

GETTEXT_PACKAGE=gajim
AC_SUBST([GETTEXT_PACKAGE])
AC_DEFINE_UNQUOTED([GETTEXT_PACKAGE],["$GETTEXT_PACKAGE"], [Gettext package])
ALL_LINGUAS="fr pt el pl es ru bg de nb cs nl pt_BR sv it eu sk no zh_CN br eo"
AM_GLIB_GNU_GETTEXT

PKG_CHECK_MODULES([DBUS], [dbus-1 >= 0.61 dbus-glib-1 >= 0.61])
AC_SUBST(DBUS_CFLAGS)
AC_SUBST(DBUS_LIBS)

PKG_CHECK_MODULES([PYGTK], [gtk+-2.0 >= 2.6.0 pygtk-2.0 >= 2.6.0])
AC_SUBST(PYGTK_CFLAGS)
AC_SUBST(PYGTK_LIBS)
PYGTK_DEFS=`$PKG_CONFIG --variable=defsdir pygtk-2.0`
AC_SUBST(PYGTK_DEFS)

AC_ARG_ENABLE(gtkspell, 
  [  --enable-gtkspell       build spell checking support [default auto]],,
  enable_gtkspell=auto)

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

PKG_CHECK_EXISTS([xscrnsaver], [have_xscrnsaver=yes], [have_xscrnsaver=no])

if test "x$have_xscrnsaver" = "xyes";then
	PKG_CHECK_MODULES([XSCRNSAVER], xscrnsaver)
	AC_SUBST(XSCRNSAVER_LIBS)
else
	# Checks for libraries.
	AC_CHECK_LIB([X11], [XOpenDisplay])
	AC_CHECK_LIB([Xext], [XMissingExtension])
	AC_CHECK_LIB([Xss], [XScreenSaverAllocInfo])
	XSCRNSAVER_LIBS=" -lX11 -lXss -lXext"
	AC_SUBST([XSCRNSAVER_LIBS])
fi


AM_PATH_PYTHON([2.4])
if test "x$PYTHON" = "x:"; then
	AC_MSG_ERROR([Python not found])
fi

AM_CHECK_PYTHON_HEADERS(,[AC_MSG_ERROR(could not find Python headers)])
AC_SUBST([PYTHON_INCLUDES])

AC_CONFIG_FILES([
	Makefile
	data/Makefile
	data/glade/Makefile
	data/emoticons/Makefile
	data/pixmaps/Makefile
	data/iconsets/Makefile
	data/gajim.desktop.in
	src/Makefile
	src/common/Makefile
	scripts/gajim
	po/Makefile.in
])
AC_OUTPUT

