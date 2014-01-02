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
from gi.repository import GdkPixbuf
from gi.repository import GObject
from gi.repository import GLib
import base64
import mimetypes
import os
import time

import gtkgui_helpers
import dialogs
import vcard

from common import gajim
from common import ged


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
        self.jid = gajim.get_jid_from_account(account)

        self.dialog = None
        self.avatar_mime_type = None
        self.avatar_encoded = None
        self.message_id = self.statusbar.push(self.context_id,
            _('Retrieving profile...'))
        self.update_progressbar_timeout_id = GLib.timeout_add(100,
            self.update_progressbar)
        self.remove_statusbar_timeout_id = None

        # Create Image for avatar button
        image = Gtk.Image()
        self.xml.get_object('PHOTO_button').set_image(image)
        self.xml.connect_signals(self)
        gajim.ged.register_event_handler('vcard-published', ged.GUI1,
            self._nec_vcard_published)
        gajim.ged.register_event_handler('vcard-not-published', ged.GUI1,
            self._nec_vcard_not_published)
        gajim.ged.register_event_handler('vcard-received', ged.GUI1,
            self._nec_vcard_received)
        self.window.show_all()
        self.xml.get_object('ok_button').grab_focus()

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
        gajim.ged.remove_event_handler('vcard-published', ged.GUI1,
            self._nec_vcard_published)
        gajim.ged.remove_event_handler('vcard-not-published', ged.GUI1,
            self._nec_vcard_not_published)
        gajim.ged.remove_event_handler('vcard-received', ged.GUI1,
            self._nec_vcard_received)
        del gajim.interface.instances[self.account]['profile']
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
        self.avatar_mime_type = None

    def on_set_avatar_button_clicked(self, widget):
        def on_ok(widget, path_to_file):
            must_delete = False
            filesize = os.path.getsize(path_to_file) # in bytes
            invalid_file = False
            msg = ''
            if os.path.isfile(path_to_file):
                stat = os.stat(path_to_file)
                if stat[6] == 0:
                    invalid_file = True
                    msg = _('File is empty')
            else:
                invalid_file = True
                msg = _('File does not exist')
            if not invalid_file and filesize > 16384: # 16 kb
                try:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file(path_to_file)
                    # get the image at 'notification size'
                    # and hope that user did not specify in ACE crazy size
                    scaled_pixbuf = gtkgui_helpers.get_scaled_pixbuf(pixbuf,
                            'tooltip')
                except GObject.GError as msg: # unknown format
                    # msg should be string, not object instance
                    msg = str(msg)
                    invalid_file = True
            if invalid_file:
                if True: # keep identation
                    dialogs.ErrorDialog(_('Could not load image'), msg,
                        transient_for=self.window)
                    return
            if filesize > 16384:
                if scaled_pixbuf:
                    path_to_file = os.path.join(gajim.TMP,
                            'avatar_scaled.png')
                    scaled_pixbuf.savev(path_to_file, 'png', [], [])
                    must_delete = True

            with open(path_to_file, 'rb') as fd:
                data = fd.read()
            pixbuf = gtkgui_helpers.get_pixbuf_from_data(data)
            try:
                # rescale it
                pixbuf = gtkgui_helpers.get_scaled_pixbuf(pixbuf, 'vcard')
            except AttributeError: # unknown format
                dialogs.ErrorDialog(_('Could not load image'),
                    transient_for=self.window)
                return
            self.dialog.destroy()
            self.dialog = None
            button = self.xml.get_object('PHOTO_button')
            image = button.get_image()
            image.set_from_pixbuf(pixbuf)
            button.show()
            text_button = self.xml.get_object('NOPHOTO_button')
            text_button.hide()
            self.avatar_encoded = base64.b64encode(data).decode('utf-8')
            # returns None if unknown type
            self.avatar_mime_type = mimetypes.guess_type(path_to_file)[0]
            if must_delete:
                try:
                    os.remove(path_to_file)
                except OSError:
                    gajim.log.debug('Cannot remove %s' % path_to_file)

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
            self.dialog = dialogs.AvatarChooserDialog(on_response_ok = on_ok,
                    on_response_cancel = on_cancel, on_response_clear = on_clear)

    def on_PHOTO_button_press_event(self, widget, event):
        """
        If right-clicked, show popup
        """
        if event.button == 3 and self.avatar_encoded: # right click
            menu = Gtk.Menu()

            # Try to get pixbuf
            pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(self.jid,
                    use_local=False)

            if pixbuf not in (None, 'ask'):
                nick = gajim.config.get_per('accounts', self.account, 'name')
                menuitem = Gtk.ImageMenuItem.new_from_stock(Gtk.STOCK_SAVE_AS,
                    None)
                menuitem.connect('activate',
                    gtkgui_helpers.on_avatar_save_as_menuitem_activate,
                    self.jid, nick)
                menu.append(menuitem)
            # show clear
            menuitem = Gtk.ImageMenuItem.new_from_stock(Gtk.STOCK_CLEAR, None)
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
                pixbuf, self.avatar_encoded, self.avatar_mime_type = \
                        vcard.get_avatar_pixbuf_encoded_mime(vcard_[i])
                if not pixbuf:
                    image.set_from_pixbuf(None)
                    button.hide()
                    text_button.show()
                    continue
                pixbuf = gtkgui_helpers.get_scaled_pixbuf(pixbuf, 'vcard')
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
                            vcard_[i], 0)
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

    def _nec_vcard_received(self, obj):
        if obj.conn.name != self.account:
            return
        if obj.jid != self.jid:
            return
        self.set_values(obj.vcard_dict)

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
        return vcard_

    def on_ok_button_clicked(self, widget):
        if self.update_progressbar_timeout_id:
            # Operation in progress
            return
        if gajim.connections[self.account].connected < 2:
            dialogs.ErrorDialog(_('You are not connected to the server'),
                    _('Without a connection, you can not publish your contact '
                    'information.'), transient_for=self.window)
            return
        vcard_ = self.make_vcard()
        nick = ''
        if 'NICKNAME' in vcard_:
            nick = vcard_['NICKNAME']
            gajim.connections[self.account].send_nickname(nick)
        if nick == '':
            nick = gajim.config.get_per('accounts', self.account, 'name')
        gajim.nicks[self.account] = nick
        gajim.connections[self.account].send_vcard(vcard_)
        self.message_id = self.statusbar.push(self.context_id,
                _('Sending profile...'))
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
