# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

'''
GUI classes related to plug-in management.

:author: Mateusz Biliński <mateusz@bilinski.it>
:since: 6th June 2008
:copyright: Copyright (2008) Mateusz Biliński <mateusz@bilinski.it>
:license: GPL
'''

from __future__ import annotations

from typing import Any
from typing import TYPE_CHECKING

from gi.repository import Gtk

from gajim.plugins.plugins_i18n import _


if TYPE_CHECKING:
    from gajim.plugins.gajimplugin import GajimPlugin


class GajimPluginConfigDialog(Gtk.Dialog):
    def __init__(self, plugin: GajimPlugin, **kwargs: Any) -> None:
        Gtk.Dialog.__init__(self,
                            title='%s %s' % (plugin.name, _('Configuration')),
                            **kwargs)
        self.plugin = plugin
        button = self.add_button('gtk-close', Gtk.ResponseType.CLOSE)
        button.connect('clicked', self.on_close_button_clicked)

        self.get_child().set_spacing(3)

        self.init()

    def on_close_dialog(self, widget: Gtk.Widget, data: Any) -> bool:
        self.hide()
        return True

    def on_close_button_clicked(self, widget: Gtk.Button) -> None:
        self.hide()

    def run(self, parent: Any = None):
        self.set_transient_for(parent)
        self.on_run()
        self.show_all()
        self.connect('delete-event', self.on_close_dialog)
        result = super(GajimPluginConfigDialog, self)
        return result

    def init(self) -> None:
        pass

    def on_run(self) -> None:
        pass
