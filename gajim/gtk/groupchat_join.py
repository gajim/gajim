# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import Any
from typing import cast

import logging

from gi.repository import Adw
from gi.repository import Gtk
from nbxmpp.errors import StanzaError
from nbxmpp.modules.muc.util import MucInfoResult
from nbxmpp.task import Task

from gajim.common import app
from gajim.common.const import MUC_DISCO_ERRORS
from gajim.common.helpers import to_user_string
from gajim.common.i18n import _
from gajim.common.util.muc import get_group_chat_nick
from gajim.common.util.standards import get_rfc5646_lang

from gajim.gtk.groupchat_info import GroupChatInfoScrolled
from gajim.gtk.groupchat_nick_chooser import GroupChatNickChooser
from gajim.gtk.util.misc import ensure_not_destroyed
from gajim.gtk.window import GajimAppWindow

log = logging.getLogger("gajim.gtk.groupchat_join")


class GroupchatJoin(GajimAppWindow):
    def __init__(self, account: str, jid: str) -> None:
        GajimAppWindow.__init__(
            self,
            name="GroupchatJoin",
            title=_("Join Group Chat"),
            default_width=500,
            default_height=550,
            add_window_padding=True,
            header_bar=True,
        )

        self._destroyed = False
        self.account = account
        self.jid = jid
        self._redirected = False

        self._main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self._main_box.set_valign(Gtk.Align.FILL)

        self._muc_info_box = GroupChatInfoScrolled(account)

        self._stack = Gtk.Stack()
        self._stack.add_named(self._muc_info_box, "info")
        self._stack.add_named(ProgressPage(), "progress")
        self._stack.add_named(ErrorPage(), "error")

        self._stack.set_visible_child_name("progress")

        self._connect(self._stack, "notify::visible-child-name", self._on_page_changed)
        self._main_box.append(self._stack)

        self._nick_chooser = GroupChatNickChooser()

        self._join_button = Gtk.Button.new_with_mnemonic(_("_Join"))
        self._join_button.set_halign(Gtk.Align.END)
        self._join_button.set_sensitive(False)
        self._join_button.add_css_class("suggested-action")
        self._connect(self._join_button, "clicked", self._on_join)

        join_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        join_box.add_css_class("linked")
        join_box.set_halign(Gtk.Align.END)
        join_box.append(self._nick_chooser)
        join_box.append(self._join_button)

        self._main_box.append(join_box)

        self.set_child(self._main_box)

        client = app.get_client(self.account)
        client.get_module("Discovery").disco_muc(
            jid,
            allow_redirect=True,
            request_vcard=True,
            callback=self._disco_info_received,  # type: ignore
        )

    def _on_page_changed(self, stack: Gtk.Stack, _param: Any) -> None:
        name = stack.get_visible_child_name()
        self._join_button.set_sensitive(name == "info")
        self._nick_chooser.set_sensitive(name == "info")

    @ensure_not_destroyed
    def _disco_info_received(self, task: Task) -> None:
        try:
            result = cast(MucInfoResult, task.finish())
        except StanzaError as error:
            log.info("Disco %s failed: %s", error.jid, error.get_text())
            self._set_error(error)
            return

        if result.redirected:
            self.jid = str(result.info.jid)

        if result.info.is_muc:
            self._muc_info_box.set_from_disco_info(result.info)
            assert result.info.jid is not None
            nickname = get_group_chat_nick(self.account, result.info.jid)
            self._nick_chooser.set_text(nickname)
            self.set_default_widget(self._join_button)
            self._stack.set_visible_child_name("info")

        else:
            self._set_error_from_code("not-muc-service")

    def _show_error_page(self, text: str) -> None:
        error_page = cast(ErrorPage, self._stack.get_child_by_name("error"))
        error_page.set_text(text)
        self._stack.set_visible_child_name("error")

    def _set_error(self, error: StanzaError) -> None:
        text = MUC_DISCO_ERRORS.get(error.condition or "", to_user_string(error))
        if error.condition == "gone":
            reason = error.get_text(get_rfc5646_lang())
            if reason:
                text = f"{text}:\n{reason}"
        self._show_error_page(text)

    def _set_error_from_code(self, error_code: str) -> None:
        self._show_error_page(MUC_DISCO_ERRORS[error_code])

    def _on_join(self, _button: Gtk.Button) -> None:
        nickname = self._nick_chooser.get_text()

        app.window.show_add_join_groupchat(self.account, self.jid, nickname=nickname)
        self.close()

    def _cleanup(self) -> None:
        self._destroyed = True


class ErrorPage(Gtk.Box):
    def __init__(self) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.set_vexpand(True)
        self.set_homogeneous(True)
        error_icon = Gtk.Image.new_from_icon_name("lucide-circle-x-symbolic")
        error_icon.set_valign(Gtk.Align.END)

        self._error_label = Gtk.Label(
            wrap=True,
            width_request=150,
            justify=Gtk.Justification.CENTER,
            valign=Gtk.Align.START,
        )
        self._error_label.add_css_class("title-3")

        self.append(error_icon)
        self.append(self._error_label)

    def set_text(self, text: str) -> None:
        self._error_label.set_text(text)


class ProgressPage(Gtk.Box):
    def __init__(self) -> None:
        Gtk.Box.__init__(
            self,
            orientation=Gtk.Orientation.VERTICAL,
            spacing=18,
            vexpand=True,
            homogeneous=True,
        )
        spinner = Adw.Spinner(halign=Gtk.Align.CENTER)
        self.append(spinner)
