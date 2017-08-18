# -*- coding:utf-8 -*-
## src/features_window.py
##
## Copyright (C) 2007 Jean-Marie Traissard <jim AT lapin.org>
##                    Julien Pivotto <roidelapluie AT gmail.com>
##                    Stefan Bethge <stefan AT lanpartei.de>
##                    Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2007-2014 Yann Leboulanger <asterix AT lagaule.org>
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
import gi
from gi.repository import Gtk, Gdk
from gajim import gtkgui_helpers

from gajim.common import app
from gajim.common.i18n import Q_

class FeaturesWindow:
    """
    Class for features window
    """

    def __init__(self):
        self.xml = gtkgui_helpers.get_gtk_builder('features_window.ui')
        self.window = self.xml.get_object('features_window')
        self.window.set_transient_for(app.interface.roster.window)
        treeview = self.xml.get_object('features_treeview')
        self.desc_label = self.xml.get_object('feature_desc_label')

        # {name: (available_function, unix_text, windows_text)}
        self.features = {
            _('SSL certificate validation'): (self.pyopenssl_available,
                _('A library used to validate server certificates to ensure a secure connection.'),
                _('Requires python-pyopenssl > 0.12 and pyasn1.'),
                _('Requires python-pyopenssl > 0.12 and pyasn1.')),
            _('Bonjour / Zeroconf'): (self.zeroconf_available,
                _('Serverless chatting with autodetected clients in a local network.'),
                _('Requires python-avahi.'),
                _('Requires pybonjour and bonjour SDK running (http://developer.apple.com/opensource/).')),
            _('Command line'): (self.dbus_available,
                _('A script to control Gajim via commandline.'),
                _('Requires python-dbus.'),
                _('Feature not available under Windows.')),
            _('OpenPGP message encryption'): (self.gpg_available,
                _('Ability to encrypting chat messages with OpenPGP.'),
                _('Requires gpg and python-gnupg (http://code.google.com/p/python-gnupg/).'),
                _('Requires gpg.exe in PATH.')),
            _('Network-Watcher'): (self.network_watcher_available,
                _('Autodetection of network status.'),
                _('Requires gnome-network-manager'),
                _('Feature not available under Windows.')),
            _('Password encryption'): (self.some_keyring_available,
                _('Passwords can be stored securely and not just in plaintext.'),
                _('Requires libsecret and a provider (such as GNOME Keyring and KSecretService).'),
                _('On Windows the Windows Credential Vault is used.')),
            _('Spell Checker'): (self.speller_available,
                _('Spellchecking of composed messages.'),
                _('Requires libgtkspell.'),
                _('Requires libgtkspell and libenchant.')),
            _('Notification'): (self.notification_available,
                _('Passive popups notifying for new events.'),
                _('Requires python-notify or instead python-dbus in conjunction with notification-daemon.'),
                _('Feature not available under Windows.')),
            _('Automatic status'): (self.idle_available,
                _('Ability to measure idle time, in order to set auto status.'),
                _('Requires libxss library.'),
                _('Requires python2.5.')),
            _('End to End message encryption'): (self.pycrypto_available,
                _('Encrypting chat messages.'),
                _('Requires python-crypto.'),
                _('Requires python-crypto.')),
            _('RST Generator'): (self.docutils_available,
                _('Generate XHTML output from RST code (see http://docutils.sourceforge.net/docs/ref/rst/restructuredtext.html).'),
                _('Requires python-docutils.'),
                _('Requires python-docutils.')),
            _('Audio / Video'): (self.farstream_available,
                _('Ability to start audio and video chat.'),
                _('Requires gir1.2-farstream-0.2, gir1.2-gstreamer-1.0, gstreamer1.0-libav and gstreamer1.0-plugins-ugly.'),
                _('Feature not available under Windows.')),
            _('UPnP-IGD'): (self.gupnp_igd_available,
                _('Ability to request your router to forward port for file transfer.'),
                _('Requires gir1.2-gupnpigd-1.0.'),
                _('Feature not available under Windows.')),
            _('UPower'): (self.upower_available,
                _('Ability to disconnect properly just before suspending the machine.'),
                _('Requires upower and python-dbus.'),
                _('Feature not available under Windows.')),
        }

        # name, supported
        self.model = Gtk.ListStore(str, bool)
        treeview.set_model(self.model)

        col = Gtk.TreeViewColumn(Q_('?features:Available'))
        treeview.append_column(col)
        cell = Gtk.CellRendererToggle()
        cell.set_property('radio', True)
        col.pack_start(cell, True)
        col.add_attribute(cell, 'active', 1)

        col = Gtk.TreeViewColumn(_('Feature'))
        treeview.append_column(col)
        cell = Gtk.CellRendererText()
        col.pack_start(cell, True)
        col.add_attribute(cell, 'text', 0)

        # Fill model
        for feature in self.features:
            func = self.features[feature][0]
            rep = func()
            self.model.append([feature, rep])

        self.model.set_sort_column_id(0, Gtk.SortType.ASCENDING)

        self.xml.connect_signals(self)
        self.window.show_all()
        self.xml.get_object('close_button').grab_focus()

    def on_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.window.destroy()

    def on_close_button_clicked(self, widget):
        self.window.destroy()

    def on_features_treeview_cursor_changed(self, widget):
        selection = widget.get_selection()
        if not selection:
            return
        rows = selection.get_selected_rows()[1]
        if not rows:
            return
        path = rows[0]
        feature = self.model[path][0]
        text = self.features[feature][1] + '\n'
        if os.name == 'nt':
            text = text + self.features[feature][3]
        else:
            text = text + self.features[feature][2]
        self.desc_label.set_text(text)

    def pyopenssl_available(self):
        try:
            import OpenSSL.SSL
            import OpenSSL.crypto
            ver = OpenSSL.__version__
            ver_l = [int(i) for i in ver.split('.')]
            if ver_l < [0, 12]:
                raise ImportError
            import pyasn1
        except Exception:
            return False
        return True

    def zeroconf_available(self):
        return app.HAVE_ZEROCONF

    def dbus_available(self):
        from gajim.common import dbus_support
        return dbus_support.supported

    def gpg_available(self):
        return app.HAVE_GPG

    def network_watcher_available(self):
        from gajim import network_watcher
        return network_watcher.supported

    def some_keyring_available(self):
        if os.name == 'nt':
            return True
        try:
            gi.require_version('Secret', '1')
            from gi.repository import Secret
        except (ValueError, ImportError):
            return False
        return True

    def speller_available(self):
        try:
            __import__('gajim.gtkspell')
        except ValueError:
            return False
        return True

    def notification_available(self):
        if os.name == 'nt':
            return False
        from gajim.common import dbus_support
        if self.dbus_available() and dbus_support.get_notifications_interface():
            return True
        try:
            __import__('pynotify')
        except Exception:
            return False
        return True

    def idle_available(self):
        from gajim.common import sleepy
        return sleepy.SUPPORTED

    def pycrypto_available(self):
        return app.HAVE_PYCRYPTO

    def docutils_available(self):
        try:
            __import__('docutils')
        except Exception:
            return False
        return True

    def farstream_available(self):
        return app.HAVE_FARSTREAM

    def gupnp_igd_available(self):
        return app.HAVE_UPNP_IGD

    def upower_available(self):
        if os.name == 'nt':
            return False
        from gajim import upower_listener
        return upower_listener.supported
