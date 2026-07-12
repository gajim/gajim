# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

from typing import TYPE_CHECKING

import math
from pathlib import Path

import gi

try:
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst
except Exception:
    if TYPE_CHECKING:
        from gi.repository import Gst

Gst.init(None)


def extract_audio_properties(
    input_path: Path,
) -> tuple[list[tuple[float, float]], float] | None:
    playbin = Gst.ElementFactory.make("playbin")
    audio_sink = Gst.Bin.new("audiosink")
    audioconvert = Gst.ElementFactory.make("audioconvert")
    level = Gst.ElementFactory.make("level")
    fakesink = Gst.ElementFactory.make("fakesink")

    pipeline_elements = [
        playbin,
        audio_sink,
        audioconvert,
        level,
        fakesink,
    ]

    if any(element is None for element in pipeline_elements):
        raise Exception(
            f"\n{__name__}: Could not set up pipeline for audio preview analyzer"
        )

    assert playbin is not None
    assert audioconvert is not None
    assert level is not None
    assert fakesink is not None

    audio_sink.add(audioconvert)
    audio_sink.add(level)
    audio_sink.add(fakesink)

    audioconvert.link(level)
    level.link(fakesink)

    fakesink.set_property("sync", False)

    sink_pad = audioconvert.get_static_pad("sink")
    assert sink_pad is not None
    ghost_pad = Gst.GhostPad.new("sink", sink_pad)
    assert ghost_pad is not None
    audio_sink.add_pad(ghost_pad)

    # 0x02 = GST_PLAY_FLAG_AUDIO — skip video/text decoding
    playbin.set_property("flags", 0x02)
    playbin.set_property("audio-sink", audio_sink)
    playbin.set_property("uri", input_path.as_uri())

    state_return = playbin.set_state(Gst.State.PLAYING)
    if state_return == Gst.StateChangeReturn.FAILURE:
        playbin.set_state(Gst.State.NULL)
        raise Exception(f"\n{__name__}: Failed to set GST playbin to PLAYING")

    bus = playbin.get_bus()
    if not bus:
        playbin.set_state(Gst.State.NULL)
        raise Exception(f"\n{__name__}: Could not get GST bus")

    samples: list[tuple[float, float]] = []
    duration: float = 0.0

    try:
        while True:
            msg = bus.timed_pop_filtered(
                Gst.CLOCK_TIME_NONE,
                Gst.MessageType.EOS
                | Gst.MessageType.ERROR
                | Gst.MessageType.DURATION_CHANGED
                | Gst.MessageType.ELEMENT,
            )

            if msg is None:
                break

            if msg.type == Gst.MessageType.ERROR:
                err, debug = msg.parse_error()
                raise Exception(f"\n{__name__}: Error: {err}, debug: {debug}")

            if msg.type == Gst.MessageType.EOS:
                _success, duration = playbin.query_duration(Gst.Format.TIME)
                break

            if msg.type == Gst.MessageType.DURATION_CHANGED:
                _success, duration = playbin.query_duration(Gst.Format.TIME)

            if msg.type == Gst.MessageType.ELEMENT:
                structure = msg.get_structure()
                if (
                    structure
                    and structure.get_name() == "level"
                    and structure.has_field("rms")
                ):
                    rms_values = structure.get_value("rms")
                    if rms_values:
                        num_channels = min(2, len(rms_values))
                        if num_channels == 0:
                            samples.append((0.0, 0.0))
                        elif num_channels == 1:
                            lin_val = math.pow(10, rms_values[0] / 10 / 2)
                            samples.append((lin_val, lin_val))
                        else:
                            lin_val1 = math.pow(10, rms_values[0] / 10 / 2)
                            lin_val2 = math.pow(10, rms_values[1] / 10 / 2)
                            samples.append((lin_val1, lin_val2))
    finally:
        playbin.set_state(Gst.State.NULL)

    return samples, duration
