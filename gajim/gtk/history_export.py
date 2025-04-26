# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import Literal
from typing import overload

import logging
from datetime import datetime
from pathlib import Path

from gi.repository import Gtk
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common import configpaths
from gajim.common.i18n import _
from gajim.common.modules.contacts import ResourceContact
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.archive.models import Message
from gajim.common.util.uri import make_path_from_jid

from gajim.gtk.assistant import Assistant
from gajim.gtk.assistant import ErrorPage
from gajim.gtk.assistant import Page
from gajim.gtk.builder import get_builder
from gajim.gtk.dropdown import GajimDropDown
from gajim.gtk.filechoosers import FileChooserButton

log = logging.getLogger("gajim.gtk.history_export")


class HistoryExport(Assistant):
    def __init__(self, account: str | None = None, jid: JID | None = None) -> None:
        Assistant.__init__(self)

        self.account = account
        self.jid = jid

        self.add_button("back", _("Back"))
        self.add_button("close", _("Close"))
        self.add_button(
            "export", _("Export"), complete=True, css_class="suggested-action"
        )

        self.set_button_visible_func(self._visible_func)

        self.add_pages({"start": ExportSettings(account, jid)})

        progress_page = self.add_default_page("progress")
        progress_page.set_title(_("Exporting History..."))
        progress_page.set_text(_("Exporting your messages..."))

        success_page = self.add_default_page("success")
        success_page.set_title(_("Export Finished"))
        success_page.set_text(_("Your messages have been exported successfully"))

        error_page = self.add_default_page("error")
        error_page.set_title(_("Error while Exporting"))
        error_page.set_text(_("An error occurred while exporting your messages"))

        self._connect(self, "button-clicked", self._on_button_clicked)

    @overload
    def get_page(self, name: Literal["error"]) -> ErrorPage: ...

    @overload
    def get_page(self, name: Literal["start"]) -> ExportSettings: ...

    def get_page(self, name: str) -> Page:
        return self._pages[name]

    @staticmethod
    def _visible_func(_assistant: Assistant, page_name: str) -> list[str]:
        if page_name == "start":
            return ["close", "export"]

        if page_name == "progress":
            return []

        if page_name == "success":
            return ["back", "close"]

        if page_name == "error":
            return ["back", "close"]
        raise ValueError(f"page {page_name} unknown")

    def _on_button_clicked(self, _assistant: Assistant, button_name: str) -> None:
        if button_name == "export":
            self.show_page("progress", Gtk.StackTransitionType.SLIDE_LEFT)
            self._on_export()

        elif button_name == "back":
            self.show_page("start", Gtk.StackTransitionType.SLIDE_RIGHT)

        elif button_name == "close":
            self.close()

    def _on_export(self) -> None:
        start_page = self.get_page("start")
        account, jid, directory = start_page.get_export_settings()

        current_time = datetime.now()
        time_str = current_time.strftime("%Y-%m-%d-%H-%M-%S")
        export_dir = directory / f"export_{time_str}"

        if jid is None:
            rows = app.storage.archive.get_conversation_jids(account)
            jids = [jid for jid, _m_type in rows]
        else:
            jids = [jid]

        for jid in jids:
            messages = app.storage.archive.get_messages_for_export(account, jid)
            if not messages:
                continue

            file_path = make_path_from_jid(export_dir, jid)
            try:
                file_path.mkdir(parents=True, exist_ok=True)
            except OSError as err:
                self.get_page("error").set_text(
                    _(
                        "An error occurred while trying to create a "
                        "file at %(path)s: %(error)s"
                    )
                    % {"path": file_path, "error": str(err)}
                )
                self.show_page("error", Gtk.StackTransitionType.SLIDE_LEFT)
                return

            with open(file_path / "history.txt", "w", encoding="utf-8") as file:
                file.write(f"History for {jid}\n\n")
                for message in messages:
                    if message.call is not None:
                        continue

                    file.write(self._get_export_line(message))

        self.show_page("success", Gtk.StackTransitionType.SLIDE_LEFT)

    def _get_nickname(self, message: Message) -> str:
        if message.direction == ChatDirection.OUTGOING:
            return _("You")

        if message.type == MessageType.GROUPCHAT:
            if message.occupant is not None:
                if message.occupant.nickname is not None:
                    return message.occupant.nickname

            if message.resource is not None:
                return message.resource

            return _("Room")

        return str(message.remote.jid)

    def _get_export_line(self, message: Message) -> str:
        name = self._get_nickname(message)
        timestamp = message.timestamp.astimezone().strftime("%Y-%m-%d %H:%M:%S")

        text = message.text
        if corrected_message := message.get_last_correction():
            text = corrected_message.text

        return f'{timestamp} {name}: {text or ""}\n'


class ExportSettings(Page):
    def __init__(self, account: str | None, jid: JID | None) -> None:
        Page.__init__(self)
        self._account = account
        self._jid = jid

        self._export_directory = configpaths.get("MY_DATA")

        self.title = _("Export Chat History")

        self._ui = get_builder("history_export.ui")
        self.append(self._ui.select_account_box)

        accounts_data: dict[str, str] = {}
        for account_data in app.get_enabled_accounts_with_labels():
            accounts_data[account_data[0]] = account_data[1]

        self._accounts_dropdown = GajimDropDown(data=accounts_data, fixed_width=40)
        self._ui.settings_grid.attach(self._accounts_dropdown, 1, 0, 1, 1)
        self._connect(
            self._accounts_dropdown, "notify::selected", self._on_account_changed
        )

        self._chats_dropdown = GajimDropDown(fixed_width=40)
        self._update_chat_dropdown()
        self._connect(self._chats_dropdown, "notify::selected", self._on_chat_changed)
        self._ui.settings_grid.attach(self._chats_dropdown, 1, 1, 1, 1)

        if self._account is not None:
            self._accounts_dropdown.select_key(self._account)

        if self._jid is not None:
            self._chats_dropdown.select_key(str(self._jid))

        file_chooser_button = FileChooserButton(
            path=self._export_directory,
            mode="folder-open",
            label=_("Choose History Export Directory"),
        )
        file_chooser_button.set_size_request(250, -1)
        self._connect(file_chooser_button, "path-picked", self._on_path_picked)
        self._ui.settings_grid.attach(file_chooser_button, 1, 2, 1, 1)

        self._set_complete()

    def _on_account_changed(self, dropdown: GajimDropDown, *args: Any) -> None:
        item = dropdown.get_selected_item()
        assert item is not None
        account = item.props.key
        self._account = account
        self._update_chat_dropdown()
        self._set_complete()

    def _on_chat_changed(self, dropdown: GajimDropDown, *args: Any) -> None:
        item = dropdown.get_selected_item()
        if item is None:
            return

        address = item.props.key
        if address:
            self._jid = JID.from_string(address)
        else:
            self._jid = None

    def _update_chat_dropdown(self) -> None:
        if self._account is None:
            self._chats_dropdown.set_data({})
            return

        rows = app.storage.archive.get_conversation_jids(self._account)
        client = app.get_client(self._account)

        chats: dict[str, str] = {"": _("All Chats")}
        for jid, m_type in rows:
            contact = client.get_module("Contacts").get_contact(
                jid, groupchat=m_type != MessageType.CHAT
            )
            assert not isinstance(contact, ResourceContact)
            chats[str(jid)] = f"{contact.name} ({jid})"

        self._chats_dropdown.set_data(chats)

    def _set_complete(self) -> None:
        self.complete = bool(self._account is not None)
        self.update_page_complete()

    def _on_path_picked(
        self, _file_chooser_button: FileChooserButton, paths: list[Path]
    ) -> None:
        if not paths:
            return
        self._export_directory = paths[0]

    def get_export_settings(self) -> tuple[str, JID | None, Path]:
        assert self._account is not None
        assert self._export_directory is not None
        return self._account, self._jid, self._export_directory
