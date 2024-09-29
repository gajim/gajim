# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import TYPE_CHECKING

import datetime
import logging
import math
import sys
from collections import deque
from collections.abc import Callable
from pathlib import Path

from gajim.common import app
from gajim.common import configpaths
from gajim.common.i18n import _

try:
    from gi.repository import Gst
except Exception:
    if TYPE_CHECKING:
        from gi.repository import Gst

log = logging.getLogger('gajim.gtk.voice_message_recorder')


GST_ERROR_ON_START = 0
GST_ERROR_ON_RECORDING = 1
GST_ERROR_ON_STOP = 2
GST_ERROR_ON_MERGING = 3

class VoiceMessageRecorder:

    def __init__(self, error_callback: Callable[[int, str], None]) -> None:
        # React to settings change
        app.settings.connect_signal(
            'audio_input_device', self._on_audio_input_device_changed
        )

        # Device from setting
        self._audio_input_device = self._extract_first_word(
            app.settings.get('audio_input_device')
        )

        if (sys.platform == 'win32'
                and self._audio_input_device == 'autoaudiosrc'):
            self._audio_input_device = 'wasapisrc'

        log.debug('Audio input device: %s', self._audio_input_device)

        self._error_callback = error_callback
        self._start_switch = False
        self._audiosrc_drop = False
        self._src_do_switch_sent = False

        # Recording state
        self._new_recording = True
        self._output_file_counter = 0
        self._output_file_valid = False
        self._output_files_invalid: list[int] = []
        self._num_samples = 80
        self._num_samples_buffer = 20
        self._samples: deque[float] = deque(
            [0.0] * self._num_samples, maxlen=self._num_samples
        )
        self._samples_buffer: deque[float] = deque(
            [0.0] * self._num_samples_buffer, maxlen=self._num_samples_buffer
        )
        self._buffer_level = 0
        self._rec_time = {'start': 0, 'total': 0}


        # Gstreamer pipeline
        self._pipeline = Gst.Pipeline.new('pipeline')
        self._audiosrc = Gst.ElementFactory.make(self._audio_input_device)
        self._queue = Gst.ElementFactory.make('queue')
        audioconvert = Gst.ElementFactory.make('audioconvert')
        audioresample = Gst.ElementFactory.make('audioresample')
        audiolevel = Gst.ElementFactory.make('level')
        opusenc = Gst.ElementFactory.make('opusenc')
        mp4mux = Gst.ElementFactory.make('mp4mux')
        self._filesink = Gst.ElementFactory.make('filesink')

        pipeline_elements = [
            self._pipeline,
            self._audiosrc,
            self._queue,
            audioconvert,
            audioresample,
            audiolevel,
            opusenc,
            mp4mux,
            self._filesink
        ]

        if any(element is None for element in pipeline_elements):
            log.debug('Could not set up full audio recording pipeline.')
            self._pipeline_setup_failed = True
            return
        self._pipeline_setup_failed = False
        log.debug('Setting up pipeline!')

        assert self._pipeline is not None
        assert self._audiosrc is not None
        assert self._queue is not None
        assert audioconvert is not None
        assert audioresample is not None
        assert audiolevel is not None
        assert opusenc is not None
        assert mp4mux is not None
        assert self._filesink is not None

        # Voice message storage location
        self._filetype = 'm4a'
        timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        self._file_name = f'voice-message-{timestamp}.{self._filetype}'
        self._file_path: Path = configpaths.get_temp_dir() / self._file_name

        if self._audio_input_device == 'wasapisrc':
            self._audiosrc.set_property('role', 'comms')
        opusenc.set_property('audio-type', 'voice')
        audiolevel.set_property('message', True)
        self._filesink.set_property('location', str(self._file_path))
        self._filesink.set_property('async', False)

        self._pipeline.add(self._audiosrc)
        self._pipeline.add(self._queue)
        self._pipeline.add(audioconvert)
        self._pipeline.add(audioresample)
        self._pipeline.add(audiolevel)
        self._pipeline.add(opusenc)
        self._pipeline.add(mp4mux)
        self._pipeline.add(self._filesink)

        self._audiosrc.link(self._queue)
        self._queue.link(audioconvert)
        audioconvert.link(audioresample)
        audioresample.link(audiolevel)
        audiolevel.link(opusenc)
        opusenc.link(mp4mux)
        mp4mux.link(self._filesink)

        self._clock: Gst.Clock | None = None

        self._bus = self._pipeline.get_bus()
        self._bus.add_signal_watch()
        self._id = self._bus.connect('message', self._on_gst_message)

    @property
    def recording_in_progress(self) -> bool:
        _, pipeline_state, _ = self._pipeline.get_state(timeout=100)
        return pipeline_state != Gst.State.NULL

    @property
    def audio_file_is_valid(self) -> bool:
        return self._output_file_valid

    @property
    def audio_file_abspath(self) -> Path:
        return self._file_path

    @property
    def audio_file_uri(self) -> str:
        uri = self._file_path.as_uri()
        assert uri is not None
        return uri

    @property
    def pipeline_setup_failed(self) -> bool:
        return self._pipeline_setup_failed

    def cleanup(self) -> None:
        self._file_path.unlink()
        self._pipeline.get_bus().disconnect(self._id)

    def start_recording(self) -> None:
        assert self._filesink is not None

        if self._new_recording:
            self._new_recording = False
            timestamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
            self._file_name = f'voice-message-{timestamp}.{self._filetype}'
            self._file_path = configpaths.get_temp_dir() / self._file_name

        self._output_file_counter += 1
        self._filesink.set_property(
            'location', f'{self._file_path}.part{self._output_file_counter}'
        )
        log.debug('Creating new recording file: %s',
                  self._filesink.get_property('location'))
        self._pipeline.set_state(Gst.State.PLAYING)
        message = self._pipeline.get_bus().pop_filtered(Gst.MessageType.ERROR)
        if message is not None:
            self._handle_error_on_start(message)
        self._clock = self._pipeline.get_pipeline_clock()
        self._rec_time['start'] = self._clock.get_time()

    def stop_recording(self) -> None:
        if not self.recording_in_progress:
            return

        assert self._clock is not None

        self._rec_time['total'] += \
            (self._clock.get_time() - self._rec_time['start'])

        self._pipeline.send_event(Gst.Event.new_eos())
        message = self._pipeline.get_bus().timed_pop_filtered(
            Gst.CLOCK_TIME_NONE, Gst.MessageType.EOS | Gst.MessageType.ERROR
        )
        self._pipeline.set_state(Gst.State.NULL)
        assert message is not None
        self._handle_error_on_stop(message)

        self._merge_output_files()

    def stop_and_reset(self) -> None:
        if self.recording_in_progress:
            self.stop_recording()

        self._new_recording = True
        self._output_file_valid = False
        self._output_file_counter = 0
        self._output_files_invalid = []
        self._samples = deque([0] * self._num_samples, maxlen=self._num_samples)
        self._rec_time = {'start': 0, 'total': 0}

    def recording_time(self) -> int:
        delta = 0
        if self.recording_in_progress and self._clock is not None:
            delta = self._clock.get_time() - self._rec_time['start']
        return self._rec_time['total'] + delta

    def request_new_sample(self) -> None:
        if self._buffer_level != 0:
            samples_avg = math.fsum(
                list(self._samples_buffer)) / self._buffer_level
            self._buffer_level = 0
        else:
            samples_avg = 0
        self._samples_buffer = deque(
            [0.0] * self._num_samples_buffer, maxlen=self._num_samples_buffer
        )
        self._samples.appendleft(samples_avg)

    def recording_samples(self) -> list[tuple[float, float]]:
        sample_list = reversed(list(self._samples))
        result: list[tuple[float, float]] = []
        for sample in sample_list:
            result.append((sample, sample))
        return result

    def audio_input_device_exists(self, gst_cmd: str) -> bool:
        device = self._extract_first_word(gst_cmd)
        return Gst.ElementFactory.find(device) is not None

    def _is_error(self, message: Gst.Message | None) -> bool:
        if message is not None and message.type == Gst.MessageType.ERROR:
            self._log_error(message)
            return True
        return False

    def _log_error(self, message: Gst.Message | None) -> None:
        if message is None:
            return

        structure = message.get_structure()
        if structure is not None:
            gerror = structure.get_value('gerror')
            debug = structure.get_value('debug')

            assert gerror is not None
            log.debug('gerror code: %s', gerror.code)
            log.debug('gerror domain: %s', gerror.domain)
            log.debug('debug: %s', debug)

    def _error_info(self,
                    message: Gst.Message | None
                    ) -> tuple[str | None, int | None]:
        if message is None:
            return None, None
        structure = message.get_structure()
        assert structure is not None
        gerror = structure.get_value('gerror')
        assert gerror is not None
        return gerror.domain, gerror.code

    def _handle_error_on_start(self, message: Gst.Message) -> None:
        assert message is not None
        if not self._is_error(message):
            return

        log.debug('Error on starting the recording!')
        self._output_files_invalid.append(self._output_file_counter)

        domain, code = self._error_info(message)
        if domain == 'gst-resource-error-quark':
            if code == 5:
                # GST_RESOURCE_ERROR_OPEN_READ (5)
                # used when resource fails to open for reading.
                self._error_callback(
                    GST_ERROR_ON_START,
                    _('Is a microphone plugged in and accessible?')
                )

    def _handle_error_on_recording(self, message: Gst.Message | None):
        if message is not None and not self._is_error(message):
            return

        log.debug('Error during the recording!')

        domain, code = self._error_info(message)
        if domain == 'gst-resource-error-quark':
            if code == 9:
                # GST_RESOURCE_ERROR_READ (9)
                # used when the resource can't be read from.
                self._error_callback(
                    GST_ERROR_ON_RECORDING,
                    _('Is a microphone plugged in and accessible?')
                )

        if domain == 'gst-stream-error-quark':
            if code == 1:
                # GST_STREAM_ERROR_FAILED (1)
                # a general error which doesn't fit in any other category.
                # Make sure you add a custom message to the error call.
                self._error_callback(
                    GST_ERROR_ON_RECORDING,
                    _('Error in audio data stream.')
                )

    def _handle_error_on_stop(self, message: Gst.Message | None) -> None:
        if message is not None and not self._is_error(message):
            return
        # TODO
        log.debug('Error when stopping the recording!')

    def _handle_error_on_merging(self, message: Gst.Message | None) -> None:
        if message is not None and not self._is_error(message):
            return
        # TODO
        log.debug('Error when merging the recordings!')

    def _custom_message(self, name: str) -> None:
        custom_structure = Gst.Structure.new_empty(name)
        custom_message = Gst.Message.new_application(None, custom_structure)
        assert custom_message is not None
        self._bus.post(custom_message)

    def _on_gst_message(self, _bus: Gst.Bus, message: Gst.Message) -> None:
        structure = message.get_structure()
        if structure is None:
            return
        message_string = structure.to_string()

        if message.type == Gst.MessageType.ELEMENT:
            name = structure.get_name()
            if name == 'level':
                if not structure.has_field('rms'):
                    return

                rms_values = structure.get_value('rms')
                assert rms_values is not None
                if len(rms_values) > 0:
                    rms_value = rms_values[0]
                    self._rms = math.pow(10, rms_value / 10 / 2)
                    self._samples_buffer.appendleft(self._rms)
                    self._buffer_level += 1 % self._num_samples
            log.debug('gst element message: %s', message_string)
        elif message.type == Gst.MessageType.ERROR:
            self._handle_error_on_recording(message)
        elif message.type == Gst.MessageType.EOS:
            pass
        elif message.type == Gst.MessageType.APPLICATION:
            if structure.get_name() == 'start_switch':
                assert self._audiosrc is not None

                self._start_switch = True
                self._src_do_switch_sent = False
                src_pad = self._audiosrc.get_static_pad('src')
                assert src_pad is not None
                src_pad.add_probe(Gst.PadProbeType.BLOCK, self._probe_callback)
            elif structure.get_name() == 'do_switch':
                if self._audiosrc_drop:
                    self._switch_sources()

    def _switch_sources(self) -> None:
        assert self._audiosrc is not None
        assert self._queue is not None

        # Remove old src
        self._audiosrc.set_state(Gst.State.NULL)
        self._audiosrc.unlink(self._queue)
        self._pipeline.remove(self._audiosrc)
        del self._audiosrc

        # Create new audio source
        if (sys.platform == 'win32'
                and self._audio_input_device == 'autoaudiosrc'):
            self._audio_input_device = 'wasapisrc'

        self._audiosrc = Gst.ElementFactory.make(self._audio_input_device)

        assert self._audiosrc is not None
        if self._audio_input_device == 'wasapisrc':
            self._audiosrc.set_property('role', 'comms')
        self._pipeline.add(self._audiosrc)
        self._audiosrc.link(self._queue)
        self._audiosrc.set_state(Gst.State.PLAYING)
        self._start_switch = False

    def _on_audio_input_device_changed(self, *args: Any) -> None:
        old_device = self._audio_input_device
        self._audio_input_device = self._extract_first_word(
            app.settings.get('audio_input_device')
        )
        log.debug(
            'Switching from %s to %s', old_device, self._audio_input_device)
        if self.recording_in_progress:
            self._custom_message('start_switch')
        else:
            self._switch_sources()

    def _probe_callback(
        self, pad: Gst.Pad, info: Gst.PadProbeInfo
    ) -> Gst.PadProbeReturn:
        if self._start_switch:
            if not self._src_do_switch_sent:
                self._audiosrc_drop = True
                self._custom_message('do_switch')
            return Gst.PadProbeReturn.DROP

        self._src_do_switch_sent = False
        self._audiosrc_drop = False
        pad.remove_probe(info.id)
        return Gst.PadProbeReturn.OK

    def _file_merge_required(self) -> bool:
        return self._output_file_counter > 1

    def _merge_opus_m4a_command(self) -> str:
        log.info('Merging opus files started')

        # Use as_posix() on file path to convert "\" to "/" on Windows
        sources = ''
        for i in range(1, self._output_file_counter + 1):
            if i in self._output_files_invalid:
                continue
            source = ' ! '.join([
                f'filesrc location={self._file_path.as_posix()}.part{i}',
                'qtdemux',
                'opusdec',
                'c. '
            ])
            sources += source

        command = ' ! '.join([
            'concat name=c',
            'queue',
            'audioconvert',
            'audioresample',
            'opusenc audio-type=voice',
            'mp4mux ',
            f'filesink location={self._file_path.as_posix()} {sources}'
        ])
        return command

    def _merge_output_files(self) -> None:
        command = self._merge_opus_m4a_command()
        pipeline = Gst.parse_launch(command)

        # Remove the original output file first before writing into it
        if self._file_path.exists():
            self._file_path.unlink()

        pipeline.set_state(Gst.State.PLAYING)

        bus = pipeline.get_bus()
        if bus is None:
            return

        message = bus.timed_pop_filtered(
            Gst.CLOCK_TIME_NONE, Gst.MessageType.EOS | Gst.MessageType.ERROR
        )
        pipeline.set_state(Gst.State.NULL)

        self._handle_error_on_merging(message)
        self._output_file_valid = True
        log.debug('Merging files finished')

    @staticmethod
    def _extract_first_word(gst_cmd: str) -> str:
        '''
        Gajim gives us a string with an audio src plus additional parameters
        such as volume. This method takes only the first word == audio src.
        '''
        if ' ' in gst_cmd:
            idx = gst_cmd.index(' ')
            gst_cmd = gst_cmd[:idx]
        return gst_cmd

