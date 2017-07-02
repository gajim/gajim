INCLUDES = \
	$(PYTHON_INCLUDES)
export MACOSX_DEPLOYMENT_TARGET=10.4

gajimsrcdir = $(gajim_srcdir)
nobase_dist_gajimsrc_PYTHON = \
	$(srcdir)/*.py \
	$(srcdir)/common/*.py \
	$(srcdir)/common/protocol/*.py \
	$(srcdir)/common/zeroconf/*.py \
	$(srcdir)/command_system/*.py \
	$(srcdir)/command_system/implementation/*.py \
	$(srcdir)/plugins/*.py

dist-hook:
			rm -f $(distdir)/ipython_view.py

MAINTAINERCLEANFILES = Makefile.in
