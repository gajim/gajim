# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass
from dataclasses import field

from gajim.common.events import ApplicationEvent

from .manifest import PluginManifest


@dataclass
class PluginAdded(ApplicationEvent):
    name: str = field(init=False, default='plugin-added')
    manifest: PluginManifest


@dataclass
class PluginRemoved(ApplicationEvent):
    name: str = field(init=False, default='plugin-removed')
    manifest: PluginManifest
