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
import dbus
import dbus.glib

class MusicTrackInfo(object):
	__slots__ = ['title', 'album', 'artist', 'duration', 'track_number']


class MusicTrackListener(gobject.GObject):
	__gsignals__ = { 'music-track-changed': (gobject.SIGNAL_RUN_LAST, None,
		(object,)) }

	_instance = None
	@classmethod
	def get(cls):
		if cls._instance is None:
			cls._instance = cls()
		return cls._instance
	
	def __init__(self):
		super(MusicTrackListener, self).__init__()
		bus = dbus.SessionBus()
		bus.add_signal_receiver(self._muine_music_track_change_cb, 'SongChanged',
			'org.gnome.Muine.Player')
		bus.add_signal_receiver(self._rhythmbox_music_track_change_cb,
			'playingUriChanged', 'org.gnome.Rhythmbox.Player')

	def _muine_music_track_change_cb(self, arg):
		d = dict((x.strip() for x in  s1.split(':', 1)) for s1 in arg.split('\n'))
		info = MusicTrackInfo()
		info.title = d['title']
		info.album = d['album']
		info.artist = d['artist']
		info.duration = int(d['duration'])
		info.track_number = int(d['track_number'])
		self.emit('music-track-changed', info)

	def _rhythmbox_music_track_change_cb(self, uri):
		bus = dbus.SessionBus()
		rbshellobj = bus.get_object('org.gnome.Rhythmbox', '/org/gnome/Rhythmbox/Shell')
		rbshell = rbshell = dbus.Interface(rbshellobj, 'org.gnome.Rhythmbox.Shell')
		props = rbshell.getSongProperties(uri)
		info = MusicTrackInfo()
		info.title = props['title']
		info.album = props['album']
		info.artist = props['artist']
		info.duration = int(props['duration'])
		info.track_number = int(props['track-number'])
		self.emit('music-track-changed', info)

# here we test :)
if __name__ == '__main__':
	def music_track_change_cb(listener, music_track_info):
		print music_track_info.title
	MusicTrackListener.get().connect('music-track-changed', music_track_change_cb)
	gobject.MainLoop().run()
