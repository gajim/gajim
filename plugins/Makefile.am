INCLUDES = \
	$(PYTHON_INCLUDES)

gajimpluginsdir = $(gajim_pluginsdir)

dist_gajimplugins_PYTHON = 

pluginsdirs = ${sort ${dir ${wildcard ${srcdir}/*/ ${srcdir}/*/*/}}}

pluginsfiles = $(wildcard ${p}/*.py ${p}/manifest.ini ${p}/*.ui ${p}/*.png)

nobase_gajimplugins_DATA = $(foreach p, ${pluginsdirs}, $(pluginsfiles))


MAINTAINERCLEANFILES = Makefile.in
