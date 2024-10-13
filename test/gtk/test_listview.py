# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk

from gajim.gtk.widgets import GajimAppWindow

from . import util


class Country(GObject.Object):
    __gtype_name__ = "Country"

    def __init__(self, country_id: str, country_name: str, pm: str) -> None:
        super().__init__()

        self._country_id = country_id
        self._country_name = country_name
        self._country_pm = pm

    @GObject.Property(type=str)
    def country_id(self) -> str:
        return self._country_id

    @GObject.Property(type=str)
    def country_name(self) -> str:
        return self._country_name

    @GObject.Property(type=str)
    def country_pm(self) -> str:
        return self._country_pm

    def __repr__(self) -> str:
        return f"Country(country_id={self.country_id}, country_name={self.country_name})"  # noqa


class ListViewTest(GajimAppWindow):
    def __init__(self) -> None:
        GajimAppWindow.__init__(
            self,
            name='',
            title='Test ListView',
            default_width=800,
            default_height=800,
        )

        nodes = {
            "at": ("Austria", "Van der Bellen"),
            "uk": ("United Kingdom", "Charles III"),
            "us": ("United States", "Biden"),
        }

        self.model = Gio.ListStore(item_type=Country)
        for n in nodes.keys():
            self.model.append(
                Country(country_id=n, country_name=nodes[n][0], pm=nodes[n][1])
            )

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_factory_setup)
        factory.connect("bind", self._on_factory_bind, "country_name")
        factory.connect("unbind", self._on_factory_unbind, "country_name")
        factory.connect("teardown", self._on_factory_teardown)

        self.lv = Gtk.ListView(
            model=Gtk.NoSelection(model=self.model),
            factory=factory,
            hexpand=True,
        )

        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=12, valign=Gtk.Align.CENTER
        )
        box.props.margin_start = 12
        box.props.margin_end = 12
        box.props.margin_top = 6
        box.props.margin_bottom = 6
        box.append(Gtk.Label(label="Some Table:"))
        box.append(self.lv)

        self.set_child(box)

    def _cleanup(self) -> None:
        pass

    def _on_factory_setup(
        self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem
    ) -> None:
        print('setup', list_item)
        cell = Gtk.Inscription()
        cell._binding = None
        list_item.set_child(cell)

    def _on_factory_bind(
        self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem, what: str
    ) -> None:
        country = list_item.get_item()
        print('bind', country)
        cell = list_item.get_child()
        cell._binding = country.bind_property(
            what, cell, "text", GObject.BindingFlags.SYNC_CREATE
        )

    def _on_factory_unbind(
        self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem, what: str
    ) -> None:
        country = list_item.get_item()
        print('unbind', country)
        cell = list_item.get_child()
        if cell._binding:
            cell._binding.unbind()
            cell._binding = None

    def _on_factory_teardown(
        self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem
    ) -> None:
        print('teardown', list_item)


window = ListViewTest()
window.show()

util.run_app()
