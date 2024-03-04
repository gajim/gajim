# Copyright (C) 2009 Thibaut GIRKA <thib AT sitedethib.com>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging

try:
    from gi.repository import Gst
except Exception:
    pass

from gajim.common.i18n import _

log = logging.getLogger('gajim.c.multimedia_helpers')


class DeviceManager:
    def __init__(self) -> None:
        self.devices: dict[str, str] = {}

    def detect(self) -> None:
        self.devices = {}

    def get_devices(self) -> dict[str, str]:
        if not self.devices:
            self.detect()
        return self.devices

    def detect_element(self, name: str, text: str, pipe: str = '%s') -> None:
        if Gst.ElementFactory.find(name):
            element: Gst.Element | None = Gst.ElementFactory.make(
                name, f'{name}presencetest')
            if element is None:
                log.warning('could not create %spresencetest', name)
                return

            if hasattr(element.props, 'device'):
                element.set_state(Gst.State.READY)
                devices = element.get_properties('device')
                if devices:
                    self.devices[text % _('Default device')] = pipe % name
                    for device in devices:
                        if device is None:
                            continue
                        element.set_state(Gst.State.NULL)
                        element.set_property('device', device)
                        element.set_state(Gst.State.READY)
                        device_name = element.get_property('device-name')
                        self.devices[text % device_name] = pipe % \
                            f'{name} device={device}'
                element.set_state(Gst.State.NULL)
            else:
                self.devices[text] = pipe % name
        else:
            log.info('element %s not found', name)


class AudioInputManager(DeviceManager):
    def detect(self) -> None:
        self.devices: dict[str, str] = {}
        # Test src
        self.detect_element('audiotestsrc',
                            _('Audio test'),
                            '%s is-live=true name=gajim_vol')
        # Auto src
        self.detect_element('autoaudiosrc',
                            _('Autodetect'),
                            '%s ! volume name=gajim_vol')
        # Alsa src
        self.detect_element('alsasrc',
                            _('ALSA: %s'),
                            '%s ! volume name=gajim_vol')
        # Pulseaudio src
        self.detect_element('pulsesrc',
                            _('Pulse: %s'),
                            '%s ! volume name=gajim_vol')


class AudioOutputManager(DeviceManager):
    def detect(self) -> None:
        self.devices: dict[str, str] = {}
        # Fake sink
        self.detect_element('fakesink', _('Fake audio output'))
        # Auto sink
        self.detect_element('autoaudiosink', _('Autodetect'))
        # Alsa sink
        self.detect_element('alsasink', _('ALSA: %s'), '%s sync=false')
        # Pulseaudio sink
        self.detect_element('pulsesink', _('Pulse: %s'), '%s sync=true')


class VideoInputManager(DeviceManager):
    def detect(self) -> None:
        self.devices: dict[str, str] = {}
        # Test src
        self.detect_element(
            'videotestsrc',
            _('Video test'),
            '%s is-live=true ! video/x-raw,framerate=10/1 ! videoconvert')
        # Auto src
        self.detect_element('autovideosrc', _('Autodetect'))
        # Best source on Linux, for both camera and screen sharing
        self.detect_element('pipewiresrc', _('Pipewire'))
        # Camera source on Linux
        self.detect_element('v4l2src', _('V4L2: %s'))
        # X11 screen sharing on Linux
        self.detect_element('ximagesrc', _('X11'))
        # Recommended source on Windows
        self.detect_element('ksvideosrc', _('Windows'))
        # Recommended source on OS X
        self.detect_element('avfvideosrc', _('macOS'))
