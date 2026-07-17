# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import Literal
from typing import overload

import logging
import threading
from datetime import datetime
from pathlib import Path

from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common import configpaths
from gajim.common.export.html import generate_html
from gajim.common.export.html import generate_overview_html
from gajim.common.export.html import make_overview_avatar_src
from gajim.common.export.html import write_shared_assets
from gajim.common.i18n import _
from gajim.common.modules.contacts import ResourceContact
from gajim.common.storage.archive.const import MessageType
from gajim.common.util.filesystem import make_path_from_jid

from gajim.gtk.assistant import Assistant
from gajim.gtk.assistant import AssistantErrorPage
from gajim.gtk.assistant import AssistantPage
from gajim.gtk.builder import get_builder
from gajim.gtk.dropdown import GajimDropDown
from gajim.gtk.filechoosers import FileChooserButton
from gajim.gtk.util.misc import open_file

log = logging.getLogger("gajim.gtk.history_export")


class HistoryExport(Assistant):
    def __init__(self, account: str | None = None, jid: JID | None = None) -> None:
        Assistant.__init__(self)

        self.account = account
        self.jid = jid
        self._export_dir: Path | None = None
        self._export_html: Path | None = None
        self._cancel_event: threading.Event | None = None

        self.add_button("back", _("Back"))
        self.add_button("cancel", _("Cancel"))
        self.add_button("close", _("Close"))
        self.add_button("open-folder", _("Open Folder"))
        self.add_button("open-html", _("Open in Browser"))
        self.add_button(
            "export", _("Export"), complete=True, css_class="suggested-action"
        )

        self.set_button_visible_func(self._visible_func)

        self.add_pages({"start": ExportSettings(account, jid)})

        self._progress_page = ExportProgressPage()
        self.add_pages({"progress": self._progress_page})

        success_page = self.add_default_page("success")
        success_page.set_title(_("Export Finished"))
        success_page.set_text(_("Your messages have been exported successfully"))

        error_page = self.add_default_page("error")
        error_page.set_title(_("Error while Exporting"))
        error_page.set_text(_("An error occurred while exporting your messages"))

        self._cancelled_page = ExportCancelledPage()
        self.add_pages({"cancelled": self._cancelled_page})

        self._connect(self, "button-clicked", self._on_button_clicked)

    @overload
    def get_page(self, name: Literal["error"]) -> AssistantErrorPage: ...

    @overload
    def get_page(self, name: Literal["start"]) -> ExportSettings: ...

    @overload
    def get_page(self, name: Literal["progress"]) -> ExportProgressPage: ...

    @overload
    def get_page(self, name: Literal["cancelled"]) -> ExportCancelledPage: ...

    def get_page(self, name: str) -> AssistantPage:
        return self._pages[name]

    @staticmethod
    def _visible_func(assistant: Assistant, page_name: str) -> list[str]:
        assert isinstance(assistant, HistoryExport)

        if page_name == "start":
            return ["close", "export"]

        if page_name == "progress":
            return ["cancel"]

        if page_name == "success":
            return ["back", "open-folder", "open-html", "close"]

        if page_name == "error":
            return ["back", "close"]

        if page_name == "cancelled":
            buttons: list[str] = ["back", "close"]
            if assistant._export_dir is not None:
                buttons = ["back", "open-folder", "close"]
            if assistant._export_html is not None:
                buttons = ["back", "open-folder", "open-html", "close"]
            return buttons

        raise ValueError(f"page {page_name} unknown")

    def _on_button_clicked(self, _assistant: Assistant, button_name: str) -> None:
        if button_name == "export":
            self.show_page("progress", Gtk.StackTransitionType.SLIDE_LEFT)
            self._on_export()

        elif button_name == "cancel":
            if self._cancel_event is not None:
                self._cancel_event.set()

        elif button_name == "back":
            self.show_page("start", Gtk.StackTransitionType.SLIDE_RIGHT)

        elif button_name == "open-folder":
            if self._export_dir is not None:
                open_file(self._export_dir)

        elif button_name == "open-html":
            if self._export_html is not None:
                open_file(self._export_html)

        elif button_name == "close":
            if self._cancel_event is not None:
                self._cancel_event.set()
            self.close()

    def _on_export(self) -> None:
        start_page = self.get_page("start")
        account, jids, directory = start_page.get_export_settings()

        current_time = datetime.now()
        time_str = current_time.strftime("%Y-%m-%d-%H-%M-%S")
        export_dir = directory / f"export_{time_str}"

        rows = app.storage.archive.get_conversation_jids(account)
        jid_set = set(jids)
        jid_types = [(j, m_type) for j, m_type in rows if j in jid_set]
        in_db = {j for j, _ in jid_types}
        for jid in jids:
            if jid not in in_db:
                jid_types.append((jid, MessageType.CHAT))

        self._export_dir = None
        self._export_html = None
        self._cancel_event = threading.Event()
        self._progress_page.reset(len(jid_types))

        thread = threading.Thread(
            target=self._export_worker,
            args=(account, jid_types, export_dir, self._cancel_event),
            daemon=True,
        )
        thread.start()

    def _export_worker(
        self,
        account: str,
        jid_types: list[tuple[JID, MessageType]],
        export_dir: Path,
        cancel_event: threading.Event,
    ) -> None:
        client = app.get_client(account)
        exported: list[tuple[str, str, str, str]] = []

        write_shared_assets(export_dir)

        for cur_jid, m_type in jid_types:
            if cancel_event.is_set():
                break

            try:
                contact = client.get_module("Contacts").get_contact(
                    cur_jid, groupchat=m_type != MessageType.CHAT
                )
                assert not isinstance(contact, ResourceContact)
                display_name = contact.name
            except Exception:
                display_name = str(cur_jid)

            GLib.idle_add(self._progress_page.set_current, display_name)

            if cancel_event.is_set():
                break

            messages = list(
                app.storage.archive.get_messages_for_export(account, cur_jid)
            )

            if cancel_event.is_set():
                break

            if not messages:
                GLib.idle_add(self._progress_page.mark_skipped, display_name)
                continue

            file_path = make_path_from_jid(export_dir, cur_jid)
            try:
                file_path.mkdir(parents=True, exist_ok=True)
            except OSError as err:
                GLib.idle_add(self._on_export_error, str(err), file_path)
                return

            depth = len(file_path.relative_to(export_dir).parts)
            assets_prefix = "/".join([".."] * depth) + "/assets"
            html_content = generate_html(
                display_name, messages, file_path, assets_prefix=assets_prefix
            )
            with open(file_path / "history.html", "w", encoding="utf-8") as f:
                f.write(html_content)

            rel = (file_path / "history.html").relative_to(export_dir)

            try:
                sha = app.storage.archive.get_contact_value(
                    account, cur_jid, "avatar_sha"
                )
            except Exception:
                sha = None
            avatar_src = make_overview_avatar_src(
                sha, display_name, file_path, export_dir
            )

            exported.append((display_name, str(cur_jid), rel.as_posix(), avatar_src))

            GLib.idle_add(self._progress_page.mark_done, display_name)

        GLib.idle_add(self._on_export_done, export_dir, exported, cancel_event.is_set())

    def _on_export_done(
        self,
        export_dir: Path,
        exported: list[tuple[str, str, str, str]],
        cancelled: bool,
    ) -> None:
        self._progress_page.stop()

        if exported:
            overview = generate_overview_html(exported, assets_prefix="assets")
            index_path = export_dir / "index.html"
            with open(index_path, "w", encoding="utf-8") as f:
                f.write(overview)
            self._export_html = index_path

        if exported:
            self._export_dir = export_dir

        if cancelled:
            n = len(exported)
            if n == 0:
                text = _("The export was cancelled before any chats were exported.")
            elif n == 1:
                text = _("The export was cancelled. 1 chat was exported.")
            else:
                text = _("The export was cancelled. %d chats were exported.") % n
            self._cancelled_page.set_text(text)
            self.show_page("cancelled", Gtk.StackTransitionType.SLIDE_LEFT)
        else:
            self.show_page("success", Gtk.StackTransitionType.SLIDE_LEFT)

    def _on_export_error(self, error: str, path: Path) -> None:
        self._progress_page.stop()
        self.get_page("error").set_text(
            _("An error occurred while trying to create a file at %(path)s: %(error)s")
            % {"path": path, "error": error}
        )
        self.show_page("error", Gtk.StackTransitionType.SLIDE_LEFT)


class ExportProgressPage(AssistantPage):
    def __init__(self) -> None:
        AssistantPage.__init__(self)
        self.title = _("Exporting History...")
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(18)
        self.set_valign(Gtk.Align.FILL)

        self._total = 0
        self._done = 0

        top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        top_box.set_halign(Gtk.Align.CENTER)

        self._spinner = Gtk.Spinner()
        top_box.append(self._spinner)

        self._current_label = Gtk.Label()
        self._current_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._current_label.set_max_width_chars(40)
        top_box.append(self._current_label)
        self.append(top_box)

        self._progress_bar = Gtk.ProgressBar()
        self._progress_bar.set_show_text(True)
        self.append(self._progress_bar)

        self._completed_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._completed_box.set_margin_start(12)
        self._completed_box.set_margin_end(12)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        scrolled.set_child(self._completed_box)
        self.append(scrolled)

    def reset(self, total: int) -> None:
        self._total = total
        self._done = 0
        self._spinner.start()
        self._current_label.set_text(_("Preparing…"))
        self._progress_bar.set_fraction(0.0)
        self._progress_bar.set_text(f"0 / {total}")
        while (child := self._completed_box.get_first_child()) is not None:
            self._completed_box.remove(child)

    def set_current(self, name: str) -> None:
        self._current_label.set_text(_("Exporting: %s") % name)

    def mark_done(self, name: str) -> None:
        self._done += 1
        frac = self._done / self._total if self._total else 1.0
        self._progress_bar.set_fraction(frac)
        self._progress_bar.set_text(f"{self._done} / {self._total}")
        self._add_row(name, done=True)

    def mark_skipped(self, name: str) -> None:
        self._add_row(name, done=False)

    def _add_row(self, name: str, done: bool) -> None:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        icon_name = "lucide-check-symbolic" if done else "lucide-minus-symbolic"
        icon = Gtk.Image.new_from_icon_name(icon_name)
        if done:
            icon.add_css_class("success")
        else:
            icon.add_css_class("dim-label")
        row.append(icon)

        label = Gtk.Label(label=name)
        label.set_halign(Gtk.Align.START)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_max_width_chars(40)
        if not done:
            label.add_css_class("dim-label")
        row.append(label)

        self._completed_box.append(row)

    def stop(self) -> None:
        self._spinner.stop()
        self._current_label.set_text("")


class ExportCancelledPage(AssistantPage):
    def __init__(self) -> None:
        AssistantPage.__init__(self)
        self.title = _("Export Cancelled")
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(18)
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)

        icon = Gtk.Image.new_from_icon_name("process-stop-symbolic")
        icon.set_pixel_size(48)
        self.append(icon)

        self._text_label = Gtk.Label()
        self._text_label.set_justify(Gtk.Justification.CENTER)
        self._text_label.set_wrap(True)
        self._text_label.set_max_width_chars(40)
        self.append(self._text_label)

    def set_text(self, text: str) -> None:
        self._text_label.set_text(text)


class ExportSettings(AssistantPage):
    def __init__(self, account: str | None, jid: JID | None) -> None:
        AssistantPage.__init__(self)
        self._account = account
        self._initial_jid: str | None = str(jid) if jid is not None else None
        self._export_directory = configpaths.get("MY_DATA")
        self.title = _("Export Chat History")

        self._chat_checks: dict[str, Gtk.CheckButton] = {}
        self._select_all_check: Gtk.CheckButton | None = None
        self._updating_select_all = False
        self._chat_list_populated = False

        self._ui = get_builder("history_export.ui")
        self.append(self._ui.select_account_box)

        accounts_data: dict[str, str] = {}
        for account_data in app.get_enabled_accounts_with_labels():
            accounts_data[account_data[0]] = account_data[1]

        self._accounts_dropdown: GajimDropDown[str] = GajimDropDown(
            data=accounts_data, fixed_width=40
        )
        self._ui.settings_grid.attach(self._accounts_dropdown, 1, 0, 1, 1)
        self._connect(
            self._accounts_dropdown, "notify::selected", self._on_account_changed
        )

        self._chats_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        chats_scrolled = Gtk.ScrolledWindow()
        chats_scrolled.set_size_request(250, 180)
        chats_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        chats_scrolled.set_child(self._chats_box)
        self._ui.settings_grid.attach(chats_scrolled, 1, 1, 1, 1)

        if self._account is not None:
            self._accounts_dropdown.select_key(self._account)
        else:
            # No specific account requested; adopt the dropdown's default selection.
            item = self._accounts_dropdown.get_selected_item()
            if item is not None:
                self._account = item.key

        # Populate the chat list once if the notify::selected handler above
        # didn't already do it — that happens when the requested account is
        # already the dropdown's default (first) item, so no signal fires.
        # Skipping the second call preserves _initial_jid for the signal path.
        if not self._chat_list_populated:
            self._update_chat_list()

        file_chooser_button = FileChooserButton(
            path=self._export_directory,
            mode="folder-open",
            label=_("Choose History Export Directory"),
        )
        file_chooser_button.set_size_request(250, -1)
        self._connect(file_chooser_button, "path-picked", self._on_path_picked)
        self._ui.settings_grid.attach(file_chooser_button, 1, 2, 1, 1)

        self._set_complete()

    def _on_account_changed(self, dropdown: GajimDropDown[str], *args: Any) -> None:
        item = dropdown.get_selected_item()
        assert item is not None
        self._account = item.key
        self._update_chat_list()
        self._set_complete()

    def _update_chat_list(self) -> None:
        self._chat_list_populated = True
        initial_jid = self._initial_jid
        self._initial_jid = None

        while (child := self._chats_box.get_first_child()) is not None:
            self._chats_box.remove(child)
        self._chat_checks = {}
        self._select_all_check = None

        if self._account is None:
            self._set_complete()
            return

        rows = app.storage.archive.get_conversation_jids(self._account)
        client = app.get_client(self._account)

        chats: dict[str, str] = {}
        for jid, m_type in rows:
            contact = client.get_module("Contacts").get_contact(
                jid, groupchat=m_type != MessageType.CHAT
            )
            assert not isinstance(contact, ResourceContact)
            chats[str(jid)] = f"{contact.name} ({jid})"

        if not chats:
            self._set_complete()
            return

        select_all = Gtk.CheckButton(label=_("All Chats"))
        select_all.set_active(initial_jid is None)
        self._select_all_check = select_all
        self._connect(select_all, "toggled", self._on_select_all_toggled)
        self._chats_box.append(select_all)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator.set_margin_top(4)
        separator.set_margin_bottom(4)
        self._chats_box.append(separator)

        for jid_str, display in chats.items():
            cb = Gtk.CheckButton(label=display)
            cb.set_active(initial_jid is None or jid_str == initial_jid)
            self._chat_checks[jid_str] = cb
            self._connect(cb, "toggled", self._on_chat_toggled)
            self._chats_box.append(cb)

        if initial_jid is not None:
            self._update_select_all_state()

        self._set_complete()

    def _on_select_all_toggled(self, checkbox: Gtk.CheckButton) -> None:
        if self._updating_select_all:
            return
        self._updating_select_all = True
        active = checkbox.get_active()
        for cb in self._chat_checks.values():
            cb.set_active(active)
        self._updating_select_all = False
        self._set_complete()

    def _on_chat_toggled(self, _checkbox: Gtk.CheckButton) -> None:
        if self._updating_select_all:
            return
        self._update_select_all_state()
        self._set_complete()

    def _update_select_all_state(self) -> None:
        if self._select_all_check is None:
            return
        checked = sum(1 for cb in self._chat_checks.values() if cb.get_active())
        total = len(self._chat_checks)
        self._updating_select_all = True
        if checked == 0:
            self._select_all_check.set_inconsistent(False)
            self._select_all_check.set_active(False)
        elif checked == total:
            self._select_all_check.set_inconsistent(False)
            self._select_all_check.set_active(True)
        else:
            self._select_all_check.set_inconsistent(True)
        self._updating_select_all = False

    def _set_complete(self) -> None:
        if self._account is None:
            self.complete = False
            self.update_page_complete()
            return
        self.complete = any(cb.get_active() for cb in self._chat_checks.values())
        self.update_page_complete()

    def _on_path_picked(
        self, _file_chooser_button: FileChooserButton, paths: list[Path]
    ) -> None:
        if not paths:
            return
        self._export_directory = paths[0]

    def get_export_settings(self) -> tuple[str, list[JID], Path]:
        assert self._account is not None
        assert self._export_directory is not None
        selected = [
            JID.from_string(k) for k, cb in self._chat_checks.items() if cb.get_active()
        ]
        return self._account, selected, self._export_directory
