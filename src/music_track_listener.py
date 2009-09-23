# -*- coding: utf-8 -*-
## src/music_track_listener.py
##
## Copyright (C) 2006 Gustavo Carneiro <gjcarneiro AT gmail.com>
##                    Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006-2008 Yann Leboulanger <asterix AT lagaule.org>
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

import gobject
if __name__ == '__main__':
	# install _() func before importing dbus_support
	from common import i18n

from common import dbus_support
if dbus_support.supported:
	import dbus
	import dbus.glib

class MusicTrackInfo(object):
	__slots__ = ['title', 'album', 'artist', 'duration', 'track_number',
		'paused']

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

		## MPRIS
		bus.add_signal_receiver(self._mpris_music_track_change_cb, 'TrackChange',
			'org.freedesktop.MediaPlayer')
		bus.add_signal_receiver(self._mpris_playing_changed_cb, 'StatusChange',
			'org.freedesktop.MediaPlayer')
		bus.add_signal_receiver(self._player_name_owner_changed,
			'NameOwnerChanged', 'org.freedesktop.DBus',
			arg0='org.freedesktop.MediaPlayer')

		## Muine
		bus.add_signal_receiver(self._muine_music_track_change_cb, 'SongChanged',
			'org.gnome.Muine.Player')
		bus.add_signal_receiver(self._player_name_owner_changed,
			'NameOwnerChanged', 'org.freedesktop.DBus', arg0='org.gnome.Muine')
		bus.add_signal_receiver(self._player_playing_changed_cb, 'StateChanged',
			'org.gnome.Muine.Player')

		## Rhythmbox
		bus.add_signal_receiver(self._player_name_owner_changed,
			'NameOwnerChanged', 'org.freedesktop.DBus', arg0='org.gnome.Rhythmbox')
		bus.add_signal_receiver(self._rhythmbox_playing_changed_cb,
			'playingChanged', 'org.gnome.Rhythmbox.Player')
		bus.add_signal_receiver(self._player_playing_song_property_changed_cb,
			'playingSongPropertyChanged', 'org.gnome.Rhythmbox.Player')

		## Banshee
		bus.add_signal_receiver(self._banshee_state_changed_cb,
			'StateChanged', 'org.bansheeproject.Banshee.PlayerEngine')
		bus.add_signal_receiver(self._player_name_owner_changed,
			'NameOwnerChanged', 'org.freedesktop.DBus',
			arg0='org.bansheeproject.Banshee')

		## Quod Libet
		bus.add_signal_receiver(self._quodlibet_state_change_cb,
			'SongStarted', 'net.sacredchao.QuodLibet')
		bus.add_signal_receiver(self._quodlibet_state_change_cb,
			'Paused', 'net.sacredchao.QuodLibet')
		bus.add_signal_receiver(self._quodlibet_state_change_cb,
			'Unpaused', 'net.sacredchao.QuodLibet')
		bus.add_signal_receiver(self._player_name_owner_changed,
			'NameOwnerChanged', 'org.freedesktop.DBus',
			arg0='net.sacredchao.QuodLibet')

	def _player_name_owner_changed(self, name, old, new):
		if not new:
			self.emit('music-track-changed', None)

	def _player_playing_changed_cb(self, playing):
		if playing:
			self.emit('music-track-changed', self._last_playing_music)
		else:
			self.emit('music-track-changed', None)

	def _player_playing_song_property_changed_cb(self, a, b, c, d):
		if b == 'rb:stream-song-title':
			self.emit('music-track-changed', self._last_playing_music)

	def _mpris_properties_extract(self, song):
		info = MusicTrackInfo()
		info.title = song.get('title', '')
		info.album = song.get('album', '')
		info.artist = song.get('artist', '')
		info.duration = int(song.get('length', 0))
		return info

	def _mpris_playing_changed_cb(self, playing):
		if type(playing) is dbus.Struct:
			if playing[0]:
				self.emit('music-track-changed', None)
			else:
				self.emit('music-track-changed', self._last_playing_music)
		else: # Workaround for e.g. Audacious
			if playing:
				self.emit('music-track-changed', None)
			else:
				self.emit('music-track-changed', self._last_playing_music)

	def _mpris_music_track_change_cb(self, arg):
		self._last_playing_music = self._mpris_properties_extract(arg)
		self.emit('music-track-changed', self._last_playing_music)

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

	def _rhythmbox_playing_changed_cb(self, playing):
		if playing:
			info = self.get_playing_track()
			self.emit('music-track-changed', info)
		else:
			self.emit('music-track-changed', None)

	def _rhythmbox_properties_extract(self, props):
		info = MusicTrackInfo()
		info.title = props.get('title', None)
		info.album = props.get('album', None)
		info.artist = props.get('artist', None)
		info.duration = int(props.get('duration', 0))
		info.track_number = int(props.get('track-number', 0))
		return info

	def _banshee_state_changed_cb(self, state):
		if state == 'playing':
			bus = dbus.SessionBus()
			banshee = bus.get_object('org.bansheeproject.Banshee',
				'/org/bansheeproject/Banshee/PlayerEngine')
			currentTrack = banshee.GetCurrentTrack()
			self._last_playing_music = self._banshee_properties_extract(
				currentTrack)
			self.emit('music-track-changed', self._last_playing_music)
		elif state == 'paused':
			self.emit('music-track-changed', None)

	def _banshee_properties_extract(self, props):
		info = MusicTrackInfo()
		info.title = props.get('name', None)
		info.album = props.get('album', None)
		info.artist = props.get('artist', None)
		info.duration = int(props.get('length', 0))
		return info

	def _quodlibet_state_change_cb(self, state=None):
		info = self.get_playing_track()
		if info:
			self.emit('music-track-changed', info)
		else:
			self.emit('music-track-changed', None)

	def _quodlibet_properties_extract(self, props):
		info = MusicTrackInfo()
		info.title = props.get('title', None)
		info.album = props.get('album', None)
		info.artist = props.get('artist', None)
		info.duration = int(props.get('~#length', 0))
		return info

	def get_playing_track(self):
		'''Return a MusicTrackInfo for the currently playing
		song, or None if no song is playing'''

		bus = dbus.SessionBus()

		## Check Muine playing track
		test = False
		if hasattr(bus, 'name_has_owner'):
			if bus.name_has_owner('org.gnome.Muine'):
				test = True
		elif dbus.dbus_bindings.bus_name_has_owner(bus.get_connection(),
		'org.gnome.Muine'):
			test = True
		if test:
			obj = bus.get_object('org.gnome.Muine', '/org/gnome/Muine/Player')
			player = dbus.Interface(obj, 'org.gnome.Muine.Player')
			if player.GetPlaying():
				song_string = player.GetCurrentSong()
				song = self._muine_properties_extract(song_string)
				self._last_playing_music = song
				return song

		## Check Rhythmbox playing song
		test = False
		if hasattr(bus, 'name_has_owner'):
			if bus.name_has_owner('org.gnome.Rhythmbox'):
				test = True
		elif dbus.dbus_bindings.bus_name_has_owner(bus.get_connection(),
		'org.gnome.Rhythmbox'):
			test = True
		if test:
			rbshellobj = bus.get_object('org.gnome.Rhythmbox',
				'/org/gnome/Rhythmbox/Shell')
			player = dbus.Interface(
				bus.get_object('org.gnome.Rhythmbox',
				'/org/gnome/Rhythmbox/Player'), 'org.gnome.Rhythmbox.Player')
			rbshell = dbus.Interface(rbshellobj, 'org.gnome.Rhythmbox.Shell')
			try:
				uri = player.getPlayingUri()
			except dbus.DBusException:
				uri = None
			if not uri:
				return None
			props = rbshell.getSongProperties(uri)
			info = self._rhythmbox_properties_extract(props)
			self._last_playing_music = info
			return info

		## Check Banshee playing track
		test = False
		if hasattr(bus, 'name_has_owner'):
			if bus.name_has_owner('org.bansheeproject.Banshee'):
				test = True
		elif dbus.dbus_bindings.bus_name_has_owner(bus.get_connection(),
		'org.bansheeproject.Banshee'):
			test = True
		if test:
			banshee = bus.get_object('org.bansheeproject.Banshee',
				'/org/bansheeproject/Banshee/PlayerEngine')
			currentTrack = banshee.GetCurrentTrack()
			if currentTrack:
				song = self._banshee_properties_extract(currentTrack)
				self._last_playing_music = song
				return song

		## Check Quod Libet playing track
		test = False
		if hasattr(bus, 'name_has_owner'):
			if bus.name_has_owner('net.sacredchao.QuodLibet'):
				test = True
		elif dbus.dbus_bindings.bus_name_has_owner(bus.get_connection(),
		'net.sacredchao.QuodLibet'):
			test = True
		if test:
			quodlibet = bus.get_object('net.sacredchao.QuodLibet',
				'/net/sacredchao/QuodLibet')
			if quodlibet.IsPlaying():
				currentTrack = quodlibet.CurrentSong()
				song = self._quodlibet_properties_extract(currentTrack)
				self._last_playing_music = song
				return song

		return None

# here we test :)
if __name__ == '__main__':
	def music_track_change_cb(listener, music_track_info):
		if music_track_info is None:
			print 'Stop!'
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

# vim: se ts=3:
