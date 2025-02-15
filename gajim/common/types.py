# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# Types for typechecking

from typing import Any
from typing import TYPE_CHECKING
from typing import Union

import weakref
from collections.abc import Callable

import nbxmpp
from gi.repository import GdkPixbuf
from nbxmpp.const import PresenceShow
from nbxmpp.protocol import JID
from nbxmpp.structs import BookmarkData

from gajim.common.const import PresenceShowExt

if TYPE_CHECKING:
    from nbxmpp.client import Client as xmppClient  # noqa: F401

    from gajim.common.client import Client
    from gajim.common.modules.contacts import BareContact
    from gajim.common.modules.contacts import CommonContact  # noqa: F401
    from gajim.common.modules.contacts import GroupchatContact
    from gajim.common.modules.contacts import GroupchatParticipant
    from gajim.common.modules.contacts import ResourceContact
    from gajim.common.settings import Settings
    from gajim.plugins.pluginmanager import PluginManager
    from gajim.plugins.repository import PluginRepository

    from gajim.gtk.css_config import CSSConfig

    ContactT = (BareContact |
                ResourceContact |
                GroupchatContact |
                GroupchatParticipant)

PluginManagerT = Union['PluginManager']
PluginRepositoryT = Union['PluginRepository']

ConnectionT = Union['Client']
CSSConfigT = Union['CSSConfig']

# PEP
PEPNotifyCallback = Callable[[nbxmpp.JID, nbxmpp.Node], None]
PEPHandlersDict = dict[str, list[PEPNotifyCallback]]

# Plugins
PluginExtensionPoints = dict[str, tuple[Callable[..., None] | None,
                                        Callable[..., None] | None]]

SettingsT = Union['Settings']

BookmarksDict = dict[JID, BookmarkData]

GdkPixbufType = GdkPixbuf.Pixbuf | GdkPixbuf.PixbufAnimation

AnyCallableT = Callable[..., Any]
ObservableCbDict = dict[str, list[weakref.WeakMethod[AnyCallableT]]]

BareContactT = Union['BareContact']
ChatContactT = Union['BareContact', 'GroupchatContact', 'GroupchatParticipant']
OneOnOneContactT = Union['BareContact', 'GroupchatParticipant']
GroupchatContactT = Union['GroupchatContact']

PresenceShowT = PresenceShowExt | PresenceShow
