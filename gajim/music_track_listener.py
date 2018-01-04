# -*- coding: utf-8 -*-
## gajim/music_track_listener.py
##
## Copyright (C) 2006 Gustavo Carneiro <gjcarneiro AT gmail.com>
##                    Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2008 Jean-Marie Traissard <jim AT lapin.org>
##                    Jonathan Schleifer <js-gajim AT webkeks.org>
##                    Stephan Erb <steve-e AT h3c.de>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

import logging

from gi.repository import GObject
from gi.repository import Gio, GLib

log = logging.getLogger('gajim.music_track_listener')


def _get_music_players():
    players = [
        'org.mpris.MediaPlayer2.audacious',
        'org.mpris.MediaPlayer2.bmp',
        'org.mpris.MediaPlayer2.GnomeMusic',
        'org.mpris.MediaPlayer2.quodlibet',
        'org.mpris.MediaPlayer2.rhythmbox',
        'org.mpris.MediaPlayer2.vlc',
        'org.mpris.MediaPlayer2.xmms2'
    ]

    return players


class MusicTrackInfo(object):
    __slots__ = ['title', 'album', 'artist', 'duration', 'track_number',
                 'paused']


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
        super(MusicTrackListener, self).__init__()
        self._last_playing_music = None
        self.con = {}

        players = _get_music_players()
        for name in players:
            Gio.bus_watch_name(
                Gio.BusType.SESSION,
                name,
                Gio.BusNameWatcherFlags.NONE,
                self._appeared,
                self._vanished)

    def _appeared(self, connection, name, name_owner, *user_data):
        '''Set up a listener for music player signals'''
        log.info('%s appeared', name)
        self.con[name] = connection.signal_subscribe(
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
            self._last_playing_music = info
            self.emit('music-track-changed', info)

    def _vanished(self, connection, name, *user_data):
        log.info('%s vanished', name)
        if name in self.con:
            connection.signal_unsubscribe(
                self.con[name])
            self.con.pop(name)

            self.emit('music-track-changed', None)

    def _signal_received(self, connection, sender_name, object_path,
                         interface_name, signal_name, parameters, *user_data):
        '''Signal handler for PropertiesChanged event'''

        if 'PlaybackStatus' not in parameters[1]:
            return

        log.info('Signal received: %s - %s', interface_name, parameters)

        info = self.get_playing_track(user_data[0])
        self._last_playing_music = info

        self.emit('music-track-changed', info)

    def _properties_extract(self, properties):
        meta = properties.get('Metadata')
        if meta is None or not meta:
            return None

        info = MusicTrackInfo()
        info.title = meta.get('xesam:title')
        info.album = meta.get('xesam:album')
        artist = meta.get('xesam:artist')
        if artist is not None and len(artist):
            info.artist = artist[0]
        else:
            info.artist = None
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
        except GLib.Error as e:
            if e.domain == 'g-dbus-error-quark':
                log.debug("Could not enable music listener: %s", e.message)
                return None
            else:
                raise
        else:
            info = self._properties_extract(result[0])
            self._last_playing_music = info
            return info


# here we test :)
if __name__ == '__main__':
    def music_track_change_cb(listener, music_track_info):
        if music_track_info is None or music_track_info.paused:
            print('Stop!')
        else:
            print(music_track_info.title)
    listener = MusicTrackListener.get()
    listener.connect('music-track-changed', music_track_change_cb)
    GObject.MainLoop().run()
