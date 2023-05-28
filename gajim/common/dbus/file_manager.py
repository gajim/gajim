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


import logging

from gi.repository import Gio
from gi.repository import GLib

from gajim.common.util.classes import Singleton

log = logging.getLogger('gajim.c.dbus.file_manager')


class DBusFileManager(metaclass=Singleton):
    '''
    (Partial) implementation of a client for
    https://freedesktop.org/wiki/Specifications/file-manager-interface/
    '''

    def __init__(self) -> None:
        self._proxy: Gio.DBusProxy | None
        Gio.DBusProxy.new_for_bus(
            Gio.BusType.SESSION,
            Gio.DBusProxyFlags.DO_NOT_AUTO_START_AT_CONSTRUCTION,
            None,
            'org.freedesktop.FileManager1',
            '/org/freedesktop/FileManager1',
            'org.freedesktop.FileManager1',
            None,
            self._on_proxy_ready,
            )

    def _on_proxy_ready(self, _: None, res: Gio.AsyncResult) -> None:
        try:
            self._proxy = Gio.DBusProxy.new_finish(res)
        except GLib.Error as err:
            log.warning('Couldn’t construct dbus proxy: %s', err.message)

    def is_available(self) -> bool:
        return self._proxy is not None

    def show_items_sync(self,
                        uris: list[str],
                        startup_id: str = '',
                        timeout_ms: int = 500,
                        ) -> bool:
        '''
        Opens parent folder(s), selecting/highlighting the specified
        files/folders.  E.g., for ['file:/home/user/Downloads/xyzzy.foo',
        'file:/home/user/Downloads/Quuxes'], opens ~/Downloads with
        xyzzy.foo and Quuxes items selected.

        Returns True on success.

        Fails if called too early after construction; check `is_available()`.
        '''

        if self._proxy is None:
            log.debug('ShowItems: no dbus proxy')
            return False

        try:
            self._proxy.call_sync(
                'ShowItems',
                GLib.Variant('(ass)', (uris, startup_id)),
                Gio.DBusCallFlags.NONE,
                timeout_ms,
                None,
                )
            return True
        except GLib.Error as err:
            log.warning('ShowItems failed: %s', err.message)
            return False


def init() -> None:
    DBusFileManager()
