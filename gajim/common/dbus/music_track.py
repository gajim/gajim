# Copyright (C) 2006 Gustavo Carneiro <gjcarneiro AT gmail.com>
#                    Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2008 Jean-Marie Traissard <jim AT lapin.org>
#                    Jonathan Schleifer <js-gajim AT webkeks.org>
#                    Stephan Erb <steve-e AT h3c.de>
#
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

from gi.repository import GObject
from gi.repository import Gio, GLib

log = logging.getLogger('gajim.c.dbus.music_track')

MPRIS_PLAYER_PREFIX = 'org.mpris.MediaPlayer2.'


class MusicTrackInfo:
    __slots__ = ['title', 'album', 'artist', 'duration', 'track_number',
                 'paused']
    def __init__(self):
        self.title = None
        self.album = None
        self.artist = None
        self.duration = None
        self.track_number = None
        self.paused = None


class MusicTrackListener(GObject.GObject):
    __gsignals__ = {
        'music-track-changed': (GObject.SignalFlags.RUN_LAST, None, (object,)),
    }

    _instance = None

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        super().__init__()
        self.players = {}
        self.connection = None

    def start(self):
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
            if error.domain == 'g-dbus-error-quark':
                log.debug("Could not list names: %s", error.message)
                return
            raise

        for name in result[0]:
            if name.startswith(MPRIS_PLAYER_PREFIX):
                self._add_player(name)

    def stop(self):
        for name in list(self.players):
            if name.startswith(MPRIS_PLAYER_PREFIX):
                self._remove_player(name)

    def _signal_name_owner_changed(self,
                                   _connection,
                                   _sender_name,
                                   _object_path,
                                   _interface_name,
                                   _signal_name,
                                   parameters,
                                   *_user_data):
        name, old_owner, new_owner = parameters
        if name.startswith(MPRIS_PLAYER_PREFIX):
            if new_owner and not old_owner:
                self._add_player(name)
            else:
                self._remove_player(name)

    def _add_player(self, name):
        '''Set up a listener for music player signals'''
        log.info('%s appeared', name)

        if name in self.players:
            return

        self.players[name] = self.connection.signal_subscribe(
            name,
            'org.freedesktop.DBus.Properties',
            'PropertiesChanged',
            '/org/mpris/MediaPlayer2',
            None,
            Gio.DBusSignalFlags.NONE,
            self._signal_received,
            name)

        info = self.get_playing_track(name)
        if info is not None:
            self.emit('music-track-changed', info)

    def _remove_player(self, name):
        log.info('%s vanished', name)
        if name in self.players:
            self.connection.signal_unsubscribe(
                self.players[name])
            self.players.pop(name)

            self.emit('music-track-changed', None)

    def _signal_received(self,
                         _connection,
                         _sender_name,
                         _object_path,
                         interface_name,
                         _signal_name,
                         parameters,
                         *user_data):
        '''Signal handler for PropertiesChanged event'''

        if 'PlaybackStatus' not in parameters[1]:
            return

        log.info('Signal received: %s - %s', interface_name, parameters)

        info = self.get_playing_track(user_data[0])

        self.emit('music-track-changed', info)

    @staticmethod
    def _properties_extract(properties):
        meta = properties.get('Metadata')
        if meta is None or not meta:
            return None

        info = MusicTrackInfo()
        info.title = meta.get('xesam:title')
        info.album = meta.get('xesam:album')
        info.artist = meta.get('xesam:artist')
        info.duration = float(meta.get('mpris:length', 0))
        info.track_number = meta.get('xesam:trackNumber', 0)

        status = properties.get('PlaybackStatus')
        info.paused = status is not None and status == 'Paused'

        return info

    def get_playing_track(self, name):
        '''Return a MusicTrackInfo for the currently playing
        song, or None if no song is playing'''
        proxy = Gio.DBusProxy.new_for_bus_sync(
            Gio.BusType.SESSION,
            Gio.DBusProxyFlags.NONE,
            None,
            name,
            '/org/mpris/MediaPlayer2',
            'org.freedesktop.DBus.Properties',
            None)

        try:
            result = proxy.call_sync(
                "GetAll",
                GLib.Variant('(s)', ('org.mpris.MediaPlayer2.Player',)),
                Gio.DBusCallFlags.NONE,
                -1,
                None)
        except GLib.Error as error:
            if error.domain == 'g-dbus-error-quark':
                log.debug("Could not enable music listener: %s", error.message)
                return None
            raise
        else:
            info = self._properties_extract(result[0])
            return info


# here we test :)
if __name__ == '__main__':
    def music_track_change_cb(_listener, music_track_info):
        if music_track_info is None or music_track_info.paused:
            print('Stop!')
        else:
            print(music_track_info.title)
    listener = MusicTrackListener.get()
    listener.connect('music-track-changed', music_track_change_cb)
    listener.start()
    GLib.MainLoop().run()
