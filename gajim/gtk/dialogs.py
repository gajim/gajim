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

from datetime import datetime
from collections import namedtuple

from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Pango

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.const import ButtonAction
from gajim.common.helpers import convert_gio_to_openssl_cert

from gajim.gtk.util import get_builder
from gajim.gtk.util import get_thumbnail_size


class DialogButton(namedtuple('DialogButton', ('response text callback args '
                                               'kwargs action is_default'))):
    @classmethod
    def make(cls, type_=None, **kwargs):
        # Defaults
        default_kwargs = {
            'response': None,
            'text': None,
            'callback': None,
            'args': [],
            'kwargs': {},
            'action': None,
            'is_default': False
        }

        if type_ is not None:
            if type_ == 'OK':
                default_kwargs['response'] = Gtk.ResponseType.OK
                default_kwargs['text'] = _('_OK')

            elif type_ == 'Cancel':
                default_kwargs['response'] = Gtk.ResponseType.CANCEL
                default_kwargs['text'] = _('_Cancel')

            elif type_ == 'Accept':
                default_kwargs['response'] = Gtk.ResponseType.ACCEPT
                default_kwargs['text'] = _('_Accept')
                default_kwargs['is_default'] = True
                default_kwargs['action'] = ButtonAction.SUGGESTED

            elif type_ == 'Delete':
                default_kwargs['response'] = Gtk.ResponseType.REJECT
                default_kwargs['text'] = _('_Delete')
                default_kwargs['action'] = ButtonAction.DESTRUCTIVE

            elif type_ == 'Remove':
                default_kwargs['response'] = Gtk.ResponseType.REJECT
                default_kwargs['text'] = _('_Remove')
                default_kwargs['action'] = ButtonAction.DESTRUCTIVE
            else:
                raise ValueError('Unknown button type: %s ' % type_)

        default_kwargs.update(kwargs)
        return cls(**default_kwargs)


class HigDialog(Gtk.MessageDialog):
    def __init__(self,
                 parent,
                 type_,
                 buttons,
                 pritext,
                 sectext,
                 on_response_ok=None,
                 on_response_cancel=None,
                 on_response_yes=None,
                 on_response_no=None):
        self.call_cancel_on_destroy = True
        Gtk.MessageDialog.__init__(self,
                                   transient_for=parent,
                                   modal=True,
                                   destroy_with_parent=True,
                                   message_type=type_,
                                   buttons=buttons,
                                   text=pritext)

        self.format_secondary_markup(sectext)

        self.possible_responses = {
            Gtk.ResponseType.OK: on_response_ok,
            Gtk.ResponseType.CANCEL: on_response_cancel,
            Gtk.ResponseType.YES: on_response_yes,
            Gtk.ResponseType.NO: on_response_no
        }

        self.connect('response', self.on_response)
        self.connect('destroy', self.on_dialog_destroy)

    def on_response(self, dialog, response_id):
        if response_id not in self.possible_responses:
            return
        if not self.possible_responses[response_id]:
            self.destroy()
        elif isinstance(self.possible_responses[response_id], tuple):
            if len(self.possible_responses[response_id]) == 1:
                self.possible_responses[response_id][0](dialog)
            else:
                self.possible_responses[response_id][0](
                    dialog, *self.possible_responses[response_id][1:])
        else:
            self.possible_responses[response_id](dialog)

    def on_dialog_destroy(self, _widget):
        if not self.call_cancel_on_destroy:
            return None
        cancel_handler = self.possible_responses[Gtk.ResponseType.CANCEL]
        if not cancel_handler:
            return False
        if isinstance(cancel_handler, tuple):
            cancel_handler[0](None, *cancel_handler[1:])
        else:
            cancel_handler(None)
        return None

    def popup(self):
        """
        Show dialog
        """
        vb = self.get_children()[0].get_children()[0] # Give focus to top vbox
        # vb.set_flags(Gtk.CAN_FOCUS)
        vb.grab_focus()
        self.show_all()


class WarningDialog(HigDialog):
    """
    HIG compliant warning dialog
    """

    def __init__(self, pritext, sectext='', transient_for=None):
        if transient_for is None:
            transient_for = app.app.get_active_window()
        HigDialog.__init__(self,
                           transient_for,
                           Gtk.MessageType.WARNING,
                           Gtk.ButtonsType.OK,
                           pritext,
                           sectext)
        self.set_modal(False)
        self.popup()


class InformationDialog(HigDialog):
    """
    HIG compliant info dialog
    """

    def __init__(self, pritext, sectext='', transient_for=None):
        if transient_for is None:
            transient_for = app.app.get_active_window()
        HigDialog.__init__(self,
                           transient_for,
                           Gtk.MessageType.INFO,
                           Gtk.ButtonsType.OK,
                           pritext,
                           sectext)
        self.set_modal(False)
        self.popup()


class ErrorDialog(HigDialog):
    """
    HIG compliant error dialog
    """

    def __init__(self,
                 pritext,
                 sectext='',
                 on_response_ok=None,
                 on_response_cancel=None,
                 transient_for=None):
        if transient_for is None:
            transient_for = app.app.get_active_window()
        HigDialog.__init__(self,
                           transient_for,
                           Gtk.MessageType.ERROR,
                           Gtk.ButtonsType.OK,
                           pritext,
                           sectext,
                           on_response_ok=on_response_ok,
                           on_response_cancel=on_response_cancel)
        self.popup()


class CertificateDialog(Gtk.ApplicationWindow):
    def __init__(self, transient_for, account, cert):
        Gtk.ApplicationWindow.__init__(self)
        self.account = account
        self.set_name('CertificateDialog')
        self.set_application(app.app)
        self.set_show_menubar(False)
        self.set_resizable(False)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_title(_('Certificate'))

        self._ui = get_builder('certificate_dialog.ui')
        self.add(self._ui.certificate_box)

        self.connect('key-press-event', self._on_key_press)

        self._clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

        cert = convert_gio_to_openssl_cert(cert)
        # Get data for labels and copy button
        issuer = cert.get_issuer()
        subject = cert.get_subject()

        self._headline = _('Certificate for \n%s') % self.account
        self._it_common_name = subject.commonName or ''
        self._it_organization = subject.organizationName or ''
        self._it_org_unit = subject.organizationalUnitName or ''
        it_serial_no = str(cert.get_serial_number())
        it_serial_no_half = int(len(it_serial_no) / 2)
        self._it_serial_number = '%s\n%s' % (
            it_serial_no[:it_serial_no_half],
            it_serial_no[it_serial_no_half:])
        self._ib_common_name = issuer.commonName or ''
        self._ib_organization = issuer.organizationName or ''
        self._ib_org_unit = issuer.organizationalUnitName or ''
        issued = datetime.strptime(cert.get_notBefore().decode('ascii'),
                                   '%Y%m%d%H%M%SZ')
        self._issued = issued.strftime('%c %Z')
        expires = datetime.strptime(cert.get_notAfter().decode('ascii'),
                                    '%Y%m%d%H%M%SZ')
        self._expires = expires.strftime('%c %Z')
        sha1 = cert.digest('sha1').decode('utf-8')
        self._sha1 = '%s\n%s' % (sha1[:29], sha1[30:])
        sha256 = cert.digest('sha256').decode('utf-8')
        self._sha256 = '%s\n%s\n%s\n%s' % (
            sha256[:23], sha256[24:47], sha256[48:71], sha256[72:])

        # Set labels
        self._ui.label_cert_for_account.set_text(self._headline)
        self._ui.data_it_common_name.set_text(self._it_common_name)
        self._ui.data_it_organization.set_text(self._it_organization)
        self._ui.data_it_organizational_unit.set_text(self._it_org_unit)
        self._ui.data_it_serial_number.set_text(self._it_serial_number)
        self._ui.data_ib_common_name.set_text(self._ib_common_name)
        self._ui.data_ib_organization.set_text(self._ib_organization)
        self._ui.data_ib_organizational_unit.set_text(self._ib_org_unit)
        self._ui.data_issued_on.set_text(self._issued)
        self._ui.data_expires_on.set_text(self._expires)
        self._ui.data_sha1.set_text(self._sha1)
        self._ui.data_sha256.set_text(self._sha256)

        self.set_transient_for(transient_for)
        self._ui.connect_signals(self)
        self.show_all()

    def _on_key_press(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _on_copy_cert_info_button_clicked(self, _widget):
        clipboard_text = \
            self._headline + '\n\n' + \
            _('Issued to\n') + \
            _('Common Name (CN): ') + self._it_common_name + '\n' + \
            _('Organization (O): ') + self._it_organization + '\n' + \
            _('Organizational Unit (OU): ') + self._it_org_unit + '\n' + \
            _('Serial Number: ') + self._it_serial_number + '\n\n' + \
            _('Issued by\n') + \
            _('Common Name (CN): ') + self._ib_common_name + '\n' + \
            _('Organization (O): ') + self._ib_organization + '\n' + \
            _('Organizational Unit (OU): ') + self._ib_org_unit + '\n\n' + \
            _('Validity\n') + \
            _('Issued on: ') + self._issued + '\n' + \
            _('Expires on: ') + self._expires + '\n\n' + \
            _('SHA-1:') + '\n' + \
            self._sha1 + '\n' + \
            _('SHA-256:') + '\n' + \
            self._sha256 + '\n'
        self._clipboard.set_text(clipboard_text, -1)


class InvitationReceivedDialog(Gtk.ApplicationWindow):
    def __init__(self, account, event):
        Gtk.ApplicationWindow.__init__(self)
        self.set_name('InvitationReceivedDialog')
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_resizable(False)
        self.set_show_menubar(False)
        self.set_title(_('Group Chat Invitation '))

        self._ui = get_builder('groupchat_invitation_received.ui')
        self.add(self._ui.grid)
        self.show_all()
        self._ui.connect_signals(self)

        self.account = account
        self.room_jid = str(event.muc)
        self.from_ = str(event.from_)
        self.password = event.password

        if event.from_.bare_match(event.muc):
            contact_text = event.from_.resource
        else:
            contact = app.contacts.get_first_contact_from_jid(
                self.account, event.from_.bare)
            if contact is None:
                contact_text = str(event.from_)
            else:
                contact_text = contact.get_shown_name()

        invitation_label = _('<b>%(contact)s</b> has invited you to the '
                             'group chat <b>%(room_jid)s</b>') % \
                            {'contact': contact_text,
                             'room_jid': self.room_jid}
        self._ui.invitation_label.set_markup(invitation_label)

        if event.reason:
            comment = GLib.markup_escape_text(event.reason)
            comment = _('Comment: %s') % comment
            self._ui.comment_label.show()
            self._ui.comment_label.set_text(comment)

    def on_message_mnemonic_activate(self, _widget, _group_cycling=False):
        self._ui.message_expander.set_expanded(True)

    def on_accept_button_clicked(self, _widget):
        app.interface.show_or_join_groupchat(self.account,
                                             self.room_jid,
                                             password=self.password)
        self.destroy()

    def on_decline_button_clicked(self, _widget):
        text = self._ui.decline_message.get_text()
        app.connections[self.account].get_module('MUC').decline(
            self.room_jid, self.from_, text)
        self.destroy()


class PassphraseDialog:
    """
    Class for Passphrase dialog
    """
    def __init__(self, titletext, labeltext, checkbuttontext=None,
                 ok_handler=None, cancel_handler=None, transient_for=None):
        self._ui = get_builder('passphrase_dialog.ui')
        self.window = self._ui.get_object('passphrase_dialog')
        self.passphrase = -1
        self.window.set_title(titletext)
        self._ui.message_label.set_text(labeltext)

        self._ok = False

        self.cancel_handler = cancel_handler
        self.ok_handler = ok_handler
        self._ui.ok_button.connect('clicked', self.on_okbutton_clicked)
        self._ui.cancel_button.connect('clicked', self.on_cancelbutton_clicked)

        self._ui.connect_signals(self)
        if transient_for is None:
            transient_for = app.app.get_active_window()
        self.window.set_transient_for(transient_for)
        self.window.show_all()

        self.check = bool(checkbuttontext)
        if self._ui.save_passphrase_checkbutton:
            self._ui.save_passphrase_checkbutton.set_label(checkbuttontext)
        else:
            self._ui.save_passphrase_checkbutton.hide()

    def on_okbutton_clicked(self, _widget):
        if not self.ok_handler:
            return

        passph = self._ui.passphrase_entry.get_text()

        if self.check:
            checked = self._ui.save_passphrase_checkbutton.get_active()
        else:
            checked = False

        self._ok = True

        self.window.destroy()

        if isinstance(self.ok_handler, tuple):
            self.ok_handler[0](passph, checked, *self.ok_handler[1:])
        else:
            self.ok_handler(passph, checked)

    def on_cancelbutton_clicked(self, _widget):
        self.window.destroy()

    def on_passphrase_dialog_destroy(self, _widget):
        if self.cancel_handler and not self._ok:
            self.cancel_handler()


class ConfirmationDialog(Gtk.MessageDialog):
    def __init__(self, title, text, sec_text, buttons,
                 modal=True, transient_for=None):
        if transient_for is None:
            transient_for = app.app.get_active_window()
        Gtk.MessageDialog.__init__(self,
                                   title=title,
                                   text=text,
                                   transient_for=transient_for,
                                   message_type=Gtk.MessageType.QUESTION,
                                   modal=modal)

        self._buttons = {}

        for button in buttons:
            self._buttons[button.response] = button
            self.add_button(button.text, button.response)
            if button.is_default:
                self.set_default_response(button.response)
            if button.action is not None:
                widget = self.get_widget_for_response(button.response)
                widget.get_style_context().add_class(button.action.value)

        self.format_secondary_markup(sec_text)

        self.connect('response', self._on_response)

    def _on_response(self, _dialog, response):
        if response == Gtk.ResponseType.DELETE_EVENT:
            # Look if DELETE_EVENT is mapped to another response
            response = self._buttons.get(response, None)
            if response is None:
                # If DELETE_EVENT was not mapped we assume CANCEL
                response = Gtk.ResponseType.CANCEL

        button = self._buttons.get(response, None)
        if button is None:
            self.destroy()
            return

        if button.callback is not None:
            button.callback(*button.args, **button.kwargs)
        self.destroy()

    def show(self):
        self.show_all()


NewConfirmationDialog = ConfirmationDialog


class ConfirmationCheckDialog(ConfirmationDialog):
    def __init__(self, title, text, sec_text, check_text,
                 buttons, modal=True, transient_for=None):
        ConfirmationDialog.__init__(self,
                                    title,
                                    text,
                                    sec_text,
                                    buttons,
                                    transient_for=transient_for,
                                    modal=modal)

        self._checkbutton = Gtk.CheckButton.new_with_mnemonic(check_text)
        self._checkbutton.set_can_focus(False)
        self._checkbutton.set_margin_start(30)
        self._checkbutton.set_margin_end(30)
        label = self._checkbutton.get_child()
        label.set_line_wrap(True)
        label.set_max_width_chars(50)
        label.set_halign(Gtk.Align.START)
        label.set_line_wrap_mode(Pango.WrapMode.WORD)
        label.set_margin_start(10)

        self.get_content_area().add(self._checkbutton)

    def _on_response(self, _dialog, response):
        button = self._buttons.get(response)
        if button is not None:
            button.args.insert(0, self._checkbutton.get_active())
        super()._on_response(_dialog, response)


NewConfirmationCheckDialog = ConfirmationCheckDialog


class PastePreviewDialog(ConfirmationCheckDialog):
    def __init__(self, title, text, sec_text, check_text, image,
                 buttons, modal=True, transient_for=None):
        ConfirmationCheckDialog.__init__(self,
                                         title,
                                         text,
                                         sec_text,
                                         check_text,
                                         buttons,
                                         transient_for=transient_for,
                                         modal=modal)

        preview = Gtk.Image()
        preview.set_halign(Gtk.Align.CENTER)
        preview.get_style_context().add_class('preview-image')
        size = 300
        image_width = image.get_width()
        image_height = image.get_height()

        if size > image_width and size > image_height:
            preview.set_from_pixbuf(image)
        else:
            thumb_width, thumb_height = get_thumbnail_size(image, size)
            pixbuf_scaled = image.scale_simple(
                thumb_width, thumb_height, GdkPixbuf.InterpType.BILINEAR)
            preview.set_from_pixbuf(pixbuf_scaled)

        content_area = self.get_content_area()
        content_area.pack_start(preview, True, True, 0)
        content_area.reorder_child(preview, 2)


class InputDialog(ConfirmationDialog):
    def __init__(self, title, text, sec_text, buttons, input_str=None,
                 transient_for=None, modal=True):
        ConfirmationDialog.__init__(self,
                                    title,
                                    text,
                                    sec_text,
                                    buttons,
                                    transient_for=transient_for,
                                    modal=modal)

        self._entry = Gtk.Entry()
        self._entry.set_activates_default(True)
        self._entry.set_margin_start(50)
        self._entry.set_margin_end(50)

        if input_str:
            self._entry.set_text(input_str)
            self._entry.select_region(0, -1)  # select all

        self.get_content_area().add(self._entry)

    def _on_response(self, _dialog, response):
        button = self._buttons.get(response)
        if button is not None:
            button.args.insert(0, self._entry.get_text())
        super()._on_response(_dialog, response)


class TimeoutWindow:
    """
    Class designed to be derivated by other windows
    Derived windows close automatically after reaching the timeout
    """
    def __init__(self, timeout):
        self.title_text = ''
        self._countdown_left = timeout
        self._timeout_source_id = None

    def start_timeout(self):
        if self._countdown_left > 0:
            self.countdown()
            self._timeout_source_id = GLib.timeout_add_seconds(
                1, self.countdown)

    def stop_timeout(self, *args, **kwargs):
        if self._timeout_source_id is not None:
            GLib.source_remove(self._timeout_source_id)
            self._timeout_source_id = None
        self.set_title(self.title_text)

    def on_timeout(self):
        """
        To be implemented by derivated classes
        """

    def countdown(self):
        if self._countdown_left <= 0:
            self._timeout_source_id = None
            self.on_timeout()
            return False

        self.set_title('%s [%s]' % (
            self.title_text, str(self._countdown_left)))
        self._countdown_left -= 1
        return True


class ShortcutsWindow:
    def __init__(self):
        transient = app.app.get_active_window()
        builder = get_builder('shortcuts_window.ui')
        self.window = builder.get_object('shortcuts_window')
        self.window.connect('destroy', self._on_window_destroy)
        self.window.set_transient_for(transient)
        self.window.show_all()
        self.window.present()

    def _on_window_destroy(self, _widget):
        self.window = None
