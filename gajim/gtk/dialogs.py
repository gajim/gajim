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

from collections import namedtuple

from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common import helpers
from gajim.common.i18n import _
from gajim.common.const import ButtonAction

from gajim.gtk.util import get_builder
from gajim.gtk.util import load_icon


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
                default_kwargs['text'] = 'OK'

            elif type_ == 'Cancel':
                default_kwargs['response'] = Gtk.ResponseType.CANCEL
                default_kwargs['text'] = _('Cancel')

            elif type_ == 'Delete':
                default_kwargs['response'] = Gtk.ResponseType.OK
                default_kwargs['text'] = _('Delete')
                default_kwargs['action'] = ButtonAction.DESTRUCTIVE

            elif type_ == 'Remove':
                default_kwargs['response'] = Gtk.ResponseType.OK
                default_kwargs['text'] = _('Remove')
                default_kwargs['action'] = ButtonAction.DESTRUCTIVE
            else:
                raise ValueError('Unknown button type: %s ' % type_)

        default_kwargs.update(kwargs)
        return cls(**default_kwargs)


class HigDialog(Gtk.MessageDialog):
    def __init__(self, parent, type_, buttons, pritext, sectext,
    on_response_ok=None, on_response_cancel=None, on_response_yes=None,
    on_response_no=None):
        self.call_cancel_on_destroy = True
        Gtk.MessageDialog.__init__(self, transient_for=parent,
           modal=True, destroy_with_parent=True,
           message_type=type_, buttons=buttons, text=pritext)

        self.format_secondary_markup(sectext)

        self.possible_responses = {Gtk.ResponseType.OK: on_response_ok,
            Gtk.ResponseType.CANCEL: on_response_cancel,
            Gtk.ResponseType.YES: on_response_yes,
            Gtk.ResponseType.NO: on_response_no}

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
                self.possible_responses[response_id][0](dialog,
                    *self.possible_responses[response_id][1:])
        else:
            self.possible_responses[response_id](dialog)

    def on_dialog_destroy(self, widget):
        if not self.call_cancel_on_destroy:
            return
        cancel_handler = self.possible_responses[Gtk.ResponseType.CANCEL]
        if not cancel_handler:
            return False
        if isinstance(cancel_handler, tuple):
            cancel_handler[0](None, *cancel_handler[1:])
        else:
            cancel_handler(None)

    def popup(self):
        """
        Show dialog
        """
        vb = self.get_children()[0].get_children()[0] # Give focus to top vbox
#        vb.set_flags(Gtk.CAN_FOCUS)
        vb.grab_focus()
        self.show_all()


class AspellDictError:
    def __init__(self, lang):
        ErrorDialog(
            _('Dictionary for language "%s" not available') % lang,
            _('You have to install the dictionary "%s" to use spellchecking, '
              'or choose another language by setting the speller_language '
              'option.\n\n'
              'Highlighting misspelled words feature will not be used') % lang)


class ConfirmationDialog(HigDialog):
    """
    HIG compliant confirmation dialog
    """

    def __init__(self, pritext, sectext='', on_response_ok=None,
    on_response_cancel=None, transient_for=None):
        self.user_response_ok = on_response_ok
        self.user_response_cancel = on_response_cancel
        HigDialog.__init__(self, transient_for,
           Gtk.MessageType.QUESTION, Gtk.ButtonsType.OK_CANCEL, pritext, sectext,
           self.on_response_ok, self.on_response_cancel)
        self.popup()

    def on_response_ok(self, widget):
        if self.user_response_ok:
            if isinstance(self.user_response_ok, tuple):
                self.user_response_ok[0](*self.user_response_ok[1:])
            else:
                self.user_response_ok()
        self.call_cancel_on_destroy = False
        self.destroy()

    def on_response_cancel(self, widget):
        if self.user_response_cancel:
            if isinstance(self.user_response_cancel, tuple):
                self.user_response_cancel[0](*self.user_response_ok[1:])
            else:
                self.user_response_cancel()
        self.call_cancel_on_destroy = False
        self.destroy()


class NonModalConfirmationDialog(HigDialog):
    """
    HIG compliant non modal confirmation dialog
    """

    def __init__(self, pritext, sectext='', on_response_ok=None,
    on_response_cancel=None):
        self.user_response_ok = on_response_ok
        self.user_response_cancel = on_response_cancel
        transient_for = app.app.get_active_window()
        HigDialog.__init__(self, transient_for, Gtk.MessageType.QUESTION,
            Gtk.ButtonsType.OK_CANCEL, pritext, sectext, self.on_response_ok,
            self.on_response_cancel)
        self.set_modal(False)

    def on_response_ok(self, widget):
        if self.user_response_ok:
            if isinstance(self.user_response_ok, tuple):
                self.user_response_ok[0](*self.user_response_ok[1:])
            else:
                self.user_response_ok()
        self.call_cancel_on_destroy = False
        self.destroy()

    def on_response_cancel(self, widget):
        if self.user_response_cancel:
            if isinstance(self.user_response_cancel, tuple):
                self.user_response_cancel[0](*self.user_response_cancel[1:])
            else:
                self.user_response_cancel()
        self.call_cancel_on_destroy = False
        self.destroy()


class WarningDialog(HigDialog):
    """
    HIG compliant warning dialog
    """

    def __init__(self, pritext, sectext='', transient_for=None):
        if transient_for is None:
            transient_for = app.app.get_active_window()
        HigDialog.__init__(self, transient_for, Gtk.MessageType.WARNING,
            Gtk.ButtonsType.OK, pritext, sectext)
        self.set_modal(False)
        self.popup()


class InformationDialog(HigDialog):
    """
    HIG compliant info dialog
    """

    def __init__(self, pritext, sectext='', transient_for=None):
        if transient_for is None:
            transient_for = app.app.get_active_window()
        HigDialog.__init__(self, transient_for, Gtk.MessageType.INFO, Gtk.ButtonsType.OK,
            pritext, sectext)
        self.set_modal(False)
        self.popup()


class ErrorDialog(HigDialog):
    """
    HIG compliant error dialog
    """

    def __init__(self, pritext, sectext='', on_response_ok=None,
    on_response_cancel=None, transient_for=None):
        if transient_for is None:
            transient_for = app.app.get_active_window()
        HigDialog.__init__(self, transient_for, Gtk.MessageType.ERROR, Gtk.ButtonsType.OK,
            pritext, sectext, on_response_ok=on_response_ok,
            on_response_cancel=on_response_cancel)
        self.popup()


class YesNoDialog(HigDialog):
    """
    HIG compliant YesNo dialog
    """

    def __init__(self, pritext, sectext='', checktext='', text_label=None,
    on_response_yes=None, on_response_no=None, type_=Gtk.MessageType.QUESTION,
    transient_for=None):
        self.user_response_yes = on_response_yes
        self.user_response_no = on_response_no
        if transient_for is None:
            transient_for = app.app.get_active_window()
        HigDialog.__init__(self, transient_for, type_, Gtk.ButtonsType.YES_NO, pritext,
            sectext, on_response_yes=self.on_response_yes,
            on_response_no=self.on_response_no)

        vbox = self.get_content_area()
        if checktext:
            self.checkbutton = Gtk.CheckButton.new_with_mnemonic(checktext)
            vbox.pack_start(self.checkbutton, False, True, 0)
        else:
            self.checkbutton = None
        if text_label:
            label = Gtk.Label(label=text_label)
            vbox.pack_start(label, False, True, 0)
            buff = Gtk.TextBuffer()
            self.textview = Gtk.TextView.new_with_buffer(buff)
            frame = Gtk.Frame()
            frame.set_shadow_type(Gtk.ShadowType.IN)
            frame.add(self.textview)
            vbox.pack_start(frame, False, True, 0)
        else:
            self.textview = None
        self.set_modal(False)
        self.popup()

    def on_response_yes(self, widget):
        if self.user_response_yes:
            if self.textview:
                buff = self.textview.get_buffer()
                start, end = buff.get_bounds()
                txt = self.textview.get_buffer().get_text(start, end, True)

            if isinstance(self.user_response_yes, tuple):
                if self.textview:
                    self.user_response_yes[0](self.is_checked(), txt,
                        *self.user_response_yes[1:])
                else:
                    self.user_response_yes[0](self.is_checked(),
                        *self.user_response_yes[1:])
            else:
                if self.textview:
                    self.user_response_yes(self.is_checked(), txt)
                else:
                    self.user_response_yes(self.is_checked())
        self.call_cancel_on_destroy = False
        self.destroy()

    def on_response_no(self, widget):
        if self.user_response_no:
            if self.textview:
                buff = self.textview.get_buffer()
                start, end = buff.get_bounds()
                txt = self.textview.get_buffer().get_text(start, end, True)

            if isinstance(self.user_response_no, tuple):
                if self.textview:
                    self.user_response_no[0](txt, *self.user_response_no[1:])
                else:
                    self.user_response_no[0](*self.user_response_no[1:])
            else:
                if self.textview:
                    self.user_response_no(txt)
                else:
                    self.user_response_no()
        self.call_cancel_on_destroy = False
        self.destroy()

    def is_checked(self):
        """
        Get active state of the checkbutton
        """
        if not self.checkbutton:
            return False
        return self.checkbutton.get_active()


class ConfirmationDialogCheck(ConfirmationDialog):
    """
    HIG compliant confirmation dialog with checkbutton
    """

    def __init__(self, pritext, sectext='', checktext='', on_response_ok=None,
    on_response_cancel=None, is_modal=True, transient_for=None):
        self.user_response_ok = on_response_ok
        self.user_response_cancel = on_response_cancel
        if transient_for is None:
            transient_for = app.app.get_active_window()
        HigDialog.__init__(self, transient_for, Gtk.MessageType.QUESTION,
           Gtk.ButtonsType.OK_CANCEL, pritext, sectext, self.on_response_ok,
           self.on_response_cancel)

        self.set_default_response(Gtk.ResponseType.OK)

        ok_button = self.get_widget_for_response(Gtk.ResponseType.OK)
        ok_button.grab_focus()

        self.checkbutton = Gtk.CheckButton.new_with_mnemonic(checktext)
        self.get_content_area().pack_start(self.checkbutton, False, True, 0)
        self.set_modal(is_modal)
        self.popup()

    def on_response_ok(self, widget):
        if self.user_response_ok:
            if isinstance(self.user_response_ok, tuple):
                self.user_response_ok[0](self.is_checked(),
                    *self.user_response_ok[1:])
            else:
                self.user_response_ok(self.is_checked())
        self.call_cancel_on_destroy = False
        self.destroy()

    def on_response_cancel(self, widget):
        if self.user_response_cancel:
            if isinstance(self.user_response_cancel, tuple):
                self.user_response_cancel[0](self.is_checked(),
                    *self.user_response_cancel[1:])
            else:
                self.user_response_cancel(self.is_checked())
        self.call_cancel_on_destroy = False
        self.destroy()

    def is_checked(self):
        """
        Get active state of the checkbutton
        """
        return self.checkbutton.get_active()


class ConfirmationDialogDoubleCheck(ConfirmationDialog):
    """
    HIG compliant confirmation dialog with 2 checkbuttons
    """

    def __init__(self, pritext, sectext='', checktext1='', checktext2='',
    tooltip1='', tooltip2='', on_response_ok=None, on_response_cancel=None,
    transient_for=None, is_modal=True):
        self.user_response_ok = on_response_ok
        self.user_response_cancel = on_response_cancel
        if transient_for is None:
            transient_for = app.app.get_active_window()
        HigDialog.__init__(self, transient_for, Gtk.MessageType.QUESTION,
           Gtk.ButtonsType.OK_CANCEL, pritext, sectext, self.on_response_ok,
           self.on_response_cancel)

        self.set_default_response(Gtk.ResponseType.OK)

        ok_button = self.get_widget_for_response(Gtk.ResponseType.OK)
        ok_button.grab_focus()

        vbox = self.get_content_area()
        if checktext1:
            self.checkbutton1 = Gtk.CheckButton.new_with_mnemonic(checktext1)
            if tooltip1:
                self.checkbutton1.set_tooltip_text(tooltip1)
            vbox.pack_start(self.checkbutton1, False, True, 0)
        else:
            self.checkbutton1 = None
        if checktext2:
            self.checkbutton2 = Gtk.CheckButton.new_with_mnemonic(checktext2)
            if tooltip2:
                self.checkbutton2.set_tooltip_text(tooltip2)
            vbox.pack_start(self.checkbutton2, False, True, 0)
        else:
            self.checkbutton2 = None

        self.set_modal(is_modal)
        self.popup()

    def on_response_ok(self, widget):
        if self.user_response_ok:
            if isinstance(self.user_response_ok, tuple):
                self.user_response_ok[0](self.is_checked(),
                    *self.user_response_ok[1:])
            else:
                self.user_response_ok(self.is_checked())
        self.call_cancel_on_destroy = False
        self.destroy()

    def on_response_cancel(self, widget):
        if self.user_response_cancel:
            if isinstance(self.user_response_cancel, tuple):
                self.user_response_cancel[0](*self.user_response_cancel[1:])
            else:
                self.user_response_cancel()
        self.call_cancel_on_destroy = False
        self.destroy()

    def is_checked(self):
        ''' Get active state of the checkbutton '''
        if self.checkbutton1:
            is_checked_1 = self.checkbutton1.get_active()
        else:
            is_checked_1 = False
        if self.checkbutton2:
            is_checked_2 = self.checkbutton2.get_active()
        else:
            is_checked_2 = False
        return [is_checked_1, is_checked_2]


class PlainConnectionDialog(ConfirmationDialogDoubleCheck):
    """
    Dialog that is shown when using an insecure connection
    """
    def __init__(self, account, on_ok, on_cancel):
        pritext = _('Insecure connection')
        sectext = _('You are about to connect to the account %(account)s '
            '(%(server)s) insecurely. This means conversations will not be '
            'encrypted, and is strongly discouraged.\nAre you sure you want '
            'to do that?') % {'account': account,
            'server': app.get_hostname_from_account(account)}
        checktext1 = _('Yes, I really want to connect insecurely')
        tooltip1 = _('Gajim will NOT connect unless you check this box')
        checktext2 = _('_Do not ask me again')
        ConfirmationDialogDoubleCheck.__init__(self, pritext, sectext,
            checktext1, checktext2, tooltip1=tooltip1, on_response_ok=on_ok,
            on_response_cancel=on_cancel, is_modal=False)
        self.ok_button = self.get_widget_for_response(Gtk.ResponseType.OK)
        self.ok_button.set_sensitive(False)
        self.checkbutton1.connect('clicked', self.on_checkbutton_clicked)
        self.set_title(_('Insecure connection'))

    def on_checkbutton_clicked(self, widget):
        self.ok_button.set_sensitive(widget.get_active())

class ConfirmationDialogDoubleRadio(ConfirmationDialog):
    """
    HIG compliant confirmation dialog with 2 radios
    """
    def __init__(self, pritext, sectext='', radiotext1='', radiotext2='',
    on_response_ok=None, on_response_cancel=None, is_modal=True, transient_for=None):
        self.user_response_ok = on_response_ok
        self.user_response_cancel = on_response_cancel

        if transient_for is None:
            transient_for = app.app.get_active_window()
        HigDialog.__init__(self, transient_for, Gtk.MessageType.QUESTION,
                Gtk.ButtonsType.OK_CANCEL, pritext, sectext, self.on_response_ok,
                self.on_response_cancel)

        self.set_default_response(Gtk.ResponseType.OK)

        ok_button = self.get_widget_for_response(Gtk.ResponseType.OK)
        ok_button.grab_focus()

        vbox = self.get_content_area()
        self.radiobutton1 = Gtk.RadioButton(label=radiotext1)
        vbox.pack_start(self.radiobutton1, False, True, 0)

        self.radiobutton2 = Gtk.RadioButton(group=self.radiobutton1,
                label=radiotext2)
        vbox.pack_start(self.radiobutton2, False, True, 0)

        self.set_modal(is_modal)
        self.popup()

    def on_response_ok(self, widget):
        if self.user_response_ok:
            if isinstance(self.user_response_ok, tuple):
                self.user_response_ok[0](self.is_checked(),
                        *self.user_response_ok[1:])
            else:
                self.user_response_ok(self.is_checked())
        self.call_cancel_on_destroy = False
        self.destroy()

    def on_response_cancel(self, widget):
        if self.user_response_cancel:
            if isinstance(self.user_response_cancel, tuple):
                self.user_response_cancel[0](*self.user_response_cancel[1:])
            else:
                self.user_response_cancel()
        self.call_cancel_on_destroy = False
        self.destroy()

    def is_checked(self):
        ''' Get active state of the checkbutton '''
        if self.radiobutton1:
            is_checked_1 = self.radiobutton1.get_active()
        else:
            is_checked_1 = False
        if self.radiobutton2:
            is_checked_2 = self.radiobutton2.get_active()
        else:
            is_checked_2 = False
        return [is_checked_1, is_checked_2]

class FTOverwriteConfirmationDialog(ConfirmationDialog):
    """
    HIG compliant confirmation dialog to overwrite or resume a file transfert
    """
    def __init__(self, pritext, sectext='', propose_resume=True,
    on_response=None, transient_for=None):
        if transient_for is None:
            transient_for = app.app.get_active_window()
        HigDialog.__init__(self, transient_for, Gtk.MessageType.QUESTION,
            Gtk.ButtonsType.CANCEL, pritext, sectext)

        self.on_response = on_response

        if propose_resume:
            b = Gtk.Button(label='', stock=Gtk.STOCK_REFRESH)
            align = b.get_children()[0]
            hbox = align.get_children()[0]
            label = hbox.get_children()[1]
            label.set_text(_('_Resume'))
            label.set_use_underline(True)
            self.add_action_widget(b, 100)

        b = Gtk.Button(label='', stock=Gtk.STOCK_SAVE_AS)
        align = b.get_children()[0]
        hbox = align.get_children()[0]
        label = hbox.get_children()[1]
        label.set_text(_('Re_place'))
        label.set_use_underline(True)
        self.add_action_widget(b, 200)

        self.connect('response', self.on_dialog_response)
        self.show_all()

    def on_dialog_response(self, dialog, response):
        if self.on_response:
            if isinstance(self.on_response, tuple):
                self.on_response[0](response, *self.on_response[1:])
            else:
                self.on_response(response)
        self.call_cancel_on_destroy = False
        self.destroy()


class CommonInputDialog:
    """
    Common Class for Input dialogs
    """

    def __init__(self, title, label_str, is_modal, ok_handler, cancel_handler,
                 transient_for=None):
        self.dialog = self.xml.get_object('input_dialog')
        label = self.xml.get_object('label')
        self.dialog.set_title(title)
        label.set_markup(label_str)
        self.cancel_handler = cancel_handler
        self.vbox = self.xml.get_object('vbox')
        if transient_for is None:
            transient_for = app.app.get_active_window()
        self.dialog.set_transient_for(transient_for)

        self.ok_handler = ok_handler
        okbutton = self.xml.get_object('okbutton')
        okbutton.connect('clicked', self.on_okbutton_clicked)
        cancelbutton = self.xml.get_object('cancelbutton')
        cancelbutton.connect('clicked', self.on_cancelbutton_clicked)
        self.xml.connect_signals(self)
        self.dialog.show_all()

    def on_input_dialog_destroy(self, widget):
        if self.cancel_handler:
            self.cancel_handler()

    def on_okbutton_clicked(self, widget):
        user_input = self.get_text()
        if user_input:
            user_input = user_input
        self.cancel_handler = None
        self.dialog.destroy()
        if isinstance(self.ok_handler, tuple):
            self.ok_handler[0](user_input, *self.ok_handler[1:])
        else:
            self.ok_handler(user_input)

    def on_cancelbutton_clicked(self, widget):
        self.dialog.destroy()

    def destroy(self):
        self.dialog.destroy()


class InputDialog(CommonInputDialog):
    """
    Class for Input dialog
    """

    def __init__(self, title, label_str, input_str=None, is_modal=True,
                 ok_handler=None, cancel_handler=None, transient_for=None):
        self.xml = get_builder('input_dialog.ui')
        CommonInputDialog.__init__(self, title, label_str, is_modal,
                                   ok_handler, cancel_handler,
                                   transient_for=transient_for)
        self.input_entry = self.xml.get_object('input_entry')
        if input_str:
            self.set_entry(input_str)

    def on_input_dialog_delete_event(self, widget, event):
        '''
        may be implemented by subclasses
        '''
        pass

    def set_entry(self, value):
        self.input_entry.set_text(value)
        self.input_entry.select_region(0, -1) # select all

    def get_text(self):
        return self.input_entry.get_text()


class InputDialogCheck(InputDialog):
    """
    Class for Input dialog
    """

    def __init__(self, title, label_str, checktext='', input_str=None,
                 is_modal=True, ok_handler=None, cancel_handler=None,
                 transient_for=None):
        self.xml = get_builder('input_dialog.ui')
        InputDialog.__init__(self, title, label_str, input_str=input_str,
                             is_modal=is_modal, ok_handler=ok_handler,
                             cancel_handler=cancel_handler,
                             transient_for=transient_for)
        self.input_entry = self.xml.get_object('input_entry')
        if input_str:
            self.input_entry.set_text(input_str)
            self.input_entry.select_region(0, -1) # select all

        if checktext:
            self.checkbutton = Gtk.CheckButton.new_with_mnemonic(checktext)
            self.vbox.pack_start(self.checkbutton, False, True, 0)
            self.checkbutton.show()

    def on_okbutton_clicked(self, widget):
        user_input = self.get_text()
        if user_input:
            user_input = user_input
        self.cancel_handler = None
        self.dialog.destroy()
        if isinstance(self.ok_handler, tuple):
            self.ok_handler[0](user_input, self.is_checked(), *self.ok_handler[1:])
        else:
            self.ok_handler(user_input, self.is_checked())

    def get_text(self):
        return self.input_entry.get_text()

    def is_checked(self):
        """
        Get active state of the checkbutton
        """
        try:
            return self.checkbutton.get_active()
        except Exception:
            # There is no checkbutton
            return False


class ChangeNickDialog(InputDialogCheck):
    """
    Class for changing room nickname in case of conflict
    """

    def __init__(self, account, room_jid, title, prompt, check_text=None,
                 change_nick=False, transient_for=None):
        """
        change_nick must be set to True when we are already occupant of the room
        and we are changing our nick
        """
        InputDialogCheck.__init__(self, title, '',
                                  input_str='', is_modal=True, ok_handler=None,
                                  cancel_handler=None,
                                  transient_for=transient_for)
        self.room_queue = [(account, room_jid, prompt, change_nick)]
        self.check_next()

    def on_input_dialog_delete_event(self, widget, event):
        self.on_cancelbutton_clicked(widget)
        return True

    def setup_dialog(self):
        self.gc_control = app.interface.msg_win_mgr.get_gc_control(
                self.room_jid, self.account)
        if not self.gc_control and \
        self.room_jid in app.interface.minimized_controls[self.account]:
            self.gc_control = \
                app.interface.minimized_controls[self.account][self.room_jid]
        if not self.gc_control:
            self.check_next()
            return
        label = self.xml.get_object('label')
        label.set_markup(self.prompt)
        self.set_entry(self.gc_control.nick + \
                app.config.get('gc_proposed_nick_char'))

    def check_next(self):
        if not self.room_queue:
            self.cancel_handler = None
            self.dialog.destroy()
            if 'change_nick_dialog' in app.interface.instances:
                del app.interface.instances['change_nick_dialog']
            return
        self.account, self.room_jid, self.prompt, self.change_nick = \
            self.room_queue.pop(0)
        self.setup_dialog()
        self.dialog.show()

    def on_okbutton_clicked(self, widget):
        nick = self.get_text()
        if nick:
            nick = nick
        # send presence to room
        try:
            nick = helpers.parse_resource(nick)
        except Exception:
            # invalid char
            ErrorDialog(_('Invalid nickname'),
                    _('The nickname contains invalid characters.'))
            return
        self.on_ok(nick, self.is_checked())

    def on_ok(self, nick, is_checked):
        app.connections[self.account].join_gc(nick, self.room_jid, None,
            change_nick=self.change_nick)
        if app.gc_connected[self.account][self.room_jid]:
            # We are changing nick, we will change self.nick when we receive
            # presence that inform that it works
            self.gc_control.new_nick = nick
        else:
            # We are connecting, we will not get a changed nick presence so
            # change it NOW. We don't already have a nick so it's harmless
            self.gc_control.nick = nick
        self.check_next()

    def on_cancelbutton_clicked(self, widget):
        self.gc_control.new_nick = ''
        self.check_next()

    def add_room(self, account, room_jid, prompt, change_nick=False):
        if (account, room_jid, prompt, change_nick) not in self.room_queue:
            self.room_queue.append((account, room_jid, prompt, change_nick))


class InputTextDialog(CommonInputDialog):
    """
    Class for multilines Input dialog (more place than InputDialog)
    """

    def __init__(self, title, label_str, input_str=None, is_modal=True,
                 ok_handler=None, cancel_handler=None, transient_for=None):
        self.xml = get_builder('input_text_dialog.ui')
        CommonInputDialog.__init__(self, title, label_str, is_modal,
                                   ok_handler, cancel_handler,
                                   transient_for=transient_for)
        self.input_buffer = self.xml.get_object('input_textview').get_buffer()
        if input_str:
            self.input_buffer.set_text(input_str)
            start_iter, end_iter = self.input_buffer.get_bounds()
            self.input_buffer.select_range(start_iter, end_iter) # select all

    def get_text(self):
        start_iter, end_iter = self.input_buffer.get_bounds()
        return self.input_buffer.get_text(start_iter, end_iter, True)


class DoubleInputDialog:
    """
    Class for Double Input dialog
    """

    def __init__(self, title, label_str1, label_str2, input_str1=None,
    input_str2=None, is_modal=True, ok_handler=None, cancel_handler=None,
    transient_for=None):
        self.xml = get_builder('dubbleinput_dialog.ui')
        self.dialog = self.xml.get_object('dubbleinput_dialog')
        label1 = self.xml.get_object('label1')
        self.input_entry1 = self.xml.get_object('input_entry1')
        label2 = self.xml.get_object('label2')
        self.input_entry2 = self.xml.get_object('input_entry2')
        self.dialog.set_title(title)
        label1.set_markup(label_str1)
        label2.set_markup(label_str2)
        self.cancel_handler = cancel_handler
        if input_str1:
            self.input_entry1.set_text(input_str1)
            self.input_entry1.select_region(0, -1) # select all
        if input_str2:
            self.input_entry2.set_text(input_str2)
            self.input_entry2.select_region(0, -1) # select all
        if transient_for is None:
            transient_for = app.app.get_active_window()
        self.dialog.set_transient_for(transient_for)

        self.dialog.set_modal(is_modal)

        self.ok_handler = ok_handler
        okbutton = self.xml.get_object('okbutton')
        okbutton.connect('clicked', self.on_okbutton_clicked)
        cancelbutton = self.xml.get_object('cancelbutton')
        cancelbutton.connect('clicked', self.on_cancelbutton_clicked)
        self.xml.connect_signals(self)
        self.dialog.show_all()

    def on_dubbleinput_dialog_destroy(self, widget):
        if not self.cancel_handler:
            return False
        if isinstance(self.cancel_handler, tuple):
            self.cancel_handler[0](*self.cancel_handler[1:])
        else:
            self.cancel_handler()

    def on_okbutton_clicked(self, widget):
        user_input1 = self.input_entry1.get_text()
        user_input2 = self.input_entry2.get_text()
        self.cancel_handler = None
        self.dialog.destroy()
        if not self.ok_handler:
            return
        if isinstance(self.ok_handler, tuple):
            self.ok_handler[0](user_input1, user_input2, *self.ok_handler[1:])
        else:
            self.ok_handler(user_input1, user_input2)

    def on_cancelbutton_clicked(self, widget):
        self.dialog.destroy()
        if not self.cancel_handler:
            return
        if isinstance(self.cancel_handler, tuple):
            self.cancel_handler[0](*self.cancel_handler[1:])
        else:
            self.cancel_handler()


class CertificatDialog(InformationDialog):
    def __init__(self, transient_for, account, cert):
        issuer = cert.get_issuer()
        subject = cert.get_subject()
        InformationDialog.__init__(self,
            _('Certificate for account %s') % account, _('''<b>Issued to:</b>
Common Name (CN): %(scn)s
Organization (O): %(sorg)s
Organizationl Unit (OU): %(sou)s
Serial Number: %(sn)s

<b>Issued by:</b>
Common Name (CN): %(icn)s
Organization (O): %(iorg)s
Organizationl Unit (OU): %(iou)s

<b>Validity:</b>
Issued on: %(io)s
Expires on: %(eo)s

<b>Fingerprint</b>
SHA-1 Fingerprint: %(sha1)s

SHA-256 Fingerprint: %(sha256)s
''') % {
            'scn': subject.commonName, 'sorg': subject.organizationName,
            'sou': subject.organizationalUnitName,
            'sn': cert.get_serial_number(), 'icn': issuer.commonName,
            'iorg': issuer.organizationName,
            'iou': issuer.organizationalUnitName,
            'io': cert.get_notBefore().decode('utf-8'),
            'eo': cert.get_notAfter().decode('utf-8'),
            'sha1': cert.digest('sha1').decode('utf-8'),
            'sha256': cert.digest('sha256').decode('utf-8')})
        surface = load_icon('application-certificate', self, size=32)
        if surface is not None:
            img = Gtk.Image.new_from_surface(surface)
            img.show_all()
            self.set_image(img)
        self.set_transient_for(transient_for)
        self.set_title(_('Certificate for account %s') % account)


class SSLErrorDialog(ConfirmationDialogDoubleCheck):
    def __init__(self, account, certificate, pritext, sectext, checktext1,
                 checktext2, on_response_ok=None, on_response_cancel=None):
        self.account = account
        self.cert = certificate
        ConfirmationDialogDoubleCheck.__init__(
            self, pritext, sectext,
            checktext1, checktext2, on_response_ok=on_response_ok,
            on_response_cancel=on_response_cancel, is_modal=False)
        b = Gtk.Button(_('View certificate…'))
        b.connect('clicked', self.on_cert_clicked)
        b.show_all()
        area = self.get_action_area()
        area.pack_start(b, True, True, 0)

    def on_cert_clicked(self, button):
        CertificatDialog(self, self.account, self.cert)


class ChangePasswordDialog(Gtk.Dialog):
    def __init__(self, account, success_cb, transient_for):
        super().__init__(title=_('Change Password'),
                         transient_for=transient_for,
                         destroy_with_parent=True)

        self._account = account
        self._success_cb = success_cb

        self._builder = get_builder('change_password_dialog.ui')
        self.get_content_area().add(
            self._builder.get_object('change_password_box'))
        self._password1_entry = self._builder.get_object('password1_entry')
        self._password2_entry = self._builder.get_object('password2_entry')
        self._error_label = self._builder.get_object('error_label')

        self.add_button(_('_OK'), Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        self.get_style_context().add_class('dialog-margin')
        self.connect('response', self._on_dialog_response)
        self.show_all()

    def _on_dialog_response(self, dialog, response):
        if response != Gtk.ResponseType.OK:
            self.destroy()
            return

        password1 = self._password1_entry.get_text()
        if not password1:
            self._error_label.set_text(_('You must enter a password'))
            return
        password2 = self._password2_entry.get_text()
        if password1 != password2:
            self._error_label.set_text(_('Passwords do not match'))
            return

        self._password1_entry.set_sensitive(False)
        self._password2_entry.set_sensitive(False)

        con = app.connections[self._account]
        con.get_module('Register').change_password(
            password1, self._on_success, self._on_error)

    def _on_success(self):
        self._success_cb(self._password1_entry.get_text())
        self.destroy()

    def _on_error(self, error_text):
        self._error_label.set_text(error_text)
        self._password1_entry.set_sensitive(True)
        self._password2_entry.set_sensitive(True)


class NewConfirmationDialog(Gtk.MessageDialog):
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


class NewConfirmationCheckDialog(NewConfirmationDialog):
    def __init__(self, title, text, sec_text, check_text,
                 buttons, modal=True, transient_for=None):
        NewConfirmationDialog.__init__(self,
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


class ShortcutsWindow:
    def __init__(self):
        transient = app.app.get_active_window()
        builder = get_builder('shortcuts_window.ui')
        self.window = builder.get_object('shortcuts_window')
        self.window.connect('destroy', self._on_window_destroy)
        self.window.set_transient_for(transient)
        self.window.show_all()
        self.window.present()

    def _on_window_destroy(self, widget):
        self.window = None
