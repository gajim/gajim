import sys
from distutils.core import setup, Extension
import commands


retval, output = commands.getstatusoutput("pkg-config --cflags gtk+-2.0 pygtk-2.0")
if retval != 0:
	print "Failed to find package details for gtk+-2.0"
	print
	print output
	sys.exit(1)
cflags = output.strip().split()
retval, output = commands.getstatusoutput("pkg-config --libs gtk+-2.0 pygtk-2.0")
if retval != 0:
	print "Failed to find package details for gtk+-2.0"
	print
	print output
	sys.exit(1)
libs = output.strip().split()


setup(name='syncmenu', version='0.2',
      author='James Newton', author_email='baron@codepunks.org',
      ext_modules=[
      	Extension('syncmenu', ['pysyncmenu.c', 'sync-menu.c'],
				  extra_link_args=libs + ['-framework', 'Carbon'],
				  extra_compile_args=['-Wall'] + cflags)
      ])

# vim: se ts=3:
