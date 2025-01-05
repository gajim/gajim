# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Gtk

# Avoid circular imports from common.helpers
from gajim.common import app  # type: ignore # noqa: F401

from gajim.gtk.assistant import Assistant
from gajim.gtk.assistant import Page

from . import util


class TestAssistant(Assistant):
    def __init__(self):
        Assistant.__init__(self)

        self.add_pages({"start": Start()})

        progress = self.add_default_page("progress")
        progress.set_title("Executing...")
        progress.set_text("Something is in progress...")

        error = self.add_default_page("error")
        error.set_title("Error")
        error.set_heading("Error Heading")
        error.set_text("This is the error text")

        success = self.add_default_page("success")
        success.set_title("Success")
        success.set_heading("Success Heading")
        success.set_text("This is the success text")

        self.add_button("forward", "Forward", "suggested-action", complete=True)
        self.add_button("close", "Close", "destructive-action")
        self.add_button("back", "Back")

        self.set_button_visible_func(self._visible_func)

        self.connect("button-clicked", self._on_button_clicked)
        self.connect("page-changed", self._on_page_changed)

        self.show_all()

    @staticmethod
    def _visible_func(_assistant: Assistant, page_name: str) -> list[str]:
        if page_name == "start":
            return ["forward"]

        if page_name == "progress":
            return ["forward", "back"]

        if page_name == "success":
            return ["forward", "back"]

        if page_name == "error":
            return ["back", "close"]
        raise ValueError("page %s unknown" % page_name)

    def _on_button_clicked(self, _assistant: Assistant, button_name: str) -> None:
        page = self.get_current_page()
        if button_name == "forward":
            if page == "start":
                self.show_page("progress", Gtk.StackTransitionType.SLIDE_LEFT)
            elif page == "progress":
                self.show_page("success", Gtk.StackTransitionType.SLIDE_LEFT)
            elif page == "success":
                self.show_page("error", Gtk.StackTransitionType.SLIDE_LEFT)
            return

        if button_name == "back":
            if page == "progress":
                self.show_page("start")
            if page == "success":
                self.show_page("progress")
            if page == "error":
                self.show_page("success")
            return

        if button_name == "close":
            self.window.close()

    def _on_page_changed(self, _assistant: Assistant, page_name: str) -> None:
        if page_name == "start":
            self.set_default_button("forward")

        elif page_name == "progress":
            self.set_default_button("forward")

        elif page_name == "success":
            self.set_default_button("forward")

        elif page_name == "error":
            self.set_default_button("back")


class Start(Page):
    def __init__(self):
        Page.__init__(self)

        self.title = "Start"
        self.complete = False

        heading = Gtk.Label(label="Test Assistant")
        heading.add_css_class("large-header")

        label1 = Gtk.Label(
            label="This is label 1 with some text",
            wrap=True,
            max_width_chars=50,
            halign=Gtk.Align.CENTER,
            justify=Gtk.Justification.CENTER,
            margin_bottom=24,
        )

        entry = Gtk.Entry()
        entry.set_activates_default(True)
        entry.connect("changed", self._on_changed)

        self._server = Gtk.CheckButton.new_with_mnemonic("A fancy checkbox")
        self._server.set_halign(Gtk.Align.CENTER)

        self.append(heading)
        self.append(label1)
        self.append(entry)
        self.append(self._server)

    def _on_changed(self, entry: Gtk.Entry) -> None:
        self.complete = bool(entry.get_text())
        self.update_page_complete()


window = TestAssistant()
window.show()

util.run_app()
