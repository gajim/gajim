# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Literal
from typing import overload

import logging
from datetime import datetime
from pathlib import Path

from gi.repository import Gtk

from gajim.common import app
from gajim.common import configpaths
from gajim.common.i18n import _
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.archive.models import Message
from gajim.common.util.uri import make_path_from_jid

from gajim.gtk.assistant import Assistant
from gajim.gtk.assistant import ErrorPage
from gajim.gtk.assistant import Page
from gajim.gtk.builder import get_builder
from gajim.gtk.filechoosers import FileChooserButton

log = logging.getLogger("gajim.gtk.history_export")


class HistoryExport(Assistant):
    def __init__(self, account: str | None = None) -> None:
        Assistant.__init__(self)

        self.account = account

        self.add_button(
            "export", _("Export"), complete=True, css_class="suggested-action"
        )
        self.add_button("close", _("Close"))
        self.add_button("back", _("Back"))
        self.set_button_visible_func(self._visible_func)

        self.add_pages({"start": SelectAccountDir(account)})

        progress_page = self.add_default_page("progress")
        progress_page.set_title(_("Exporting History..."))
        progress_page.set_text(_("Exporting your messages..."))

        success_page = self.add_default_page("success")
        success_page.set_title(_("Export Finished"))
        success_page.set_text(_("Your messages have been exported successfully"))

        error_page = self.add_default_page("error")
        error_page.set_title(_("Error while Exporting"))
        error_page.set_text(_("An error occurred while exporting your messages"))

        self.connect("button-clicked", self._on_button_clicked)

    @overload
    def get_page(self, name: Literal["error"]) -> ErrorPage: ...

    @overload
    def get_page(self, name: Literal["start"]) -> SelectAccountDir: ...

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
        account, directory = start_page.get_account_and_directory()

        current_time = datetime.now()
        time_str = current_time.strftime("%Y-%m-%d-%H-%M-%S")
        export_dir = directory / f"export_{time_str}"

        jids = app.storage.archive.get_conversation_jids(account)

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

            assert message.resource is not None
            return message.resource

        return str(message.remote.jid)

    def _get_export_line(self, message: Message) -> str:
        name = self._get_nickname(message)
        timestamp = message.timestamp.astimezone().strftime("%Y-%m-%d %H:%M:%S")

        text = message.text
        if message.corrections:
            text = message.get_last_correction().text

        return f'{timestamp} {name}: {text or ""}\n'


class SelectAccountDir(Page):
    def __init__(self, account: str | None) -> None:
        Page.__init__(self)
        self._account = account
        self._export_directory = configpaths.get("MY_DATA")

        self.title = _("Export Chat History")

        self._ui = get_builder("history_export.ui")
        self.append(self._ui.select_account_box)

        accounts = app.get_enabled_accounts_with_labels()
        liststore = Gtk.ListStore(str, str)
        for acc in accounts:
            liststore.append(acc)

        self._ui.account_combo.set_model(liststore)

        if self._account is not None:
            self._ui.account_combo.set_active_id(self._account)
        else:
            self._ui.account_combo.set_active(0)

        file_chooser_button = FileChooserButton(
            path=self._export_directory,
            mode="folder-open",
            label=_("Choose History Export Directory"),
        )
        file_chooser_button.set_size_request(250, -1)
        self._connect(file_chooser_button, "path-picked", self._on_path_picked)
        self._ui.settings_grid.attach(file_chooser_button, 1, 1, 1, 1)

        self._connect(self._ui.account_combo, "changed", self._on_account_changed)

        self._set_complete()

    def _on_account_changed(self, combobox: Gtk.ComboBox) -> None:
        account = combobox.get_active_id()
        self._account = account
        self._set_complete()

    def _set_complete(self) -> None:
        self.complete = bool(self._account is not None)
        self.update_page_complete()

    def _on_path_picked(
        self, _file_chooser_button: FileChooserButton, paths: list[Path]
    ) -> None:
        if not paths:
            return
        self._export_directory = paths[0]

    def get_account_and_directory(self) -> tuple[str, Path]:
        assert self._account is not None
        assert self._export_directory is not None
        return self._account, self._export_directory
