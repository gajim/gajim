#!/usr/bin/env python3

import os
import sys

if sys.version_info < (3, 5):
    sys.exit('Gajim needs Python 3.5+')

from setuptools import setup, find_packages
from setuptools import Command
from setuptools.command.build_py import build_py as _build
from setuptools.command.install import install as _install
from distutils import log
from distutils.util import convert_path, newer

import subprocess

import gajim

pos = [x for x in os.listdir('po') if x[-3:] == ".po"]
ALL_LINGUAS = sorted([os.path.split(x)[-1][:-3] for x in pos])
MAN_FILES = ['gajim.1', 'gajim-history-manager.1', 'gajim-remote.1']
META_FILES = [('data/org.gajim.Gajim.desktop', 'share/applications', '--desktop'),
              ('data/org.gajim.Gajim.appdata.xml', 'share/metainfo', '--xml')]
cwd = os.path.dirname(os.path.realpath(__file__))
build_dir = os.path.join(cwd, "build")


def update_trans():
    '''
    Update translation files
    '''
    template = os.path.join('po', 'gajim.pot')
    files = [os.path.join(root, f) for root, d, files in os.walk('gajim') for f in files if os.path.isfile(
        os.path.join(root, f)) and (f.endswith('.py') or f.endswith('.ui'))]
    files.append(os.path.join("data", "org.gajim.Gajim.desktop.in"))
    files.append(os.path.join("data", "org.gajim.Gajim.appdata.xml.in"))
    cmd = 'xgettext --from-code=utf-8 --keyword=Q_ -o %s %s' % (
        template, " ".join(files))
    if os.system(cmd) != 0:
        msg = "ERROR: %s could not be created!\n" % template
        raise SystemExit(msg)

    for lang in ALL_LINGUAS:
        po_file = os.path.join('po', lang + '.po')
        cmd = 'msgmerge -U %s %s' % (po_file, template)
        if os.system(cmd) != 0:
            msg = 'ERROR: Updating language translation file failed.'
            ask = msg + '\n Continue updating y/n [n] '
            reply = input(ask)
            if reply in ['n', 'N']:
                raise SystemExit(msg)
        log.info('Updating %s', po_file)


def build_trans(build_cmd):
    '''
    Translate the language files into gajim.mo
    '''
    for lang in ALL_LINGUAS:
        po_file = os.path.join('po', lang + '.po')
        mo_file = os.path.join(build_dir, 'mo', lang, 'LC_MESSAGES', 'gajim.mo')
        mo_dir = os.path.dirname(mo_file)
        if not (os.path.isdir(mo_dir) or os.path.islink(mo_dir)):
            os.makedirs(mo_dir)

        if newer(po_file, mo_file):
            cmd = 'msgfmt %s -o %s' % (po_file, mo_file)
            if os.system(cmd) != 0:
                os.remove(mo_file)
                msg = 'ERROR: Building language translation files failed.'
                ask = msg + '\n Continue building y/n [n] '
                reply = input(ask)
                if reply in ['n', 'N']:
                    raise SystemExit(msg)
            log.info('Compiling %s >> %s', po_file, mo_file)


def install_trans(install_cmd):
    data_files = install_cmd.distribution.data_files
    for lang in ALL_LINGUAS:
        mo_file = os.path.join(build_dir, 'mo', lang, 'LC_MESSAGES', 'gajim.mo')
        target = 'share/locale/' + lang + '/LC_MESSAGES'
        data_files.append((target, [mo_file]))


def build_man(build_cmd):
    '''
    Compress Gajim manual files
    '''
    newdir = os.path.join(build_dir, 'man')
    if not (os.path.isdir(newdir) or os.path.islink(newdir)):
        os.makedirs(newdir)

    for man in MAN_FILES:
        filename = os.path.join('data', man)
        man_file_gz = os.path.join(newdir, man + '.gz')
        if os.path.exists(man_file_gz):
            if newer(filename, man_file_gz):
                os.remove(man_file_gz)
            else:
                filename = False

        if filename:
            import gzip
            # Binary io, so open is OK
            with open(filename, 'rb') as f_in,\
                    gzip.open(man_file_gz, 'wb') as f_out:
                f_out.writelines(f_in)
                log.info('Compiling %s >> %s', filename, man_file_gz)


def install_man(install_cmd):
    data_files = install_cmd.distribution.data_files
    man_dir = os.path.join(build_dir, 'man')
    target = 'share/man/man1'

    for man in MAN_FILES:
        man_file_gz = os.path.join(man_dir, man + '.gz')
        data_files.append((target, [man_file_gz]))


def build_intl(build_cmd):
    '''
    Merge translation files into desktop and mime files
    '''
    base = build_dir

    for filename, _, option in META_FILES:
        filenamelocal = convert_path(filename)
        newfile = os.path.join(base, filenamelocal)
        newdir = os.path.dirname(newfile)
        if not(os.path.isdir(newdir) or os.path.islink(newdir)):
            os.makedirs(newdir)
        merge(filenamelocal + '.in', newfile, option)


def install_intl(install_cmd):
    data_files = install_cmd.distribution.data_files

    for filename, target, _ in META_FILES:
        data_files.append((target, [build_dir + '/' + filename]))


def merge(in_file, out_file, option, po_dir='po'):
    '''
    Run the msgfmt command.
    '''
    if os.path.exists(in_file):
        cmd = (('msgfmt %(opt)s -d %(po_dir)s --template %(in_file)s '
                '-o %(out_file)s') %
               {'opt': option,
                'po_dir': po_dir,
                'in_file': in_file,
                'out_file': out_file})
        if os.system(cmd) != 0:
            msg = ('ERROR: %s was not merged into the translation files!\n' %
                   out_file)
            raise SystemExit(msg)
        log.info('Compiling %s >> %s', in_file, out_file)


class build(_build):
    def run(self):
        build_trans(self)
        if sys.platform != 'win32':
            build_man(self)
            build_intl(self)
        _build.run(self)


class install(_install):
    def run(self):
        install_trans(self)
        if sys.platform != 'win32':
            install_man(self)
            install_intl(self)
        _install.run(self)


class test(Command):
    description = "Run all tests"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        exit(subprocess.call("./test/runtests.py"))


class test_nogui(test):
    description = "Run tests without GUI"

    def run(self):
        exit(subprocess.call(["./test/runtests.py", "-n"]))


class update_po(Command):
    description = "Update po files"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        update_trans()


package_data_activities = ['data/activities/*/*/*.png']
package_data_emoticons = ['data/emoticons/*/emoticons_theme.py',
                          'data/emoticons/*/*.png',
                          'data/emoticons/*/LICENSE']
package_data_gui = ['data/gui/*.ui']
package_data_icons = ['data/icons/hicolor/*/*/*.png',
                      'data/icons/hicolor/*/*/*.svg']
package_data_iconsets = ['data/iconsets/*/*/*.gif',
                         'data/iconsets/*/*/*.png',
                         'data/iconsets/transports/*/*/*.png']
package_data_moods = ['data/moods/*/*.png']
package_data_other = ['data/other/*']
package_data_sounds = ['data/sounds/*.wav']
package_data_style = ['data/style/gajim.css']
package_plugins_data = ['data/plugins/*/*']
package_data = (package_data_activities
                + package_data_emoticons
                + package_data_gui
                + package_data_icons
                + package_data_iconsets
                + package_data_moods
                + package_data_other
                + package_data_sounds
                + package_data_style
                + package_plugins_data)


# only install subdirectories of data
data_files_app_icon = [
    ("share/icons/hicolor/64x64/apps",
     ["gajim/data/icons/hicolor/64x64/apps/org.gajim.Gajim.png"]),
    ("share/icons/hicolor/128x128/apps",
     ["gajim/data/icons/hicolor/128x128/apps/org.gajim.Gajim.png"]),
    ("share/icons/hicolor/scalable/apps",
     ["gajim/data/icons/hicolor/scalable/apps/org.gajim.Gajim.svg"]),
    ("share/icons/hicolor/symbolic/apps",
     ["gajim/data/icons/hicolor/symbolic/apps/org.gajim.Gajim-symbolic.svg"])
]

data_files = data_files_app_icon

setup(
    name="gajim",
    description='A GTK+ Jabber client',
    version=gajim.__version__,
    author="Philipp Hörist, Yann Leboulanger",
    author_email="gajim-devel@gajim.org",
    url='https://gajim.org',
    license='GPL v3',
    classifiers=[
        'Programming Language :: Python :: 3',
    ],
    cmdclass={
        'build_py': build,
        'install': install,
        'test': test,
        'test_nogui': test_nogui,
        'update_po': update_po,
    },
    entry_points={
        'console_scripts': [
            'gajim-remote = gajim.gajim_remote:main',
        ],
        'gui_scripts': [
            'gajim = gajim.gajim:main',
            'gajim-history-manager = gajim.history_manager:main',
        ]
    },
    packages=find_packages(exclude=["gajim.dev", "test*"]),
    package_data={'gajim': package_data},
    data_files=data_files,
    install_requires=[
        'nbxmpp>=0.6.4',
        'pyOpenSSL>=0.12',
        'pyasn1',
    ],
    extras_require={
        'secret_password': ["keyring"]
    }
)
