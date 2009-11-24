INCLUDES = \
	$(PYTHON_INCLUDES)
export MACOSX_DEPLOYMENT_TARGET=10.4

gajimsrcdir = $(pkgdatadir)/src
gajimsrc_PYTHON = $(srcdir)/*.py

gajimsrc1dir = $(pkgdatadir)/src/common
gajimsrc1_PYTHON = \
				$(srcdir)/common/*.py

gajimsrc2dir = $(pkgdatadir)/src/common/xmpp
gajimsrc2_PYTHON = \
				$(srcdir)/common/xmpp/*.py

gajimsrc3dir = $(pkgdatadir)/src/common/zeroconf
gajimsrc3_PYTHON = \
				$(srcdir)/common/zeroconf/*.py

gajimsrc4dir = $(pkgdatadir)/src/command_system
gajimsrc4_PYTHON = \
				   $(srcdir)/command_system/*.py

gajimsrc5dir = $(pkgdatadir)/src/command_system/implementation
gajimsrc5_PYTHON = \
				   $(srcdir)/command_system/implementation/*.py

DISTCLEANFILES =

EXTRA_DIST = $(gajimsrc_PYTHON) \
			$(gajimsrc1_PYTHON) \
			$(gajimsrc2_PYTHON) \
			$(gajimsrc3_PYTHON) \
			$(gajimsrc4_PYTHON) \
			$(gajimsrc5_PYTHON)

dist-hook:
			rm -f $(distdir)/ipython_view.py

MAINTAINERCLEANFILES = Makefile.in
