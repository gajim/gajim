# -*- coding:utf-8 -*-
## src/filetransfers_window.py
##
## Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
## Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006 Travis Shirk <travis AT pobox.com>
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

from gi.repository import Gtk
from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import Pango
import os
import time

import gtkgui_helpers
import tooltips
import dialogs

from common import gajim
from common import helpers
from common.file_props import FilesProp
from common.protocol.bytestream import (is_transfer_active, is_transfer_paused,
        is_transfer_stopped)
from nbxmpp.protocol import NS_JINGLE_FILE_TRANSFER
import logging
log = logging.getLogger('gajim.filetransfer_window')

C_IMAGE = 0
C_LABELS = 1
C_FILE = 2
C_TIME = 3
C_PROGRESS = 4
C_PERCENT = 5
C_PULSE = 6
C_SID = 7


class FileTransfersWindow:
    def __init__(self):
        self.files_props = {'r' : {}, 's': {}}
        self.height_diff = 0
        self.xml = gtkgui_helpers.get_gtk_builder('filetransfers.ui')
        self.window = self.xml.get_object('file_transfers_window')
        self.tree = self.xml.get_object('transfers_list')
        self.cancel_button = self.xml.get_object('cancel_button')
        self.pause_button = self.xml.get_object('pause_restore_button')
        self.cleanup_button = self.xml.get_object('cleanup_button')
        self.notify_ft_checkbox = self.xml.get_object(
                'notify_ft_complete_checkbox')

        shall_notify = gajim.config.get('notify_on_file_complete')
        self.notify_ft_checkbox.set_active(shall_notify
                                                                                                )
        self.model = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str, str, str, int,
            int, str)
        self.tree.set_model(self.model)
        col = Gtk.TreeViewColumn()

        render_pixbuf = Gtk.CellRendererPixbuf()

        col.pack_start(render_pixbuf, True)
        render_pixbuf.set_property('xpad', 3)
        render_pixbuf.set_property('ypad', 3)
        render_pixbuf.set_property('yalign', .0)
        col.add_attribute(render_pixbuf, 'pixbuf', 0)
        self.tree.append_column(col)

        col = Gtk.TreeViewColumn(_('File'))
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, False)
        col.add_attribute(renderer, 'markup', C_LABELS)
        renderer.set_property('yalign', 0.)
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, True)
        col.add_attribute(renderer, 'markup', C_FILE)
        renderer.set_property('xalign', 0.)
        renderer.set_property('yalign', 0.)
        renderer.set_property('ellipsize', Pango.EllipsizeMode.END)
        col.set_resizable(True)
        col.set_expand(True)
        self.tree.append_column(col)

        col = Gtk.TreeViewColumn(_('Time'))
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, False)
        col.add_attribute(renderer, 'markup', C_TIME)
        renderer.set_property('yalign', 0.5)
        renderer.set_property('xalign', 0.5)
        renderer = Gtk.CellRendererText()
        renderer.set_property('ellipsize', Pango.EllipsizeMode.END)
        col.set_resizable(True)
        col.set_expand(False)
        self.tree.append_column(col)

        col = Gtk.TreeViewColumn(_('Progress'))
        renderer = Gtk.CellRendererProgress()
        renderer.set_property('yalign', 0.5)
        renderer.set_property('xalign', 0.5)
        col.pack_start(renderer, False)
        col.add_attribute(renderer, 'text', C_PROGRESS)
        col.add_attribute(renderer, 'value', C_PERCENT)
        col.add_attribute(renderer, 'pulse', C_PULSE)
        col.set_resizable(True)
        col.set_expand(False)
        self.tree.append_column(col)

        self.images = {}
        self.icons = {
                'upload': Gtk.STOCK_GO_UP,
                'download': Gtk.STOCK_GO_DOWN,
                'stop': Gtk.STOCK_STOP,
                'waiting': Gtk.STOCK_REFRESH,
                'pause': Gtk.STOCK_MEDIA_PAUSE,
                'continue': Gtk.STOCK_MEDIA_PLAY,
                'ok': Gtk.STOCK_APPLY,
                'computing': Gtk.STOCK_EXECUTE,
                'hash_error': Gtk.STOCK_STOP,
        }

        self.tree.get_selection().set_mode(Gtk.SelectionMode.SINGLE)
        self.tree.get_selection().connect('changed', self.selection_changed)
        self.tooltip = tooltips.FileTransfersTooltip()
        self.file_transfers_menu = self.xml.get_object('file_transfers_menu')
        self.open_folder_menuitem = self.xml.get_object('open_folder_menuitem')
        self.cancel_menuitem = self.xml.get_object('cancel_menuitem')
        self.pause_menuitem = self.xml.get_object('pause_menuitem')
        self.continue_menuitem = self.xml.get_object('continue_menuitem')
        self.remove_menuitem = self.xml.get_object('remove_menuitem')
        self.xml.connect_signals(self)

    def find_transfer_by_jid(self, account, jid):
        """
        Find all transfers with peer 'jid' that belong to 'account'
        """
        active_transfers = [[], []] # ['senders', 'receivers']
        allfp = FilesProp.getAllFileProp()
        for file_props in allfp:
            if file_props.type_ == 's' and file_props.tt_account == account:
                # 'account' is the sender
                receiver_jid = file_props.receiver.split('/')[0]
                if jid == receiver_jid and not is_transfer_stopped(file_props):
                    active_transfers[0].append(file_props)
            elif file_props.type_ == 'r' and file_props.tt_account == account:
                # 'account' is the recipient
                sender_jid = file_props.sender.split('/')[0]
                if jid == sender_jid and not is_transfer_stopped(file_props):
                    active_transfers[1].append(file_props)
            else:
                raise Exception('file_props has no type')
        return active_transfers

    def show_completed(self, jid, file_props):
        """
        Show a dialog saying that file (file_props) has been transferred
        """
        def on_open(widget, file_props):
            dialog.destroy()
            if not file_props.file_name:
                return
            path = os.path.split(file_props.file_name)[0]
            if os.path.exists(path) and os.path.isdir(path):
                helpers.launch_file_manager(path)
            self.tree.get_selection().unselect_all()

        if file_props.type_ == 'r':
            # file path is used below in 'Save in'
            (file_path, file_name) = os.path.split(file_props.file_name)
        else:
            file_name = file_props.name
        sectext = '\t' + _('Filename: %s') % GLib.markup_escape_text(file_name)
        sectext += '\n\t' + _('Size: %s') % \
        helpers.convert_bytes(file_props.size)
        if file_props.type_ == 'r':
            jid = file_props.sender.split('/')[0]
            sender_name = gajim.contacts.get_first_contact_from_jid(
                    file_props.tt_account, jid).get_shown_name()
            sender = sender_name
        else:
            #You is a reply of who sent a file
            sender = _('You')
        sectext += '\n\t' + _('Sender: %s') % sender
        sectext += '\n\t' + _('Recipient: ')
        if file_props.type_ == 's':
            jid = file_props.receiver.split('/')[0]
            receiver_name = gajim.contacts.get_first_contact_from_jid(
                    file_props.tt_account, jid).get_shown_name()
            recipient = receiver_name
        else:
            #You is a reply of who received a file
            recipient = _('You')
        sectext += recipient
        if file_props.type_ == 'r':
            sectext += '\n\t' + _('Saved in: %s') % file_path
        dialog = dialogs.HigDialog(None, Gtk.MessageType.INFO, Gtk.ButtonsType.NONE,
                        _('File transfer completed'), sectext)
        if file_props.type_ == 'r':
            button = Gtk.Button(_('_Open Containing Folder'))
            button.connect('clicked', on_open, file_props)
            dialog.action_area.pack_start(button, True, True, 0)
        ok_button = dialog.add_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)
        def on_ok(widget):
            dialog.destroy()
        ok_button.connect('clicked', on_ok)
        dialog.show_all()

    def show_request_error(self, file_props):
        """
        Show error dialog to the recipient saying that transfer has been canceled
        """
        dialogs.InformationDialog(_('File transfer cancelled'), _('Connection with peer cannot be established.'))
        self.tree.get_selection().unselect_all()

    def show_send_error(self, file_props):
        """
        Show error dialog to the sender saying that transfer has been canceled
        """
        dialogs.InformationDialog(_('File transfer cancelled'),
                _('Connection with peer cannot be established.'))
        self.tree.get_selection().unselect_all()

    def show_stopped(self, jid, file_props, error_msg=''):
        if file_props.type_ == 'r':
            file_name = os.path.basename(file_props.file_name)
        else:
            file_name = file_props.name
        sectext = '\t' + _('Filename: %s') % GLib.markup_escape_text(file_name)
        sectext += '\n\t' + _('Recipient: %s') % jid
        if error_msg:
            sectext += '\n\t' + _('Error message: %s') % error_msg
        dialogs.ErrorDialog(_('File transfer stopped'), sectext)
        self.tree.get_selection().unselect_all()

    def show_hash_error(self, jid, file_props, account):

        def on_yes(dummy, fjid, file_props, account):
            # Delete old file
            os.remove(file_props.file_name)
            jid, resource = gajim.get_room_and_nick_from_fjid(fjid)
            if resource:
                contact = gajim.contacts.get_contact(account, jid, resource)
            else:
                contact = gajim.contacts.get_contact_with_highest_priority(
                    account, jid)
                fjid = contact.get_full_jid()
            # Request the file to the sender
            sid = helpers.get_random_string_16()
            new_file_props = FilesProp.getNewFileProp(account, sid)
            new_file_props.file_name = file_props.file_name
            new_file_props.name = file_props.name
            new_file_props.desc = file_props.desc
            new_file_props.size = file_props.size
            new_file_props.date = file_props.date
            new_file_props.hash_ = file_props.hash_
            new_file_props.type_ = 'r'
            tsid = gajim.connections[account].start_file_transfer(fjid,
                                                            new_file_props,
                                                                True)
            new_file_props.transport_sid = tsid
            self.add_transfer(account, contact, new_file_props)

        if file_props.type_ == 'r':
            file_name = os.path.basename(file_props.file_name)
        else:
            file_name = file_props.name
        dialogs.YesNoDialog(('File transfer error'),
            _('The file %(file)s has been fully received, but it seems to be '
            'wrongly received.\nDo you want to reload it?') % \
            {'file': file_name}, on_response_yes=(on_yes, jid, file_props,
            account), type_=Gtk.MessageType.ERROR)

    def show_file_send_request(self, account, contact):
        win = Gtk.ScrolledWindow()
        win.set_shadow_type(Gtk.ShadowType.IN)
        win.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)

        from message_textview import MessageTextView
        desc_entry = MessageTextView()
        win.add(desc_entry)

        def on_ok(widget):
            file_dir = None
            files_path_list = dialog.get_filenames()
            files_path_list = gtkgui_helpers.decode_filechooser_file_paths(
                    files_path_list)
            text_buffer = desc_entry.get_buffer()
            desc = text_buffer.get_text(text_buffer.get_start_iter(),
                text_buffer.get_end_iter(), True)
            for file_path in files_path_list:
                if self.send_file(account, contact, file_path, desc) \
                and file_dir is None:
                    file_dir = os.path.dirname(file_path)
            if file_dir:
                gajim.config.set('last_send_dir', file_dir)
                dialog.destroy()

        dialog = dialogs.FileChooserDialog(_('Choose File to Send...'),
                Gtk.FileChooserAction.OPEN, (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL),
                Gtk.ResponseType.OK,
                True, # select multiple true as we can select many files to send
                gajim.config.get('last_send_dir'),
                on_response_ok=on_ok,
                on_response_cancel=lambda e:dialog.destroy()
                )

        btn = Gtk.Button.new_with_mnemonic(_('_Send'))
        btn.set_property('can-default', True)
        # FIXME: add send icon to this button (JUMP_TO)
        dialog.add_action_widget(btn, Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)

        desc_hbox = Gtk.HBox(False, 5)
        desc_hbox.pack_start(Gtk.Label(_('Description: ')), False, False, 0)
        desc_hbox.pack_start(win, True, True, 0)

        dialog.vbox.pack_start(desc_hbox, False, False, 0)

        btn.show()
        desc_hbox.show_all()

    def send_file(self, account, contact, file_path, file_desc=''):
        """
        Start the real transfer(upload) of the file
        """
        if gtkgui_helpers.file_is_locked(file_path):
            pritext = _('Gajim cannot access this file')
            sextext = _('This file is being used by another process.')
            dialogs.ErrorDialog(pritext, sextext)
            return

        if isinstance(contact, str):
            if contact.find('/') == -1:
                return
            (jid, resource) = contact.split('/', 1)
            contact = gajim.contacts.create_contact(jid=jid, account=account,
                resource=resource)
        file_name = os.path.split(file_path)[1]
        file_props = self.get_send_file_props(account, contact,
                        file_path, file_name, file_desc)
        if file_props is None:
            return False
        if contact.supports(NS_JINGLE_FILE_TRANSFER):
            log.info("contact %s supports jingle file transfer"%(contact.get_full_jid()))
            gajim.connections[account].start_file_transfer(contact.get_full_jid(),
                                                           file_props)
            self.add_transfer(account, contact, file_props)
        else:
            log.info("contact does not support jingle file transfer")
            gajim.connections[account].send_file_request(file_props)
            self.add_transfer(account, contact, file_props)
        return True

    def _start_receive(self, file_path, account, contact, file_props):
        file_dir = os.path.dirname(file_path)
        if file_dir:
            gajim.config.set('last_save_dir', file_dir)
        file_props.file_name = file_path
        file_props.type_ = 'r'
        self.add_transfer(account, contact, file_props)
        gajim.connections[account].send_file_approval(file_props)

    def on_file_request_accepted(self, account, contact, file_props):
        def on_ok(widget, account, contact, file_props):
            file_path = dialog2.get_filename()
            file_path = gtkgui_helpers.decode_filechooser_file_paths(
                (file_path,))[0]
            if os.path.exists(file_path):
                # check if we have write permissions
                if not os.access(file_path, os.W_OK):
                    file_name = GLib.markup_escape_text(os.path.basename(
                        file_path))
                    dialogs.ErrorDialog(
                        _('Cannot overwrite existing file "%s"' % file_name),
                        _('A file with this name already exists and you do not '
                        'have permission to overwrite it.'))
                    return
                stat = os.stat(file_path)
                dl_size = stat.st_size
                file_size = file_props.size
                dl_finished = dl_size >= file_size

                def on_response(response):
                    if response < 0:
                        return
                    elif response == 100:
                        file_props.offset = dl_size
                    dialog2.destroy()
                    self._start_receive(file_path, account, contact, file_props)

                dialog = dialogs.FTOverwriteConfirmationDialog(
                    _('This file already exists'), _('What do you want to do?'),
                    propose_resume=not dl_finished, on_response=on_response,
                    transient_for=dialog2)
                dialog.set_destroy_with_parent(True)
                return
            else:
                dirname = os.path.dirname(file_path)
                if not os.access(dirname, os.W_OK) and os.name != 'nt':
                    # read-only bit is used to mark special folder under
                    # windows, not to mark that a folder is read-only.
                    # See ticket #3587
                    dialogs.ErrorDialog(_('Directory "%s" is not writable') % \
                        dirname, _('You do not have permission to create files '
                        'in this directory.'))
                    return
            dialog2.destroy()
            self._start_receive(file_path, account, contact, file_props)

        def on_cancel(widget, account, contact, file_props):
            dialog2.destroy()
            gajim.connections[account].send_file_rejection(file_props)

        dialog2 = dialogs.FileChooserDialog(
            title_text=_('Save File as...'),
            action=Gtk.FileChooserAction.SAVE,
            buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_SAVE, Gtk.ResponseType.OK),
            default_response=Gtk.ResponseType.OK,
            current_folder=gajim.config.get('last_save_dir'),
            on_response_ok=(on_ok, account, contact, file_props),
            on_response_cancel=(on_cancel, account, contact, file_props))

        dialog2.set_current_name(file_props.name)
        dialog2.connect('delete-event', lambda widget, event:
            on_cancel(widget, account, contact, file_props))

    def show_file_request(self, account, contact, file_props):
        """
        Show dialog asking for comfirmation and store location of new file
        requested by a contact
        """
        if not file_props or not file_props.name:
            return
        sec_text = '\t' + _('File: %s') % GLib.markup_escape_text(
            file_props.name)
        if file_props.size:
            sec_text += '\n\t' + _('Size: %s') % \
                    helpers.convert_bytes(file_props.size)
        if file_props.mime_type:
            sec_text += '\n\t' + _('Type: %s') % file_props.mime_type
        if  file_props.desc:
            sec_text += '\n\t' + _('Description: %s') % file_props.desc
        prim_text = _('%s wants to send you a file:') % contact.jid
        dialog = None

        def on_response_ok(account, contact, file_props):
            self.on_file_request_accepted(account, contact, file_props)

        def on_response_cancel(account, file_props):
            gajim.connections[account].send_file_rejection(file_props)

        dialog = dialogs.NonModalConfirmationDialog(prim_text, sec_text,
                on_response_ok=(on_response_ok, account, contact, file_props),
                on_response_cancel=(on_response_cancel, account, file_props))
        dialog.connect('delete-event', lambda widget, event:
            on_response_cancel(account, file_props))
        dialog.popup()

    def get_icon(self, ident):
        return self.images.setdefault(ident,
            self.window.render_icon_pixbuf(self.icons[ident],
                Gtk.IconSize.MENU))

    def set_status(self,file_props, status):
        """
        Change the status of a transfer to state 'status'
        """
        iter_ = self.get_iter_by_sid(file_props.type_, file_props.sid)
        if iter_ is None:
            return
        self.model[iter_][C_SID]
        if status == 'stop':
            file_props.stopped = True
        elif status == 'ok':
            file_props.completed = True
            text = self._format_percent(100)
            received_size = int(file_props.received_len)
            full_size = file_props.size
            text += helpers.convert_bytes(received_size) + '/' + \
                helpers.convert_bytes(full_size)
            self.model.set(iter_, C_PROGRESS, text)
            self.model.set(iter_, C_PULSE, GLib.MAXINT32)
        elif status == 'computing':
            self.model.set(iter_, C_PULSE, 1)
            text = _('Checking file...') + '\n'
            received_size = int(file_props.received_len)
            full_size = file_props.size
            text += helpers.convert_bytes(received_size) + '/' + \
                helpers.convert_bytes(full_size)
            self.model.set(iter_, C_PROGRESS, text)
            def pulse():
                p = self.model.get(iter_, C_PULSE)[0]
                if p == GLib.MAXINT32:
                    return False
                self.model.set(iter_, C_PULSE, p + 1)
                return True
            GLib.timeout_add(100, pulse)
        elif status == 'hash_error':
            text = _('File error') + '\n'
            received_size = int(file_props.received_len)
            full_size = file_props.size
            text += helpers.convert_bytes(received_size) + '/' + \
                helpers.convert_bytes(full_size)
            self.model.set(iter_, C_PROGRESS, text)
            self.model.set(iter_, C_PULSE, GLib.MAXINT32)
        self.model.set(iter_, C_IMAGE, self.get_icon(status))
        path = self.model.get_path(iter_)
        self.select_func(path)

    def _format_percent(self, percent):
        """
        Add extra spaces from both sides of the percent, so that progress string
        has always a fixed size
        """
        _str = '          '
        if percent != 100.:
            _str += ' '
        if percent < 10:
            _str += ' '
        _str += str(percent) + '%          \n'
        return _str

    def _format_time(self, _time):
        times = { 'hours': 0, 'minutes': 0, 'seconds': 0 }
        _time = int(_time)
        times['seconds'] = _time % 60
        if _time >= 60:
            _time /= 60
            times['minutes'] = _time % 60
            if _time >= 60:
                times['hours'] = _time / 60

        #Print remaining time in format 00:00:00
        #You can change the places of (hours), (minutes), (seconds) -
        #they are not translatable.
        return _('%(hours)02.d:%(minutes)02.d:%(seconds)02.d') % times

    def _get_eta_and_speed(self, full_size, transfered_size, file_props):
        if len(file_props.transfered_size) == 0:
            return 0., 0.
        elif len(file_props.transfered_size) == 1:
            speed = round(float(transfered_size) / file_props.elapsed_time)
        else:
            # first and last are (time, transfered_size)
            first = file_props.transfered_size[0]
            last = file_props.transfered_size[-1]
            transfered = last[1] - first[1]
            tim = last[0] - first[0]
            if tim == 0:
                return 0., 0.
            speed = round(float(transfered) / tim)
        if speed == 0.:
            return 0., 0.
        remaining_size = full_size - transfered_size
        eta = remaining_size / speed
        return eta, speed

    def _remove_transfer(self, iter_, sid, file_props):
        self.model.remove(iter_)
        if not file_props:
            return
        if file_props.tt_account:
            # file transfer is set
            account = file_props.tt_account
            if account in gajim.connections:
                # there is a connection to the account
                gajim.connections[account].remove_transfer(file_props)
            if file_props.type_ == 'r': # we receive a file
                other = file_props.sender
            else: # we send a file
                other = file_props.receiver
            if isinstance(other, str):
                jid = gajim.get_jid_without_resource(other)
            else: # It's a Contact instance
                jid = other.jid
            for ev_type in ('file-error', 'file-completed', 'file-request-error',
            'file-send-error', 'file-stopped'):
                for event in gajim.events.get_events(account, jid, [ev_type]):
                    if event.parameters.sid == file_props.sid:
                        gajim.events.remove_events(account, jid, event)
                        gajim.interface.roster.draw_contact(jid, account)
                        gajim.interface.roster.show_title()
        FilesProp.deleteFileProp(file_props)
        del(file_props)

    def set_progress(self, typ, sid, transfered_size, iter_=None):
        """
        Change the progress of a transfer with new transfered size
        """
        file_props = FilesProp.getFilePropByType(typ, sid)
        full_size = file_props.size
        if full_size == 0:
            percent = 0
        else:
            percent = round(float(transfered_size) / full_size * 100, 1)
        if iter_ is None:
            iter_ = self.get_iter_by_sid(typ, sid)
        if iter_ is not None:
            just_began = False
            if self.model[iter_][C_PERCENT] == 0 and int(percent > 0):
                just_began = True
            text = self._format_percent(percent)
            if transfered_size == 0:
                text += '0'
            else:
                text += helpers.convert_bytes(transfered_size)
            text += '/' + helpers.convert_bytes(full_size)
            # Kb/s

            # remaining time
            if file_props.offset:
                transfered_size -= file_props.offset
                full_size -= file_props.offset

            if file_props.elapsed_time > 0:
                file_props.transfered_size.append((file_props.last_time, transfered_size))
            if len(file_props.transfered_size) > 6:
                file_props.transfered_size.pop(0)
            eta, speed = self._get_eta_and_speed(full_size, transfered_size,
                    file_props)

            self.model.set(iter_, C_PROGRESS, text)
            self.model.set(iter_, C_PERCENT, int(percent))
            text = self._format_time(eta)
            text += '\n'
            #This should make the string Kb/s,
            #where 'Kb' part is taken from %s.
            #Only the 's' after / (which means second) should be translated.
            text += _('(%(filesize_unit)s/s)') % {'filesize_unit':
                    helpers.convert_bytes(speed)}
            self.model.set(iter_, C_TIME, text)

            # try to guess what should be the status image
            if file_props.type_ == 'r':
                status = 'download'
            else:
                status = 'upload'
            if file_props.paused == True:
                status = 'pause'
            elif file_props.stalled == True:
                status = 'waiting'
            if file_props.connected == False:
                status = 'stop'
            self.model.set(iter_, 0, self.get_icon(status))
            if transfered_size == full_size:
                # If we are receiver and this is a jingle session
                if file_props.type_ == 'r' and  \
                      file_props.session_type == 'jingle' and file_props.hash_:
                    # Show that we are computing the hash
                    self.set_status(file_props, 'computing')
                else:
                    self.set_status(file_props, 'ok')
            elif just_began:
                path = self.model.get_path(iter_)
                self.select_func(path)

    def get_iter_by_sid(self, typ, sid):
        """
        Return iter to the row, which holds file transfer, identified by the
        session id
        """
        iter_ = self.model.get_iter_first()
        while iter_:
            if typ + sid == self.model[iter_][C_SID]:
                return iter_
            iter_ = self.model.iter_next(iter_)

    def __convert_date(self, epoch):
        # Converts date-time from seconds from epoch to iso 8601
        import time, datetime
        ts = time.gmtime(epoch)
        dt = datetime.datetime(ts.tm_year, ts.tm_mon, ts.tm_mday, ts.tm_hour,
                               ts.tm_min,  ts.tm_sec)
        return dt.isoformat()

    def get_send_file_props(self, account, contact, file_path, file_name,
    file_desc=''):
        """
        Create new file_props object and set initial file transfer
        properties in it
        """
        if os.path.isfile(file_path):
            stat = os.stat(file_path)
        else:
            dialogs.ErrorDialog(_('Invalid File'), _('File: ') + file_path)
            return None
        if stat[6] == 0:
            dialogs.ErrorDialog(_('Invalid File'),
            _('It is not possible to send empty files'))
            return None
        file_props = FilesProp.getNewFileProp(account,
                                    sid=helpers.get_random_string_16())
        mod_date = os.path.getmtime(file_path)
        file_props.file_name = file_path
        file_props.name = file_name
        file_props.date = self.__convert_date(mod_date)
        file_props.type_ = 's'
        file_props.desc = file_desc
        file_props.elapsed_time = 0
        file_props.size = stat[6]
        file_props.sender = account
        file_props.receiver = contact
        file_props.tt_account = account
        return file_props

    def add_transfer(self, account, contact, file_props):
        """
        Add new transfer to FT window and show the FT window
        """
        self.on_transfers_list_leave_notify_event(None)
        if file_props is None:
            return
        file_props.elapsed_time = 0
        iter_ = self.model.prepend()
        text_labels = '<b>' + _('Name: ') + '</b>\n'
        if file_props.type_ == 'r':
            text_labels += '<b>' + _('Sender: ') + '</b>'
        else:
            text_labels += '<b>' + _('Recipient: ') + '</b>'

        if file_props.type_ == 'r':
            file_name = os.path.split(file_props.file_name)[1]
        else:
            file_name = file_props.name
        text_props = GLib.markup_escape_text(file_name) + '\n'
        text_props += contact.get_shown_name()
        self.model.set(iter_, 1, text_labels, 2, text_props, C_PULSE, -1, C_SID,
                file_props.type_ + file_props.sid)
        self.set_progress(file_props.type_, file_props.sid, 0, iter_)
        if file_props.started is False:
            status = 'waiting'
        elif file_props.type_ == 'r':
            status = 'download'
        else:
            status = 'upload'
        file_props.tt_account = account
        self.set_status(file_props, status)
        self.set_cleanup_sensitivity()
        self.window.show_all()

    def on_transfers_list_motion_notify_event(self, widget, event):
        w = self.tree.get_window()
        device = w.get_display().get_device_manager().get_client_pointer()
        pointer = w.get_device_position(device)
        props = widget.get_path_at_pos(int(event.x), int(event.y))
        self.height_diff = pointer[2] - int(event.y)
        if self.tooltip.timeout > 0:
            if not props or self.tooltip.id != props[0]:
                self.tooltip.hide_tooltip()
        if props:
            row = props[0]
            iter_ = None
            try:
                iter_ = self.model.get_iter(row)
            except Exception:
                self.tooltip.hide_tooltip()
                return
            sid = self.model[iter_][C_SID]
            file_props = FilesProp.getFilePropByType(sid[0], sid[1:])
            if file_props is not None:
                if self.tooltip.timeout == 0 or self.tooltip.id != props[0]:
                    self.tooltip.id = row
                    self.tooltip.timeout = GLib.timeout_add(500,
                        self.show_tooltip, widget)

    def on_transfers_list_leave_notify_event(self, widget=None, event=None):
        if event is not None:
            self.height_diff = int(event.y)
        elif self.height_diff is 0:
            return
        w = self.tree.get_window()
        device = w.get_display().get_device_manager().get_client_pointer()
        pointer = w.get_device_position(device)
        props = self.tree.get_path_at_pos(pointer[1],
            pointer[2] - self.height_diff)
        if self.tooltip.timeout > 0:
            if not props or self.tooltip.id == props[0]:
                self.tooltip.hide_tooltip()

    def on_transfers_list_row_activated(self, widget, path, col):
        # try to open the containing folder
        self.on_open_folder_menuitem_activate(widget)

    def set_cleanup_sensitivity(self):
        """
        Check if there are transfer rows and set cleanup_button sensitive, or
        insensitive if model is empty
        """
        if len(self.model) == 0:
            self.cleanup_button.set_sensitive(False)
        else:
            self.cleanup_button.set_sensitive(True)

    def set_all_insensitive(self):
        """
        Make all buttons/menuitems insensitive
        """
        self.pause_button.set_sensitive(False)
        self.pause_menuitem.set_sensitive(False)
        self.continue_menuitem.set_sensitive(False)
        self.remove_menuitem.set_sensitive(False)
        self.cancel_button.set_sensitive(False)
        self.cancel_menuitem.set_sensitive(False)
        self.open_folder_menuitem.set_sensitive(False)
        self.set_cleanup_sensitivity()

    def set_buttons_sensitive(self, path, is_row_selected):
        """
        Make buttons/menuitems sensitive as appropriate to the state of file
        transfer located at path 'path'
        """
        if path is None:
            self.set_all_insensitive()
            return
        current_iter = self.model.get_iter(path)
        sid = self.model[current_iter][C_SID]
        file_props = FilesProp.getFilePropByType(sid[0], sid[1:])
        self.remove_menuitem.set_sensitive(is_row_selected)
        self.open_folder_menuitem.set_sensitive(is_row_selected)
        is_stopped = False
        if is_transfer_stopped(file_props):
            is_stopped = True
        self.cancel_button.set_sensitive(not is_stopped)
        self.cancel_menuitem.set_sensitive(not is_stopped)
        if not is_row_selected:
            # no selection, disable the buttons
            self.set_all_insensitive()
        elif not is_stopped:
            if is_transfer_active(file_props):
                # file transfer is active
                self.toggle_pause_continue(True)
                self.pause_button.set_sensitive(True)
            elif is_transfer_paused(file_props):
                # file transfer is paused
                self.toggle_pause_continue(False)
                self.pause_button.set_sensitive(True)
            else:
                self.pause_button.set_sensitive(False)
                self.pause_menuitem.set_sensitive(False)
                self.continue_menuitem.set_sensitive(False)
        else:
            self.pause_button.set_sensitive(False)
            self.pause_menuitem.set_sensitive(False)
            self.continue_menuitem.set_sensitive(False)
        return True

    def selection_changed(self, args):
        """
        Selection has changed - change the sensitivity of the buttons/menuitems
        """
        selection = args
        selected = selection.get_selected_rows()
        if selected[1] != []:
            selected_path = selected[1][0]
            self.select_func(selected_path)
        else:
            self.set_all_insensitive()

    def select_func(self, path):
        is_selected = False
        selected = self.tree.get_selection().get_selected_rows()
        if selected[1] != []:
            selected_path = selected[1][0]
            if selected_path == path:
                is_selected = True
        self.set_buttons_sensitive(path, is_selected)
        self.set_cleanup_sensitivity()
        return True

    def on_cleanup_button_clicked(self, widget):
        i = len(self.model) - 1
        while i >= 0:
            iter_ = self.model.get_iter((i))
            sid = self.model[iter_][C_SID]
            file_props = FilesProp.getFilePropByType(sid[0], sid[1:])
            if is_transfer_stopped(file_props):
                self._remove_transfer(iter_, sid, file_props)
            i -= 1
        self.tree.get_selection().unselect_all()
        self.set_all_insensitive()

    def toggle_pause_continue(self, status):
        if status:
            label = _('Pause')
            self.pause_button.set_label(label)
            self.pause_button.set_image(Gtk.Image.new_from_stock(
                    Gtk.STOCK_MEDIA_PAUSE, Gtk.IconSize.MENU))

            self.pause_menuitem.set_sensitive(True)
            self.pause_menuitem.set_no_show_all(False)
            self.continue_menuitem.hide()
            self.continue_menuitem.set_no_show_all(True)

        else:
            label = _('_Continue')
            self.pause_button.set_label(label)
            self.pause_button.set_image(Gtk.Image.new_from_stock(
                    Gtk.STOCK_MEDIA_PLAY, Gtk.IconSize.MENU))
            self.pause_menuitem.hide()
            self.pause_menuitem.set_no_show_all(True)
            self.continue_menuitem.set_sensitive(True)
            self.continue_menuitem.set_no_show_all(False)

    def on_pause_restore_button_clicked(self, widget):
        selected = self.tree.get_selection().get_selected()
        if selected is None or selected[1] is None:
            return
        s_iter = selected[1]
        sid = self.model[s_iter][C_SID]
        file_props = FilesProp.getFilePropByType(sid[0], sid[1:])
        if is_transfer_paused(file_props):
            file_props.last_time = time.time()
            file_props.paused = False
            types = {'r' : 'download', 's' : 'upload'}
            self.set_status(file_props, types[sid[0]])
            self.toggle_pause_continue(True)
            if file_props.continue_cb:
                file_props.continue_cb()
        elif is_transfer_active(file_props):
            file_props.paused = True
            self.set_status(file_props, 'pause')
            # reset that to compute speed only when we resume
            file_props.transfered_size = []
            self.toggle_pause_continue(False)

    def on_cancel_button_clicked(self, widget):
        selected = self.tree.get_selection().get_selected()
        if selected is None or selected[1] is None:
            return
        s_iter = selected[1]
        sid = self.model[s_iter][C_SID]
        file_props = FilesProp.getFilePropByType(sid[0], sid[1:])
        account = file_props.tt_account
        if account not in gajim.connections:
            return
        con = gajim.connections[account]
        # Check if we are in a IBB transfer
        if file_props.direction:
            con.CloseIBBStream(file_props)
        con.disconnect_transfer(file_props)
        self.set_status(file_props, 'stop')

    def show_tooltip(self, widget):
        if self.height_diff == 0:
            self.tooltip.hide_tooltip()
            return
        w = self.tree.get_window()
        device = w.get_display().get_device_manager().get_client_pointer()
        pointer = w.get_device_position(device)
        props = self.tree.get_path_at_pos(pointer[1],
            pointer[2] - self.height_diff)
        # check if the current pointer is at the same path
        # as it was before setting the timeout
        if props and self.tooltip.id == props[0]:
            iter_ = self.model.get_iter(props[0])
            sid = self.model[iter_][C_SID]
            file_props = FilesProp.getFilePropByType(sid[0], sid[1:])
            # bounding rectangle of coordinates for the cell within the treeview
            rect = self.tree.get_cell_area(props[0], props[1])
            # position of the treeview on the screen
            position = widget.get_window().get_origin()[1:]
            self.tooltip.show_tooltip(file_props, rect.height,
                position[1] + rect.y + self.height_diff)
        else:
            self.tooltip.hide_tooltip()

    def on_notify_ft_complete_checkbox_toggled(self, widget):
        gajim.config.set('notify_on_file_complete',
                widget.get_active())

    def on_file_transfers_dialog_delete_event(self, widget, event):
        self.on_transfers_list_leave_notify_event(widget, None)
        self.window.hide()
        return True # do NOT destory window

    def on_close_button_clicked(self, widget):
        self.window.hide()

    def show_context_menu(self, event, iter_):
        # change the sensitive propery of the buttons and menuitems
        if iter_:
            path = self.model.get_path(iter_)
            self.set_buttons_sensitive(path, True)

        event_button = gtkgui_helpers.get_possible_button_event(event)
        self.file_transfers_menu.show_all()
        self.file_transfers_menu.popup(None, self.tree, None, None,
                event_button, event.time)

    def on_transfers_list_key_press_event(self, widget, event):
        """
        When a key is pressed in the treeviews
        """
        self.tooltip.hide_tooltip()
        iter_ = None
        try:
            iter_ = self.tree.get_selection().get_selected()[1]
        except TypeError:
            self.tree.get_selection().unselect_all()

        if iter_ is not None:
            path = self.model.get_path(iter_)
            self.tree.get_selection().select_path(path)

        if event.keyval == Gdk.KEY_Menu:
            self.show_context_menu(event, iter_)
            return True


    def on_transfers_list_button_release_event(self, widget, event):
        # hide tooltip, no matter the button is pressed
        self.tooltip.hide_tooltip()
        path = None
        try:
            path = self.tree.get_path_at_pos(int(event.x), int(event.y))[0]
        except TypeError:
            self.tree.get_selection().unselect_all()
        if path is None:
            self.set_all_insensitive()
        else:
            self.select_func(path)

    def on_transfers_list_button_press_event(self, widget, event):
        # hide tooltip, no matter the button is pressed
        self.tooltip.hide_tooltip()
        path, iter_ = None, None
        try:
            path = self.tree.get_path_at_pos(int(event.x), int(event.y))[0]
        except TypeError:
            self.tree.get_selection().unselect_all()
        if event.button == 3: # Right click
            if path:
                self.tree.get_selection().select_path(path)
                iter_ = self.model.get_iter(path)
            self.show_context_menu(event, iter_)
            if path:
                return True

    def on_open_folder_menuitem_activate(self, widget):
        selected = self.tree.get_selection().get_selected()
        if not selected or not selected[1]:
            return
        s_iter = selected[1]
        sid = self.model[s_iter][C_SID]
        file_props = FilesProp.getFilePropByType(sid[0], sid[1:])
        if not file_props.file_name:
            return
        path = os.path.split(file_props.file_name)[0]
        if os.path.exists(path) and os.path.isdir(path):
            helpers.launch_file_manager(path)

    def on_cancel_menuitem_activate(self, widget):
        self.on_cancel_button_clicked(widget)

    def on_continue_menuitem_activate(self, widget):
        self.on_pause_restore_button_clicked(widget)

    def on_pause_menuitem_activate(self, widget):
        self.on_pause_restore_button_clicked(widget)

    def on_remove_menuitem_activate(self, widget):
        selected = self.tree.get_selection().get_selected()
        if not selected or not selected[1]:
            return
        s_iter = selected[1]
        sid = self.model[s_iter][C_SID]
        file_props = FilesProp.getFilePropByType(sid[0], sid[1:])
        self._remove_transfer(s_iter, sid, file_props)
        self.set_all_insensitive()

    def on_file_transfers_window_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Escape: # ESCAPE
            self.window.hide()
