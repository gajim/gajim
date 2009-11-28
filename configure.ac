AC_INIT([Gajim - A Jabber Instant Messager],
		[0.13.0.1-dev],[http://trac.gajim.org/],[gajim])
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
PKG_CHECK_MODULES([PYGTK], [gtk+-2.0 >= 2.16.0 pygtk-2.0 >= 2.16.0])
AC_SUBST(PYGTK_CFLAGS)
AC_SUBST(PYGTK_LIBS)
PYGTK_DEFS=`$PKG_CONFIG --variable=defsdir pygtk-2.0`
AC_SUBST(PYGTK_DEFS)

AM_PATH_PYTHON([2.5])
if test "x$PYTHON" = "x:"; then
	AC_MSG_ERROR([Python not found])
fi

ACLOCAL_AMFLAGS="\${ACLOCAL_FLAGS}"
AC_SUBST(ACLOCAL_AMFLAGS)

AM_CHECK_PYTHON_HEADERS(,[AC_MSG_ERROR(could not find Python headers)])
AC_SUBST([PYTHON_INCLUDES])

dnl ****
dnl enable installation in python-2.x/site-packages/gajim
dnl ****
AC_ARG_ENABLE(site-packages,
  [AS_HELP_STRING([--enable-site-packages],
	[install gajim sources in PYTHONDIR/site-packages/gajim
instead of DATADIR/gajim/src.])]
,
AC_SUBST([gajim_srcdir], [\${pkgpythondir}])
,
AC_SUBST([gajim_srcdir], [\${datadir}/\${PACKAGE}/src])
)

AS_AC_EXPAND(GAJIM_SRCDIR, "${gajim_srcdir}")
AS_AC_EXPAND(PKGDATADIR, "${datadir}/${PACKAGE}")
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
	icons/Makefile
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
  Installation:
    Prefix ........... ${prefix}
    Python modules ... ${GAJIM_SRCDIR}
    Documentation .... ${DOCDIR}
    Others ........... ${PKGDATADIR}
*****************************"

