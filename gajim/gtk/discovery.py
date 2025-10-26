# Copyright (C) 2005-2006 Stéphan Kochen <stephan AT kochen.nl>
# Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2005-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2006 Tomasz Melcer <liori AT exroot.org>
# Copyright (C) 2007 Stephan Erb <steve-e AT h3c.de>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# The appearance of the treeview, and parts of the dialog, are controlled by
# AgentBrowser (sub-)classes. Methods that probably should be overridden when
# subclassing are: (look at the docstrings and source for additional info)
# - def cleanup(self) *
# - def _create_treemodel(self) *
# - def _add_actions(self)
# - def _clean_actions(self)
# - def update_actions(self)
# - def default_action(self)
# - def _find_item(self, jid, node)
# - def _add_item(self, jid, node, parent_node, item, force)
# - def _update_info(self, iter_, jid, node, identities, features, data)
# - def _update_error(self, iter_, jid, node)
#
# * Should call the super class for this method.
# All others do not have to call back to the super class (but can if they want
# the functionality).
# There are more methods, of course, but this is a basic set.

from __future__ import annotations

from typing import Any
from typing import cast
from typing import Concatenate
from typing import Generic
from typing import TypeVar

import logging
import types
import weakref
from collections.abc import Callable
from collections.abc import Iterator

from gi.repository import GLib
from gi.repository import Gtk
from nbxmpp.errors import StanzaError
from nbxmpp.modules.pubsub import PubSubSubscription
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.structs import DiscoIdentity
from nbxmpp.structs import DiscoInfo
from nbxmpp.structs import DiscoItem
from nbxmpp.structs import DiscoItems
from nbxmpp.task import Task

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.util.jid import InvalidFormat
from gajim.common.util.jid import parse_jid

from gajim.gtk.alert import InformationAlertDialog
from gajim.gtk.builder import get_builder
from gajim.gtk.component_search import ComponentSearch
from gajim.gtk.util.icons import icon_exists
from gajim.gtk.util.window import open_window
from gajim.gtk.widgets import GajimAppWindow

_T = TypeVar("_T")
_InfoCacheT = tuple[list[DiscoIdentity], list[str], list[Any]]

log = logging.getLogger("gajim.gtk.discovery")

LABELS = {
    1: _("This service has not yet responded with detailed information"),
    2: _(
        "This service could not respond with detailed information.\n"
        "It is most likely a legacy service or broken."
    ),
}

# Dictionary mapping category, type pairs to browser class, image pairs.
# This is a function, so we can call it after the classes are declared.
# For the browser class, None means that the service will only be browsable
# when it advertises disco as it's feature, False means it's never browsable.


def _gen_agent_type_info():
    return {
        # Defaults
        (0, 0): (None, None),
        # XMPP server
        ("server", "im"): (ToplevelAgentBrowser, "jabber"),
        ("services", "jabber"): (ToplevelAgentBrowser, "jabber"),
        ("hierarchy", "branch"): (AgentBrowser, "jabber"),
        # Services
        ("conference", "text"): (MucBrowser, "conference"),
        ("headline", "rss"): (AgentBrowser, "rss"),
        ("headline", "weather"): (False, "weather"),
        ("gateway", "weather"): (False, "weather"),
        ("_jid", "weather"): (False, "weather"),
        ("gateway", "sip"): (False, "sip"),
        ("directory", "user"): (None, "jud"),
        ("pubsub", "generic"): (DiscussionGroupsBrowser, "pubsub"),
        ("pubsub", "service"): (DiscussionGroupsBrowser, "pubsub"),
        ("pubsub", "pep"): (DiscussionGroupsBrowser, "pubsub"),
        ("proxy", "bytestreams"): (None, "bytestreams"),  # Socks5 FT proxy
        ("headline", "newmail"): (ToplevelAgentBrowser, "mail"),
        # Transports
        ("conference", "irc"): (ToplevelAgentBrowser, "irc"),
        ("_jid", "irc"): (False, "irc"),
        ("gateway", "irc"): (False, "irc"),
        ("gateway", "gadu-gadu"): (False, "gadu-gadu"),
        ("_jid", "gadugadu"): (False, "gadu-gadu"),
        ("gateway", "http-ws"): (False, "http-ws"),
        ("gateway", "icq"): (False, "icq"),
        ("_jid", "icq"): (False, "icq"),
        ("gateway", "sms"): (False, "sms"),
        ("_jid", "sms"): (False, "sms"),
        ("gateway", "smtp"): (False, "mail"),
        ("gateway", "mrim"): (False, "mrim"),
        ("_jid", "mrim"): (False, "mrim"),
        ("gateway", "facebook"): (False, "facebook"),
        ("_jid", "facebook"): (False, "facebook"),
        ("gateway", "tv"): (False, "tv"),
        ("gateway", "twitter"): (False, "twitter"),
    }


# Category type to "human-readable" description string
_cat_to_descr: dict[str | tuple[str, str], str] = {
    "other": _("Others"),
    "gateway": _("Transports"),
    "_jid": _("Transports"),
    "conference": _("Group Chat"),
}


class CacheItem(Generic[_T]):
    """
    An object to store cache items and their timeouts
    """

    def __init__(self, value: _T) -> None:
        self.value = value
        self.source: int | None = None

    def __call__(self) -> _T:
        return self.value


class CacheDictionary(Generic[_T]):
    """
    A dictionary that keeps items around for only a specific time.  Lifetime is
    in minutes. Getrefresh specifies whether to refresh when an item is merely
    accessed instead of set as well
    """

    def __init__(self, lifetime: int, getrefresh: bool = True) -> None:
        self.lifetime = lifetime * 1000 * 60
        self.getrefresh = getrefresh
        self.cache: dict[str, CacheItem[_T]] = {}

    def cleanup(self) -> None:
        for key in list(self.cache.keys()):
            item = self.cache[key]
            if item.source:
                GLib.source_remove(item.source)
            del self.cache[key]

    def _expire_timeout(self, key: str) -> bool:
        """
        The timeout has expired, remove the object
        """
        if key in self.cache:
            del self.cache[key]
        return False

    def _refresh_timeout(self, key: str) -> None:
        """
        The object was accessed, refresh the timeout
        """
        item = self.cache[key]
        if item.source:
            GLib.source_remove(item.source)
        if self.lifetime:
            source = GLib.timeout_add_seconds(
                int(self.lifetime / 1000), self._expire_timeout, key
            )
            item.source = source

    def __getitem__(self, key: str) -> _T:
        item = self.cache[key]
        if self.getrefresh:
            self._refresh_timeout(key)
        return item()

    def __setitem__(self, key: str, value: _T) -> None:
        item = CacheItem(value)
        self.cache[key] = item
        self._refresh_timeout(key)

    def __delitem__(self, key: str) -> None:
        item = self.cache[key]
        if item.source:
            GLib.source_remove(item.source)
        del self.cache[key]

    def __contains__(self, key: str) -> bool:
        return key in self.cache


def get_agent_address(jid: str | JID, node: str | None = None) -> str:
    """
    Get an agent's address for displaying in the GUI
    """
    if node:
        return f"{node}@{jid}"
    return str(jid)


class Closure:
    """
    A weak reference to a callback with arguments as an object

    Weak references to methods immediately die, even if the object is still
    alive. Besides a handy way to store a callback, this provides a workaround
    that keeps a reference to the object instead.

    Userargs and removeargs must be tuples.
    """

    def __init__(
        self,
        cb: Any,
        userargs: tuple[Any, ...],
        remove: Callable[..., Any],
        removeargs: tuple[Any, ...],
    ) -> None:

        self.userargs = userargs or ()
        self.remove = remove
        self.removeargs = removeargs or ()
        if isinstance(cb, types.MethodType):
            self.meth_self = weakref.ref(cb.__self__, self._remove)
            self.meth_name = cb.__name__

        elif callable(cb):
            self.meth_self = None
            self.cb: weakref.ReferenceType[Any] = weakref.ref(cb, self._remove)

        else:
            raise TypeError("Object is not callable")

    def _remove(self, ref: Any) -> None:
        self.remove(self, *self.removeargs)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if self.meth_self:
            obj = self.meth_self()
            cb = getattr(obj, self.meth_name)
        else:
            cb = self.cb()

        if cb is None:
            return

        args = args + self.userargs
        return cb(*args, **kwargs)


class ServicesCache:
    """
    Class that caches our query results. Each connection will have it's own
    ServiceCache instance
    """

    def __init__(self, account: str) -> None:
        self.account = account
        self._items: CacheDictionary[list[DiscoItem]] = CacheDictionary(
            0, getrefresh=False
        )
        self._info: CacheDictionary[_InfoCacheT] = CacheDictionary(0, getrefresh=False)
        self._cbs: dict[tuple[str, str], list[Any]] = {}

    def cleanup(self) -> None:
        self._items.cleanup()
        self._info.cleanup()

    def _clean_closure(self, cb: Any, type_: str, addr: str):
        # A closure died, clean up
        cbkey = (type_, addr)
        try:
            self._cbs[cbkey].remove(cb)
        except KeyError:
            return
        except ValueError:
            return
        # Clean an empty list
        if not self._cbs[cbkey]:
            del self._cbs[cbkey]

    def get_icon(
        self, identities: list[DiscoIdentity] | None = None, addr: str = ""
    ) -> str:
        """
        Return the icon for an agent
        """
        if identities is None:
            identities = []
        # Grab the first identity with an icon
        for identity in identities:
            try:
                cat, type_ = identity.category, identity.type
                info = _agent_type_info[(cat, type_)]
            except KeyError:
                continue
            service_name = info[1]
            if service_name:
                break
        else:
            # Loop fell through, default to unknown
            service_name = addr.split(".")[0]

        # Or load it
        icon_name = f"gajim-agent-{service_name}"
        if icon_exists(icon_name):
            return icon_name
        return "gajim-agent-jabber"

    def get_browser(
        self,
        identities: list[DiscoIdentity] | None = None,
        features: list[str] | None = None,
    ) -> type[AgentBrowser] | None:
        """
        Return the browser class for an agent
        """
        if identities is None:
            identities = []
        if features is None:
            features = []
        # First pass, we try to find a ToplevelAgentBrowser
        for identity in identities:
            try:
                cat, type_ = identity.category, identity.type
                info = _agent_type_info[(cat, type_)]
            except KeyError:
                continue
            browser = info[0]
            if browser is ToplevelAgentBrowser:
                return browser

        # Second pass, we haven't found a ToplevelAgentBrowser
        for identity in identities:
            try:
                cat, type_ = identity.category, identity.type
                info = _agent_type_info[(cat, type_)]
            except KeyError:
                continue
            browser = info[0]
            if browser:
                assert not isinstance(browser, bool)
                return browser
        # Namespace.BROWSE is deprecated, but we check for it anyways.
        # Some services list it in features and respond to
        # Namespace.DISCO_ITEMS anyways.
        # Allow browsing for unknown types as well.
        if (
            (not features and not identities)
            or Namespace.DISCO_ITEMS in features
            or Namespace.BROWSE in features
        ):
            return ToplevelAgentBrowser
        return None

    def get_info(
        self,
        jid: str,
        node: str,
        cb: Callable[
            Concatenate[
                str,
                str,
                list[DiscoIdentity] | None,
                list[str] | None,
                list[Any] | None,
                ...,
            ],
            Any,
        ],
        force: bool = False,
        nofetch: bool = False,
        args: tuple[Any, ...] | None = None,
    ) -> None:
        """
        Get info for an agent
        """

        if args is None:
            args = ()

        addr = get_agent_address(jid, node)
        # Check the cache
        if addr in self._info and not force:
            info = self._info[addr]
            cb(jid, node, *info, *args)
            return

        if nofetch:
            return

        # Create a closure object
        cbkey = ("info", addr)
        cb = Closure(cb, userargs=args, remove=self._clean_closure, removeargs=cbkey)
        # Are we already fetching this?
        if cbkey in self._cbs:
            self._cbs[cbkey].append(cb)
        else:
            self._cbs[cbkey] = [cb]
            client = app.get_client(self.account)
            client.get_module("Discovery").disco_info(
                jid, node, callback=self._disco_info_received
            )

    def get_items(
        self,
        jid: str,
        node: str,
        cb: Callable[Concatenate[str, str, list[DiscoItem] | None, ...], None],
        force: bool = False,
        nofetch: bool = False,
        args: tuple[Any, ...] | None = None,
    ) -> None:
        """
        Get a list of items in an agent
        """
        if args is None:
            args = ()

        addr = get_agent_address(jid, node)
        # Check the cache
        if addr in self._items and not force:
            items = self._items[addr]
            cb(jid, node, items, *args)
            return

        if nofetch:
            return

        # Create a closure object
        cbkey = ("items", addr)
        cb = Closure(cb, userargs=args, remove=self._clean_closure, removeargs=cbkey)
        # Are we already fetching this?
        if cbkey in self._cbs:
            self._cbs[cbkey].append(cb)
        else:
            self._cbs[cbkey] = [cb]
            client = app.get_client(self.account)
            client.get_module("Discovery").disco_items(
                jid, node, callback=self._disco_items_received
            )

    def _disco_info_received(self, task: Any) -> None:
        """
        Callback for when we receive an agent's info
        array is (agent, node, identities, features, data)
        """

        try:
            result = cast(DiscoInfo, task.finish())
        except StanzaError as error:
            self._disco_info_error(error)
            return

        identities = result.identities
        if not identities:
            # Ejabberd doesn't send identities when using admin nodes
            identities = [DiscoIdentity(category="server", type="im", name=result.node)]

        self._on_agent_info(
            str(result.jid),
            result.node or "",
            identities,
            result.features,
            result.dataforms,
        )

    def _disco_info_error(self, error: StanzaError) -> None:
        """
        Callback for when a query fails. Even after the browse and agents
        namespaces
        """
        assert error.jid is not None
        addr = get_agent_address(error.jid)

        # Call callbacks
        cbkey = ("info", addr)
        if cbkey in self._cbs:
            for cb in self._cbs[cbkey]:
                cb(str(error.jid), "", None, None, None)
            # clean_closure may have beaten us to it
            if cbkey in self._cbs:
                del self._cbs[cbkey]

    def _on_agent_info(
        self,
        fjid: str,
        node: str,
        identities: list[DiscoIdentity],
        features: list[str],
        dataforms: list[Any],
    ) -> None:
        addr = get_agent_address(fjid, node)

        # Store in cache
        self._info[addr] = (identities, features, dataforms)

        # Call callbacks
        cbkey = ("info", addr)
        if cbkey in self._cbs:
            for cb in self._cbs[cbkey]:
                cb(fjid, node, identities, features, dataforms)
            # clean_closure may have beaten us to it
            if cbkey in self._cbs:
                del self._cbs[cbkey]

    def _disco_items_received(self, task: Any) -> None:
        """
        Callback for when we receive an agent's items
        array is (agent, node, items)
        """

        try:
            result = cast(DiscoItems, task.finish())
        except StanzaError as error:
            self._disco_items_error(error)
            return

        addr = get_agent_address(result.jid, result.node)

        # Store in cache
        self._items[addr] = result.items

        # Call callbacks
        cbkey = ("items", addr)
        if cbkey in self._cbs:
            for cb in self._cbs[cbkey]:
                cb(str(result.jid), result.node, result.items)
            # clean_closure may have beaten us to it
            if cbkey in self._cbs:
                del self._cbs[cbkey]

    def _disco_items_error(self, error: StanzaError) -> None:
        """
        Callback for when a query fails. Even after the browse and agents
        namespaces
        """
        assert error.jid is not None
        addr = get_agent_address(error.jid)

        # Call callbacks
        cbkey = ("items", addr)
        if cbkey in self._cbs:
            for cb in self._cbs[cbkey]:
                cb(str(error.jid), "", None)
            # clean_closure may have beaten us to it
            if cbkey in self._cbs:
                del self._cbs[cbkey]


class ServiceDiscoveryWindow(GajimAppWindow):
    """
    Class that represents the Services Discovery window
    """

    def __init__(
        self,
        account: str,
        jid: str = "",
        node: str = "",
        address_entry: bool = False,
        parent: ServiceDiscoveryWindow | None = None,
    ) -> None:
        GajimAppWindow.__init__(
            self, name="ServiceDiscoveryWindow", default_width=550, default_height=550
        )

        self._account = account
        self.parent = parent
        if not jid:
            jid = app.get_hostname_from_account(account)
            node = ""

        self.jid: str | None = None
        self.browser = None
        self.children: list[ServiceDiscoveryWindow] = []
        self.dying = False
        self.node = ""
        self.reloading = False

        # Check connection
        if not app.account_is_available(account):
            InformationAlertDialog(
                _("Not Connected"),
                _(
                    "You are not connected to the server. "
                    "Without a connection, you can not browse available services"
                ),
            )
            raise RuntimeError("You must be connected to browse services")

        # Get a ServicesCache object.
        cache = app.services_cache.get(account)
        if cache is None:
            self.cache = ServicesCache(account)
            app.services_cache[account] = self.cache
        else:
            self.cache = cast(ServicesCache, cache)

        self._ui = get_builder("service_discovery_window.ui")
        self.set_child(self._ui.service_discovery)

        # self.window = self._ui.service_discovery_window
        self.services_treeview = self._ui.services_treeview
        self.model = None
        # This is more reliable than the cursor-changed signal.
        selection = self.services_treeview.get_selection()
        self._connect_after(
            selection, "changed", self._on_services_treeview_selection_changed
        )
        self._connect(
            self.services_treeview,
            "row-activated",
            self._on_services_treeview_row_activated,
        )
        self._connect(
            self._ui.address_comboboxtext,
            "changed",
            self._on_address_comboboxtext_changed,
        )
        self._connect(self._ui.browse_button, "clicked", self._on_go_button_clicked)

        self._connect(self.window, "close-request", self._on_close_request)

        self.services_scrollwin = self._ui.services_scrollwin
        self.progressbar = self._ui.services_progressbar
        self.banner_header = self._ui.banner_agent_header
        self.banner_subheader = self._ui.banner_agent_subheader
        self.banner_icon = self._ui.banner_agent_icon
        self.style_event_id = 0
        self.action_buttonbox = self._ui.action_buttonbox

        # Address combobox
        self.address_comboboxtext = None
        if address_entry:
            self.address_comboboxtext = self._ui.address_comboboxtext

            self.latest_addresses = app.settings.get("latest_disco_addresses").split()
            if jid in self.latest_addresses:
                self.latest_addresses.remove(jid)
            self.latest_addresses.insert(0, jid)
            if len(self.latest_addresses) > 10:
                self.latest_addresses = self.latest_addresses[0:10]
            for j in self.latest_addresses:
                self.address_comboboxtext.append_text(j)
            child = cast(Gtk.Editable, self.address_comboboxtext.get_child())
            child.set_text(jid)
        else:
            # Don't show it at all if we didn't ask for it
            self._ui.address_box.set_visible(False)

        self._initial_state()
        self.travel(jid, node)

        self.show()

    @property
    def account(self) -> str:
        return self._account

    def _initial_state(self):
        """
        Set some initial state on the window. Separated in a method because it's
        handy to use within browser's cleanup method
        """
        self.progressbar.set_visible(False)
        title_text = _("Service Discovery using account %s") % self.account
        self.window.set_title(title_text)
        self._set_window_banner_text(_("Service Discovery"))
        self.banner_icon.clear()
        self.banner_icon.set_visible(False)  # Just clearing it doesn't work

    def _set_window_banner_text(self, text: str, text_after: str | None = None) -> None:
        self.banner_header.set_text(text)
        if text_after is not None:
            self.banner_subheader.set_visible(True)
            self.banner_subheader.set_text(text_after)
        else:
            self.banner_subheader.set_visible(False)

    def _cleanup(self) -> None:
        self._destroy()
        app.check_finalize(self)

    def _destroy(self, chain: bool = False) -> None:
        """
        Close the browser. This can optionally close its children and propagate
        to the parent. This should happen on actions like register, or join to
        kill off the entire browser chain
        """
        if self.dying:
            return
        self.dying = True

        # self.browser._get_agent_address() would break when no browser.
        if self.browser:
            self.window.set_visible(False)
            self.browser.cleanup()
            self.browser = None
        self.window.close()

        for child in self.children[:]:
            child.parent = None
            if chain:
                child._destroy(chain=chain)
                self.children.remove(child)
        if self.parent:
            if self in self.parent.children:
                self.parent.children.remove(self)
            if chain and not self.parent.children:
                self.parent._destroy(chain=chain)
                self.parent = None
        else:
            self.cache.cleanup()

    def reload(self) -> None:
        if not self.jid:
            return
        self.reloading = True
        self.travel(self.jid, self.node)

    def travel(self, jid: str, node: str) -> None:
        """
        Travel to an agent within the current services window
        """
        if self.browser:
            self.browser.cleanup()
            self.browser = None

        # We need to store these, self.browser is not always available.
        self.jid = jid
        self.node = node
        self.cache.get_info(jid, node, self._travel, force=self.reloading)

    def _travel(
        self,
        jid: str,
        node: str,
        identities: list[DiscoIdentity] | None,
        features: list[str] | None,
        data: list[Any] | None,
    ) -> None:
        """
        Continuation of travel
        """
        if self.dying or jid != self.jid or node != self.node:
            return

        if not identities:
            if not self.address_comboboxtext:
                # We can't travel anywhere else.
                self._destroy()

            if self.parent is not None:
                InformationAlertDialog(
                    _("Service Not Found"),
                    _(
                        "There is no service at the address you entered, or it is "
                        "not responding. Check the address and try again."
                    ),
                    parent=self.parent.window,
                )
                return

        assert features is not None
        assert data is not None

        klass = self.cache.get_browser(identities, features)
        if not klass:
            InformationAlertDialog(
                _("Service Not Browsable"),
                _("This type of service does not contain any items to browse."),
                parent=self.window,
            )
            return

        self.browser = klass(self.account, jid, node)
        self.browser.prepare_window(self)
        self.browser.browse(force=self.reloading)
        self.reloading = False

    def open(self, jid: str, node: str) -> None:
        """
        Open an agent. By default, this happens in a new window
        """
        win = open_window(
            "ServiceDiscoveryWindow",
            account=self.account,
            jid=jid,
            node=node,
            parent=self,
        )
        self.children.append(win)

    def _on_close_request(self, _widget: Gtk.ApplicationWindow) -> None:
        self._destroy()

    def _on_address_comboboxtext_changed(self, combo: Gtk.ComboBoxText) -> None:
        if combo.get_active() != -1:
            # User selected one of the entries so do auto-visit
            entry = combo.get_child()
            assert isinstance(entry, Gtk.Entry)
            jid = entry.get_text()
            try:
                jid = parse_jid(jid)
            except InvalidFormat as s:
                InformationAlertDialog(_("Invalid Server Name"), str(s))
                return
            self.travel(jid, "")

    def _on_go_button_clicked(self, _button: Gtk.Button) -> None:
        entry = self._ui.address_comboboxtext.get_child()
        assert isinstance(entry, Gtk.Entry)
        jid = entry.get_text()
        try:
            jid = parse_jid(jid)
        except InvalidFormat as s:
            InformationAlertDialog(_("Invalid Server Name"), str(s), parent=self.window)
            return
        if jid == self.jid:  # jid has not changed
            return
        if jid in self.latest_addresses:
            self.latest_addresses.remove(jid)
        self.latest_addresses.insert(0, jid)
        if len(self.latest_addresses) > 10:
            self.latest_addresses = self.latest_addresses[0:10]

        assert self.address_comboboxtext is not None
        model = cast(Gtk.ListStore, self.address_comboboxtext.get_model())
        model.clear()

        for j in self.latest_addresses:
            self.address_comboboxtext.append_text(j)
        app.settings.set("latest_disco_addresses", " ".join(self.latest_addresses))
        self.travel(jid, "")

    def _on_services_treeview_row_activated(
        self,
        _treeview: Gtk.TreeView,
        path: Gtk.TreePath,
        col: Gtk.TreeViewColumn | None,
    ) -> None:
        if self.browser:
            self.browser.default_action()

    def _on_services_treeview_selection_changed(
        self, _treeselection: Gtk.TreeSelection
    ) -> None:
        if self.browser:
            self.browser.update_actions()


class AgentBrowser:
    """
    Class that deals with browsing agents and appearance of the browser window.
    This class and subclasses should basically be treated as "part" of the
    ServiceDiscoveryWindow class, but had to be separated because this part is
    dynamic
    """

    def __init__(self, account: str, jid: str, node: str) -> None:
        self.account = account
        self.jid = jid
        self.node = node
        self._total_items = 0
        self.browse_button = None
        # This is for some timeout callbacks
        self.active = False

    def _get_agent_address(self):
        """
        Get the agent's address for displaying in the GUI
        """
        return get_agent_address(self.jid, self.node)

    def _set_initial_title(self):
        """
        Set the initial window title based on agent address
        """
        self.window.window.set_title(
            _("Browsing %(address)s using account %(account)s")
            % {"address": self._get_agent_address(), "account": self.account}
        )
        self.window._set_window_banner_text(  # pyright: ignore
            self._get_agent_address()
        )

    def _create_treemodel(self):
        """
        Create the treemodel for the services treeview. When subclassing, note
        that the first two columns should ALWAYS be of type string and contain
        the JID and node of the item respectively
        """
        # JID, node, name, address
        self.model = Gtk.ListStore(str, str, str, str)
        self.model.set_sort_column_id(3, Gtk.SortType.ASCENDING)
        self.window.services_treeview.set_model(self.model)
        # Name column
        col = Gtk.TreeViewColumn(_("Name"))
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, True)
        col.add_attribute(renderer, "text", 2)
        self.window.services_treeview.insert_column(col, -1)
        col.set_resizable(True)
        # Address column
        col = Gtk.TreeViewColumn(_("XMPP Address"))
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, True)
        col.add_attribute(renderer, "text", 3)
        self.window.services_treeview.insert_column(col, -1)
        col.set_resizable(True)
        self.window.services_treeview.set_headers_visible(True)

    def _clean_treemodel(self):
        self.model.clear()
        for col in self.window.services_treeview.get_columns():
            self.window.services_treeview.remove_column(col)
        self.window.services_treeview.set_headers_visible(False)

    def _add_actions(self):
        """
        Add the action buttons to the buttonbox for actions the browser can
        perform
        """
        self.browse_button = Gtk.Button()
        self.browse_button.connect("clicked", self.on_browse_button_clicked)
        self.window.action_buttonbox.append(self.browse_button)
        self.browse_button.set_label(_("Browse"))
        self.browse_button.set_visible(True)

    def _clean_actions(self):
        """
        Remove the action buttons specific to this browser
        """
        if self.browse_button:
            self.window.action_buttonbox.remove(self.browse_button)
            self.browse_button = None

    def _set_title(
        self,
        _jid: str,
        _node: str,
        identities: list[DiscoIdentity] | None,
        _features: list[str] | None,
        _data: list[Any] | None,
    ) -> None:
        """
        Set the window title based on agent info
        """
        # Set the banner and window title

        if identities is None:
            # Query returned error
            return

        name = ""
        if len(identities) > 1:
            # Check if an identity with server category is present
            for _index, identity in enumerate(identities):
                if identity.category == "server" and identity.name is not None:
                    name = identity.name
                    break
                if identities[0].name is not None:
                    name = identities[0].name

        if name:
            self.window._set_window_banner_text(  # pyright: ignore
                self._get_agent_address(), name
            )

        # Add an icon to the banner.
        icon_name = self.cache.get_icon(identities, addr=self._get_agent_address())
        self.window.banner_icon.set_from_icon_name(icon_name)
        self.window.banner_icon.set_visible(True)

    def _clean_title(self) -> None:
        # Everything done here is done in window._initial_state
        # This is for subclasses.
        pass

    def prepare_window(self, window: ServiceDiscoveryWindow) -> None:
        """
        Prepare the service discovery window. Called when a browser is hooked up
        with a ServiceDiscoveryWindow instance
        """
        self.window = window
        self.cache = window.cache

        self._set_initial_title()
        self._create_treemodel()
        self._add_actions()

        self.update_actions()

        self.active = True
        self.cache.get_info(self.jid, self.node, self._set_title)

    def cleanup(self):
        """
        Cleanup when the window intends to switch browsers
        """
        self.active = False

        self._clean_actions()
        self._clean_treemodel()
        self._clean_title()

        self.window._initial_state()  # pyright: ignore

    def on_browse_button_clicked(self, _button: Gtk.Button | None = None) -> None:
        """
        When we want to browse an agent: open a new services window with a
        browser for the agent type
        """
        model, iter_ = self.window.services_treeview.get_selection().get_selected()
        if not iter_:
            return
        jid = model[iter_][0]
        if jid:
            node = model[iter_][1]
            self.window.open(jid, node)

    def update_actions(self) -> None:
        """
        When we select a row: activate action buttons based on the agent's info
        """
        if self.browse_button:
            self.browse_button.set_sensitive(False)
        model, iter_ = self.window.services_treeview.get_selection().get_selected()
        if not iter_:
            return
        jid = model[iter_][0]
        node = model[iter_][1]
        if jid:
            self.cache.get_info(jid, node, self._update_actions, nofetch=True)

    def _update_actions(
        self,
        _jid: str,
        _node: str,
        identities: list[DiscoIdentity] | None,
        features: list[str] | None,
        _data: list[Any] | None,
    ) -> None:
        """
        Continuation of update_actions
        """
        if not identities or not self.browse_button:
            return

        assert features is not None

        klass = self.cache.get_browser(identities, features)
        if klass:
            self.browse_button.set_sensitive(True)

    def default_action(self) -> None:
        """
        When we double-click a row: perform the default action on the selected
        item
        """
        model, iter_ = self.window.services_treeview.get_selection().get_selected()
        if not iter_:
            return
        jid = model[iter_][0]
        node = model[iter_][1]
        if jid:
            self.cache.get_info(jid, node, self._default_action, nofetch=True)

    def _default_action(
        self,
        _jid: str,
        _node: str,
        identities: list[DiscoIdentity] | None,
        features: list[str] | None,
        _data: list[Any] | None,
    ) -> bool:
        """
        Continuation of default_action
        """

        if identities is None:
            # Query returned error
            return False

        assert features is not None

        if self.cache.get_browser(identities, features):
            # Browse if we can
            self.on_browse_button_clicked()
            return True
        return False

    def browse(self, force: bool = False) -> None:
        """
        Fill the treeview with agents, fetching the info if necessary
        """
        self.model.clear()
        self._total_items = self._progress = 0
        self.window.progressbar.set_visible(True)
        self._pulse_timeout = GLib.timeout_add(250, self._pulse_timeout_cb)
        self.cache.get_items(
            self.jid, self.node, self._agent_items, force=force, args=(force,)
        )

    def _pulse_timeout_cb(self, *args: Any) -> bool:
        """
        Simple callback to keep the progressbar pulsing
        """
        if not self.active:
            return False
        self.window.progressbar.pulse()
        return True

    def _find_item(self, jid: str, node: str) -> Gtk.TreeIter | None:
        """
        Check if an item is already in the treeview. Return an iter to it if so,
        None otherwise
        """
        iter_ = self.model.get_iter_first()
        while iter_:
            cjid = self.model.get_value(iter_, 0)
            cnode = self.model.get_value(iter_, 1)
            if jid == cjid and node == cnode:
                break
            iter_ = self.model.iter_next(iter_)
        if iter_:
            return iter_
        return None

    def add_self_line(self) -> None:
        pass

    def _agent_items(
        self, jid: str, node: str, items: list[DiscoItem] | None, force: bool
    ) -> None:
        """
        Callback for when we receive a list of agent items
        """
        self.model.clear()
        self.add_self_line()
        self._total_items = 0
        GLib.source_remove(self._pulse_timeout)
        self.window.progressbar.set_visible(False)
        # The server returned an error
        if not items:
            if self.window.parent is not None:
                InformationAlertDialog(
                    _("Service Not Browsable"),
                    _("This service does not contain any items to browse."),
                    parent=self.window.parent.window,
                )
            if not self.window.address_comboboxtext:
                # We can't travel anywhere else.
                self.window.window.close()
            return

        # We got a list of items
        def fill_partial_rows(items: list[DiscoItem]) -> Iterator[bool]:
            """Generator to fill the listmodel of a treeview progressively."""
            for item in items:
                if self.window.dying:
                    yield False

                # If such an item is already here: don't add it
                if self._find_item(str(item.jid), item.node or ""):
                    continue

                self._total_items += 1
                self._add_item(node, item, force)
                if (self._total_items % 10) == 0:
                    yield True
            # Stop idle_add()
            yield False

        loader = fill_partial_rows(items)
        GLib.idle_add(next, loader)

    def _agent_info(
        self,
        jid: str,
        node: str,
        identities: list[DiscoIdentity] | None,
        features: list[str] | None,
        data: list[Any] | None,
    ) -> None:
        """
        Callback for when we receive info about an agent's item
        """

        iter_ = self._find_item(jid, node)
        if not iter_:
            # Not in the treeview, stop
            return

        if identities is None:
            # The server returned an error
            self._update_error(iter_, jid, node)

        else:
            assert features is not None
            assert data is not None
            # We got our info
            self._update_info(iter_, jid, node, identities, features, data)

        self.update_actions()

    def _add_item(self, parent_node: str, item: DiscoItem, force: bool) -> None:
        """
        Called when an item should be added to the model. The result of a
        disco#items query
        """
        node = item.node or ""
        name = item.name or ""
        jid = str(item.jid)

        self.model.append((jid, node, name, get_agent_address(jid, node)))
        self.cache.get_info(jid, node, self._agent_info, force=force)

    def _update_info(
        self,
        iter_: Gtk.TreeIter,
        jid: str,
        node: str,
        identities: list[DiscoIdentity],
        features: list[str],
        data: list[Any],
    ) -> None:
        """
        Called when an item should be updated in the model with further info.
        The result of a disco#info query
        """
        name = identities[0].name or ""
        if name:
            self.model[iter_][2] = name

    def _update_error(self, iter_: Gtk.TreeIter, jid: str, node: str) -> None:
        """Called when a disco#info query failed for an item."""


class ToplevelAgentBrowser(AgentBrowser):
    """
    This browser is used at the top level of a jabber server to browse services
    such as transports, conference servers, etc
    """

    def __init__(self, *args: Any):
        AgentBrowser.__init__(self, *args)
        self._progressbar_sourceid = None
        self._progress = 0
        self.register_button = None
        self.join_button = None
        self.execute_button = None
        self.search_button = None
        self._scroll_signal = None

    def add_self_line(self):
        addr = get_agent_address(self.jid, self.node)
        descr = f"<b>{addr}</b>"
        # Guess which kind of service this is
        identities: list[DiscoIdentity] = []
        type_ = app.get_transport_name_from_jid(self.jid, use_config_setting=False)
        if type_:
            identity = DiscoIdentity(category="_jid", type=type_, name=None)
            identities.append(identity)
        # Set the pixmap for the row
        icon_name = self.cache.get_icon(identities, addr=addr)
        self.model.append(None, [self.jid, self.node, icon_name, descr, LABELS[1]])
        # Grab info on the service
        self.cache.get_info(self.jid, self.node, self._agent_info, force=False)

    def _pixbuf_renderer_data_func(
        self,
        col: Gtk.TreeViewColumn,
        cell: Gtk.CellRenderer,
        model: Gtk.TreeModel,
        iter_: Gtk.TreeIter,
        data: Any = None,
    ) -> None:
        """
        Callback for setting the pixbuf renderer's properties
        """
        jid = model.get_value(iter_, 0)
        if jid:
            icon_name = model.get_value(iter_, 2)
            cell.set_property("icon-size", Gtk.IconSize.LARGE)
            cell.set_property("visible", True)
            cell.set_property("icon_name", icon_name)
        else:
            cell.set_property("visible", False)

    def _text_renderer_data_func(
        self,
        col: Gtk.TreeViewColumn,
        cell: Gtk.CellRenderer,
        model: Gtk.TreeModel,
        iter_: Gtk.TreeIter,
        data: Any = None,
    ) -> None:
        """
        Callback for setting the text renderer's properties
        """
        jid = model.get_value(iter_, 0)
        markup = model.get_value(iter_, 3)
        state = model.get_value(iter_, 4)
        cell.set_property("markup", markup)
        if jid:
            if state is not None:
                # fetching or error
                cell.set_property("foreground_set", True)
            else:
                # Normal/success
                cell.set_property("foreground_set", False)
        else:
            cell.set_property("foreground_set", False)

    def _treemodel_sort_func(
        self,
        model: Gtk.TreeModel,
        iter1: Gtk.TreeIter,
        iter2: Gtk.TreeIter,
        data: Any = None,
    ) -> int:
        """
        Sort function for our treemode
        """
        # Compare state
        state1 = model.get_value(iter1, 4)
        state2 = model.get_value(iter2, 4)
        if state1 is not None:
            return 1
        if state2 is not None:
            return -1
        descr1 = model.get_value(iter1, 3)
        descr2 = model.get_value(iter2, 3)
        # Compare strings
        if descr1 > descr2:
            return 1
        if descr1 < descr2:
            return -1
        return 0

    def _create_treemodel(self) -> None:
        # JID, node, icon, description, state
        # state is None on success or has a string
        # from LABELS on error or while fetching
        view = self.window.services_treeview
        self.model = Gtk.TreeStore(str, str, str, str, str)
        self.model.set_sort_func(4, self._treemodel_sort_func)
        self.model.set_sort_column_id(4, Gtk.SortType.ASCENDING)
        view.set_model(self.model)

        col = Gtk.TreeViewColumn()
        # Icon Renderer
        renderer = Gtk.CellRendererPixbuf()
        renderer.set_property("xpad", 6)
        col.pack_start(renderer, False)
        col.set_cell_data_func(renderer, self._pixbuf_renderer_data_func)
        # Text Renderer
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, True)
        col.set_cell_data_func(renderer, self._text_renderer_data_func)
        renderer.set_property("foreground", "dark gray")

        view.set_tooltip_column(4)
        view.insert_column(col, -1)
        col.set_resizable(True)

    def _clean_treemodel(self) -> None:
        # Disconnect signals
        if self._scroll_signal:
            scrollwin = self.window.services_scrollwin
            scrollwin.disconnect(self._scroll_signal)
            self._scroll_signal = None
        AgentBrowser._clean_treemodel(self)

    def _add_actions(self) -> None:
        AgentBrowser._add_actions(self)
        self.execute_button = Gtk.Button(label=_("_Command"), use_underline=True)
        self.execute_button.connect("clicked", self._on_execute_button_clicked)
        image = Gtk.Image.new_from_icon_name("lucide-terminal-symbolic")
        self.execute_button.set_child(image)
        self.window.action_buttonbox.append(self.execute_button)
        self.execute_button.set_visible(True)

        self.register_button = Gtk.Button(label=_("Re_gister"), use_underline=True)
        self.register_button.connect("clicked", self._on_register_button_clicked)
        self.window.action_buttonbox.append(self.register_button)
        self.register_button.set_visible(True)

        self.join_button = Gtk.Button(label=_("Join"), use_underline=True)
        self.join_button.connect("clicked", self._on_join_button_clicked)
        self.window.action_buttonbox.append(self.join_button)
        self.join_button.set_visible(True)

        self.search_button = Gtk.Button(label=_("_Search"), use_underline=True)
        self.search_button.connect("clicked", self.on_search_button_clicked)
        image = Gtk.Image.new_from_icon_name("lucide-search-symbolic")
        self.search_button.set_child(image)
        self.window.action_buttonbox.append(self.search_button)
        self.search_button.set_visible(True)

    def _clean_actions(self) -> None:
        if self.execute_button:
            self.window.action_buttonbox.remove(self.execute_button)
            self.execute_button = None
        if self.register_button:
            self.window.action_buttonbox.remove(self.register_button)
            self.register_button = None
        if self.join_button:
            self.window.action_buttonbox.remove(self.join_button)
            self.join_button = None
        if self.search_button:
            self.window.action_buttonbox.remove(self.search_button)
            self.search_button = None
        AgentBrowser._clean_actions(self)

    def on_search_button_clicked(self, _button: Gtk.Button | None = None) -> None:
        """
        When we want to search something: open search window
        """
        model, iter_ = self.window.services_treeview.get_selection().get_selected()
        if not iter_:
            return
        service = model[iter_][0]
        ComponentSearch(self.account, service, self.window.window)

    def cleanup(self) -> None:
        AgentBrowser.cleanup(self)

    def _on_execute_button_clicked(self, _button: Gtk.Button | None = None) -> None:
        """
        When we want to execute a command: open adhoc command window
        """
        model, iter_ = self.window.services_treeview.get_selection().get_selected()
        if not iter_:
            return
        service = model[iter_][0]
        open_window("AdHocCommands", account=self.account, jids=[service])

    def _on_register_button_clicked(self, _button: Gtk.Button | None = None) -> None:
        """
        When we want to register an agent: request information about registering
        with the agent and close the window
        """
        model, iter_ = self.window.services_treeview.get_selection().get_selected()
        if not iter_:
            return
        jid = JID.from_string(model[iter_][0])
        if jid:
            open_window("ServiceRegistration", account=self.account, address=jid)

    def _on_join_button_clicked(self, _button: Gtk.Button | None = None) -> None:
        """
        When we want to join an IRC room or create a new MUC room: Opens the
        join_groupchat_window
        """
        model, iter_ = self.window.services_treeview.get_selection().get_selected()
        if not iter_:
            return
        service = model[iter_][0]
        app.window.show_add_join_groupchat(self.account, service)

    def update_actions(self) -> None:
        if self.execute_button:
            self.execute_button.set_sensitive(False)
        if self.register_button:
            self.register_button.set_sensitive(False)
        if self.browse_button:
            self.browse_button.set_sensitive(False)
        if self.join_button:
            self.join_button.set_sensitive(False)
        if self.search_button:
            self.search_button.set_sensitive(False)
        model, iter_ = self.window.services_treeview.get_selection().get_selected()
        if not iter_:
            return
        if not model[iter_][0]:
            # We're on a category row
            return
        if model[iter_][4] is not None:
            # We don't have the info (yet)
            # It's either unknown or a transport:
            # Register button should be active
            if self.register_button:
                self.register_button.set_sensitive(True)
            # Guess what kind of service we're dealing with
            if self.browse_button:
                jid = model[iter_][0]
                type_ = app.get_transport_name_from_jid(jid, use_config_setting=False)
                if type_:
                    identity = DiscoIdentity(category="_jid", type=type_)
                    klass = self.cache.get_browser([identity])
                    if klass:
                        self.browse_button.set_sensitive(True)
                else:
                    # We couldn't guess
                    self.browse_button.set_sensitive(True)
        else:
            # Normal case, we have info
            AgentBrowser.update_actions(self)

    def _update_actions(
        self,
        jid: str,
        node: str,
        identities: list[DiscoIdentity] | None,
        features: list[str] | None,
        data: list[Any] | None,
    ):
        AgentBrowser._update_actions(self, jid, node, identities, features, data)

        if identities is None:
            # Discoinfo ran into an error
            return

        assert features is not None

        if self.execute_button and Namespace.COMMANDS in features:
            self.execute_button.set_sensitive(True)
        if self.search_button and Namespace.SEARCH in features:
            self.search_button.set_sensitive(True)
        # Don't authorize to register with a server via disco
        if self.register_button and Namespace.REGISTER in features and jid != self.jid:
            # We can register this agent
            registered_transports: list[JID | str] = []
            client = app.get_client(self.account)
            for contact in client.get_module("Roster").iter_contacts():
                if contact.is_gateway:
                    registered_transports.append(contact.jid)
            registered_transports.append(self.jid)
            if jid in registered_transports:
                self.register_button.set_label(_("_Edit"))
            else:
                self.register_button.set_label(_("Re_gister"))
            self.register_button.set_sensitive(True)

    def _default_action(
        self,
        jid: str,
        node: str,
        identities: list[DiscoIdentity] | None,
        features: list[str] | None,
        data: list[Any] | None,
    ) -> bool:
        if AgentBrowser._default_action(self, jid, node, identities, features, data):
            return True

        assert features is not None
        if Namespace.REGISTER in features:
            # Register if we can't browse
            self._on_register_button_clicked()
            return True
        return False

    def browse(self, force: bool = False) -> None:
        self._progress = 0
        AgentBrowser.browse(self, force=force)

    def _expand_all(self) -> None:
        """
        Expand all items in the treeview
        """
        self.window.services_treeview.expand_all()

    def _update_progressbar(self) -> None:
        """
        Update the progressbar
        """
        # Refresh this every update
        if self._progressbar_sourceid:
            GLib.source_remove(self._progressbar_sourceid)

        fraction = 0
        if self._total_items:
            self.window.progressbar.set_text(
                _("Scanning %(current)d / %(total)d ...")
                % {"current": self._progress, "total": self._total_items + 1}
            )
            fraction = float(self._progress) / float(self._total_items)
            if self._progress >= self._total_items:
                # We show the progressbar for just a bit before hiding it.
                id_ = GLib.timeout_add_seconds(2, self._hide_progressbar_cb)
                self._progressbar_sourceid = id_
            else:
                self.window.progressbar.set_visible(True)
                # Hide the progressbar if we're timing out anyways. (20 secs)
                id_ = GLib.timeout_add_seconds(20, self._hide_progressbar_cb)
                self._progressbar_sourceid = id_
        self.window.progressbar.set_fraction(fraction)

    def _hide_progressbar_cb(self, *args: Any) -> bool:
        """
        Simple callback to hide the progressbar a second after we finish
        """
        if self.active:
            self.window.progressbar.set_visible(False)
        return False

    def _friendly_category(self, category: str, type_: str = "") -> str:
        """
        Get the friendly category name
        """
        cat = None
        if type_:
            # Try type-specific override
            try:
                cat = _cat_to_descr[(category, type_)]
            except KeyError:
                pass
        if not cat:
            try:
                cat = _cat_to_descr[category]
            except KeyError:
                cat = _cat_to_descr["other"]
        return cat

    def _create_category(self, cat: str, type_: str = "") -> Gtk.TreeIter:
        """
        Creates a category row
        """
        cat = self._friendly_category(cat, type_)
        return self.model.append(None, ["", "", None, cat, None])

    def _find_category(self, cat: str, type_: str = "") -> Gtk.TreeIter | None:
        """
        Looks up a category row and returns the iterator to it, or None
        """
        cat = self._friendly_category(cat, type_)
        iter_ = self.model.get_iter_first()
        while iter_:
            if self.model.get_value(iter_, 3) == cat:
                break
            iter_ = self.model.iter_next(iter_)
        if iter_:
            return iter_
        return None

    def _find_item(self, jid: str, node: str) -> Gtk.TreeIter | None:
        iter_ = None
        cat_iter = self.model.get_iter_first()
        while cat_iter and not iter_:
            cjid = self.model.get_value(cat_iter, 0)
            cnode = self.model.get_value(cat_iter, 1)
            if jid == cjid and node == cnode:
                iter_ = cat_iter
                break
            iter_ = self.model.iter_children(cat_iter)
            while iter_:
                cjid = self.model.get_value(iter_, 0)
                cnode = self.model.get_value(iter_, 1)
                if jid == cjid and node == cnode:
                    break
                iter_ = self.model.iter_next(iter_)
            cat_iter = self.model.iter_next(cat_iter)
        if iter_:
            return iter_
        return None

    def _add_item(self, parent_node: str, item: DiscoItem, force: bool) -> None:
        node = item.node or ""
        jid = str(item.jid)

        # Row text
        addr = get_agent_address(jid, node)
        if item.name:
            descr = f"<b>{item.name}</b>\n{addr}"
        else:
            descr = f"<b>{addr}</b>"
        # Guess which kind of service this is
        identities: list[DiscoIdentity] = []
        type_ = app.get_transport_name_from_jid(jid, use_config_setting=False)
        if type_:
            identity = DiscoIdentity(category="_jid", type=type_)
            identities.append(identity)
            cat_args = ("_jid", type_)
        else:
            # Put it in the 'other' category for now
            cat_args = ("other",)

        icon_name = self.cache.get_icon(identities, addr=addr)
        # Put it in the right category
        cat = self._find_category(*cat_args)
        if not cat:
            cat = self._create_category(*cat_args)
        self.model.append(cat, [jid, node, icon_name, descr, LABELS[1]])
        GLib.idle_add(self._expand_all)
        # Grab info on the service
        self.cache.get_info(jid, node, self._agent_info, force=force)
        self._update_progressbar()

    def _update_info(
        self,
        iter_: Gtk.TreeIter,
        jid: str,
        node: str,
        identities: list[DiscoIdentity],
        features: list[str],
        data: list[Any],
    ) -> None:
        addr = get_agent_address(jid, node)
        if not identities:
            descr = "<b>{addr}</b>"
        else:
            name = identities[0].name or ""
            if name:
                descr = f"<b>{name}</b>\n{addr}"
            else:
                descr = f"<b>{addr}</b>"

        # Update progress
        self._progress += 1
        self._update_progressbar()

        # Search for an icon and category we can display
        icon_name = self.cache.get_icon(identities, addr=addr)
        cat, type_ = "", ""
        for identity in identities:
            try:
                cat, type_ = identity.category, identity.type
            except KeyError:
                continue
            break

        # Check if we have to move categories
        old_cat_iter = self.model.iter_parent(iter_)
        if not old_cat_iter or self.model.get_value(old_cat_iter, 3) == cat:
            # Already in the right category, just update
            self.model[iter_][2] = icon_name
            self.model[iter_][3] = descr
            self.model[iter_][4] = None
            return
        # Not in the right category, move it.
        self.model.remove(iter_)

        old_cat = self.model.get_value(old_cat_iter, 3)
        # Check if the old category is empty
        if not self.model.iter_is_valid(old_cat_iter):
            old_cat_iter = self._find_category(old_cat)
        if not self.model.iter_children(old_cat_iter):
            assert old_cat_iter is not None
            self.model.remove(old_cat_iter)

        cat_iter = self._find_category(cat, type_)
        if not cat_iter:
            cat_iter = self._create_category(cat, type_)
        self.model.append(cat_iter, [jid, node, icon_name, descr, None])
        self._expand_all()

    def _update_error(self, iter_: Gtk.TreeIter, jid: str, node: str) -> None:
        self.model[iter_][4] = LABELS[2]
        self._progress += 1
        self._update_progressbar()


class MucBrowser(AgentBrowser):
    def __init__(self, *args: Any, **kwargs: Any):
        AgentBrowser.__init__(self, *args, **kwargs)
        self.join_button = None

    def _create_treemodel(self):
        # JID, node, name, users_int, users_str, description, fetched
        # This is rather long, I'd rather not use a data_func here though.
        # Users is a string, because want to be able to leave it empty.
        self.model = Gtk.ListStore(str, str, str, int, str, str, bool)
        self.model.set_sort_column_id(2, Gtk.SortType.ASCENDING)
        self.window.services_treeview.set_model(self.model)
        # Name column
        col = Gtk.TreeViewColumn(_("Name"))
        col.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        col.set_fixed_width(100)
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, True)
        col.add_attribute(renderer, "text", 2)
        col.set_sort_column_id(2)
        self.window.services_treeview.insert_column(col, -1)
        col.set_resizable(True)
        # Users column
        col = Gtk.TreeViewColumn(_("Users"))
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, True)
        col.add_attribute(renderer, "text", 4)
        col.set_sort_column_id(3)
        self.window.services_treeview.insert_column(col, -1)
        col.set_resizable(True)
        # Description column
        col = Gtk.TreeViewColumn(_("Description"))
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, True)
        col.add_attribute(renderer, "text", 5)
        col.set_sort_column_id(4)
        self.window.services_treeview.insert_column(col, -1)
        col.set_resizable(True)
        # Id column
        col = Gtk.TreeViewColumn(_("Id"))
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, True)
        col.add_attribute(renderer, "text", 0)
        col.set_sort_column_id(0)
        self.window.services_treeview.insert_column(col, -1)
        col.set_resizable(True)
        self.window.services_treeview.set_headers_visible(True)
        self.window.services_treeview.set_headers_clickable(True)
        # Source id for idle callback used to start disco#info queries.
        self._fetch_source = None
        # Query failure counter
        self._broken = 0
        # Connect to scrollwindow scrolling
        self.vadj = self.window.services_scrollwin.get_property("vadjustment")
        self.vadj_cbid = self.vadj.connect("value-changed", self.on_scroll)

    def _clean_treemodel(self) -> None:
        if self.vadj_cbid:
            self.vadj.disconnect(self.vadj_cbid)
            self.vadj_cbid = None
        AgentBrowser._clean_treemodel(self)

    def _add_actions(self) -> None:
        self.join_button = Gtk.Button(label=_("_Join"), use_underline=True)
        self.join_button.connect("clicked", self._on_join_button_clicked)
        self.window.action_buttonbox.append(self.join_button)
        self.join_button.set_visible(True)

    def _clean_actions(self):
        if self.join_button:
            self.window.action_buttonbox.remove(self.join_button)
            self.join_button = None

    def _on_join_button_clicked(self, *args: Any) -> None:
        """
        When we want to join a conference: ask specific information about the
        selected agent and close the window
        """
        model, iter_ = self.window.services_treeview.get_selection().get_selected()
        if not iter_:
            return
        service = model[iter_][0]
        app.window.show_add_join_groupchat(self.account, service)

    def update_actions(self) -> None:
        sens = self.window.services_treeview.get_selection().count_selected_rows()
        if self.join_button:
            self.join_button.set_sensitive(sens > 0)

    def default_action(self) -> None:
        self._on_join_button_clicked()

    def _start_info_query(self) -> bool:
        """
        Idle callback to start checking for visible rows
        """
        self._fetch_source = None
        self._query_visible()
        return False

    def on_scroll(self, *args: Any) -> None:
        """
        Scrollwindow callback to trigger new queries on scrolling
        """
        # This apparently happens when inactive sometimes
        self._query_visible()

    def _query_visible(self) -> None:
        """
        Query the next visible row for info
        """
        if self._fetch_source:
            # We're already fetching
            return
        view = self.window.services_treeview
        if not view.get_realized():
            # Prevent a silly warning, try again in a bit.
            self._fetch_source = GLib.timeout_add(100, self._start_info_query)
            return
        range_ = view.get_visible_range()
        if not range_:
            return
        start, end = range_
        iter_ = self.model.get_iter(start)
        while iter_:
            if not self.model.get_value(iter_, 6):
                jid = self.model.get_value(iter_, 0)
                node = self.model.get_value(iter_, 1)
                self.cache.get_info(jid, node, self._agent_info)
                self._fetch_source = True
                return
            if self.model.get_path(iter_) == end:
                break
            iter_ = self.model.iter_next(iter_)
        self._fetch_source = None

    def _channel_altinfo(
        self,
        jid: str,
        node: str,
        items: list[DiscoItem] | None,
        name: str | None = None,
    ) -> None:
        """
        Callback for the alternate disco#items query. We try to at least get
        the amount of users in the room if the service does not support MUC
        dataforms
        """
        if items is None:
            # The server returned an error
            self._broken += 1
            if self._broken >= 3:
                # Disable queries completely after 3 failures
                if self.vadj_cbid:
                    self.vadj.disconnect(self.vadj_cbid)
                    self.vadj_cbid = None
                self._fetch_source = None
                return
        else:
            iter_ = self._find_item(jid, node)
            if iter_:
                if name:
                    self.model[iter_][2] = name
                self.model[iter_][3] = len(items)  # The number of users
                self.model[iter_][4] = str(len(items))  # The number of users
                self.model[iter_][6] = True
        self._fetch_source = None
        self._query_visible()

    def _add_item(self, parent_node: str | None, item: DiscoItem, force: bool) -> None:
        node = item.node or ""
        name = item.name or ""
        jid = str(item.jid)

        self.model.append((jid, node, name, -1, "", "", False))
        if not self._fetch_source:
            self._fetch_source = GLib.idle_add(self._start_info_query)

    def _update_info(
        self,
        iter_: Gtk.TreeIter,
        jid: str,
        node: str,
        identities: list[DiscoIdentity],
        features: list[str],
        data: list[Any],
    ) -> None:
        name = identities[0].name or ""
        for form in data:
            typefield = form.vars.get("FORM_TYPE")
            if (
                typefield
                and typefield.value == "http://jabber.org/protocol/muc#roominfo"
            ):
                # Fill model row from the form's fields
                users = form.vars.get("muc#roominfo_occupants")
                descr = form.vars.get("muc#roominfo_description")
                if users:
                    self.model[iter_][3] = int(users.value)
                    self.model[iter_][4] = users.value
                if descr and descr.value:
                    self.model[iter_][5] = descr.value
                # Only set these when we find a form with additional info
                # Some servers don't support forms and put extra info in
                # the name attribute, so we preserve it in that case.
                self.model[iter_][2] = name
                self.model[iter_][6] = True
                break
        else:
            # We didn't find a form, switch to alternate query mode
            self.cache.get_items(jid, node, self._channel_altinfo, args=(name,))
            return
        # Continue with the next
        self._fetch_source = None
        self._query_visible()

    def _update_error(self, iter_: Gtk.TreeIter, jid: str, node: str) -> None:
        # Switch to alternate query mode
        self.cache.get_items(jid, node, self._channel_altinfo)


class DiscussionGroupsBrowser(AgentBrowser):
    """
    For browsing pubsub-based discussion groups service
    """

    def __init__(self, account: str, jid: str, node: str) -> None:
        AgentBrowser.__init__(self, account, jid, node)

        # This will become set object when we get subscriptions; None means
        # we don't know yet which groups are subscribed
        self.subscriptions: set[str] | None = None

        # This will become our action widgets when we create them; None means
        # we don't have them yet (needed for check in callback)
        self.subscribe_button = None
        self.unsubscribe_button = None

        client = app.get_client(account)
        client.get_module("PubSub").get_subscriptions(
            jid, callback=self._on_subscriptions_received
        )

    def _create_treemodel(self):
        """
        Create treemodel for the window
        """
        # JID, node, name (with description) - pango markup,
        # don't have info?, subscribed?
        self.model = Gtk.TreeStore(str, str, str, bool, bool)
        # Sort by name
        self.model.set_sort_column_id(2, Gtk.SortType.ASCENDING)
        self.window.services_treeview.set_model(self.model)

        # Name column
        # Pango markup for name and description, description printed with
        # <small/> font
        renderer = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn(_("Name"))
        col.pack_start(renderer, True)
        col.add_attribute(renderer, "markup", 2)
        col.set_resizable(True)
        self.window.services_treeview.insert_column(col, -1)
        self.window.services_treeview.set_headers_visible(True)

        # Subscription state
        renderer = Gtk.CellRendererToggle()
        col = Gtk.TreeViewColumn(_("Subscribed"))
        col.pack_start(renderer, True)
        col.add_attribute(renderer, "inconsistent", 3)
        col.add_attribute(renderer, "active", 4)
        col.set_resizable(False)
        self.window.services_treeview.insert_column(col, -1)

        # Node Column
        renderer = Gtk.CellRendererText()
        col = Gtk.TreeViewColumn(_("Node"))
        col.pack_start(renderer, True)
        col.add_attribute(renderer, "markup", 1)
        col.set_resizable(True)
        self.window.services_treeview.insert_column(col, -1)

    def _in_list_foreach(
        self, model: Gtk.TreeModel, path: Gtk.TreePath, iter_: Gtk.TreeIter, node: str
    ) -> bool:
        if model[path][1] == node:
            self.in_list = True
            return True
        return False

    def _in_list(self, node: str) -> bool:
        self.in_list = False
        self.model.foreach(self._in_list_foreach, node)
        return self.in_list

    def _add_item(self, parent_node: str | None, item: DiscoItem, force: bool) -> None:
        """
        Called when we got basic information about new node from query. Show the
        item
        """
        node = item.node or ""
        name = item.name or ""
        jid = str(item.jid)

        if self.subscriptions is not None:
            dunno = False
            subscribed = node in self.subscriptions
        else:
            dunno = True
            subscribed = False

        name = GLib.markup_escape_text(name)
        name = "<b>%s</b>" % name

        if parent_node:
            parent_iter = self._get_iter(parent_node)
        else:
            parent_iter = None

        if not node or not self._in_list(node):
            self.model.append(parent_iter, [jid, node, name, dunno, subscribed])

    def _get_iter(self, node: str) -> Gtk.TreeIter | None:
        """Look for an iter with the given node"""
        self.found_iter: Gtk.TreeIter | None = None

        def is_node(
            model: Gtk.TreeModel, _path: Gtk.TreePath, iter_: Gtk.TreeIter, node: str
        ) -> bool:
            if model[iter_][1] == node:
                self.found_iter = iter_
                return True
            return False

        self.model.foreach(is_node, node)
        return self.found_iter

    def _add_actions(self) -> None:
        self.subscribe_button = Gtk.Button(label=_("_Subscribe"), use_underline=True)
        self.subscribe_button.set_sensitive(False)
        self.subscribe_button.connect("clicked", self._on_subscribe_button_clicked)
        self.window.action_buttonbox.append(self.subscribe_button)
        self.subscribe_button.set_visible(True)

        self.unsubscribe_button = Gtk.Button(
            label=_("_Unsubscribe"), use_underline=True
        )
        self.unsubscribe_button.set_sensitive(False)
        self.unsubscribe_button.connect("clicked", self._on_unsubscribe_button_clicked)
        self.window.action_buttonbox.append(self.unsubscribe_button)
        self.unsubscribe_button.set_visible(True)

    def _clean_actions(self) -> None:
        assert self.subscribe_button is not None
        assert self.unsubscribe_button is not None

        self.window.action_buttonbox.remove(self.subscribe_button)
        self.subscribe_button = None

        self.window.action_buttonbox.remove(self.unsubscribe_button)
        self.unsubscribe_button = None

    def update_actions(self) -> None:
        """
        Called when user selected a row. Make subscribe/unsubscribe buttons
        sensitive appropriately
        """
        if self.subscribe_button is None or self.unsubscribe_button is None:
            # _add_actions was not called yet
            return

        model, iter_ = self.window.services_treeview.get_selection().get_selected()
        if not iter_ or self.subscriptions is None:
            # No item selected or no subscriptions info, all buttons are
            # insensitive
            self.subscribe_button.set_sensitive(False)
            self.unsubscribe_button.set_sensitive(False)
            return

        subscribed = model.get_value(iter_, 4)  # 4 = subscribed?
        self.subscribe_button.set_sensitive(not subscribed)
        self.unsubscribe_button.set_sensitive(subscribed)

    def _on_subscribe_button_clicked(self, _button: Gtk.Button) -> None:
        """
        Called when 'subscribe' button is pressed. Send subscription request
        """
        model, iter_ = self.window.services_treeview.get_selection().get_selected()
        if iter_ is None:
            return

        node = model.get_value(iter_, 1)  # 1 = groupnode

        client = app.get_client(self.account)
        client.get_module("PubSub").subscribe(
            node, self.jid, callback=self._on_subscribe_response, user_data=node
        )

    def _on_unsubscribe_button_clicked(self, _button: Gtk.Button) -> None:
        """
        Called when 'unsubscribe' button is pressed. Send unsubscription request
        """
        model, iter_ = self.window.services_treeview.get_selection().get_selected()
        if iter_ is None:
            return

        node = model.get_value(iter_, 1)  # 1 = groupnode

        client = app.get_client(self.account)
        client.get_module("PubSub").unsubscribe(
            node, self.jid, callback=self._on_unsubscribe_response, user_data=node
        )

    def _on_subscriptions_received(self, task: Task) -> None:
        try:
            result = cast(list[PubSubSubscription], task.finish())
        except Exception as error:
            log.exception("Failed to retrieve subscriptions: %s", error)
            return

        groups = {sub.node for sub in result}
        if groups:
            log.info("Received subscribed nodes: %s", ", ".join(groups))

        self.subscriptions = groups

        # Try to setup existing items in model
        model = self.window.services_treeview.get_model()
        assert model is not None
        for row in model:
            # 1 = group node
            # 3 = insensitive checkbox for subscribed
            # 4 = subscribed?
            groupnode = row[1]
            row[3] = False
            row[4] = groupnode in groups

        # we now know subscriptions, update button states
        self.update_actions()

    def _on_subscribe_response(self, task: Task) -> None:
        groupnode = cast(str, task.get_user_data())
        try:
            result = cast(PubSubSubscription, task.finish())
        except Exception as error:
            log.exception("Failed to subscribe: %s, %s", groupnode, error)
            return

        if result.subscription != "subscribed":
            log.warning("Unhandled subscription value: %s", result.subscription)
            return

        assert self.subscriptions is not None
        self.subscriptions.add(groupnode)

        model = self.window.services_treeview.get_model()
        assert model is not None
        for row in model:
            if row[1] == groupnode:  # 1 = groupnode
                row[4] = True
                break

        self.update_actions()

    def _on_unsubscribe_response(self, task: Task) -> None:
        groupnode = cast(str, task.get_user_data())
        try:
            task.finish()
        except Exception as error:
            log.exception("Failed to unsubscribe: %s, %s", groupnode, error)
            return

        assert self.subscriptions is not None
        self.subscriptions.remove(groupnode)

        model = self.window.services_treeview.get_model()
        assert model is not None
        for row in model:
            if row[1] == groupnode:  # 1 = groupnode
                row[4] = False
                break

        self.update_actions()


# Fill the global agent type info dictionary
_agent_type_info = _gen_agent_type_info()
