# -*- coding: utf-8 -*-
## src/lastfm_track_listener.py
##
## Copyright (C) 2007 Olivier Mehani <shtrom-gajim AT ssji.net>
##                    Yann Leboulanger <asterix AT lagaule.org>
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
from lastfm import LastFM

class LastFMTrackInfo(object):
	__slots__ = ['title', 'album', 'artist']

	def __eq__(self, other):
		if self.__class__ != other.__class__:
			return False
		return self.title == other.title and self.album == other.album and \
			self.artist == other.artist

	def __ne__(self, other):
		return not self.__eq__(other)

class LastFMTrackListener(gobject.GObject):
	__gsignals__ = {
		'music-track-changed': (gobject.SIGNAL_RUN_LAST, None, (object,)),
	}

	# polling period in milliseconds
	INTERVAL = 60000 #LastFM.MAX_DELAY * 250 # 1/4 of LastFM's delay (in s)

	_instance = None
	@classmethod
	def get(cls, username):
		if cls._instance is None:
			cls._instance = cls(username)
		else:
			cls._instance._lfm.setUsername(username)
		return cls._instance
	
	def __init__(self, username):
		super(LastFMTrackListener, self).__init__()
		self._lfm_user = username
		self._lfm = LastFM(self._lfm_user)
		self._last_playing_music = None
		self._lastfm_music_track_change()
		gobject.timeout_add(self.INTERVAL, self._lastfm_periodic_check)
		
	def _lastfm_properties_extract(self, song_tuple):
		if song_tuple:
			info = LastFMTrackInfo()
			info.title = song_tuple[LastFM.NAME]
			info.album = song_tuple[LastFM.ALBUM]
			info.artist = song_tuple[LastFM.ARTIST]
			return info
		return None

	def _lastfm_periodic_check(self):
		if self._lfm.updateData():
			self._lastfm_music_track_change()
		return True

	def _lastfm_music_track_change(self):
		info = self._lastfm_properties_extract(
			self._lfm.getLastRecentSong())
		self._last_playing_music = info
		self.emit('music-track-changed', info)

	def get_playing_track(self):
		'''Return a LastFMTrackInfo for the currently playing
		song, or None if no song is playing'''
		return self._last_playing_music

# here we test :)
if __name__ == '__main__':
	from sys import argv
	if len(argv) != 2:
		raise Exception("Incorrect number of arguments. Only the Last.fm username is required.")

	def music_track_change_cb(listener, music_track_info):
		if music_track_info is None:
			print "Stop!"
		else:
			print 'Now playing: "%s" by %s' % (
				music_track_info.title, music_track_info.artist)

	listener = LastFMTrackListener.get(argv[1])
	listener.connect('music-track-changed', music_track_change_cb)
	track = listener.get_playing_track()
	if track is None:
		print 'Now not playing anything'
	else:
		print 'Now playing: "%s" by %s' % (track.title, track.artist)
	gobject.MainLoop().run()

# vim: se ts=3:
