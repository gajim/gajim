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

GETTEXT_PACKAGE=gajim
AC_SUBST([GETTEXT_PACKAGE])
AC_DEFINE_UNQUOTED([GETTEXT_PACKAGE],["$GETTEXT_PACKAGE"], [Gettext package])
ALL_LINGUAS="fr pt el pl es ru bg de nb cs nl pt_BR sv it eu sk no zh_CN br eo"
AM_GLIB_GNU_GETTEXT

AC_PATH_X

PKG_CHECK_MODULES([DBUS], [dbus-1 >= 0.61 dbus-glib-1 >= 0.61])
AC_SUBST(DBUS_CFLAGS)
AC_SUBST(DBUS_LIBS)

PKG_CHECK_MODULES([PYGTK], [gtk+-2.0 >= 2.6.0 pygtk-2.0 >= 2.6.0])
AC_SUBST(PYGTK_CFLAGS)
AC_SUBST(PYGTK_LIBS)
PYGTK_DEFS=`$PKG_CONFIG --variable=defsdir pygtk-2.0`
AC_SUBST(PYGTK_DEFS)


PKG_CHECK_MODULES([GTKSPELL], [gtkspell-2.0])
AC_SUBST(GTKSPELL_CFLAGS)
AC_SUBST(GTKSPELL_LIBS)

PKG_CHECK_MODULES([XSCRNSAVER], xscrnsaver)
dnl AC_SUBST(XSCRNSAVER_LIBS)

# Checks for libraries.
# FIXME: Replace `main' with a function in `-lX11':
AC_CHECK_LIB([X11], [main])
# FIXME: Replace `main' with a function in `-lXext':
AC_CHECK_LIB([Xext], [main])
# FIXME: Replace `main' with a function in `-lXss':
AC_CHECK_LIB([Xss], [main])


AM_PATH_PYTHON([2.4])
if test "x$PYTHON" = "x:"; then
	AC_MSG_ERROR([Python not found])
fi

AM_CHECK_PYTHON_HEADERS(,[AC_MSG_ERROR(could not find Python headers)])



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

