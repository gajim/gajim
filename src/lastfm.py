#!/usr/bin/env python
"""
LastFM Python class
Copyright (C) 2007 Olivier Mehani <shtrom@ssji.net>

$Id: lastfm.py 52 2007-11-03 23:19:00Z shtrom $
Python class to handily retrieve song information from a Last.fm account.

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""

__version__ = '$Revision: 64 $'

from urllib import urlopen
from xml.dom import minidom
from time import time

class LastFM:
	# Where to fetch the played song information
	LASTFM_FORMAT_URL = \
		'http://ws.audioscrobbler.com/1.0/user/%s/recenttracks.xml'
	# Delay in seconds after which the last song entry is considered too old tox
	# be displayed.
	MAX_DELAY = 600

	ARTIST = 0
	NAME = 1
	ALBUM = 2
	TIME = 3

	def __init__(self, username, proxies=None):
		"""
		Create a new LastFM object.

		username, the Last.fm username
		proxies, the list of proxies to use to connect to the Last.fm data, as
		expected by urllib.urlopen()
		"""
		self.setUsername(username)
		self._proxies = proxies
		self.scrobbling = False
		self.updateData()

	def __str__(self):
		return 'Last.fm song tracker for user %s.%s' % (self._username,
			self.formatSongTitle(
			' Last song was \"%(n)s\" by \"%(a)s\" in album \"%(b)s\".'))

	def getUsername(self):
		return self._username

	def setUsername(self, username):
		self._username = username
		self.lastSongs = []

	def updateData(self):
		"""
		Fetch the last recent tracks list and update the object accordingly.

		Return True if the last played time has changed, False otherwise.
		"""
		try:
			xmldocument = urlopen(self.LASTFM_FORMAT_URL % self._username,
				self._proxies)
			xmltree = minidom.parse(xmldocument)
		except:
			print 'Error parsing XML from Last.fm...'
			return False

		if xmltree.childNodes.length != 1:
			raise Exception('XML document not formed as expected')

		recenttracks = xmltree.childNodes[0]

		tracklist = recenttracks.getElementsByTagName('track')

		# do not update if nothing more has been scrobbled since last time
		if len(tracklist) > 0 and \
		int(tracklist[0].getElementsByTagName('date')[0].
		getAttribute('uts')) != self.getLastScrobbledTime(): 
			self.lastSongs = []
			for track in tracklist:
				artistNode = track.getElementsByTagName('artist')[0]
				if artistNode.firstChild:
					artist = artistNode.firstChild.data
				else:
					artist = None

				nameNode = track.getElementsByTagName('name')[0]
				if nameNode.firstChild:
					name = nameNode.firstChild.data
				else:
					name = None

				albumNode = track.getElementsByTagName('album')[0]
				if albumNode.firstChild:
					album = albumNode.firstChild.data
				else:
					album = None

					timeNode = track.getElementsByTagName('date')[0]
					self.lastSongs.append((artist, name, album,
						int(timeNode.getAttribute('uts'))))
			self.scrobbling = True
			return True

		# if nothing has been scrobbled for too long, an update to the
		# "currently" playing song should be made
		if self.scrobbling and not self.lastSongIsRecent():
			self.scrobbling = False
			return True

		return False

	def getLastSong(self):
		"""
		Return the last played song as a tuple of (ARTIST, SONG, ALBUM, TIME).
		"""
		if len(self.lastSongs) < 1:
			return None
		return self.lastSongs[0]

	def getLastScrobbledTime(self):
		"""
		Return the Unix time the last song was played.
		"""
		if len(self.lastSongs) < 1:
			return 0
		return self.lastSongs[0][self.TIME]

	def timeSinceLastScrobbled(self, lst=None):
		"""
		Return the time in seconds since the last song has been scrobbled.

		lst, the Unix time at which a song has been scrobbled, defaults to that
		of the last song
		"""
		if lst is None:
			lst = self.getLastScrobbledTime()
		return int(time()) - lst

	def lastSongIsRecent(self, delay=None):
		"""
		Return a boolean stating whether the last song has been played less
		the specified delay earlier.

		delay, the delay to use, defaults to self.MAX_DELAY
		"""
		if delay is None:
			delay = self.MAX_DELAY
		return self.timeSinceLastScrobbled() < delay

	def getLastRecentSong(self, delay=None):
		"""
		Return the last *recently* played song.

		"Recently" means that the song has been played less than delay
		earlier.

		delay, the delay to use, see lastSongIsRecent for the semantics
		"""
		self.updateData()
		if self.lastSongIsRecent(delay):
			return self.getLastSong()
		return None

	def formatSongTitle(self, formatString='%(a)s - %(n)s', songTuple=None):
		"""
		Format a song tuple according to a format string. This makes use of the
		basic Python string formatting operations.

		formatString, the string according to which the song should be formated:
		"%(a)s" is replaced by the artist;
		"%(n)s" is replaced by the name of the song;
		"%(b)s" is replaced by the album;
		defaults to "%s - %t".
		songTuple, the tuple representing the song, defaults to the last song
		"""
		str = ''
		if songTuple is None:
			songTuple = self.getLastRecentSong()

		if songTuple is not None:
			dict = {
				'a': songTuple[0],
				'n': songTuple[1],
				'b': songTuple[2]
				}
			str = formatString % dict

		return str

# Fallback if the script is called directly
if __name__ == '__main__':
	from sys import argv
	from time import sleep
	if len(argv) != 2:
		raise Exception('Incorrect number of arguments. Only the Last.fm username is required.')

	lfm = LastFM(argv[1])
	print lfm
	while 1:
		if lfm.updateData():
			print lfm.formatSongTitle()
		sleep(60) 

# vim: se ts=3:
