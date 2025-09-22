from datetime import datetime

from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common import events
from gajim.common import ged
from gajim.common.i18n import _
from gajim.common.storage.archive.models import Message
from gajim.common.storage.archive.storage import ThreadDetails
from gajim.common.util.identicons import get_identicon_pixbuf
from gajim.common.util.user_strings import get_uf_relative_time


class ThreadInfoBox(Gtk.Box):
    def __init__(self) -> None:
        super().__init__(
            orientation=Gtk.Orientation.HORIZONTAL,
            halign=Gtk.Align.FILL,
            hexpand=True,
            css_classes=["mx-9", "mb-3"],
        )
        box = Gtk.Box(hexpand=True, halign=Gtk.Align.START)
        self._image = Gtk.Image.new_from_icon_name("lucide-thread-all-symbolic")
        self._image.set_visible(True)
        self._label = Gtk.Label(css_classes=["ms-6", "dimmed"])
        box.append(self._image)
        box.append(self._label)
        self._new_thread_button = Gtk.Button(
            icon_name="lucide-thread-new-symbolic",
            halign=Gtk.Align.END,
            action_name="win.thread-start",
            tooltip_text=_("Start a new thread"),
        )
        self._thread_none_button = Gtk.Button(
            icon_name="lucide-thread-del-symbolic",
            halign=Gtk.Align.END,
            action_name="win.thread-select-none",
            tooltip_text=_("Show unthreaded messages only"),
        )
        self._all_threads_button = Gtk.Button(
            icon_name="lucide-thread-all-symbolic",
            halign=Gtk.Align.END,
            action_name="win.thread-deselect",
            tooltip_text=_("Show messages from all threads"),
        )
        self._toggle_thread_list_button = Gtk.Button(
            action_name="win.thread-toggle-list",
            tooltip_text=_("Show/hide thread list"),
        )

        toggle_box = Gtk.Box()
        toggle_box.append(Gtk.Image.new_from_icon_name("lucide-thread-symbolic"))
        self.toggle_chevron_image = Gtk.Image.new_from_icon_name(
            "lucide-chevron-left-symbolic"
        )
        toggle_box.append(self.toggle_chevron_image)
        self._toggle_thread_list_button.set_child(toggle_box)

        self.append(box)
        self.append(self._new_thread_button)
        self.append(self._thread_none_button)
        self.append(self._all_threads_button)
        self.append(self._toggle_thread_list_button)

        self._all_threads()
        app.ged.register_event_handler(
            "register-actions", ged.GUI1, self._on_register_actions
        )

    def _on_register_actions(self, _event: events.RegisterActions) -> None:
        app.window.get_action("thread-select").connect(
            "activate", self._on_thread_select
        )
        app.window.get_action("thread-select-none").connect(
            "activate", self._on_thread_select_none
        )
        app.window.get_action("thread-deselect").connect(
            "activate", self._on_thread_deselect
        )

    def set_thread(self, thread_id: str, new: bool = False) -> None:
        if new:
            self._label.set_label(_("Starting a new thread"))
        else:
            self._label.set_label(_("Showing messages from a specific thread"))
        self._image.set_from_pixbuf(get_identicon_pixbuf(thread_id, 10))
        self._new_thread_button.set_visible(False)
        self._thread_none_button.set_visible(False)
        self._all_threads_button.set_visible(True)

    def _all_threads(self) -> None:
        self._label.set_label(_("Showing messages from all threads"))
        self._image.set_from_icon_name("lucide-thread-all-symbolic")
        self._new_thread_button.set_visible(True)
        self._thread_none_button.set_visible(True)
        self._all_threads_button.set_visible(False)

    def _on_thread_deselect(
        self, _action: Gio.Action, _parameter: GLib.Variant
    ) -> None:
        self._all_threads()

    def _on_thread_select(self, _action: Gio.Action, parameter: GLib.Variant) -> None:
        self.set_thread(parameter.get_string())

    def _on_thread_select_none(
        self, _action: Gio.Action, _parameter: GLib.Variant
    ) -> None:
        self._label.set_label(_("Showing only unthreaded messages"))
        self._image.set_from_icon_name("lucide-thread-del-symbolic")
        self._new_thread_button.set_visible(True)
        self._thread_none_button.set_visible(False)
        self._all_threads_button.set_visible(True)


class ThreadItem(Gtk.ListItem):
    title = GObject.Property(type=str)
    author = GObject.Property(
        type=str
    )  # TODO: this never changes, so need for Property?
    msg_count = GObject.Property(type=int)
    created = GObject.Property(
        type=float
    )  # TODO: this never changes, so need for Property?
    updated = GObject.Property(type=float)

    def __init__(self, thread_id: str):
        super().__init__()
        self._thread_id = thread_id

    @property
    def thread_id(self) -> str:
        return self._thread_id


class ThreadWidget(Gtk.Box):
    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        self.set_margin_top(8)
        self.set_margin_bottom(8)
        self.set_margin_start(12)
        self.set_margin_end(12)

        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        title_label = Gtk.Label()
        title_label.set_ellipsize(Pango.EllipsizeMode.END)
        title_label.set_xalign(0)
        title_label.set_wrap(True)
        title_label.set_hexpand(True)

        self._image = Gtk.Image()

        title_box.append(title_label)
        title_box.append(self._image)
        self.append(title_box)

        # Create horizontal box for metadata
        meta_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        author_label = Gtk.Label()
        author_label.set_xalign(0)
        meta_box.append(author_label)

        msg_count_label = Gtk.Label()
        msg_count_label.set_xalign(0)
        meta_box.append(msg_count_label)

        updated_label = Gtk.Label()
        updated_label.set_xalign(1)
        updated_label.set_hexpand(True)
        meta_box.append(updated_label)

        self.append(meta_box)

        separator = Gtk.Separator()
        separator.set_margin_top(4)
        self.append(separator)

        self._title_label = title_label
        self._author_label = author_label
        self._updated_label = updated_label
        self._msg_count_label = msg_count_label

    def bind_data(self, item: ThreadItem):
        self._image.set_from_pixbuf(get_identicon_pixbuf(item.thread_id, 10))
        item.connect("notify::author", self._on_author)
        item.connect("notify::title", self._on_title)
        item.connect("notify::msg-count", self._on_msg_count)
        item.connect("notify::updated", self._on_updated)
        for k in "author", "title", "msg-count", "updated":
            item.notify(k)

    def _on_title(self, item: ThreadItem, _value: GObject.ParamSpecString) -> None:
        for line in item.title.split("\n"):
            if line.strip():
                break
        else:
            line = "Untitled"
        self._title_label.set_markup(f"<b>{GLib.markup_escape_text(line)}</b>")

    def _on_author(self, item: ThreadItem, _value: GObject.ParamSpecString) -> None:
        # TODO: translation
        self._author_label.set_markup(
            f"<small>by {GLib.markup_escape_text(item.author)}</small>"
        )

    def _on_msg_count(self, item: ThreadItem, _value: GObject.ParamSpecInt) -> None:
        if item.msg_count == 1:
            t = "message"  # TODO: translation
        else:
            t = "messages"
        self._msg_count_label.set_markup(f"<small>{item.msg_count} {t}</small>")

    def _on_updated(self, item: ThreadItem, _value: GObject.ParamSpecDouble) -> None:
        if item.updated is None:
            return
        self._updated_label.set_markup(
            "<small>"
            + get_uf_relative_time(datetime.fromtimestamp(item.updated))
            + "</small>"
        )


class ThreadList(Gtk.Box):
    __gtype_name__ = "ThreadList"

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self._store = Gio.ListStore.new(ThreadItem)
        self._sorter = Gtk.CustomSorter.new(self._compare_threads)
        self._sort_model = Gtk.SortListModel.new(self._store, self._sorter)

        selection = Gtk.SingleSelection.new(self._sort_model)
        selection.set_autoselect(False)
        selection.set_can_unselect(True)
        selection.connect("selection-changed", self._on_selection_changed)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", _on_factory_setup)
        factory.connect("bind", _on_factory_bind)

        self._list_view = Gtk.ListView()
        self._list_view.set_model(selection)
        self._list_view.set_factory(factory)

        self._scrolled = Gtk.ScrolledWindow()
        self._scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._scrolled.set_child(self._list_view)
        self._scrolled.set_vexpand(True)

        self.append(self._scrolled)

        app.ged.register_event_handler(
            "register-actions", ged.GUI1, self._on_register_actions
        )

        self._programmatic_selection = False

    def _on_register_actions(self, _event: events.RegisterActions) -> None:
        app.window.get_action("thread-select").connect(
            "activate", self._on_thread_select
        )
        app.window.get_action("thread-select-none").connect(
            "activate", self._on_thread_select_none
        )
        app.window.get_action("thread-deselect").connect(
            "activate", self._on_thread_deselect
        )

    def _on_selection_changed(
        self, selection: Gtk.SingleSelection, _position: int, _n_items: int
    ) -> None:
        if self._programmatic_selection:
            return
        item = selection.get_selected_item()
        if item is not None:
            app.window.get_action("thread-select").activate(
                GLib.Variant("s", item.thread_id)
            )

    def _on_thread_select(self, _action: str, parameter: GLib.Variant) -> None:
        print("on thread select")
        thread_id = parameter.get_string()
        selected_item = self._list_view.get_model().get_selected_item()
        if selected_item is not None and selected_item.thread_id == thread_id:
            print("nothing to do")
            return

        i, item = self._get_item(thread_id)
        if item is None:
            print("thread not found")
        else:
            self._programmatic_selection = True
            self._list_view.get_model().select_item(i, True)
            self._list_view.scroll_to(i, Gtk.ListScrollFlags.SELECT)
            self._programmatic_selection = False

    def _on_thread_deselect(self, _action, _parameter) -> None:
        print("deselect")
        self._programmatic_selection = True
        self._list_view.get_model().unselect_all()
        self._programmatic_selection = False

    def _on_thread_select_none(self, _action, _parameter) -> None:
        print("select-none")
        self._programmatic_selection = True
        self._list_view.get_model().unselect_all()
        self._programmatic_selection = False

    @staticmethod
    def _compare_threads(item1: ThreadItem, item2: ThreadItem, user_data=None):
        """Compare function for sorting threads by timestamp"""
        if item1.updated < item2.updated:
            return -1
        elif item1.updated > item2.updated:
            return 1
        return 0

    def add_thread(self, thread: ThreadDetails) -> None:
        item = ThreadItem(thread.thread.id)
        if thread.first_msg is not None:
            item.title = thread.first_msg.text
            if thread.first_msg.occupant is not None:
                item.author = thread.first_msg.occupant.nickname
        item.msg_count = thread.msg_count
        if thread.last_msg is not None:
            item.updated = thread.last_msg.timestamp.timestamp()
        self._store.append(item)

    def add_message(self, message: Message) -> None:
        if message.thread is None:
            return
        i, item = self._get_item(message.thread.id)
        if item is None:
            print("new thread from new message")  # FIXME:
            item = ThreadItem(message.thread.id)
            item.title = message.text
            if message.occupant is not None:
                item.author = message.occupant.nickname
            item.msg_count = 1
            item.updated = message.timestamp.timestamp()
            self._store.append(item)
        else:
            assert isinstance(item, ThreadItem)
            item.msg_count += 1
            if item.updated < message.timestamp.timestamp():
                item.updated = message.timestamp.timestamp()
                self._sorter.changed(Gtk.SorterChange.DIFFERENT)
            self._store.items_changed(i, 1, 1)
        self.scroll_to_bottom()

    def _get_item(self, thread_id: str) -> tuple[int, ThreadItem] | tuple[None, None]:
        """Get a thread by its ID"""
        for i in range(self._store.get_n_items()):
            thread_item: ThreadItem = self._store.get_item(i)
            if thread_item.thread_id == thread_id:
                return i, thread_item
        return None, None

    def reset(self):
        self._store.remove_all()

    def _get_max_scroll(self) -> float:
        vadj = self._scrolled.get_vadjustment()
        return vadj.get_upper() - vadj.get_page_size()

    def _scroll_is_at_bottom(self) -> bool:
        return self._scrolled.get_vadjustment().get_value() == self._get_max_scroll()

    def _scroll_to_bottom(self):
        """Method 1: Using vertical adjustment"""
        vadj = self._scrolled.get_vadjustment()
        vadj.set_value(self._get_max_scroll())
        return False

    def scroll_to_bottom(self, force: bool = False):
        if not force and not self._scroll_is_at_bottom():
            return
        GLib.idle_add(self._scroll_to_bottom)


def _on_factory_setup(_factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem):
    widget = ThreadWidget()
    list_item.set_child(widget)


def _on_factory_bind(_factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem):
    thread_item = list_item.get_item()
    widget = list_item.get_child()
    widget.bind_data(thread_item)
