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

from __future__ import annotations

from typing import Any
from typing import cast
from typing import NamedTuple

from gi.repository import GdkPixbuf
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.const import ButtonAction
from gajim.common.i18n import _

from gajim.gtk.builder import get_builder
from gajim.gtk.util import get_thumbnail_size


class DialogButton(NamedTuple):
    response: Gtk.ResponseType
    text: str
    callback: Any
    args: Any
    kwargs: Any
    action: ButtonAction | None
    is_default: bool

    @classmethod
    def make(cls, type_: str | None = None, **kwargs: Any) -> DialogButton:
        # Defaults
        default_kwargs: dict[str, Any] = {
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
                raise ValueError(f'Unknown button type: {type_} ')

        default_kwargs.update(kwargs)
        return cls(**default_kwargs)


class HigDialog(Gtk.MessageDialog):

    _message_type = Gtk.MessageType.INFO
    _buttons_type = Gtk.ButtonsType.OK
    _modal = True

    def __init__(self,
                 text: str,
                 secondary_text: str | None = None,
                 *,
                 use_markup: bool = False,
                 secondary_use_markup: bool = False,
                 transient_for: Gtk.Window | None = None,
                 ) -> None:

        if transient_for is None:
            transient_for = app.app.get_active_window()
            assert transient_for is not None

        Gtk.MessageDialog.__init__(self,
                                   transient_for=transient_for,
                                   modal=self._modal,
                                   destroy_with_parent=True,
                                   message_type=self._message_type,
                                   buttons=self._buttons_type,
                                   text=text,
                                   use_markup=use_markup,
                                   secondary_text=secondary_text or '',
                                   secondary_use_markup=secondary_use_markup)

        self.connect('response', self.on_response)
        self.show()

    def on_response(self,
                    _dialog: Gtk.MessageDialog,
                    _response_id: Gtk.ResponseType
                    ) -> None:
        self.destroy()


class InformationDialog(HigDialog):

    _message_type = Gtk.MessageType.INFO
    _modal = False


class WarningDialog(HigDialog):

    _message_type = Gtk.MessageType.WARNING
    _modal = False


class ErrorDialog(HigDialog):

    _message_type = Gtk.MessageType.ERROR
    _modal = True


class ConfirmationDialog(Gtk.MessageDialog):
    def __init__(self,
                 title: str,
                 text: str,
                 sec_text: str,
                 buttons: list[DialogButton],
                 modal: bool = True,
                 transient_for: Gtk.Window | None = None
                 ) -> None:
        if transient_for is None:
            transient_for = app.app.get_active_window()
        Gtk.MessageDialog.__init__(self,
                                   title=title,
                                   text=text,
                                   transient_for=transient_for,
                                   message_type=Gtk.MessageType.QUESTION,
                                   modal=modal)

        self.get_style_context().add_class('confirmation-dialog')

        self._buttons: dict[Gtk.ResponseType, DialogButton] = {}

        for button in buttons:
            if button.response == Gtk.ResponseType.CANCEL:
                # Map CANCEL to DELETE_EVENT. Otherwise, button args for
                # CANCEL will not be propagated (i.e. checkbutton state)
                self._buttons[Gtk.ResponseType.DELETE_EVENT] = button

            self._buttons[button.response] = button
            self.add_button(button.text, button.response)
            if button.is_default:
                self.set_default_response(button.response)
            if button.action is not None:
                widget = cast(
                    Gtk.Button, self.get_widget_for_response(button.response))
                widget.get_style_context().add_class(button.action.value)

        self.format_secondary_markup(sec_text)

        self.connect('response', self._on_response)

    def _on_response(self,
                     _dialog: Gtk.MessageDialog,
                     response: Gtk.ResponseType
                     ) -> None:
        if response == Gtk.ResponseType.DELETE_EVENT:
            # Look if DELETE_EVENT is mapped to another response
            button = self._buttons.get(response, None)
            if button is None:
                # If DELETE_EVENT was not mapped we assume CANCEL
                response = Gtk.ResponseType.CANCEL

        button = self._buttons.get(response, None)
        if button is None:
            self.destroy()
            return

        if button.callback is not None:
            button.callback(*button.args, **button.kwargs)
        self.destroy()

    def show(self) -> None:
        self.show_all()


class ConfirmationCheckDialog(ConfirmationDialog):
    def __init__(self,
                 title: str,
                 text: str,
                 sec_text: str,
                 check_text: str,
                 buttons: list[DialogButton],
                 modal: bool = True,
                 transient_for: Gtk.Window | None = None
                 ) -> None:
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
        assert isinstance(label, Gtk.Label)
        label.set_line_wrap(True)
        label.set_max_width_chars(50)
        label.set_halign(Gtk.Align.START)
        label.set_line_wrap_mode(Pango.WrapMode.WORD)
        label.set_margin_start(10)

        self.get_content_area().add(self._checkbutton)

    def _on_response(self,
                     _dialog: Gtk.MessageDialog,
                     response: Gtk.ResponseType
                     ) -> None:
        button = self._buttons.get(response)
        if button is not None:
            button.args.insert(0, self._checkbutton.get_active())
        super()._on_response(_dialog, response)


class PastePreviewDialog(ConfirmationDialog):
    def __init__(self,
                 title: str,
                 text: str,
                 sec_text: str,
                 check_text: str,
                 image: GdkPixbuf.Pixbuf,
                 buttons: list[DialogButton],
                 modal: bool = True,
                 transient_for: Gtk.Window | None = None
                 ) -> None:
        ConfirmationDialog.__init__(self,
                                    title,
                                    text,
                                    sec_text,
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
    def __init__(self,
                 title: str,
                 text: str,
                 sec_text: str,
                 buttons: list[DialogButton],
                 input_str: str | None = None,
                 modal: bool = True,
                 transient_for: Gtk.Window | None = None,
                 ) -> None:
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

    def _on_response(self,
                     _dialog: Gtk.MessageDialog,
                     response: Gtk.ResponseType
                     ) -> None:
        button = self._buttons.get(response)
        if button is not None:
            button.args.insert(0, self._entry.get_text())
        super()._on_response(_dialog, response)


class ShortcutsWindow:
    def __init__(self):
        transient = app.app.get_active_window()
        assert transient
        builder = get_builder('shortcuts_window.ui')
        self.window = cast(Gtk.Window, builder.get_object('shortcuts_window'))
        self.window.connect('destroy', self._on_window_destroy)
        self.window.set_transient_for(transient)
        self.window.show_all()
        self.window.present()

    def _on_window_destroy(self, _widget: Gtk.Widget) -> None:
        self.window = None
