# Copyright (C) 2007 Jean-Marie Traissard <jim AT lapin.org>
#                    Julien Pivotto <roidelapluie AT gmail.com>
#                    Stefan Bethge <stefan AT lanpartei.de>
#                    Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2007-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import NamedTuple

import sys

from gi.repository import Gtk

from gajim.common import app
from gajim.common import passwords
from gajim.common.i18n import _

from gajim.gtk.widgets import GajimAppWindow


class Feature(NamedTuple):
    name: str
    available: bool
    tooltip: str
    dependency_u: str
    dependency_w: str
    enabled: bool | None


class Features(GajimAppWindow):
    def __init__(self) -> None:
        GajimAppWindow.__init__(self, name="Features", title=_("Features"))

        grid = Gtk.Grid(name="FeaturesInfoGrid", row_spacing=10, width_request=400)

        self.feature_listbox = Gtk.ListBox(
            hexpand=True, vexpand=True, selection_mode=Gtk.SelectionMode.NONE
        )

        grid.attach(self.feature_listbox, 0, 0, 1, 1)

        box = Gtk.Box(spacing=18)
        box.append(grid)
        self.set_child(box)

        for feature in self._get_features():
            self._add_feature(feature)

    def _cleanup(self) -> None:
        pass

    def _add_feature(self, feature: Feature) -> None:
        item = FeatureItem(feature)
        self.feature_listbox.append(item)

    def _get_features(self) -> list[Feature]:
        av_available = app.is_installed("AV") and sys.platform != "win32"
        notification_sounds_available: bool = app.is_installed(
            "GSOUND"
        ) or sys.platform in ("win32", "darwin")
        notification_sounds_enabled: bool = app.settings.get("sounds_on")
        spell_check_enabled: bool = app.settings.get("use_speller")

        auto_status = [app.settings.get("autoaway"), app.settings.get("autoxa")]
        auto_status_enabled = bool(any(auto_status))

        return [
            Feature(
                _("Audio Preview"),
                app.is_installed("GST"),
                _("Enables Gajim to provide a Audio preview"),
                _("Requires: gstreamer-1.0, gst-plugins-base-1.0"),
                _("No additional requirements"),
                None,
            ),
            Feature(
                _("Audio / Video Calls"),
                av_available,
                _("Enables Gajim to provide Audio and Video chats"),
                _(
                    "Requires: farstream-0.2, gstreamer-1.0, "
                    "gst-plugins-base-1.0, gst-plugins-ugly-1.0, "
                    "gst-libav"
                ),
                _("Feature not available on Windows"),
                None,
            ),
            Feature(
                _("Automatic Status"),
                self._idle_available(),
                _(
                    "Enables Gajim to measure your computer’s idle time in "
                    "order to set your Status automatically"
                ),
                _("Requires: libxss"),
                _("No additional requirements"),
                auto_status_enabled,
            ),
            Feature(
                _("Notification Sounds"),
                notification_sounds_available,
                _("Enables Gajim to play sounds for various notifications"),
                _("Requires: gsound"),
                _("No additional requirements"),
                notification_sounds_enabled,
            ),
            Feature(
                _("Secure Password Storage"),
                passwords.is_keyring_available(),
                _(
                    "Enables Gajim to store Passwords securely instead of "
                    "storing them in plaintext"
                ),
                _("Requires: gnome-keyring or kwallet"),
                _("No additional requirements"),
                app.settings.get("use_keyring"),
            ),
            Feature(
                _("Spell Checker"),
                app.is_installed("SPELLING"),
                _("Enables Gajim to spell check your messages while composing"),
                _("Requires: libspelling"),
                _("No additional requirements"),
                spell_check_enabled,
            ),
            Feature(
                _("UPnP-IGD Port Forwarding"),
                app.is_installed("UPNP"),
                _(
                    "Enables Gajim to request your router to forward ports "
                    "for file transfers"
                ),
                _("Requires: gupnpigd-1.0"),
                _("Feature not available on Windows"),
                None,
            ),
        ]

    @staticmethod
    def _idle_available() -> bool:
        from gajim.common import idle

        return idle.Monitor.is_available()


class FeatureItem(Gtk.Grid):
    def __init__(self, feature: Feature) -> None:
        Gtk.Grid.__init__(self)
        self.set_column_spacing(12)

        feature_label = Gtk.Label(label=feature.name)
        feature_label.set_halign(Gtk.Align.START)
        self._box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._box.append(feature_label)
        self._box.set_tooltip_text(feature.tooltip)

        feature_dependency = Gtk.Label(label=feature.dependency_u)
        feature_dependency.add_css_class("dim-label")

        if sys.platform == "win32":
            feature_dependency.set_label(feature.dependency_w)
        else:
            feature_dependency.set_label(feature.dependency_u)

        if not feature.available:
            feature_dependency.set_halign(Gtk.Align.START)
            feature_dependency.set_xalign(0.0)
            feature_dependency.set_yalign(0.0)
            feature_dependency.set_wrap(True)
            feature_dependency.set_max_width_chars(50)
            feature_dependency.set_selectable(True)
            self._box.append(feature_dependency)

        self._icon = Gtk.Image()
        self._label_disabled = Gtk.Label(label=_("Disabled in Preferences"))
        self._label_disabled.add_css_class("dim-label")
        self._set_feature(feature.available, feature.enabled)

        self.attach(self._icon, 0, 0, 1, 1)
        self.attach(self._box, 1, 0, 1, 1)

    def do_unroot(self) -> None:
        Gtk.Grid.do_unroot(self)
        app.check_finalize(self)

    def _set_feature(self, available: bool, enabled: bool | None) -> None:
        self._icon.remove_css_class("error-color")
        self._icon.remove_css_class("warning-color")
        self._icon.remove_css_class("success-color")

        if not available:
            self._icon.set_from_icon_name("window-close-symbolic")
            self._icon.add_css_class("error-color")
            return

        if enabled is not None and not enabled:
            self._icon.set_from_icon_name("dialog-warning-symbolic")
            self._box.append(self._label_disabled)
            self._icon.add_css_class("warning-color")
        else:
            self._icon.set_from_icon_name("emblem-ok-symbolic")
            self._icon.add_css_class("success-color")
