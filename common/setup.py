from distutils.core import setup, Extension

module1 = Extension( 'idle',
		     sources = ['idle.c'],
#                     extra_compile_args = ['-W'],
                     libraries = ['gtk-x11-2.0','gdk-x11-2.0','glib-2.0','X11','Xext','Xss','atk-1.0'],
                     library_dirs = ['/usr/X11R6/lib'],
                     include_dirs = ['/usr/include/gtk-2.0', '/usr/include/glib-2.0','/usr/lib/gtk-2.0/include','/usr/lib/glib-2.0/include','/usr/include/pango-1.0','/usr/include/atk-1.0']
		   )

setup (name = 'idle', version = '1.0', description = 'interface to X11/scrnserver.h', ext_modules = [module1])
