# -*- coding: utf-8 -*-
##	musictracklistener.py
##
## Copyright (C) 2006 Gustavo Carneiro <gjcarneiro@gmail.com>
## Copyright (C) 2006 Nikos Kouremenos <kourem@gmail.com>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim.  If not, see <http://www.gnu.org/licenses/>.
##
import os
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
		# Banshee sucks because it only supports polling.
		# Thus, we only register this is we are very sure that it's
		# installed.
		if os.name == 'posix' and os.system('which banshee >/dev/null 2>&1') == 0:
			banshee_bus = dbus.SessionBus()
			dubus = banshee_bus.get_object('org.freedesktop.DBus',
				'/org/freedesktop/dbus')
			self.dubus_methods = dbus.Interface(dubus, 'org.freedesktop.DBus')
			self.current_banshee_title = ''
			self.banshee_paused_before = False
			self.banshee_is_here = False
			gobject.timeout_add(10000, self._check_if_banshee_bus)
			if self.dubus_methods.NameHasOwner('org.gnome.Banshee'):
				self._get_banshee_bus()
				self.banshee_is_here = True
			# Otherwise, it opens Banshee!
			self.banshee_props ={}
			gobject.timeout_add(1000, self._banshee_check_track_status)

	def _check_if_banshee_bus(self):
		if self.dubus_methods.NameHasOwner('org.gnome.Banshee'):
			self._get_banshee_bus()
			self.banshee_is_here = True
		else:
			self.banshee_is_here = False
		return True

	def _get_banshee_bus(self):
		bus = dbus.SessionBus()
		banshee = bus.get_object('org.gnome.Banshee', '/org/gnome/Banshee/Player')
		self.banshee_methods = dbus.Interface(banshee, 'org.gnome.Banshee.Core')

	def do_music_track_changed(self, info):
		if info is not None:
			self._last_playing_music = info

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
		info.title = song['title']
		info.album = song['album']
		info.artist = song['artist']
		info.duration = int(song['length'])
		return info

	def _mpris_playing_changed_cb(self, playing):
		if playing == 2:
			self.emit('music-track-changed', None)

	def _mpris_music_track_change_cb(self, arg):
		info = self._mpris_properties_extract(arg)
		self.emit('music-track-changed', info)

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
		info.title = props['title']
		info.album = props['album']
		info.artist = props['artist']
		info.duration = int(props['duration'])
		info.track_number = int(props['track-number'])
		return info

	def _banshee_check_track_status(self):
		if self.dubus_methods.NameHasOwner('org.gnome.Banshee') and \
		not hasattr(self, 'banshee_methods'):
			self._get_banshee_bus()

		if self.dubus_methods.NameHasOwner('org.gnome.Banshee') and self.banshee_is_here:
			try:
				self.banshee_props['title'] = self.banshee_methods.GetPlayingTitle()
				self.banshee_props['album'] = self.banshee_methods.GetPlayingAlbum()
				self.banshee_props['artist'] = self.banshee_methods.\
					GetPlayingArtist()
				self.banshee_props['duration'] = \
				self.banshee_methods.GetPlayingDuration()
				self.banshee_props['paused'] = self.banshee_methods.\
					GetPlayingStatus()
				info = self._banshee_properties_extract(self.banshee_props)
			except dbus.DBusException, err:
				info = None

				for key in self.banshee_props.keys():
					self.banshee_props[key] = ''
				self.banshee_is_here = False

			if self.current_banshee_title != self.banshee_props['title']:
				self.emit('music-track-changed', info)
				self.banshee_paused_before = False
			if self.banshee_props['paused'] == 0 and self.banshee_paused_before ==\
			False:
				self.emit('music-track-changed', info)
				self.banshee_paused_before = True
			else: 
				if self.banshee_paused_before and self.banshee_props['paused'] == 1:
					self.emit('music-track-changed', info)
					self.banshee_paused_before = False
			self.current_banshee_title = self.banshee_props['title']
		return 1

	def _banshee_music_track_change_cb(self, arg):
		info = self._banshee_properties_extract(arg)
		self.emit('music-track-changed', info)

	def _banshee_properties_extract(self, props):
		info = MusicTrackInfo()
		info.title = props['title']
		info.album = props['album']
		info.artist = props['artist']
		info.duration = int(props['duration'])
		info.paused = props['paused']
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
			uri = player.getPlayingUri()
			if not uri:
				return None
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
