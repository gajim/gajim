# -*- coding:utf-8 -*-
## src/gajim.py
##
## Copyright (C) 2003-2008 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2004-2005 Vincent Hanquez <tab AT snarc.org>
## Copyright (C) 2005 Alex Podaras <bigpod AT gmail.com>
##                    Norman Rasmussen <norman AT rasmussen.co.za>
##                    Stéphan Kochen <stephan AT kochen.nl>
## Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
##                         Alex Mauer <hawke AT hawkesnest.net>
## Copyright (C) 2005-2007 Travis Shirk <travis AT pobox.com>
##                         Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006 Junglecow J <junglecow AT gmail.com>
##                    Stefan Bethge <stefan AT lanpartei.de>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
##                    James Newton <redshodan AT gmail.com>
## Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
##                         Julien Pivotto <roidelapluie AT gmail.com>
##                         Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

import os
import sys
import warnings

if os.name == 'nt':
    warnings.filterwarnings(action='ignore')

    if os.path.isdir('gtk'):
        # Used to create windows installer with GTK included
        paths = os.environ['PATH']
        list_ = paths.split(';')
        new_list = []
        for p in list_:
            if p.find('gtk') < 0 and p.find('GTK') < 0:
                new_list.append(p)
        new_list.insert(0, 'gtk/lib')
        new_list.insert(0, 'gtk/bin')
        os.environ['PATH'] = ';'.join(new_list)
        os.environ['GTK_BASEPATH'] = 'gtk'

if os.name == 'nt':
    # needed for docutils
    sys.path.append('.')

from common import logging_helpers
logging_helpers.init('TERM' in os.environ)

import logging
# gajim.gui or gajim.gtk more appropriate ?
log = logging.getLogger('gajim.gajim')

import getopt
from common import i18n

def parseOpts():
    profile = ''
    config_path = None

    try:
        shortargs = 'hqvl:p:c:'
        longargs = 'help quiet verbose loglevel= profile= config_path='
        opts = getopt.getopt(sys.argv[1:], shortargs, longargs.split())[0]
    except getopt.error, msg:
        print msg
        print 'for help use --help'
        sys.exit(2)
    for o, a in opts:
        if o in ('-h', '--help'):
            print 'gajim [--help] [--quiet] [--verbose] [--loglevel subsystem=level[,subsystem=level[...]]] [--profile name] [--config-path]'
            sys.exit()
        elif o in ('-q', '--quiet'):
            logging_helpers.set_quiet()
        elif o in ('-v', '--verbose'):
            logging_helpers.set_verbose()
        elif o in ('-p', '--profile'): # gajim --profile name
            profile = a
        elif o in ('-l', '--loglevel'):
            logging_helpers.set_loglevels(a)
        elif o in ('-c', '--config-path'):
            config_path = a
    return profile, config_path

profile, config_path = parseOpts()
del parseOpts

import locale
profile = unicode(profile, locale.getpreferredencoding())

import common.configpaths
common.configpaths.gajimpaths.init(config_path)
del config_path
common.configpaths.gajimpaths.init_profile(profile)
del profile

if os.name == 'nt':
    class MyStderr(object):
        _file = None
        _error = None
        def write(self, text):
            fname=os.path.join(common.configpaths.gajimpaths.cache_root,
                    os.path.split(sys.executable)[1]+'.log')
            if self._file is None and self._error is None:
                try:
                    self._file = open(fname, 'a')
                except Exception, details:
                    self._error = details
            if self._file is not None:
                self._file.write(text)
                self._file.flush()
        def flush(self):
            if self._file is not None:
                self._file.flush()

    sys.stderr = MyStderr()

# PyGTK2.10+ only throws a warning
warnings.filterwarnings('error', module='gtk')
try:
    import gtk
except Warning, msg:
    if str(msg) == 'could not open display':
        print >> sys.stderr, _('Gajim needs X server to run. Quiting...')
    else:
        print >> sys.stderr, _('importing PyGTK failed: %s') % str(msg)
    sys.exit()
warnings.resetwarnings()

if os.name == 'nt':
    warnings.filterwarnings(action='ignore')

pritext = ''

from common import exceptions
try:
    from common import gajim
except exceptions.DatabaseMalformed:
    pritext = _('Database Error')
    sectext = _('The database file (%s) cannot be read. Try to repair it (see http://trac.gajim.org/wiki/DatabaseBackup) or remove it (all history will be lost).') % common.logger.LOG_DB_PATH
else:
    from common import dbus_support
    if dbus_support.supported:
        from music_track_listener import MusicTrackListener
        import dbus

    from ctypes import CDLL
    from ctypes.util import find_library
    import platform

    sysname = platform.system()
    if sysname in ('Linux', 'FreeBSD', 'OpenBSD', 'NetBSD'):
        libc = CDLL(find_library('c'))

        # The constant defined in <linux/prctl.h> which is used to set the name of
        # the process.
        PR_SET_NAME = 15

        if sysname == 'Linux':
            libc.prctl(PR_SET_NAME, 'gajim')
        elif sysname in ('FreeBSD', 'OpenBSD', 'NetBSD'):
            libc.setproctitle('gajim')

    if gtk.pygtk_version < (2, 16, 0):
        pritext = _('Gajim needs PyGTK 2.16 or above')
        sectext = _('Gajim needs PyGTK 2.16 or above to run. Quiting...')
    elif gtk.gtk_version < (2, 16, 0):
        pritext = _('Gajim needs GTK 2.16 or above')
        sectext = _('Gajim needs GTK 2.16 or above to run. Quiting...')

    try:
        from common import check_paths
    except exceptions.PysqliteNotAvailable, e:
        pritext = _('Gajim needs PySQLite2 to run')
        sectext = str(e)

    if os.name == 'nt':
        try:
            import winsound # windows-only built-in module for playing wav
            import win32api # do NOT remove. we req this module
        except Exception:
            pritext = _('Gajim needs pywin32 to run')
            sectext = _('Please make sure that Pywin32 is installed on your system. You can get it at %s') % 'http://sourceforge.net/project/showfiles.php?group_id=78018'

if pritext:
    dlg = gtk.MessageDialog(None,
            gtk.DIALOG_DESTROY_WITH_PARENT | gtk.DIALOG_MODAL,
            gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, message_format = pritext)

    dlg.format_secondary_text(sectext)
    dlg.run()
    dlg.destroy()
    sys.exit()

del pritext

import gtkexcepthook

import gobject
if not hasattr(gobject, 'timeout_add_seconds'):
    def timeout_add_seconds_fake(time_sec, *args):
        return gobject.timeout_add(time_sec * 1000, *args)
    gobject.timeout_add_seconds = timeout_add_seconds_fake


import signal
import gtkgui_helpers

gajimpaths = common.configpaths.gajimpaths

pid_filename = gajimpaths['PID_FILE']
config_filename = gajimpaths['CONFIG_FILE']

import traceback
import errno
import dialogs

def pid_alive():
    try:
        pf = open(pid_filename)
    except IOError:
        # probably file not found
        return False

    try:
        pid = int(pf.read().strip())
        pf.close()
    except Exception:
        traceback.print_exc()
        # PID file exists, but something happened trying to read PID
        # Could be 0.10 style empty PID file, so assume Gajim is running
        return True

    if os.name == 'nt':
        try:
            from ctypes import (windll, c_ulong, c_int, Structure, c_char, POINTER, pointer, )
        except Exception:
            return True

        class PROCESSENTRY32(Structure):
            _fields_ = [
                    ('dwSize', c_ulong, ),
                    ('cntUsage', c_ulong, ),
                    ('th32ProcessID', c_ulong, ),
                    ('th32DefaultHeapID', c_ulong, ),
                    ('th32ModuleID', c_ulong, ),
                    ('cntThreads', c_ulong, ),
                    ('th32ParentProcessID', c_ulong, ),
                    ('pcPriClassBase', c_ulong, ),
                    ('dwFlags', c_ulong, ),
                    ('szExeFile', c_char*512, ),
                    ]
            def __init__(self):
                Structure.__init__(self, 512+9*4)

        k = windll.kernel32
        k.CreateToolhelp32Snapshot.argtypes = c_ulong, c_ulong,
        k.CreateToolhelp32Snapshot.restype = c_int
        k.Process32First.argtypes = c_int, POINTER(PROCESSENTRY32),
        k.Process32First.restype = c_int
        k.Process32Next.argtypes = c_int, POINTER(PROCESSENTRY32),
        k.Process32Next.restype = c_int

        def get_p(p):
            h = k.CreateToolhelp32Snapshot(2, 0) # TH32CS_SNAPPROCESS
            assert h > 0, 'CreateToolhelp32Snapshot failed'
            b = pointer(PROCESSENTRY32())
            f = k.Process32First(h, b)
            while f:
                if b.contents.th32ProcessID == p:
                    return b.contents.szExeFile
                f = k.Process32Next(h, b)

        if get_p(pid) in ('python.exe', 'gajim.exe'):
            return True
        return False
    try:
        if not os.path.exists('/proc'):
            return True # no /proc, assume Gajim is running

        try:
            f = open('/proc/%d/cmdline'% pid)
        except IOError, e:
            if e.errno == errno.ENOENT:
                return False # file/pid does not exist
            raise

        n = f.read().lower()
        f.close()
        if n.find('gajim') < 0:
            return False
        return True # Running Gajim found at pid
    except Exception:
        traceback.print_exc()

    # If we are here, pidfile exists, but some unexpected error occured.
    # Assume Gajim is running.
    return True

if pid_alive():
    pix = gtkgui_helpers.get_icon_pixmap('gajim', 48)
    gtk.window_set_default_icon(pix) # set the icon to all newly opened wind
    pritext = _('Gajim is already running')
    sectext = _('Another instance of Gajim seems to be running\nRun anyway?')
    dialog = dialogs.YesNoDialog(pritext, sectext)
    dialog.popup()
    if dialog.run() != gtk.RESPONSE_YES:
        sys.exit(3)
    dialog.destroy()
    # run anyway, delete pid and useless global vars
    if os.path.exists(pid_filename):
        os.remove(pid_filename)
    del path_to_file
    del pix
    del pritext
    del sectext
    dialog.destroy()

# Create .gajim dir
pid_dir =  os.path.dirname(pid_filename)
if not os.path.exists(pid_dir):
    check_paths.create_path(pid_dir)
# Create pid file
try:
    f = open(pid_filename, 'w')
    f.write(str(os.getpid()))
    f.close()
except IOError, e:
    dlg = dialogs.ErrorDialog(_('Disk Write Error'), str(e))
    dlg.run()
    dlg.destroy()
    sys.exit()
del pid_dir
del f

def on_exit():
    # delete pid file on normal exit
    if os.path.exists(pid_filename):
        os.remove(pid_filename)
    # Shutdown GUI and save config
    if hasattr(gajim.interface, 'roster'):
        gajim.interface.roster.prepare_quit()

import atexit
atexit.register(on_exit)

from gui_interface import Interface

if __name__ == '__main__':
    def sigint_cb(num, stack):
        sys.exit(5)
    # ^C exits the application normally to delete pid file
    signal.signal(signal.SIGINT, sigint_cb)

    log.info("Encodings: d:%s, fs:%s, p:%s", sys.getdefaultencoding(), \
            sys.getfilesystemencoding(), locale.getpreferredencoding())

    if os.name != 'nt':
        # Session Management support
        try:
            import gnome.ui
            raise ImportError
        except ImportError:
            pass
        else:
            def die_cb(cli):
                gajim.interface.roster.quit_gtkgui_interface()
            gnome.program_init('gajim', gajim.version)
            cli = gnome.ui.master_client()
            cli.connect('die', die_cb)

            path_to_gajim_script = gtkgui_helpers.get_abspath_for_script(
                    'gajim')

            if path_to_gajim_script:
                argv = [path_to_gajim_script]
                # FIXME: remove this typeerror catch when gnome python is old and
                # not bad patched by distro men [2.12.0 + should not need all that
                # NORMALLY]
                try:
                    cli.set_restart_command(argv)
                except AttributeError:
                    cli.set_restart_command(len(argv), argv)

    check_paths.check_and_possibly_create_paths()

    interface = Interface()
    interface.run()

    try:
        if os.name != 'nt':
            # This makes Gajim unusable under windows, and threads are used only
            # for GPG, so not under windows
            gtk.gdk.threads_init()
        gtk.main()
    except KeyboardInterrupt:
        print >> sys.stderr, 'KeyboardInterrupt'
