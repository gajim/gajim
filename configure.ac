AC_INIT([Gajim - A Jabber Instant Messager],
		["version-set-in-hgversion"],[http://trac.gajim.org/],[gajim])
AC_PREREQ([2.59])

AC_CONFIG_HEADER(config.h)
AC_CONFIG_AUX_DIR(config)
AC_CONFIG_MACRO_DIR([m4])

AM_INIT_AUTOMAKE([1.8])
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


ACLOCAL_AMFLAGS="\${ACLOCAL_FLAGS}"
AC_SUBST(ACLOCAL_AMFLAGS)

AM_PATH_PYTHON([2.5])

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

AC_SUBST([gajim_pluginsdir], [\${datadir}/\${PACKAGE}/plugins])

AS_AC_EXPAND(GAJIM_SRCDIR, "${gajim_srcdir}")
AS_AC_EXPAND(PKGDATADIR, "${datadir}/${PACKAGE}")
AS_AC_EXPAND(DOCDIR, "${docdir}")
AS_AC_EXPAND(LOCALEDIR, "${localedir}")
AS_AC_EXPAND(GAJIM_PLUGINSDIR, "${gajim_pluginsdir}")

AC_SUBST(VERSION)
AC_SUBST(PACKAGE)

AC_CONFIG_FILES([ 
	Makefile
	data/Makefile
	data/gui/Makefile
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
	plugins/Makefile
])
AC_OUTPUT
echo "
*****************************
  Installation:
    Prefix ........... ${prefix}
    Python modules ... ${GAJIM_SRCDIR}
    Plugins .. ....... ${GAJIM_PLUGINSDIR}
    Documentation .... ${DOCDIR}
    Others ........... ${PKGDATADIR}
*****************************"

