# -*- coding: utf-8 -*-
##	musictracklistener.py
##
## Copyright (C) 2006 Gustavo Carneiro <gjcarneiro@gmail.com>
## Copyright (C) 2006 Nikos Kouremenos <kourem@gmail.com>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 2 only.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
import gobject
import dbus_support
if dbus_support.supported:
	import dbus
	import dbus.glib

class MusicTrackInfo(object):
	__slots__ = ['title', 'album', 'artist', 'duration', 'track_number']


class MusicTrackListener(gobject.GObject):
	__gsignals__ = {
		'music-track-changed': (gobject.SIGNAL_RUN_LAST, None, (object,)),
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
		
		bus = dbus.SessionBus()

		## Muine
		bus.add_signal_receiver(self._muine_music_track_change_cb, 'SongChanged',
			'org.gnome.Muine.Player')
		bus.add_signal_receiver(self._player_name_owner_changed,
			'NameOwnerChanged', 'org.freedesktop.DBus', arg0='org.gnome.Muine')
		bus.add_signal_receiver(self._player_playing_changed_cb, 'StateChanged',
			'org.gnome.Muine.Player')

		## Rhythmbox
		bus.add_signal_receiver(self._rhythmbox_music_track_change_cb,
			'playingUriChanged', 'org.gnome.Rhythmbox.Player')
		bus.add_signal_receiver(self._player_name_owner_changed,
			'NameOwnerChanged', 'org.freedesktop.DBus', arg0='org.gnome.Rhythmbox')
		bus.add_signal_receiver(self._player_playing_changed_cb,
			'playingChanged', 'org.gnome.Rhythmbox.Player')

	def _player_name_owner_changed(self, name, old, new):
		if not new:
			self.emit('music-track-changed', None)

	def _player_playing_changed_cb(self, playing):
		if playing:
			self.emit('music-track-changed', self._last_playing_music)
		else:
			self.emit('music-track-changed', None)

	def _muine_properties_extract(self, song_string):
		d = dict((x.strip() for x in  s1.split(':', 1)) for s1 in \
			song_string.split('\n'))
		info = MusicTrackInfo()
		info.title = d['title']
		info.album = d['album']
		info.artist = d['artist']
		info.duration = int(d['duration'])
		info.track_number = int(d['track_number'])
		return info

	def _muine_music_track_change_cb(self, arg):
		info = self._muine_properties_extract(arg)
		self.emit('music-track-changed', info)

	def _rhythmbox_properties_extract(self, props):
		info = MusicTrackInfo()
		info.title = props['title']
		info.album = props['album']
		info.artist = props['artist']
		info.duration = int(props['duration'])
		info.track_number = int(props['track-number'])
		return info
	
	def _rhythmbox_music_track_change_cb(self, uri):
		bus = dbus.SessionBus()
		rbshellobj = bus.get_object('org.gnome.Rhythmbox',
			'/org/gnome/Rhythmbox/Shell')
		rbshell = dbus.Interface(rbshellobj, 'org.gnome.Rhythmbox.Shell')
		props = rbshell.getSongProperties(uri)
		info = self._rhythmbox_properties_extract(props)
		self.emit('music-track-changed', info)

	def get_playing_track(self):
		'''Return a MusicTrackInfo for the currently playing
		song, or None if no song is playing'''

		bus = dbus.SessionBus()

		## Check Muine playing track
		if dbus.dbus_bindings.bus_name_has_owner(bus.get_connection(),
			'org.gnome.Muine'):
			obj = bus.get_object('org.gnome.Muine', '/org/gnome/Muine/Player')
			player = dbus.Interface(obj, 'org.gnome.Muine.Player')
			if player.GetPlaying():
				song_string = player.GetCurrentSong()
				song = self._muine_properties_extract(song_string)
				self._last_playing_music = song
				return song

		## Check Rhythmbox playing song
		if dbus.dbus_bindings.bus_name_has_owner(bus.get_connection(),
			'org.gnome.Rhythmbox'):
			rbshellobj = bus.get_object('org.gnome.Rhythmbox',
				'/org/gnome/Rhythmbox/Shell')
			player = dbus.Interface(
				bus.get_object('org.gnome.Rhythmbox',
				'/org/gnome/Rhythmbox/Player'), 'org.gnome.Rhythmbox.Player')
			rbshell = dbus.Interface(rbshellobj, 'org.gnome.Rhythmbox.Shell')
			uri = player.getPlayingUri()
			props = rbshell.getSongProperties(uri)
			info = self._rhythmbox_properties_extract(props)
			self._last_playing_music = info
			return info

		return None

# here we test :)
if __name__ == '__main__':
	def music_track_change_cb(listener, music_track_info):
		if music_track_info is None:
			print "Stop!"
		else:
			print music_track_info.title
	listener = MusicTrackListener.get()
	listener.connect('music-track-changed', music_track_change_cb)
	track = listener.get_playing_track()
	if track is None:
		print 'Now not playing anything'
	else:
		print 'Now playing: "%s" by %s' % (track.title, track.artist)
	gobject.MainLoop().run()
