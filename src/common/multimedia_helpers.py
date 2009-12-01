##
## Copyright (C) 2009 Thibaut GIRKA <thib AT sitedethib.com>
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

import gst


class DeviceManager(object):
	def __init__(self):
		self.devices = {}

	def detect(self):
		self.devices = {}

	def get_devices(self):
		if not self.devices:
			self.detect()
		return self.devices

	def detect_element(self, name, text, pipe='%s'):
		try:
			element = gst.element_factory_make(name, '%spresencetest' % name)
			if isinstance(element, gst.interfaces.PropertyProbe):
				element.set_state(gst.STATE_READY)
				devices = element.probe_get_values_name('device')
				if devices:
					self.devices[text % _(' Default device')] = pipe % name
					for device in devices:
						element.set_property('device', device)
						device_name = element.get_property('device-name')
						self.devices[text % device_name] = pipe % '%s device=%s' % (name, device)
				element.set_state(gst.STATE_NULL)
			else:
				self.devices[text] = pipe % name
		except gst.ElementNotFoundError:
			print 'element \'%s\' not found' % name


class AudioInputManager(DeviceManager):
	def detect(self):
		self.devices = {}
		# Test src
		self.detect_element('audiotestsrc', _('Audio test'),
			'%s is-live=true name=gajim_vol')
		# Auto src
		self.detect_element('autoaudiosrc', _('Autodetect'),
			'%s ! volume name=gajim_vol')
		# Alsa src
		self.detect_element('alsasrc', _('ALSA: %s'),
			'%s ! volume name=gajim_vol')


class AudioOutputManager(DeviceManager):
	def detect(self):
		self.devices = {}
		# Fake sink
		self.detect_element('fakesink', _('Fake audio output'))
		# Auto sink
		self.detect_element('autoaudiosink', _('Autodetect'))
		# Alsa sink
		self.detect_element('alsasink', _('ALSA: %s'),
			'%s sync=false')


class VideoInputManager(DeviceManager):
	def detect(self):
		self.devices = {}
		# Test src
		self.detect_element('videotestsrc', _('Video test'),
			'%s is-live=true')
		# Auto src
		self.detect_element('autovideosrc', _('Autodetect'))
		# V4L2 src ; TODO: Figure out why it doesn't work
		self.detect_element('v4l2src', _('V4L2: %s'))
		# Funny things, just to test...
		# self.devices['GOOM'] = 'audiotestsrc ! goom'
		# self.devices['screen'] = 'ximagesrc'


class VideoOutputManager(DeviceManager):
	def detect(self):
		self.devices = {}
		# Fake video output
		self.detect_element('fakesink', _('Fake audio output'))
		# Auto sink
		self.detect_element('autovideosink', _('Autodetect'))
		# xvimage sink
		self.detect_element('xvimagesink', _('X Window System (X11/XShm/Xv): %s'))
		# ximagesink
		self.detect_element('ximagesink', _('X Window System (without Xv)'))


