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

    assert audioconvert is not None
    assert level is not None
    assert fakesink is not None

    audio_sink.add(audioconvert)
    audio_sink.add(level)
    audio_sink.add(fakesink)

    audioconvert.link(level)
    level.link(fakesink)

    fakesink.set_property("sync", False)

    samples: list[tuple[float, float]] = []
    duration: float = 0.0

    sink_pad = audioconvert.get_static_pad("sink")
    assert sink_pad is not None
    ghost_pad = Gst.GhostPad.new("sink", sink_pad)
    assert ghost_pad is not None
    audio_sink.add_pad(ghost_pad)

    assert playbin is not None
    playbin.set_property("audio-sink", audio_sink)
    playbin.set_property("uri", input_path.as_uri())
    playbin.no_more_pads()

    state_return = playbin.set_state(Gst.State.PLAYING)
    if state_return == Gst.StateChangeReturn.FAILURE:
        raise Exception(f"\n{__name__}: Failed to set GST playbin to PLAYING")

    bus = playbin.get_bus()
    if not bus:
        raise Exception(f"\n{__name__}: Could not get GST bus")

    while True:
        msg = bus.timed_pop_filtered(
            Gst.CLOCK_TIME_NONE,
            Gst.MessageType.EOS
            | Gst.MessageType.ERROR
            | Gst.MessageType.STATE_CHANGED
            | Gst.MessageType.DURATION_CHANGED
            | Gst.MessageType.ELEMENT,
        )

        if msg is None:
            break

        if msg.type == Gst.MessageType.ERROR:
            err, debug = msg.parse_error()
            raise Exception(f"\n{__name__}: Error: {err}, debug: {debug}")

        if msg.type == Gst.MessageType.EOS:
            break

        if msg.type in (
            Gst.MessageType.STATE_CHANGED,
            Gst.MessageType.DURATION_CHANGED,
        ):
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

    playbin.set_state(Gst.State.NULL)

    return samples, duration
