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

    country_id = GObject.Property(type=str)
    country_name = GObject.Property(type=str)
    country_pm = GObject.Property(type=str)


class TestListView(GajimAppWindow):
    def __init__(self) -> None:
        GajimAppWindow.__init__(
            self,
            name="",
            title=__class__.__name__,
            default_width=800,
            default_height=800,
        )

        nodes = {
            "at": ("Austria", "Van der Bellen"),
            "uk": ("United Kingdom", "Charles III"),
            "us": ("United States", "Biden"),
        }

        self.model = Gio.ListStore(item_type=Country)
        for n in nodes:
            self.model.append(
                Country(country_id=n, country_name=nodes[n][0], country_pm=nodes[n][1])
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
        cell = Gtk.Inscription()
        cell._binding = None  # pyright: ignore
        list_item.set_child(cell)

    def _on_factory_bind(
        self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem, what: str
    ) -> None:
        country = list_item.get_item()
        cell = list_item.get_child()
        assert cell is not None
        cell._binding = country.bind_property(  # pyright: ignore
            what, cell, "text", GObject.BindingFlags.SYNC_CREATE
        )

    def _on_factory_unbind(
        self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem, what: str
    ) -> None:
        cell = list_item.get_child()
        if cell._binding:  # pyright: ignore
            cell._binding.unbind()  # pyright: ignore
            cell._binding = None  # pyright: ignore

    def _on_factory_teardown(
        self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem
    ) -> None:
        pass


util.init_settings()

window = TestListView()
window.show()

util.run_app()
