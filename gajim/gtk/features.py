# Copyright (C) 2007 Jean-Marie Traissard <jim AT lapin.org>
#                    Julien Pivotto <roidelapluie AT gmail.com>
#                    Stefan Bethge <stefan AT lanpartei.de>
#                    Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2007-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
#
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

from typing import NamedTuple
from typing import List

import os
import sys

from gi.repository import Gtk
from gi.repository import Gdk

from gajim.common import app
from gajim.common.i18n import _


class Feature(NamedTuple):
    name: str
    available: bool
    tooltip: str
    dependency_u: str
    dependency_w: str
    enabled: bool


class Features(Gtk.ApplicationWindow):
    def __init__(self) -> None:
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_name('Features')
        self.set_title(_('Features'))
        self.set_resizable(False)
        self.set_transient_for(app.window)

        grid = Gtk.Grid()
        grid.set_name('FeaturesInfoGrid')
        grid.set_row_spacing(10)
        grid.set_hexpand(True)

        self.feature_listbox = Gtk.ListBox()
        self.feature_listbox.set_selection_mode(Gtk.SelectionMode.NONE)

        grid.attach(self.feature_listbox, 0, 0, 1, 1)

        box = Gtk.Box()
        box.pack_start(grid, True, True, 0)
        box.set_property('margin', 12)
        box.set_spacing(18)
        self.add(box)

        self.connect('key-press-event', self._on_key_press)

        for feature in self._get_features():
            self._add_feature(feature)

        self.show_all()

    def _on_key_press(self,
                      _widget: Gtk.Widget,
                      event: Gdk.EventButton) -> None:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _add_feature(self, feature: Feature) -> None:
        item = FeatureItem(feature)
        self.feature_listbox.add(item)

    def _get_features(self) -> List[Feature]:
        notification_sounds_available: bool = (
            app.is_installed('GSOUND') or sys.platform in ('win32', 'darwin'))
        notification_sounds_enabled: bool = app.settings.get('sounds_on')
        spell_check_enabled: bool = app.settings.get('use_speller')

        auto_status = [app.settings.get('autoaway'), app.settings.get('autoxa')]
        auto_status_enabled = bool(any(auto_status))

        return [
            Feature(_('App Indicator Icon'),
                    app.is_installed('APPINDICATOR') or
                    app.is_installed('AYATANA_APPINDICATOR'),
                    _('Enables Gajim to provide a system notification area '
                      'icon'),
                    _('Requires: libappindicator3'),
                    _('Feature not available under Windows'),
                    None),
            Feature(_('Audio / Video'),
                    app.is_installed('AV'),
                    _('Enables Gajim to provide Audio and Video chats'),
                    _('Requires: gir1.2-farstream-0.2, gir1.2-gstreamer-1.0, '
                      'gstreamer1.0-plugins-base, gstreamer1.0-plugins-ugly, '
                      'gstreamer1.0-libav, and gstreamer1.0-gtk3'),
                    _('Feature not available under Windows'),
                    None),
            Feature(_('Automatic Status'),
                    self._idle_available(),
                    _('Enables Gajim to measure your computer\'s idle time in '
                      'order to set your Status automatically'),
                    _('Requires: libxss'),
                    _('No additional requirements'),
                    auto_status_enabled),
            Feature(_('Bonjour / Zeroconf (Serverless Chat)'),
                    app.is_installed('ZEROCONF'),
                    _('Enables Gajim to automatically detected clients in a '
                      'local network for serverless chats'),
                    _('Requires: gir1.2-avahi-0.6'),
                    _('Requires: pybonjour and bonjour SDK running (%(url)s)')
                    % {'url': 'https://developer.apple.com/opensource/)'},
                    None),
            Feature(_('Location detection'),
                    app.is_installed('GEOCLUE'),
                    _('Enables Gajim to be location-aware, if the user decides '
                      'to publish the device’s location'),
                    _('Requires: geoclue'),
                    _('Feature is not available under Windows'),
                    None),
            Feature(_('Notification Sounds'),
                    notification_sounds_available,
                    _('Enables Gajim to play sounds for various notifications'),
                    _('Requires: gsound'),
                    _('No additional requirements'),
                    notification_sounds_enabled),
            Feature(_('Secure Password Storage'),
                    self._some_keyring_available(),
                    _('Enables Gajim to store Passwords securely instead of '
                      'storing them in plaintext'),
                    _('Requires: gnome-keyring or kwallet'),
                    _('Windows Credential Vault is used for secure password '
                      'storage'),
                    app.settings.get('use_keyring')),
            Feature(_('Spell Checker'),
                    app.is_installed('GSPELL'),
                    _('Enables Gajim to spell check your messages while '
                      'composing'),
                    _('Requires: Gspell'),
                    _('Requires: Gspell'),
                    spell_check_enabled),
            Feature(_('UPnP-IGD Port Forwarding'),
                    app.is_installed('UPNP'),
                    _('Enables Gajim to request your router to forward ports '
                      'for file transfers'),
                    _('Requires: gir1.2-gupnpigd-1.0'),
                    _('Feature not available under Windows'),
                    None)
        ]

    @staticmethod
    def _some_keyring_available() -> bool:
        from gajim.common import passwords
        return passwords.KEYRING_AVAILABLE

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
        self._box.pack_start(feature_label, True, True, 0)
        self._box.set_tooltip_text(feature.tooltip)

        feature_dependency = Gtk.Label(label=feature.dependency_u)
        feature_dependency.get_style_context().add_class('dim-label')

        if os.name == 'nt':
            feature_dependency.set_label(feature.dependency_w)
        else:
            feature_dependency.set_label(feature.dependency_u)

        if not feature.available:
            feature_dependency.set_halign(Gtk.Align.START)
            feature_dependency.set_xalign(0.0)
            feature_dependency.set_yalign(0.0)
            feature_dependency.set_line_wrap(True)
            feature_dependency.set_max_width_chars(50)
            feature_dependency.set_selectable(True)
            self._box.pack_start(feature_dependency, True, True, 0)

        self._icon = Gtk.Image()
        self._label_disabled = Gtk.Label(label=_('Disabled in Preferences'))
        self._label_disabled.get_style_context().add_class('dim-label')
        self._set_feature(feature.available, feature.enabled)

        self.add(self._icon)
        self.add(self._box)

    def _set_feature(self, available: bool, enabled: bool) -> None:
        self._icon.get_style_context().remove_class('error-color')
        self._icon.get_style_context().remove_class('warning-color')
        self._icon.get_style_context().remove_class('success-color')

        if not available:
            self._icon.set_from_icon_name(
                'window-close-symbolic', Gtk.IconSize.MENU)
            self._icon.get_style_context().add_class('error-color')
        elif enabled is False:
            self._icon.set_from_icon_name(
                'dialog-warning-symbolic', Gtk.IconSize.MENU)
            self._box.pack_start(self._label_disabled, True, True, 0)
            self._icon.get_style_context().add_class('warning-color')
        else:
            self._icon.set_from_icon_name(
                'emblem-ok-symbolic', Gtk.IconSize.MENU)
            self._icon.get_style_context().add_class('success-color')
