##
## Copyright (C) 2009 Thibaut GIRKA <thib AT sitedethib.com>
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

from gi.repository import Gst


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
        if Gst.ElementFactory.find(name):
            element = Gst.ElementFactory.make(name, '%spresencetest' % name)
            if hasattr(element.props, 'device'):
                element.set_state(Gst.State.READY)
                devices = element.get_properties('device')
                if devices:
                    self.devices[text % _(' Default device')] = pipe % name
                    for device in devices:
                        element.set_state(Gst.State.NULL)
                        element.set_property('device', device)
                        element.set_state(Gst.State.READY)
                        device_name = element.get_property('device-name')
                        self.devices[text % device_name] = pipe % \
                            '%s device=%s' % (name, device)
                element.set_state(Gst.State.NULL)
            else:
                self.devices[text] = pipe % name
        else:
            print('element \'%s\' not found' % name)


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
        # Pulseaudio src
        self.detect_element('pulsesrc', _('Pulse: %s'),
            '%s ! volume name=gajim_vol')


class AudioOutputManager(DeviceManager):
    def detect(self):
        self.devices = {}
        # Fake sink
        self.detect_element('fakesink', _('Fake audio output'))
        # Auto sink
        self.detect_element('autoaudiosink', _('Autodetect'))
        # Alsa sink
        self.detect_element('alsasink', _('ALSA: %s'), '%s sync=false')
        # Pulseaudio sink
        self.detect_element('pulsesink', _('Pulse: %s'), '%s sync=true')


class VideoInputManager(DeviceManager):
    def detect(self):
        self.devices = {}
        # Test src
        self.detect_element('videotestsrc', _('Video test'),
            '%s is-live=true ! video/x-raw-yuv,framerate=10/1')
        # Auto src
        self.detect_element('autovideosrc', _('Autodetect'))
        # V4L2 src
        self.detect_element('v4l2src', _('V4L2: %s'))
        # Funny things, just to test...
        # self.devices['GOOM'] = 'audiotestsrc ! goom'
        self.detect_element('ximagesrc', _('Screen'), '%s ! ffmpegcolorspace')


class VideoOutputManager(DeviceManager):
    def detect(self):
        self.devices = {}
        # Fake video output
        self.detect_element('fakesink', _('Fake video output'))
        # Auto sink
        self.detect_element('xvimagesink',
            _('X Window System (X11/XShm/Xv): %s'))
        # ximagesink
        self.detect_element('ximagesink', _('X Window System (without Xv)'))
        self.detect_element('autovideosink', _('Autodetect'))

