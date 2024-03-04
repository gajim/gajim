# Copyright (C) 2006 Gustavo Carneiro <gjcarneiro AT gmail.com>
#                    Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2008 Jean-Marie Traissard <jim AT lapin.org>
#                    Jonathan Schleifer <js-gajim AT webkeks.org>
#                    Stephan Erb <steve-e AT h3c.de>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import TypedDict

import logging
import sys

from gi.repository import Gio
from gi.repository import GLib
from nbxmpp.structs import TuneData

from gajim.common import app
from gajim.common.events import MusicTrackChanged

log = logging.getLogger('gajim.c.dbus.music_track')

MPRIS_PLAYER_PREFIX = 'org.mpris.MediaPlayer2.'


class TrackProperties(TypedDict, total=False):
    Metadata: dict[str, str]
    PlaybackStatus: str



class MusicTrackListener:

    _instance: MusicTrackListener | None = None

    @classmethod
    def get(cls) -> MusicTrackListener:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self.players: dict[str, int] = {}
        self.connection: Gio.DBusConnection | None = None
        self._current_tune: TuneData | None = None
        self._running = False

        if sys.platform not in ('win32', 'darwin'):
            self.start()

    def _emit(self, info: TuneData | None) -> None:
        self._current_tune = info
        app.ged.raise_event(MusicTrackChanged(info=info))

    @property
    def current_tune(self) -> TuneData | None:
        return self._current_tune

    def start(self):
        if self._running:
            return

        proxy = Gio.DBusProxy.new_for_bus_sync(
            Gio.BusType.SESSION,
            Gio.DBusProxyFlags.NONE,
            None,
            'org.freedesktop.DBus',
            '/org/freedesktop/DBus',
            'org.freedesktop.DBus',
            None)

        self.connection = proxy.get_connection()
        self.connection.signal_subscribe(
            'org.freedesktop.DBus',
            'org.freedesktop.DBus',
            'NameOwnerChanged',
            '/org/freedesktop/DBus',
            None,
            Gio.DBusSignalFlags.NONE,
            self._signal_name_owner_changed)

        try:
            result = proxy.call_sync(
                'ListNames',
                None,
                Gio.DBusCallFlags.NONE,
                -1,
                None)
        except GLib.Error as error:
            log.debug('Could not list names: %s', error.message)
            return

        for name in result[0]:
            if name.startswith(MPRIS_PLAYER_PREFIX):
                self._add_player(name)

        for name in list(self.players):
            self._get_playing_track(name)

        self._running = True

    def stop(self) -> None:
        for name in list(self.players):
            if name.startswith(MPRIS_PLAYER_PREFIX):
                self._remove_player(name)

    def _signal_name_owner_changed(self,
                                   _connection: Gio.DBusConnection,
                                   _sender_name: str,
                                   _object_path: str,
                                   _interface_name: str,
                                   _signal_name: str,
                                   parameters: tuple[str, str, str],
                                   *_user_data: Any):
        name, old_owner, new_owner = parameters
        if name.startswith(MPRIS_PLAYER_PREFIX):
            if new_owner and not old_owner:
                self._add_player(name)
            else:
                self._remove_player(name)

    def _add_player(self, name: str) -> None:
        '''Set up a listener for music player signals'''
        log.info('%s appeared', name)

        if name in self.players:
            return

        assert self.connection is not None
        self.players[name] = self.connection.signal_subscribe(
            name,
            'org.freedesktop.DBus.Properties',
            'PropertiesChanged',
            '/org/mpris/MediaPlayer2',
            None,
            Gio.DBusSignalFlags.NONE,
            self._signal_received,
            name)

    def _remove_player(self, name: str) -> None:
        log.info('%s vanished', name)
        if name in self.players:
            if self.connection is None:
                self._emit(None)
                return

            self.connection.signal_unsubscribe(
                self.players[name])
            self.players.pop(name)

            self._emit(None)

    def _signal_received(self,
                         _connection: Gio.DBusConnection,
                         _sender_name: str,
                         _object_path: str,
                         interface_name: str,
                         _signal_name: str,
                         parameters: tuple[str, str, str],
                         *user_data: str):
        '''Signal handler for PropertiesChanged event'''

        log.info('Signal received: %s - %s', interface_name, parameters)
        self._get_playing_track(user_data[0])

    @staticmethod
    def _get_music_info(properties: TrackProperties) -> TuneData | None:
        meta = properties.get('Metadata')
        if meta is None or not meta:
            return None

        status = properties.get('PlaybackStatus')
        if status is None or status == 'Paused':
            return None

        title = meta.get('xesam:title')
        album = meta.get('xesam:album')
        # xesam:artist is always a list of strings if not None
        artist = meta.get('xesam:artist')
        if artist is not None:
            artist = ', '.join(artist)
        return TuneData(artist=artist, title=title, source=album)

    def _get_playing_track(self, name: str) -> None:
        '''Return a TuneData for the currently playing
        song, or None if no song is playing'''
        try:
            proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION,
                Gio.DBusProxyFlags.NONE,
                None,
                name,
                '/org/mpris/MediaPlayer2',
                'org.freedesktop.DBus.Properties',
                None)
        except GLib.Error as error:
            log.debug('Could not enable music listener: %s', error.message)
            return

        def proxy_call_finished(proxy: Gio.DBusProxy,
                                res: Gio.AsyncResult
                                ) -> None:
            try:
                result = proxy.call_finish(res)
            except GLib.Error as error:
                log.debug('Could not enable music listener: %s', error.message)
                return

            assert result is not None
            info = self._get_music_info(result[0])
            if info is not None:
                self._emit(info)

        proxy.call('GetAll',
                   GLib.Variant('(s)', ('org.mpris.MediaPlayer2.Player',)),
                   Gio.DBusCallFlags.NONE,
                   -1,
                   None,
                   proxy_call_finished)
