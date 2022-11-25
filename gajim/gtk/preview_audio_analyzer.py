# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from typing import Callable
from typing import cast
from typing import Optional

import logging
import math
from pathlib import Path

try:
    from gi.repository import Gst
except Exception:
    pass

from gajim.common import app
from gajim.common.preview import AudioSampleT

log = logging.getLogger('gajim.gui.preview_audio_analyzer')


class AudioAnalyzer:
    def __init__(self,
                 filepath: Path,
                 duration_callback: Callable[[float], None],
                 samples_callback: Callable[[AudioSampleT], None]
                 ) -> None:

        self._playbin = Gst.ElementFactory.make('playbin', 'bin')

        if self._playbin is None:
            log.debug('Could not create GST playbin for AudioAnalyzer')
            return

        self._duration_callback = duration_callback
        self._duration_updated = False
        self._samples_callback = samples_callback
        self._query = Gst.Query.new_position(Gst.Format.TIME)
        self._duration = Gst.CLOCK_TIME_NONE  # in ns
        self._num_channels = 1
        self._samples: list[tuple[float, float]] = []
        self._level: Optional[Gst.Element] = None
        self._bus_watch_id: int = 0

        self._setup_audio_analyzer(filepath)

    def _setup_audio_analyzer(self, file_path: Path) -> None:
        assert isinstance(self._playbin, Gst.Bin)

        audio_sink = Gst.Bin.new('audiosink')
        audioconvert = Gst.ElementFactory.make('audioconvert', 'audioconvert')
        self._level = Gst.ElementFactory.make('level', 'level')
        fakesink = Gst.ElementFactory.make('fakesink', 'fakesink')

        pipeline_elements = [audio_sink, audioconvert, self._level, fakesink]
        if any(element is None for element in pipeline_elements):
            log.error('Could not set up pipeline for AudioAnalyzer')
            return

        assert audioconvert is not None
        assert self._level is not None
        assert fakesink is not None

        audio_sink.add(audioconvert)
        audio_sink.add(self._level)
        audio_sink.add(fakesink)

        audioconvert.link(self._level)
        self._level.link(fakesink)

        sink_pad = audioconvert.get_static_pad('sink')
        assert sink_pad is not None
        ghost_pad = Gst.GhostPad.new('sink', sink_pad)
        assert ghost_pad is not None
        audio_sink.add_pad(ghost_pad)

        self._playbin.set_property('audio-sink', audio_sink)
        file_uri = file_path.as_uri()
        self._playbin.set_property('uri', file_uri)
        self._playbin.no_more_pads()

        self._level.set_property('message', True)
        fakesink.set_property('sync', False)

        state_return = self._playbin.set_state(Gst.State.PLAYING)
        if state_return == Gst.StateChangeReturn.FAILURE:
            log.warning('Could not set up GST playbin')
            return

        self._level_element = self._playbin.get_by_name('level')
        bus = self._playbin.get_bus()
        if bus is None:
            log.debug('Could not get GST Bus')
            return

        bus.add_signal_watch()
        self._bus_watch_id = bus.connect('message', self._on_bus_message)

    def _on_bus_message(self, _bus: Gst.Bus, message: Gst.Message) -> None:
        assert self._playbin is not None

        if message.type == Gst.MessageType.EOS:
            self._samples_callback(self._samples)
            self._playbin.set_state(Gst.State.NULL)
            return

        if (message.type in (Gst.MessageType.STATE_CHANGED,
                             Gst.MessageType.DURATION_CHANGED)):
            _success, self._duration = self._playbin.query_duration(
                Gst.Format.TIME)
            if not self._duration_updated:
                if _success:
                    assert self._duration is not None
                    self._duration_callback(float(self._duration))
                    self._duration_updated = True
            return

        if message.src is self._level:
            structure = message.get_structure()
            if structure is None or structure.get_name() != 'level':
                return

            if not structure.has_field('rms'):
                return

            # RMS: Root Mean Square = Average Power
            rms_values = cast(list[float], structure.get_value('rms'))
            assert rms_values is not None
            self._num_channels = min(2, len(rms_values))

            # Convert from dB to a linear scale.
            # The sound pressure level L is defined as
            # L = 10 log_10((p/p_0)^2) dB, where p is the RMS value
            # of the sound pressure.
            if self._num_channels == 1:
                lin_val = math.pow(10, rms_values[0] / 10 / 2)
                self._samples.append((lin_val, lin_val))
            else:
                lin_val1 = math.pow(10, rms_values[0] / 10 / 2)
                lin_val2 = math.pow(10, rms_values[1] / 10 / 2)
                self._samples.append((lin_val1, lin_val2))

    def destroy(self) -> None:
        if self._playbin is not None:
            self._playbin.set_state(Gst.State.NULL)
            bus = self._playbin.get_bus()

            if bus is not None:
                bus.remove_signal_watch()
                bus.disconnect(self._bus_watch_id)

        del self._duration_callback, self._samples_callback
        app.check_finalize(self)
