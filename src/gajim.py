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
    profile_ = ''
    config_path_ = None

    try:
        shortargs = 'hqvl:p:c:'
        longargs = 'help quiet verbose loglevel= profile= config_path='
        opts = getopt.getopt(sys.argv[1:], shortargs, longargs.split())[0]
    except getopt.error, msg1:
        print msg1
        print 'for help use --help'
        sys.exit(2)
    for o, a in opts:
        if o in ('-h', '--help'):
            print 'gajim [--help] [--quiet] [--verbose] ' + \
                '[--loglevel subsystem=level[,subsystem=level[...]]] ' + \
                '[--profile name] [--config-path]'
            sys.exit()
        elif o in ('-q', '--quiet'):
            logging_helpers.set_quiet()
        elif o in ('-v', '--verbose'):
            logging_helpers.set_verbose()
        elif o in ('-p', '--profile'): # gajim --profile name
            profile_ = a
        elif o in ('-l', '--loglevel'):
            logging_helpers.set_loglevels(a)
        elif o in ('-c', '--config-path'):
            config_path_ = a
    return profile_, config_path_

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
            fname = os.path.join(common.configpaths.gajimpaths.cache_root,
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
except Warning, msg2:
    if str(msg2) == 'could not open display':
        print >> sys.stderr, _('Gajim needs X server to run. Quiting...')
    else:
        print >> sys.stderr, _('importing PyGTK failed: %s') % str(msg2)
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
    sectext = _('The database file (%s) cannot be read. Try to repair it (see '
        'http://trac.gajim.org/wiki/DatabaseBackup) or remove it (all history '
        'will be lost).') % common.logger.LOG_DB_PATH
else:
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

    if gtk.pygtk_version < (2, 16, 0):
        pritext = _('Gajim needs PyGTK 2.16 or above')
        sectext = _('Gajim needs PyGTK 2.16 or above to run. Quiting...')
    elif gtk.gtk_version < (2, 16, 0):
        pritext = _('Gajim needs GTK 2.16 or above')
        sectext = _('Gajim needs GTK 2.16 or above to run. Quiting...')

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

from common.xmpp import Message as XmppMessage

try:
    import otr, otr_windows
    gajim.otr_module = otr
    gajim.otr_windows = otr_windows
    gajim.otr_v320 = hasattr(gajim.otr_module, "OTRL_TLV_SMP1Q")
    import time
    from message_control import TYPE_CHAT
except ImportError:
    gajim.otr_module = None
    gajim.otr_windows = None

def add_appdata(data, context):
    account = data
    context.app_data = otr_windows.ContactOtrSMPWindow(
        unicode(context.username), account)

gajim.otr_add_appdata = add_appdata

def otr_dialog_destroy(widget, *args, **kwargs):
    widget.destroy()

class OtrlMessageAppOps:
    def __init__(self):
        self.fpr_model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING,
                gobject.TYPE_BOOLEAN, gobject.TYPE_STRING, gobject.TYPE_STRING,
                gobject.TYPE_STRING)

    def gajim_log(self, msg, account, fjid, no_print=False,
    is_status_message=True, thread_id=None):
        if not isinstance(fjid, unicode):
            fjid = unicode(fjid)
        if not isinstance(account, unicode):
            account = unicode(account)
        resource = gajim.get_resource_from_jid(fjid)
        jid = gajim.get_jid_without_resource(fjid)
        tim = time.localtime()

        if is_status_message is True:
            if not no_print:
                ctrl = self.get_control(fjid, account)
                if ctrl:
                    ctrl.print_conversation_line(u'[OTR] %s' % \
                        msg, 'status', '', None)
            id = gajim.logger.write('chat_msg_recv', fjid,
                message=u'[OTR: %s]' % msg, tim=tim)
            # gajim.logger.write() only marks a message as unread
            # (and so only returns an id) when fjid is a real contact
            # (NOT if it's a GC private chat)
            if id:
                gajim.logger.set_read_messages([id])
        else:
            session = gajim.connections[account].\
                    get_or_create_session(fjid, thread_id)

            session.received_thread_id |= bool(thread_id)
            session.last_receive = time.time()

            if not session.control:
                # look for an existing chat control without a
                # session
                ctrl = self.get_control(fjid, account)
                if ctrl:
                    session.control = ctrl
                    session.control.set_session(session)

            msg_id = gajim.logger.write('chat_msg_recv', fjid,
                message=u'[OTR: %s]' % msg, tim=tim)
            session.roster_message(jid, msg, tim=tim, msg_id=msg_id,
                msg_type="chat", resource=resource)

    def get_control(self, fjid, account):
        # first try to get the window with the full jid
        ctrl = gajim.interface.msg_win_mgr.get_control(fjid, account)
        if ctrl:
            # got one, be happy
            return ctrl

        # otherwise try without the resource
        ctrl = gajim.interface.msg_win_mgr.get_control(
            gajim.get_jid_without_resource(fjid), account)
        # but only use it when it is not a GC window
        if ctrl and ctrl.TYPE_ID == TYPE_CHAT:
            return ctrl

    def policy(self, opdata=None, context=None):
        policy = gajim.config.get_per('contacts', context.username,
            "otr_flags")
        if policy < 0:
            policy = gajim.config.get_per('contacts',
                gajim.get_jid_without_resource(
                context.username), 'otr_flags')
        if policy < 0:
            policy = gajim.config.get_per('accounts',
                opdata['account'], 'otr_flags')
        return policy

    def create_privkey(self, opdata='', accountname='', protocol=''):
        dialog = gtk.Dialog(
            title   = _('Generating...'),
            parent  = gajim.interface.roster.window,
            flags   = gtk.DIALOG_MODAL,
            buttons = (gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE))
        permlabel = gtk.Label(_('Generating a private key for %s...') \
            % accountname)
        permlabel.set_padding(20, 20)
        dialog.set_response_sensitive(gtk.RESPONSE_CLOSE, False)
        dialog.connect('destroy', otr_dialog_destroy)
        dialog.connect('response', otr_dialog_destroy)
        dialog.vbox.pack_start(permlabel)
        dialog.get_root_window().raise_()
        dialog.show_all()
        dialog.map()
        for c in dialog.get_children():
            c.show_now()
            c.map()

        while gtk.events_pending():
            gtk.main_iteration(block = False)

        otr.otrl_privkey_generate(
            gajim.connections[opdata['account']].otr_userstates,
            os.path.join(gajimpaths.data_root,
            '%s.key' % opdata['account']).encode(),
            accountname, gajim.OTR_PROTO)
        permlabel.set_text(_('Generating a private key for %s...\n' \
            'done.') % accountname)
        dialog.set_response_sensitive(gtk.RESPONSE_CLOSE, True)

    def is_logged_in(self, opdata={}, accountname='', protocol='',
    recipient=""):
        contact = gajim.contacts.get_contact_from_full_jid(
            opdata['account'], recipient)
        if contact:
            return contact.show \
                in ['dnd', 'xa', 'chat', 'online', 'away',
                'invisible']
        return 0

    def inject_message(self, opdata=None, accountname='', protocol='',
    recipient='', message=''):
        msg_type = otr.otrl_proto_message_type(message)

        if "msgid" not in opdata:
            opdata['msgid'] = []

        if 'kwargs' not in opdata or 'urgent' in opdata:
            # don't use send_message here to have the message
            # sent immediatly. This results in being able to
            # disconnect from OTR sessions before quitting
            stanza = XmppMessage(to = recipient,
                body = message, typ='chat')
            opdata['msgid'].append(
                gajim.connections[opdata['account']]. \
                connection.send(stanza, now = True))
            return

        if msg_type == otr.OTRL_MSGTYPE_QUERY:
            # split away XHTML-contaminated explanatory message
            message = unicode(message.splitlines()[0])
            message += _(u'\nThis user has requested an ' \
                'Off-the-Record private conversation. ' \
                'However, you do not have a plugin to ' \
                'support that.\n' \
                'See http://otr.cypherpunks.ca/ for more ' \
                'information.')

            opdata['msgid'].append(
                gajim.connections[opdata['account']]. \
                connection.send(common.xmpp.Message(
                    to=recipient, body=message, typ='chat')
                ))
            return

        jid, opdata["resource"] = gajim.get_room_and_nick_from_fjid(
                recipient)

        opdata['msgid'].append(gajim.connections[opdata['account']]. \
                send_message(jid, message, **opdata['kwargs']))

    def notify(sef, opdata=None, username='', **kwargs):
        self.gajim_log('Notify: ' + str(kwargs), opdata['account'],
            username)

    def display_otr_message(self, opdata=None, username="", msg="", **kwargs):
        self.gajim_log('OTR Message: ' + msg, opdata['account'],
            username, is_status_message=False,
            thread_id=opdata['thread_id'])
        return 0

    enc_tip = 'A private chat session <i>is established</i> to this contact ' \
            'with this fingerprint'
    unused_tip = 'A private chat session is established to this contact using ' \
            '<i>another</i> fingerprint'
    ended_tip = 'The private chat session to this contact has <i>ended</i>'
    inactive_tip = 'Communication to this contact is currently ' \
            '<i>unencrypted</i>'

    def update_context_list(self, **kwargs):
        self.fpr_model.clear()
        for conn in gajim.connections.itervalues():
            ctx = conn.otr_userstates.context_root
            while ctx is not None:
                fpr = ctx.fingerprint_root.next
                while fpr:
                    if ctx.msgstate == otr.OTRL_MSGSTATE_ENCRYPTED:
                        if ctx.active_fingerprint.fingerprint == fpr.fingerprint:
                            state = "encrypted"
                            tip = self.enc_tip
                        else:
                            state = "unused"
                            tip = self.unused_tip
                    elif ctx.msgstate == otr.OTRL_MSGSTATE_FINISHED:
                        state = "finished"
                        tip = self.ended_tip
                    else:
                        state = 'inactive'
                        tip = self.inactive_tip

                    self.fpr_model.append(
                                (ctx.username, state, bool(fpr.trust),
                                '<tt>%s</tt>' % \
                                        otr.otrl_privkey_hash_to_human(fpr.fingerprint),
                                ctx.accountname, tip)
                            )
                    fpr = fpr.next
                ctx = ctx.next

    def protocol_name(self, opdata=None, protocol=""):
        return 'XMPP'

    def new_fingerprint(self, opdata=None, username='', fingerprint='',
    **kwargs):
        self.gajim_log('New fingerprint for %s: %s' % (username,
            otr.otrl_privkey_hash_to_human(fingerprint)),
            opdata['account'], username)

    def write_fingerprints(self, opdata=''):
        otr.otrl_privkey_write_fingerprints(
            gajim.connections[opdata['account']].otr_userstates,
            os.path.join(gajimpaths.data_root, '%s.fpr' % \
            opdata['account']).encode())

    def gone_secure(self, opdata='', context=None):
        trust = context.active_fingerprint.trust \
            and 'verified' or 'unverified'
        self.gajim_log('%s secured OTR connection started' % trust,
            opdata['account'], context.username, no_print = True)

        ctrl = self.get_control(context.username, opdata['account'])
        if ctrl:
            ctrl.update_otr(True)

    def gone_insecure(self, opdata='', context=None):
        self.gajim_log('Private conversation with %s lost.',
            opdata['account'], context.username)

        ctrl = self.get_control(context.username, opdata['account'])
        if ctrl:
            ctrl.update_otr(True)

    def still_secure(self, opdata=None, context=None, is_reply=0):
        ctrl = self.get_control(context.username, opdata['account'])
        if ctrl:
            ctrl.update_otr(True)

        self.gajim_log('OTR connection was refreshed',
            opdata['account'], context.username)

    def log_message(self, opdata=None, message=''):
        gajim.log.debug(message)

    def max_message_size(self, **kwargs):
        return 0

    def account_name(self, opdata=None, account='', protocol=''):
        return gajim.get_name_from_jid(opdata['account'],
            unicode(account))

gajim.otr_ui_ops = OtrlMessageAppOps()


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
            from ctypes import (windll, c_ulong, c_int, Structure, c_char)
            from ctypes import (POINTER, pointer, )
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
                super(PROCESSENTRY32, self).__init__(self, 512+9*4)

        k = windll.kernel32
        k.CreateToolhelp32Snapshot.argtypes = c_ulong, c_ulong,
        k.CreateToolhelp32Snapshot.restype = c_int
        k.Process32First.argtypes = c_int, POINTER(PROCESSENTRY32),
        k.Process32First.restype = c_int
        k.Process32Next.argtypes = c_int, POINTER(PROCESSENTRY32),
        k.Process32Next.restype = c_int

        def get_p(pid_):
            h = k.CreateToolhelp32Snapshot(2, 0) # TH32CS_SNAPPROCESS
            assert h > 0, 'CreateToolhelp32Snapshot failed'
            b = pointer(PROCESSENTRY32())
            f3 = k.Process32First(h, b)
            while f3:
                if b.contents.th32ProcessID == pid_:
                    return b.contents.szExeFile
                f3 = k.Process32Next(h, b)

        if get_p(pid) in ('python.exe', 'gajim.exe'):
            return True
        return False
    try:
        if not os.path.exists('/proc'):
            return True # no /proc, assume Gajim is running

        try:
            f1 = open('/proc/%d/cmdline'% pid)
        except IOError, e1:
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
except IOError, e2:
    dlg = dialogs.ErrorDialog(_('Disk Write Error'), str(e2))
    dlg.run()
    dlg.destroy()
    sys.exit()
del pid_dir

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
            def die_cb(dummy):
                gajim.interface.roster.quit_gtkgui_interface()
            gnome.program_init('gajim', gajim.version)
            cli = gnome.ui.master_client()
            cli.connect('die', die_cb)

            path_to_gajim_script = gtkgui_helpers.get_abspath_for_script(
                    'gajim')

            if path_to_gajim_script:
                argv = [path_to_gajim_script]
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
