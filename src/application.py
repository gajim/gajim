# -*- coding:utf-8 -*-
## src/application.py
##
## Copyright (C) 2016 Emmanuel Gil Peyrot <linkmauve AT linkmauve.fr>
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

import sys
import os
import warnings
import logging
from gi.repository import GLib, Gio, Gtk
from common import i18n
from common import logging_helpers
logging_helpers.init(sys.stderr.isatty())

log = logging.getLogger('gajim.gajim')


class GajimApplication(Gtk.Application):
    '''Main class handling activation and command line.'''

    def __init__(self):
        Gtk.Application.__init__(self, application_id='org.gajim.Gajim',
                                 flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.add_main_option('version', ord('V'), GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE,
                             _('Show the application\'s version'))
        self.add_main_option('quiet', ord('q'), GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE,
                             _('Show only critical errors'))
        self.add_main_option('separate', ord('s'), GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE,
                             _('Separate profile files completely (even '
                               'history db and plugins)'))
        self.add_main_option('verbose', ord('v'), GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE,
                             _('Print xml stanzas and other debug '
                               'information'))
        self.add_main_option('windev', ord('w'), GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE,
                             _('Print stdout/stderr to the console '
                               'on Windows'))
        self.add_main_option('profile', ord('p'), GLib.OptionFlags.NONE,
                             GLib.OptionArg.STRING,
                             _('Use defined profile in configuration '
                               'directory'), 'NAME')
        self.add_main_option('config-path', ord('c'), GLib.OptionFlags.NONE,
                             GLib.OptionArg.STRING,
                             _('Set configuration directory'), 'PATH')
        self.add_main_option('loglevel', ord('l'), GLib.OptionFlags.NONE,
                             GLib.OptionArg.STRING,
                             _('Configure logging system'), 'LEVEL')

        self.profile = ''
        self.config_path = None
        self.profile_separation = False
        self.interface = None

        GLib.set_prgname('gajim')
        GLib.set_application_name('Gajim')

    def do_startup(self):
        Gtk.Application.do_startup(self)

    def do_activate(self):
        # If a second instance starts do_activate() is called
        # We bringt the Roster window to the front, GTK exits afterwards.
        if self.interface:
            self.interface.roster.window.present()
            return

        Gtk.Application.do_activate(self)

        if os.name == 'nt':
            import locale
            import gettext
            APP = 'gajim'
            DIR = '../po'
            lang, enc = locale.getdefaultlocale()
            os.environ['LANG'] = lang
            gettext.bindtextdomain(APP, DIR)
            gettext.textdomain(APP)
            gettext.install(APP, DIR)

        #    locale.setlocale(locale.LC_ALL, '')
        #    import ctypes
        #    import ctypes.util
        #    libintl_path = ctypes.util.find_library('intl')
        #    if libintl_path == None:
        #        local_intl = os.path.join('gtk', 'bin', 'intl.dll')
        #        if os.path.exists(local_intl):
        #            libintl_path = local_intl
        #    if libintl_path == None:
        #        raise ImportError('intl.dll library not found')
        #    libintl = ctypes.cdll.LoadLibrary(libintl_path)
        #    libintl.bindtextdomain(APP, DIR)
        #    libintl.bind_textdomain_codeset(APP, 'UTF-8')

        if os.name == 'nt':
            # needed for docutils
            sys.path.append('.')

        import locale

        import common.configpaths
        common.configpaths.gajimpaths.init(
            self.config_path, self.profile, self.profile_separation)

        if os.name == 'nt':
            plugins_locale_dir = os.path.join(common.configpaths.gajimpaths[
                'PLUGINS_USER'], 'locale').encode(locale.getpreferredencoding())
        #    libintl.bindtextdomain('gajim_plugins', plugins_locale_dir)
        #    libintl.bind_textdomain_codeset('gajim_plugins', 'UTF-8')

        if os.name == 'nt':
            warnings.filterwarnings(action='ignore')

        if Gtk.Widget.get_default_direction() == Gtk.TextDirection.RTL:
            i18n.direction_mark = '\u200F'
        pritext = ''

        from common import exceptions
        try:
            from common import gajim
        except exceptions.DatabaseMalformed:
            pritext = _('Database Error')
            sectext = _('The database file (%s) cannot be read. Try to repair it (see '
                'http://trac.gajim.org/wiki/DatabaseBackup) or remove it (all history '
                'will be lost).') % common.logger.LOG_DB_PATH
        else:
            from common import logger
            gajim.logger = logger.Logger()
            from common import caps_cache
            caps_cache.initialize(gajim.logger)
            from common import dbus_support
            if dbus_support.supported:
                from music_track_listener import MusicTrackListener

            from ctypes import CDLL
            from ctypes.util import find_library
            import platform

            sysname = platform.system()
            if sysname in ('Linux', 'FreeBSD', 'OpenBSD', 'NetBSD'):
                libc = CDLL(find_library('c'))

                # The constant defined in <linux/prctl.h> which is used to set the name
                # of the process.
                PR_SET_NAME = 15

                if sysname == 'Linux':
                    libc.prctl(PR_SET_NAME, 'gajim')
                elif sysname in ('FreeBSD', 'OpenBSD', 'NetBSD'):
                    libc.setproctitle('gajim')

        #    if Gtk.pygtk_version < (2, 22, 0):
        #        pritext = _('Gajim needs PyGTK 2.22 or above')
        #        sectext = _('Gajim needs PyGTK 2.22 or above to run. Quiting...')
        #    elif Gtk.gtk_version < (2, 22, 0):
        #    if (Gtk.get_major_version(), Gtk.get_minor_version(),
        #    Gtk.get_micro_version()) < (2, 22, 0):
        #        pritext = _('Gajim needs GTK 2.22 or above')
        #        sectext = _('Gajim needs GTK 2.22 or above to run. Quiting...')

            from common import check_paths

            if os.name == 'nt':
                try:
                    import winsound # windows-only built-in module for playing wav
                    import win32api # do NOT remove. we req this module
                except Exception:
                    pritext = _('Gajim needs pywin32 to run')
                    sectext = _('Please make sure that Pywin32 is installed on your '
                        'system. You can get it at %s') % \
                        'http://sourceforge.net/project/showfiles.php?group_id=78018'

        if pritext:
            dlg = Gtk.MessageDialog(None,
                    Gtk.DialogFlags.DESTROY_WITH_PARENT | Gtk.DialogFlags.MODAL,
                    Gtk.MessageType.ERROR, Gtk.ButtonsType.OK, message_format = pritext)

            dlg.format_secondary_text(sectext)
            dlg.run()
            dlg.destroy()
            sys.exit()

        del pritext

        #import gtkexcepthook

        import signal
        import gtkgui_helpers

        gajimpaths = common.configpaths.gajimpaths

        pid_filename = gajimpaths['PID_FILE']
        config_filename = gajimpaths['CONFIG_FILE']

        # Seed the OpenSSL pseudo random number generator from file and initialize
        RNG_SEED = gajimpaths['RNG_SEED']
        PYOPENSSL_PRNG_PRESENT = False
        try:
            import OpenSSL.rand
            from common import crypto
            PYOPENSSL_PRNG_PRESENT = True
            # Seed from file
            try:
                OpenSSL.rand.load_file(RNG_SEED)
            except TypeError:
                OpenSSL.rand.load_file(RNG_SEED.encode('utf-8'))
            crypto.add_entropy_sources_OpenSSL()
            try:
                OpenSSL.rand.write_file(RNG_SEED)
            except TypeError:
                OpenSSL.rand.write_file(RNG_SEED.encode('utf-8'))
        except ImportError:
            log.info("PyOpenSSL PRNG not available")

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
                    from ctypes import (windll, c_ulong, c_int, Structure, c_char)
                    from ctypes import (POINTER, pointer, sizeof)
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

                kernel = windll.kernel32
                kernel.CreateToolhelp32Snapshot.argtypes = c_ulong, c_ulong,
                kernel.CreateToolhelp32Snapshot.restype = c_int
                kernel.Process32First.argtypes = c_int, POINTER(PROCESSENTRY32),
                kernel.Process32First.restype = c_int
                kernel.Process32Next.argtypes = c_int, POINTER(PROCESSENTRY32),
                kernel.Process32Next.restype = c_int

                def get_p(pid_):
                    TH32CS_SNAPPROCESS = 2
                    CreateToolhelp32Snapshot = kernel.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
                    assert CreateToolhelp32Snapshot > 0, 'CreateToolhelp32Snapshot failed'
                    pe32 = PROCESSENTRY32()
                    pe32.dwSize = sizeof( PROCESSENTRY32 )
                    f3 = kernel.Process32First(CreateToolhelp32Snapshot, pointer(pe32))
                    while f3:
                        if pe32.th32ProcessID == pid_:
                            return pe32.szExeFile
                        f3 = kernel.Process32Next(CreateToolhelp32Snapshot, pointer(pe32))

                if get_p(pid) in ('python.exe', 'gajim.exe'):
                    return True
                return False
            try:
                if not os.path.exists('/proc'):
                    return True # no /proc, assume Gajim is running

                try:
                    f1 = open('/proc/%d/cmdline'% pid)
                except IOError as e1:
                    if e1.errno == errno.ENOENT:
                        return False # file/pid does not exist
                    raise

                n = f1.read().lower()
                f1.close()
                if n.find('gajim') < 0:
                    return False
                return True # Running Gajim found at pid
            except Exception:
                traceback.print_exc()

            # If we are here, pidfile exists, but some unexpected error occured.
            # Assume Gajim is running.
            return True

        def show_remote_gajim_roster():
            try:
                import dbus

                OBJ_PATH = '/org/gajim/dbus/RemoteObject'
                INTERFACE = 'org.gajim.dbus.RemoteInterface'
                SERVICE = 'org.gajim.dbus'

                # Attempt to call show_roster
                dbus.Interface(dbus.SessionBus().get_object(SERVICE, OBJ_PATH), INTERFACE).__getattr__("show_roster")()

                return True
            except Exception:
                return False

        if pid_alive():
            if (show_remote_gajim_roster()):
                print("Gajim is already running, bringing the roster to front...")
                sys.exit(0)
            pixs = []
            for size in (16, 32, 48, 64, 128):
                pix = gtkgui_helpers.get_icon_pixmap('gajim', size)
                if pix:
                    pixs.append(pix)
            if pixs:
                # set the icon to all windows
                Gtk.Window.set_default_icon_list(pixs)
            pritext = _('Gajim is already running')
            sectext = _('Another instance of Gajim seems to be running\nRun anyway?')
            dialog = dialogs.YesNoDialog(pritext, sectext)
            dialog.popup()
            if dialog.run() != Gtk.ResponseType.YES:
                sys.exit(3)
            dialog.destroy()
            # run anyway, delete pid and useless global vars
            if os.path.exists(pid_filename):
                os.remove(pid_filename)
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
            f2 = open(pid_filename, 'w')
            f2.write(str(os.getpid()))
            f2.close()
        except IOError as e2:
            dlg = dialogs.ErrorDialog(_('Disk Write Error'), str(e2))
            dlg.run()
            dlg.destroy()
            sys.exit()
        del pid_dir

        def on_exit():
            # Save the entropy from OpenSSL PRNG
            if PYOPENSSL_PRNG_PRESENT:
                try:
                    OpenSSL.rand.write_file(RNG_SEED)
                except TypeError:
                    OpenSSL.rand.write_file(RNG_SEED.encode('utf-8'))
            # delete pid file on normal exit
            if os.path.exists(pid_filename):
                os.remove(pid_filename)
            # Shutdown GUI and save config
            if hasattr(gajim.interface, 'roster') and gajim.interface.roster:
                gajim.interface.roster.prepare_quit()

        import atexit
        atexit.register(on_exit)

        from gui_interface import Interface

        def sigint_cb(num, stack):
            sys.exit(5)
        # ^C exits the application normally to delete pid file
        signal.signal(signal.SIGINT, sigint_cb)
        signal.signal(signal.SIGTERM, sigint_cb)

        log.info("Encodings: d:%s, fs:%s, p:%s", sys.getdefaultencoding(), \
                sys.getfilesystemencoding(), locale.getpreferredencoding())

        check_paths.check_and_possibly_create_paths()

        self.interface = Interface()
        self.interface.run(self)

    def do_command_line(self, command_line: Gio.ApplicationCommandLine) -> int:
        Gtk.Application.do_command_line(self, command_line)
        options = command_line.get_options_dict()
        if options.contains('quiet'):
            logging_helpers.set_quiet()
        if options.contains('separate'):
            self.profile_separation = True
        if options.contains('verbose'):
            logging_helpers.set_verbose()
        if options.contains('profile'):
            variant = options.lookup_value('profile')
            self.profile = variant.get_string()
        if options.contains('loglevel'):
            variant = options.lookup_value('loglevel')
            string = variant.get_string()
            logging_helpers.set_loglevels(string)
        if options.contains('config-path'):
            variant = options.lookup_value('config-path')
            self.config_path = variant.get_string()
        self.activate()
        return 0
