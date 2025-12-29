# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import cast
from typing import Literal
from typing import TypedDict

import logging
from collections.abc import Iterator

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import configpaths
from gajim.common.helpers import dump_json
from gajim.common.helpers import load_json
from gajim.common.i18n import _

log = logging.getLogger("gajim.gtk.shortcut_manager")

GroupsT = Literal["app", "main-win", "input", "input-global"]


class ShortcutManager:
    def __init__(self) -> None:
        self._shortcut_groups = {
            "app": APP_SHORTCUTS,
            "main-win": MAIN_WIN_SHORTCUTS,
            "input": INPUT_SHORTCUTS,
            "input-global": INPUT_GLOBAL_SHORTCUTS,
        }

        self._load_user_shortcuts()

    def store_user_shortcuts(self) -> None:
        user_path = configpaths.get("MY_SHORTCUTS")
        custom_shortcuts = filter(lambda s: s.has_custom_accel(), self.iter_shortcuts())
        user_shortcuts = {s.action_name: s.get_accelerators() for s in custom_shortcuts}
        dump_json(user_path, user_shortcuts)

    def _load_user_shortcuts(self) -> None:
        user_path = configpaths.get("MY_SHORTCUTS")
        user_shortcuts: dict[str, list[str]] = {}
        if user_path.exists():
            log.info("Load user shortcuts")
            user_shortcuts = load_json(user_path, default={})

        for shortcut_group in self._shortcut_groups.values():
            for shortcut in shortcut_group:
                shortcut = cast(GajimShortcut, shortcut)
                user_accelerators = user_shortcuts.get(shortcut.action_name)
                if user_accelerators is None:
                    continue

                shortcut.set_custom_accelerators(user_accelerators)

    def get_group(self, name: GroupsT) -> GajimShortcutGroup:
        return self._shortcut_groups[name]

    def iter_shortcuts(self) -> Iterator[GajimShortcut]:
        for shortcut_group in self._shortcut_groups.values():
            yield from shortcut_group  # pyright: ignore

    def install_shortcuts(
        self, widget: Gtk.Widget, group_name: list[GroupsT] | GroupsT
    ) -> None:
        if not isinstance(group_name, list):
            group_name = [group_name]

        for name in group_name:
            if name.endswith("global"):
                scope = Gtk.ShortcutScope.GLOBAL
            else:
                scope = Gtk.ShortcutScope.LOCAL

            controller = Gtk.ShortcutController(
                name=name, scope=scope, model=self.get_group(name)
            )
            widget.add_controller(controller)


class AcceleratorDict(TypedDict):
    original: TriggerDict
    custom: TriggerDict


class TriggerDict(TypedDict):
    trigger: Gtk.ShortcutTrigger | None
    accelerators: list[str] | None


class GajimShortcut(Gtk.Shortcut):
    __gtype_name__ = "GajimShortcut"

    def __init__(
        self,
        label: str,
        category: str,
        action_name: str,
        accelerators: list[str] | None = None,
        args: GLib.Variant | None = None,
        allow_rebind: bool = True,
    ):
        Gtk.Shortcut.__init__(self)

        self._label = label
        self._category = category
        self._allow_rebind = allow_rebind
        self._action_name = action_name

        if accelerators is None:
            accelerators = []

        self._accelerators: AcceleratorDict = {
            "original": {"trigger": None, "accelerators": None},
            "custom": {"trigger": None, "accelerators": None},
        }

        self._set_accelerators("original", accelerators)

        shortcut_action = Gtk.ShortcutAction.parse_string(f"action({action_name})")
        self.set_action(shortcut_action)

        if args is not None:
            self.set_arguments(args)

    @GObject.Property(type=str, flags=GObject.ParamFlags.READABLE)
    def label(self) -> str:
        return self._label

    @GObject.Property(type=str, flags=GObject.ParamFlags.READABLE)
    def category(self) -> str:
        return self._category

    @GObject.Property(type=bool, default=True, flags=GObject.ParamFlags.READABLE)
    def allow_rebind(self) -> bool:
        return self._allow_rebind

    @GObject.Property(type=str, flags=GObject.ParamFlags.READABLE)
    def action_name(self) -> str:
        return self._action_name

    def reset(self) -> None:
        self._accelerators["custom"]["trigger"] = None
        self._accelerators["custom"]["accelerators"] = None
        self.set_trigger(self._accelerators["original"]["trigger"])

    def get_accel_label(self) -> str:
        display = Gdk.Display.get_default()
        assert display is not None

        for name in ("custom", "original"):
            trigger = self._accelerators[name]["trigger"]
            if trigger is not None:
                if isinstance(trigger, Gtk.NeverTrigger):
                    return _("Disabled")
                return trigger.to_label(display)

        return _("Disabled")

    def set_custom_accelerators(self, accelerators: list[str] | None) -> None:
        self._set_accelerators("custom", accelerators)

    def has_custom_accel(self) -> bool:
        custom_trigger = self._accelerators["custom"]["trigger"]
        if custom_trigger is None:
            return False

        orig_trigger = self._accelerators["original"]["trigger"]
        if orig_trigger is None:
            return True

        return not orig_trigger.equal(custom_trigger)

    def get_accelerators(self) -> list[str]:
        name = "custom" if self.has_custom_accel() else "original"
        return self._accelerators[name]["accelerators"] or []

    def _set_accelerators(self, name: str, accelerators: list[str] | None) -> None:
        if not accelerators:
            trigger = Gtk.NeverTrigger.get()
            self._accelerators[name]["accelerators"] = None
            self._accelerators[name]["trigger"] = trigger
            self.set_trigger(trigger)
            return

        # Support max two accelerators
        accelerators = accelerators[:2]

        try:
            trigger = Gtk.ShortcutTrigger.parse_string("|".join(accelerators))
        except Exception:
            trigger = None

        if trigger is None:
            log.warning(
                "Unable to create shortcut trigger for: %s %s", name, accelerators
            )
            return

        self._accelerators[name]["accelerators"] = accelerators
        self._accelerators[name]["trigger"] = trigger
        self.set_trigger(trigger)


class GajimShortcutGroup(Gio.ListStore):
    def __init__(self, name: str, shortcuts: list[GajimShortcut]) -> None:
        Gio.ListStore.__init__(self, item_type=GajimShortcut)

        self._name = name
        self._shortcuts: dict[str, GajimShortcut] = {}

        for shortcut in shortcuts:
            self._shortcuts[shortcut.action_name] = shortcut
            self.append(shortcut)

    @GObject.Property(type=str, flags=GObject.ParamFlags.READABLE)
    def name(self) -> str:
        return self._name

    def get_for_action(self, action_name: str) -> GajimShortcut:
        return self._shortcuts[action_name]


APP_SHORTCUTS = GajimShortcutGroup(
    "app",
    [
        GajimShortcut(
            label=_("Start / Join Chat"),
            category="general",
            accelerators=["<Primary>N"],
            action_name="app.start-chat",
            args=GLib.Variant("as", ["", ""]),
        ),
        GajimShortcut(
            label=_("Create New Group Chat"),
            category="general",
            accelerators=["<Primary>G"],
            action_name="app.create-groupchat",
            args=GLib.Variant("s", ""),
        ),
        GajimShortcut(
            label=_("Preferences"),
            category="general",
            accelerators=["<Primary>P"],
            action_name="app.preferences",
        ),
        GajimShortcut(
            label=_("Plugins"),
            category="general",
            accelerators=["<Primary>E"],
            action_name="app.plugins",
        ),
        GajimShortcut(
            label=_("Manage Shortcuts"),
            category="general",
            accelerators=["<Primary>question"],
            action_name="app.shortcuts",
        ),
        GajimShortcut(
            label=_("Debug Console"),
            category="general",
            accelerators=["<Primary><Shift>X"],
            action_name="app.xml-console",
        ),
        GajimShortcut(
            label=_("Quit Gajim"),
            category="general",
            accelerators=["<Primary>Q"],
            action_name="app.quit",
        ),
    ],
)

MAIN_WIN_SHORTCUTS = GajimShortcutGroup(
    "main-win",
    [
        GajimShortcut(
            label=_("Increase Font Size"),
            category="general",
            accelerators=["<Primary>plus", "<Primary>KP_Add"],
            action_name="win.increase-app-font-size",
        ),
        GajimShortcut(
            label=_("Decrease Font Size"),
            category="general",
            accelerators=["<Primary>minus", "<Primary>KP_Subtract"],
            action_name="win.decrease-app-font-size",
        ),
        GajimShortcut(
            label=_("Reset Font Size"),
            category="general",
            accelerators=["<Primary>0", "<Primary>KP_0"],
            action_name="win.reset-app-font-size",
        ),
        GajimShortcut(
            label=_("Focus Search"),
            category="chats",
            accelerators=["<Primary>K"],
            action_name="win.focus-search",
        ),
        GajimShortcut(
            label=_("Search Chat History"),
            category="chats",
            accelerators=["<Primary>F"],
            action_name="win.search-history",
        ),
        GajimShortcut(
            label=_("Contact Details"),
            category="chats",
            accelerators=["<Primary>I"],
            action_name="win.show-contact-info",
        ),
        GajimShortcut(
            label=_("Change Nickname"),
            category="chats",
            accelerators=["<Primary><Shift>N"],
            action_name="win.change-nickname",
        ),
        GajimShortcut(
            label=_("Change Subject"),
            category="chats",
            accelerators=["<Primary><Shift>S"],
            action_name="win.change-subject",
        ),
        GajimShortcut(
            label="Escape",
            category="chats",
            accelerators=["Escape"],
            action_name="win.escape",
            allow_rebind=False,
        ),
        GajimShortcut(
            label=_("Close Chat"),
            category="chats",
            accelerators=["<Primary>W"],
            action_name="win.close-chat",
        ),
        GajimShortcut(
            label=_("Restore Closed Chat"),
            category="chats",
            accelerators=["<Primary><Shift>W"],
            action_name="win.restore-chat",
        ),
        GajimShortcut(
            label=_("Toggle Chat List"),
            category="chats",
            accelerators=["<Primary>R"],
            action_name="win.chat-list-visible",
        ),
        GajimShortcut(
            label=_("Switch to Next Chat"),
            category="chats",
            accelerators=["<Primary>Page_Down"],
            action_name="win.switch-next-chat",
        ),
        GajimShortcut(
            label=_("Switch to Previous Chat"),
            category="chats",
            accelerators=["<Primary>Page_Up"],
            action_name="win.switch-prev-chat",
        ),
        GajimShortcut(
            label=_("Switch to Next Unread Chat"),
            category="chats",
            accelerators=["<Primary>Tab"],
            action_name="win.switch-next-unread-chat",
        ),
        GajimShortcut(
            label=_("Switch to Previous Unread Chat"),
            category="chats",
            accelerators=["<Primary>ISO_Left_Tab"],
            action_name="win.switch-prev-unread-chat",
        ),
        GajimShortcut(
            label=_("Switch to Chat 1"),
            category="chats",
            accelerators=["<Alt>1", "<Alt>KP_1"],
            action_name="win.switch-chat-1",
        ),
        GajimShortcut(
            label=_("Switch to Chat 2"),
            category="chats",
            accelerators=["<Alt>2", "<Alt>KP_2"],
            action_name="win.switch-chat-2",
        ),
        GajimShortcut(
            label=_("Switch to Chat 3"),
            category="chats",
            accelerators=["<Alt>3", "<Alt>KP_3"],
            action_name="win.switch-chat-3",
        ),
        GajimShortcut(
            label=_("Switch to Chat 4"),
            category="chats",
            accelerators=["<Alt>4", "<Alt>KP_4"],
            action_name="win.switch-chat-4",
        ),
        GajimShortcut(
            label=_("Switch to Chat 5"),
            category="chats",
            accelerators=["<Alt>5", "<Alt>KP_5"],
            action_name="win.switch-chat-5",
        ),
        GajimShortcut(
            label=_("Switch to Chat 6"),
            category="chats",
            accelerators=["<Alt>6", "<Alt>KP_6"],
            action_name="win.switch-chat-6",
        ),
        GajimShortcut(
            label=_("Switch to Chat 7"),
            category="chats",
            accelerators=["<Alt>7", "<Alt>KP_7"],
            action_name="win.switch-chat-7",
        ),
        GajimShortcut(
            label=_("Switch to Chat 8"),
            category="chats",
            accelerators=["<Alt>8", "<Alt>KP_8"],
            action_name="win.switch-chat-8",
        ),
        GajimShortcut(
            label=_("Switch to Chat 9"),
            category="chats",
            accelerators=["<Alt>9", "<Alt>KP_9"],
            action_name="win.switch-chat-9",
        ),
        GajimShortcut(
            label=_("Switch to Workspace 1"),
            category="chats",
            accelerators=["<Primary>1", "<Primary>KP_1"],
            action_name="win.switch-workspace-1",
        ),
        GajimShortcut(
            label=_("Switch to Workspace 2"),
            category="chats",
            accelerators=["<Primary>2", "<Primary>KP_2"],
            action_name="win.switch-workspace-2",
        ),
        GajimShortcut(
            label=_("Switch to Workspace 3"),
            category="chats",
            accelerators=["<Primary>3", "<Primary>KP_3"],
            action_name="win.switch-workspace-3",
        ),
        GajimShortcut(
            label=_("Switch to Workspace 4"),
            category="chats",
            accelerators=["<Primary>4", "<Primary>KP_4"],
            action_name="win.switch-workspace-4",
        ),
        GajimShortcut(
            label=_("Switch to Workspace 5"),
            category="chats",
            accelerators=["<Primary>5", "<Primary>KP_5"],
            action_name="win.switch-workspace-5",
        ),
        GajimShortcut(
            label=_("Switch to Workspace 6"),
            category="chats",
            accelerators=["<Primary>6", "<Primary>KP_6"],
            action_name="win.switch-workspace-6",
        ),
        GajimShortcut(
            label=_("Switch to Workspace 7"),
            category="chats",
            accelerators=["<Primary>7", "<Primary>KP_7"],
            action_name="win.switch-workspace-7",
        ),
        GajimShortcut(
            label=_("Switch to Workspace 8"),
            category="chats",
            accelerators=["<Primary>8", "<Primary>KP_8"],
            action_name="win.switch-workspace-8",
        ),
        GajimShortcut(
            label=_("Switch to Workspace 9"),
            category="chats",
            accelerators=["<Primary>9", "<Primary>KP_9"],
            action_name="win.switch-workspace-9",
        ),
        GajimShortcut(
            label=_("Choose Emoji"),
            category="messages",
            accelerators=["<Primary><Shift>M"],
            action_name="win.show-emoji-chooser",
        ),
        GajimShortcut(
            label=_("Scroll Up"),
            category="messages",
            accelerators=["<Shift>Page_Up"],
            action_name="win.scroll-view-up",
        ),
        GajimShortcut(
            label=_("Scroll Down"),
            category="messages",
            accelerators=["<Shift>Page_Down"],
            action_name="win.scroll-view-down",
        ),
        GajimShortcut(
            label=_("Quote Previous Message"),
            category="messages",
            accelerators=["<Primary><Shift>Up"],
            action_name="win.quote-prev",
        ),
        GajimShortcut(
            label=_("Quote Next Message"),
            category="messages",
            accelerators=["<Primary><Shift>Down"],
            action_name="win.quote-next",
        ),
    ],
)


INPUT_SHORTCUTS = GajimShortcutGroup(
    "input",
    [
        GajimShortcut(
            label=_("Clear Input"),
            category="messages",
            accelerators=["<Primary>U"],
            action_name="text.clear",
        ),
    ],
)


INPUT_GLOBAL_SHORTCUTS = GajimShortcutGroup(
    "input-global",
    [
        GajimShortcut(
            label=_("Focus Input"),
            category="messages",
            accelerators=None,
            action_name="win.input-focus",
        ),
    ],
)
