### Adjust the sys.path so that the site-packages.zip is before the lib-dynload
### so that the osx/__init__.py in the .zip is read before looking for it in the
### lib-dynload/osx dir where the .so's are.

import sys

py = -1
lib_dyn = -1
site_zip = -1
for index in xrange(len(sys.path)):
    if 'Contents/Resources' in sys.path[index]:
        if sys.path[index].endswith('lib/python2.5'):
            py = index
        if sys.path[index].endswith('lib-dynload'):
            lib_dyn = index
        elif sys.path[index].endswith('site-packages.zip'):
            site_zip = index
if ((lib_dyn > -1) and (site_zip > -1)):
    tmp = sys.path[lib_dyn]
    sys.path[lib_dyn] = sys.path[site_zip]
    sys.path[site_zip] = tmp
if py > -1:
    del sys.path[py]
