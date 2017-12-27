# -*- coding:utf-8 -*-
## src/profile_window.py
##
## Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005-2006 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
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

# THIS FILE IS FOR **OUR** PROFILE (when we edit our INFO)

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GdkPixbuf
import base64
import os
import time
import logging
import hashlib

from gajim import gtkgui_helpers
from gajim import dialogs
from gajim import vcard
from gajim.common.const import AvatarSize

from gajim.common import app
from gajim.common import ged

log = logging.getLogger('gajim.profile')

class ProfileWindow:
    """
    Class for our information window
    """

    def __init__(self, account, transient_for=None):
        self.xml = gtkgui_helpers.get_gtk_builder('profile_window.ui')
        self.window = self.xml.get_object('profile_window')
        self.window.set_transient_for(transient_for)
        self.progressbar = self.xml.get_object('progressbar')
        self.statusbar = self.xml.get_object('statusbar')
        self.context_id = self.statusbar.get_context_id('profile')

        self.account = account
        self.jid = app.get_jid_from_account(account)

        self.dialog = None
        self.avatar_mime_type = None
        self.avatar_encoded = None
        self.avatar_sha = None
        self.message_id = self.statusbar.push(self.context_id,
            _('Retrieving profile…'))
        self.update_progressbar_timeout_id = GLib.timeout_add(100,
            self.update_progressbar)
        self.remove_statusbar_timeout_id = None

        # Create Image for avatar button
        image = Gtk.Image()
        self.xml.get_object('PHOTO_button').set_image(image)
        self.xml.connect_signals(self)
        app.ged.register_event_handler('vcard-published', ged.GUI1,
            self._nec_vcard_published)
        app.ged.register_event_handler('vcard-not-published', ged.GUI1,
            self._nec_vcard_not_published)
        self.window.show_all()
        self.xml.get_object('ok_button').grab_focus()
        app.connections[account].request_vcard(
            self._nec_vcard_received, self.jid)

    def on_information_notebook_switch_page(self, widget, page, page_num):
        GLib.idle_add(self.xml.get_object('ok_button').grab_focus)

    def update_progressbar(self):
        self.progressbar.pulse()
        return True # loop forever

    def remove_statusbar(self, message_id):
        self.statusbar.remove(self.context_id, message_id)
        self.remove_statusbar_timeout_id = None

    def on_profile_window_destroy(self, widget):
        if self.update_progressbar_timeout_id is not None:
            GLib.source_remove(self.update_progressbar_timeout_id)
        if self.remove_statusbar_timeout_id is not None:
            GLib.source_remove(self.remove_statusbar_timeout_id)
        app.ged.remove_event_handler('vcard-published', ged.GUI1,
            self._nec_vcard_published)
        app.ged.remove_event_handler('vcard-not-published', ged.GUI1,
            self._nec_vcard_not_published)
        del app.interface.instances[self.account]['profile']
        if self.dialog: # Image chooser dialog
            self.dialog.destroy()

    def on_profile_window_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.window.destroy()

    def on_clear_button_clicked(self, widget):
        # empty the image
        button = self.xml.get_object('PHOTO_button')
        image = button.get_image()
        image.set_from_pixbuf(None)
        button.hide()
        text_button = self.xml.get_object('NOPHOTO_button')
        text_button.show()
        self.avatar_encoded = None
        self.avatar_sha = None
        self.avatar_mime_type = None

    def on_set_avatar_button_clicked(self, widget):
        def on_ok(widget, path_to_file):
            with open(path_to_file, 'rb') as file:
                data = file.read()
            sha = app.interface.save_avatar(data, publish=True)
            if sha is None:
                dialogs.ErrorDialog(
                    _('Could not load image'), transient_for=self.window)
                return

            self.dialog.destroy()
            self.dialog = None

            scale = self.window.get_scale_factor()
            surface = app.interface.get_avatar(sha, AvatarSize.VCARD, scale)

            button = self.xml.get_object('PHOTO_button')
            image = button.get_image()
            image.set_from_surface(surface)
            button.show()
            text_button = self.xml.get_object('NOPHOTO_button')
            text_button.hide()

            self.avatar_sha = sha
            publish = app.interface.get_avatar(sha, publish=True)
            self.avatar_encoded = base64.b64encode(publish).decode('utf-8')
            self.avatar_mime_type = 'image/jpeg'

        def on_clear(widget):
            self.dialog.destroy()
            self.dialog = None
            self.on_clear_button_clicked(widget)

        def on_cancel(widget):
            self.dialog.destroy()
            self.dialog = None

        if self.dialog:
            self.dialog.present()
        else:
            self.dialog = dialogs.AvatarChooserDialog(
                on_response_ok=on_ok, on_response_cancel=on_cancel,
                on_response_clear=on_clear)

    def on_PHOTO_button_press_event(self, widget, event):
        """
        If right-clicked, show popup
        """
        pixbuf = self.xml.get_object('PHOTO_button').get_image().get_pixbuf()
        if event.button == 3 and pixbuf: # right click
            menu = Gtk.Menu()

            nick = app.config.get_per('accounts', self.account, 'name')
            sha = app.contacts.get_avatar_sha(self.account, self.jid)
            menuitem = Gtk.MenuItem.new_with_mnemonic(_('Save _As'))
            menuitem.connect('activate',
                gtkgui_helpers.on_avatar_save_as_menuitem_activate,
                sha, nick)
            menu.append(menuitem)
            # show clear
            menuitem = Gtk.MenuItem.new_with_mnemonic(_('_Clear'))
            menuitem.connect('activate', self.on_clear_button_clicked)
            menu.append(menuitem)
            menu.connect('selection-done', lambda w:w.destroy())
            # show the menu
            menu.show_all()
            menu.attach_to_widget(widget, None)
            menu.popup(None, None, None, None, event.button, event.time)
        elif event.button == 1: # left click
            self.on_set_avatar_button_clicked(widget)

    def on_BDAY_entry_focus_out_event(self, widget, event):
        txt = widget.get_text()
        if not txt:
            return
        try:
            time.strptime(txt, '%Y-%m-%d')
        except ValueError:
            if not widget.is_focus():
                pritext = _('Wrong date format')
                dialogs.ErrorDialog(pritext, _('Format of the date must be '
                    'YYYY-MM-DD'), transient_for=self.window)
                GLib.idle_add(lambda: widget.grab_focus())
            return True

    def set_value(self, entry_name, value):
        try:
            widget = self.xml.get_object(entry_name)
            val = widget.get_text()
            if val:
                value = val + ' / ' + value
            widget.set_text(value)
        except AttributeError:
            pass

    def set_values(self, vcard_):
        button = self.xml.get_object('PHOTO_button')
        image = button.get_image()
        text_button = self.xml.get_object('NOPHOTO_button')
        if not 'PHOTO' in vcard_:
            # set default image
            image.set_from_pixbuf(None)
            button.hide()
            text_button.show()
        for i in vcard_.keys():
            if i == 'PHOTO':
                photo_encoded = vcard_[i]['BINVAL']
                if photo_encoded == '':
                    continue
                photo_decoded = base64.b64decode(photo_encoded.encode('utf-8'))
                pixbuf = gtkgui_helpers.get_pixbuf_from_data(photo_decoded)
                if pixbuf is None:
                    continue
                pixbuf = pixbuf.scale_simple(
                    AvatarSize.PROFILE, AvatarSize.PROFILE,
                    GdkPixbuf.InterpType.BILINEAR)
                image.set_from_pixbuf(pixbuf)
                button.show()
                text_button.hide()
                continue
            if i == 'ADR' or i == 'TEL' or i == 'EMAIL':
                for entry in vcard_[i]:
                    add_on = '_HOME'
                    if 'WORK' in entry:
                        add_on = '_WORK'
                    for j in entry.keys():
                        self.set_value(i + add_on + '_' + j + '_entry', entry[j])
            if isinstance(vcard_[i], dict):
                for j in vcard_[i].keys():
                    self.set_value(i + '_' + j + '_entry', vcard_[i][j])
            else:
                if i == 'DESC':
                    self.xml.get_object('DESC_textview').get_buffer().set_text(
                        vcard_[i], len(vcard_[i].encode('utf-8')))
                else:
                    self.set_value(i + '_entry', vcard_[i])
        if self.update_progressbar_timeout_id is not None:
            if self.message_id:
                self.statusbar.remove(self.context_id, self.message_id)
            self.message_id = self.statusbar.push(self.context_id,
                    _('Information received'))
            self.remove_statusbar_timeout_id = GLib.timeout_add_seconds(3,
                self.remove_statusbar, self.message_id)
            GLib.source_remove(self.update_progressbar_timeout_id)
            self.progressbar.hide()
            self.progressbar.set_fraction(0)
            self.update_progressbar_timeout_id = None

    def _nec_vcard_received(self, jid, resource, room, vcard_):
        self.set_values(vcard_)

    def add_to_vcard(self, vcard_, entry, txt):
        """
        Add an information to the vCard dictionary
        """
        entries = entry.split('_')
        loc = vcard_
        if len(entries) == 3: # We need to use lists
            if entries[0] not in loc:
                loc[entries[0]] = []
            found = False
            for e in loc[entries[0]]:
                if entries[1] in e:
                    e[entries[2]] = txt
                    break
            else:
                loc[entries[0]].append({entries[1]: '', entries[2]: txt})
            return vcard_
        while len(entries) > 1:
            if entries[0] not in loc:
                loc[entries[0]] = {}
            loc = loc[entries[0]]
            del entries[0]
        loc[entries[0]] = txt
        return vcard_

    def make_vcard(self):
        """
        Make the vCard dictionary
        """
        entries = ['FN', 'NICKNAME', 'BDAY', 'EMAIL_HOME_USERID', 'URL',
                'TEL_HOME_NUMBER', 'N_FAMILY', 'N_GIVEN', 'N_MIDDLE', 'N_PREFIX',
                'N_SUFFIX', 'ADR_HOME_STREET', 'ADR_HOME_EXTADR', 'ADR_HOME_LOCALITY',
                'ADR_HOME_REGION', 'ADR_HOME_PCODE', 'ADR_HOME_CTRY', 'ORG_ORGNAME',
                'ORG_ORGUNIT', 'TITLE', 'ROLE', 'TEL_WORK_NUMBER', 'EMAIL_WORK_USERID',
                'ADR_WORK_STREET', 'ADR_WORK_EXTADR', 'ADR_WORK_LOCALITY',
                'ADR_WORK_REGION', 'ADR_WORK_PCODE', 'ADR_WORK_CTRY']
        vcard_ = {}
        for e in entries:
            txt = self.xml.get_object(e + '_entry').get_text()
            if txt != '':
                vcard_ = self.add_to_vcard(vcard_, e, txt)

        # DESC textview
        buff = self.xml.get_object('DESC_textview').get_buffer()
        start_iter = buff.get_start_iter()
        end_iter = buff.get_end_iter()
        txt = buff.get_text(start_iter, end_iter, False)
        if txt != '':
            vcard_['DESC'] = txt

        # Avatar
        if self.avatar_encoded:
            vcard_['PHOTO'] = {'BINVAL': self.avatar_encoded}
            if self.avatar_mime_type:
                vcard_['PHOTO']['TYPE'] = self.avatar_mime_type
        return vcard_, self.avatar_sha

    def on_ok_button_clicked(self, widget):
        if self.update_progressbar_timeout_id:
            # Operation in progress
            return
        if app.connections[self.account].connected < 2:
            dialogs.ErrorDialog(_('You are not connected to the server'),
                    _('Without a connection, you can not publish your contact '
                    'information.'), transient_for=self.window)
            return
        vcard_, sha = self.make_vcard()
        nick = ''
        if 'NICKNAME' in vcard_:
            nick = vcard_['NICKNAME']
            app.connections[self.account].send_nickname(nick)
        if nick == '':
            app.connections[self.account].retract_nickname()
            nick = app.config.get_per('accounts', self.account, 'name')
        app.nicks[self.account] = nick
        app.connections[self.account].send_vcard(vcard_, sha)
        self.message_id = self.statusbar.push(self.context_id,
                _('Sending profile…'))
        self.progressbar.show()
        self.update_progressbar_timeout_id = GLib.timeout_add(100,
            self.update_progressbar)

    def _nec_vcard_published(self, obj):
        if obj.conn.name != self.account:
            return
        if self.update_progressbar_timeout_id is not None:
            GLib.source_remove(self.update_progressbar_timeout_id)
            self.update_progressbar_timeout_id = None
        self.window.destroy()

    def _nec_vcard_not_published(self, obj):
        if obj.conn.name != self.account:
            return
        if self.message_id:
            self.statusbar.remove(self.context_id, self.message_id)
        self.message_id = self.statusbar.push(self.context_id,
            _('Information NOT published'))
        self.remove_statusbar_timeout_id = GLib.timeout_add_seconds(3,
            self.remove_statusbar, self.message_id)
        if self.update_progressbar_timeout_id is not None:
            GLib.source_remove(self.update_progressbar_timeout_id)
            self.progressbar.set_fraction(0)
            self.update_progressbar_timeout_id = None
        dialogs.InformationDialog(_('vCard publication failed'),
            _('There was an error while publishing your personal information, '
            'try again later.'), transient_for=self.window)

    def on_cancel_button_clicked(self, widget):
        self.window.destroy()
