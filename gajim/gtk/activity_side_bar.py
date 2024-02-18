# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.i18n import _

from gajim.gtk.activity_list import ActivityList


class ActivitySideBar(Gtk.EventBox):
    def __init__(self, activity_list: ActivityList) -> None:
        Gtk.EventBox.__init__(self, tooltip_text=_('Activity'))
        self.get_style_context().add_class('activity-sidebar')

        activity_list.connect(
            'unread-count-changed', self._on_unread_count_changed)

        self.connect('button-press-event', self._on_button_press)
        self.connect('enter-notify-event', self._on_hover)
        self.connect('leave-notify-event', self._on_hover)

        container = Gtk.Box()

        self._selection_bar = Gtk.Box(
            width_request=6,
            margin_start=1
        )
        self._selection_bar.get_style_context().add_class('selection-bar')
        container.add(self._selection_bar)

        surface = app.app.avatar_storage.get_activity_sidebar_icon(
            AvatarSize.ACCOUNT_SIDE_BAR, self.get_scale_factor())
        image = Gtk.Image.new_from_surface(surface)
        container.add(image)

        self._unread_label = Gtk.Label(
            halign=Gtk.Align.END,
            valign=Gtk.Align.START,
            no_show_all=True
        )
        self._unread_label.get_style_context().add_class(
            'unread-counter')

        overlay = Gtk.Overlay()
        overlay.add(container)
        overlay.add_overlay(self._unread_label)

        self.add(overlay)

        self.show_all()

    def set_unread_count(self, count: int) -> None:
        if count < 1000:
            self._unread_label.set_text(str(count))
        else:
            self._unread_label.set_text('999+')
        self._unread_label.set_visible(bool(count))

    def select(self) -> None:
        self._selection_bar.get_style_context().add_class('selection-bar-selected')

    def unselect(self) -> None:
        self._selection_bar.get_style_context().remove_class('selection-bar-selected')

    def _on_unread_count_changed(self,
                                 _widget: ActivityList,
                                 count: int
                                 ) -> None:

        self.set_unread_count(count)

    def _on_hover(self,
                  _widget: ActivitySideBar,
                  event: Gdk.EventCrossing
                  ) -> bool:

        style_context = self._selection_bar.get_style_context()
        if event.type == Gdk.EventType.ENTER_NOTIFY:
            style_context.add_class('selection-bar-hover')
        else:
            style_context.remove_class('selection-bar-hover')
        return True

    def _on_button_press(self,
                         _widget: ActivitySideBar,
                         event: Gdk.EventButton
                         ) -> bool:

        if event.button == Gdk.BUTTON_PRIMARY:
            app.window.show_activity_page()

        return True
