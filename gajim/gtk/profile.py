# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2005-2006 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
#
# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

import base64
import time
import logging
import hashlib

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib

from gajim.common import app
from gajim.common import ged
from gajim.common.i18n import _
from gajim.common.const import AvatarSize
from gajim.common.helpers import event_filter

from gajim import gtkgui_helpers

from gajim.gtk.dialogs import ErrorDialog
from gajim.gtk.dialogs import InformationDialog
from gajim.gtk.util import get_builder
from gajim.gtk.util import EventHelper
from gajim.gtk.filechoosers import AvatarChooserDialog


log = logging.getLogger('gajim.profile')


class ProfileWindow(Gtk.ApplicationWindow, EventHelper):
    def __init__(self, account):
        Gtk.ApplicationWindow.__init__(self)
        EventHelper.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_title(_('Profile'))

        self.connect('destroy', self.on_profile_window_destroy)
        self.connect('key-press-event', self.on_profile_window_key_press_event)

        self.xml = get_builder('profile_window.ui')
        self.add(self.xml.get_object('profile_box'))
        self.progressbar = self.xml.get_object('progressbar')
        self.statusbar = self.xml.get_object('statusbar')
        self.context_id = self.statusbar.get_context_id('profile')

        self.account = account
        self.jid = app.get_jid_from_account(account)
        account_label = app.config.get_per(
            'accounts', account, 'account_label')
        self.set_value('account_label', account_label)

        self.dialog = None
        self.avatar_mime_type = None
        self.avatar_encoded = None
        self.avatar_sha = None
        self.message_id = self.statusbar.push(self.context_id,
                                              _('Retrieving profile…'))
        self.update_progressbar_timeout_id = GLib.timeout_add(
            100, self.update_progressbar)
        self.remove_statusbar_timeout_id = None

        self.xml.connect_signals(self)
        self.register_events([
            ('vcard-published', ged.GUI1, self._nec_vcard_published),
            ('vcard-not-published', ged.GUI1, self._nec_vcard_not_published),
        ])

        self.show_all()
        self.xml.get_object('ok_button').grab_focus()
        app.connections[account].get_module('VCardTemp').request_vcard(
            self._nec_vcard_received, self.jid)

    def on_information_notebook_switch_page(self, widget, page, page_num):
        GLib.idle_add(self.xml.get_object('ok_button').grab_focus)

    def update_progressbar(self):
        self.progressbar.pulse()
        return True

    def remove_statusbar(self, message_id):
        self.statusbar.remove(self.context_id, message_id)
        self.remove_statusbar_timeout_id = None

    def on_profile_window_destroy(self, widget):
        if self.update_progressbar_timeout_id is not None:
            GLib.source_remove(self.update_progressbar_timeout_id)
        if self.remove_statusbar_timeout_id is not None:
            GLib.source_remove(self.remove_statusbar_timeout_id)

        if self.dialog:  # Image chooser dialog
            self.dialog.destroy()

    def on_profile_window_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _clear_photo(self, widget):
        # empty the image
        button = self.xml.get_object('PHOTO_button')
        image = self.xml.get_object('PHOTO_image')
        image.set_from_pixbuf(None)
        button.hide()
        text_button = self.xml.get_object('NOPHOTO_button')
        text_button.show()
        self.avatar_encoded = None
        self.avatar_sha = None
        self.avatar_mime_type = None

    def _on_set_avatar_clicked(self, _button):
        def on_ok(path_to_file):
            data, sha = app.interface.avatar_storage.prepare_for_publish(
                path_to_file)
            if sha is None:
                ErrorDialog(
                    _('Could not load image'), transient_for=self)
                return

            scale = self.get_scale_factor()
            surface = app.interface.avatar_storage.surface_from_filename(
                sha, AvatarSize.VCARD, scale)

            button = self.xml.get_object('PHOTO_button')
            image = self.xml.get_object('PHOTO_image')
            image.set_from_surface(surface)
            button.show()
            text_button = self.xml.get_object('NOPHOTO_button')
            text_button.hide()

            self.avatar_sha = sha
            self.avatar_encoded = base64.b64encode(data).decode('utf-8')
            self.avatar_mime_type = 'image/png'

        AvatarChooserDialog(on_ok, transient_for=self)

    def on_BDAY_entry_focus_out_event(self, widget, event):
        txt = widget.get_text()
        if not txt:
            return
        try:
            time.strptime(txt, '%Y-%m-%d')
        except ValueError:
            if not widget.is_focus():
                pritext = _('Wrong date format')
                ErrorDialog(
                    pritext,
                    _('Format of the date must be YYYY-MM-DD'),
                    transient_for=self)
                GLib.idle_add(widget.grab_focus)
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
        image = self.xml.get_object('PHOTO_image')
        text_button = self.xml.get_object('NOPHOTO_button')
        if 'PHOTO' not in vcard_:
            # set default image
            image.set_from_pixbuf(None)
            button.hide()
            text_button.show()
        for i in vcard_.keys():
            if i == 'PHOTO':
                photo_encoded = vcard_[i]['BINVAL']
                if photo_encoded == '':
                    continue
                self.avatar_encoded = photo_encoded
                photo_decoded = base64.b64decode(photo_encoded.encode('utf-8'))
                self.avatar_sha = hashlib.sha1(photo_decoded).hexdigest()
                if 'TYPE' in vcard_[i]:
                    self.avatar_mime_type = vcard_[i]['TYPE']

                scale = self.get_scale_factor()
                surface = app.interface.avatar_storage.surface_from_filename(
                    self.avatar_sha, AvatarSize.VCARD, scale)
                if surface is None:
                    pixbuf = gtkgui_helpers.scale_pixbuf_from_data(
                        photo_decoded, AvatarSize.VCARD)
                    surface = Gdk.cairo_surface_create_from_pixbuf(pixbuf,
                                                                   scale)
                image.set_from_surface(surface)
                button.show()
                text_button.hide()
                continue
            if i in ('ADR', 'TEL', 'EMAIL'):
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
            self.message_id = self.statusbar.push(
                self.context_id, _('Information received'))
            self.remove_statusbar_timeout_id = GLib.timeout_add_seconds(
                3, self.remove_statusbar, self.message_id)
            GLib.source_remove(self.update_progressbar_timeout_id)
            self.progressbar.hide()
            self.progressbar.set_fraction(0)
            self.update_progressbar_timeout_id = None

    def _nec_vcard_received(self, jid, resource, room, vcard_, *args):
        self.set_values(vcard_)

    def add_to_vcard(self, vcard_, entry, txt):
        """
        Add an information to the vCard dictionary
        """
        entries = entry.split('_')
        loc = vcard_
        if len(entries) == 3:  # We need to use lists
            if entries[0] not in loc:
                loc[entries[0]] = []

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
        entries = [
            'FN', 'NICKNAME', 'BDAY', 'EMAIL_HOME_USERID', 'JABBERID', 'URL',
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
        if not app.account_is_available(self.account):
            ErrorDialog(
                _('You are not connected to the server'),
                _('Without a connection, you can not publish your contact '
                  'information.'),
                transient_for=self)
            return
        vcard_, sha = self.make_vcard()
        nick = vcard_.get('NICKNAME') or None
        app.connections[self.account].get_module('UserNickname').set_nickname(nick)
        if not nick:
            nick = app.config.get_per('accounts', self.account, 'name')
        app.nicks[self.account] = nick
        app.connections[self.account].get_module('VCardTemp').send_vcard(
            vcard_, sha)
        self.message_id = self.statusbar.push(
            self.context_id, _('Sending profile…'))
        self.progressbar.show()
        self.update_progressbar_timeout_id = GLib.timeout_add(
            100, self.update_progressbar)

    @event_filter(['account'])
    def _nec_vcard_published(self, _event):
        if self.update_progressbar_timeout_id is not None:
            GLib.source_remove(self.update_progressbar_timeout_id)
            self.update_progressbar_timeout_id = None
        self.destroy()

    @event_filter(['account'])
    def _nec_vcard_not_published(self, _event):
        if self.message_id:
            self.statusbar.remove(self.context_id, self.message_id)
        self.message_id = self.statusbar.push(
            self.context_id, _('Information NOT published'))
        self.remove_statusbar_timeout_id = GLib.timeout_add_seconds(
            3, self.remove_statusbar, self.message_id)
        if self.update_progressbar_timeout_id is not None:
            GLib.source_remove(self.update_progressbar_timeout_id)
            self.progressbar.set_fraction(0)
            self.update_progressbar_timeout_id = None
        InformationDialog(
            _('vCard publication failed'),
            _('There was an error while publishing your personal information, '
              'try again later.'), transient_for=self)

    def on_cancel_button_clicked(self, widget):
        self.destroy()
