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

from typing import cast
from typing import Any

import logging

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Pango

from nbxmpp.errors import StanzaError
from nbxmpp.task import Task

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.i18n import get_rfc5646_lang
from gajim.common.helpers import to_user_string
from gajim.common.helpers import get_group_chat_nick
from gajim.common.const import MUC_DISCO_ERRORS

from .groupchat_info import GroupChatInfoScrolled
from .groupchat_nick import NickChooser
from .util import ensure_not_destroyed

log = logging.getLogger('gajim.gui.groupchat_join')


class GroupchatJoin(Gtk.ApplicationWindow):
    def __init__(self, account: str, jid: str) -> None:
        Gtk.ApplicationWindow.__init__(self)
        self.set_name('GroupchatJoin')
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_title(_('Join Group Chat'))
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_default_size(500, 550)

        self._destroyed = False
        self.account = account
        self.jid = jid
        self._redirected = False

        self._main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                 spacing=18)
        self._main_box.set_valign(Gtk.Align.FILL)

        self._muc_info_box = GroupChatInfoScrolled(account)

        self._stack = Gtk.Stack()
        self._stack.add_named(self._muc_info_box, 'info')
        self._stack.add_named(ProgressPage(), 'progress')
        self._stack.add_named(ErrorPage(), 'error')

        self._stack.set_visible_child_name('progress')
        progress_page = cast(ProgressPage, self._stack.get_visible_child())
        progress_page.start()

        self._stack.connect('notify::visible-child-name',
                            self._on_page_changed)
        self._main_box.add(self._stack)

        self._nick_chooser = NickChooser()

        self._join_button = Gtk.Button.new_with_mnemonic(_('_Join'))
        self._join_button.set_halign(Gtk.Align.END)
        self._join_button.set_sensitive(False)
        self._join_button.set_can_default(True)
        self._join_button.get_style_context().add_class('suggested-action')
        self._join_button.connect('clicked', self._on_join)

        join_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        join_box.get_style_context().add_class('linked')
        join_box.set_halign(Gtk.Align.END)
        join_box.add(self._nick_chooser)
        join_box.add(self._join_button)

        self._main_box.add(join_box)

        self.connect('key-press-event', self._on_key_press)
        self.connect('destroy', self._on_destroy)

        self.add(self._main_box)
        self.show_all()

        client = app.get_client(self.account)
        client.get_module('Discovery').disco_muc(
            jid,
            allow_redirect=True,
            request_vcard=True,
            callback=self._disco_info_received)

    def _on_page_changed(self, stack: Gtk.Stack, _param: Any) -> None:
        name = stack.get_visible_child_name()
        self._join_button.set_sensitive(name == 'info')
        self._nick_chooser.set_sensitive(name == 'info')

    @ensure_not_destroyed
    def _disco_info_received(self, task: Task) -> None:
        try:
            result = task.finish()
        except StanzaError as error:
            log.info('Disco %s failed: %s', error.jid, error.get_text())
            self._set_error(error)
            return

        if result.redirected:
            self.jid = result.info.jid

        if result.info.is_muc:
            self._muc_info_box.set_from_disco_info(result.info)
            nickname = get_group_chat_nick(self.account, result.info.jid)
            self._nick_chooser.set_text(nickname)
            self._join_button.grab_default()
            self._stack.set_visible_child_name('info')

        else:
            self._set_error_from_code('not-muc-service')

    def _show_error_page(self, text: str) -> None:
        error_page = cast(ErrorPage, self._stack.get_child_by_name('error'))
        error_page.set_text(text)
        self._stack.set_visible_child_name('error')

    def _set_error(self, error: StanzaError) -> None:
        text = MUC_DISCO_ERRORS.get(
            error.condition or '', to_user_string(error))
        if error.condition == 'gone':
            reason = error.get_text(get_rfc5646_lang())
            if reason:
                text = '%s:\n%s' % (text, reason)
        self._show_error_page(text)

    def _set_error_from_code(self, error_code: str) -> None:
        self._show_error_page(MUC_DISCO_ERRORS[error_code])

    def _on_join(self, _button: Gtk.Button) -> None:
        nickname = self._nick_chooser.get_text()

        app.window.show_add_join_groupchat(
            self.account, self.jid, nickname=nickname)
        self.destroy()

    def _on_destroy(self, _widget: Gtk.Widget) -> None:
        self._destroyed = True

    def _on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> None:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()


class ErrorPage(Gtk.Box):
    def __init__(self) -> None:
        Gtk.Box.__init__(self,
                         orientation=Gtk.Orientation.VERTICAL,
                         spacing=18)
        self.set_vexpand(True)
        self.set_homogeneous(True)
        error_icon = Gtk.Image.new_from_icon_name(
            'dialog-error', Gtk.IconSize.DIALOG)
        error_icon.set_valign(Gtk.Align.END)

        self._error_label = Gtk.Label()
        self._error_label.set_justify(Gtk.Justification.CENTER)
        self._error_label.set_valign(Gtk.Align.START)
        self._error_label.get_style_context().add_class('bold16')
        self._error_label.set_line_wrap(True)
        self._error_label.set_line_wrap_mode(Pango.WrapMode.WORD)
        self._error_label.set_size_request(150, -1)

        self.add(error_icon)
        self.add(self._error_label)
        self.show_all()

    def set_text(self, text: str) -> None:
        self._error_label.set_text(text)


class ProgressPage(Gtk.Box):
    def __init__(self) -> None:
        Gtk.Box.__init__(self,
                         orientation=Gtk.Orientation.VERTICAL,
                         spacing=18)
        self.set_vexpand(True)
        self.set_homogeneous(True)
        self._spinner = Gtk.Spinner()
        self._spinner.set_halign(Gtk.Align.CENTER)

        self.add(self._spinner)
        self.show_all()

    def start(self) -> None:
        self._spinner.start()

    def stop(self) -> None:
        self._spinner.stop()
