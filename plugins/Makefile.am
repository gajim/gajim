INCLUDES = \
	$(PYTHON_INCLUDES)

gajimpluginsdir = $(gajim_pluginsdir)

installedplugins = acronyms_expander banner_tweaks length_notifier plugin_installer triggers whiteboard

installedpluginsfiles = $(wildcard ${srcdir}/${p}/*.py ${srcdir}/${p}/manifest.ini ${srcdir}/${p}/*.ui ${srcdir}/${p}/*.png)

nobase_dist_gajimplugins_PYTHON = $(foreach p, ${installedplugins}, $(installedpluginsfiles))

EXTRA_DIST = \
	$(srcdir)/*/*.py \
	$(srcdir)/*/manifest.ini \
	$(srcdir)/*/*.ui

MAINTAINERCLEANFILES = Makefile.in
