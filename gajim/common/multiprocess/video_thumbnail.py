# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

import typing

from pathlib import Path

import gi

try:
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst
except Exception:
    if typing.TYPE_CHECKING:
        from gi.repository import Gst

Gst.init(None)

def extract_video_thumbnail_and_properties(
        input_: Path,
        output: Path | None,
        preview_size: int
    ) -> tuple[bytes, dict[str, typing.Any]]:
    pipeline = Gst.Pipeline.new()

    uridecodebin = Gst.ElementFactory.make("uridecodebin3")
    videoconvert = Gst.ElementFactory.make("videoconvert")
    videoscale = Gst.ElementFactory.make("videoscale")
    capsfilter = Gst.ElementFactory.make("capsfilter")
    pngenc = Gst.ElementFactory.make("pngenc")
    appsink = Gst.ElementFactory.make("appsink")

    pipeline_elements = [
        uridecodebin,
        videoconvert,
        videoscale,
        capsfilter,
        pngenc,
        appsink
    ]
    if any(element is None for element in pipeline_elements):
        raise Exception(f"\n{__name__}: Some pipeline elements were None")

    assert uridecodebin is not None
    assert videoconvert is not None
    assert videoscale is not None
    assert capsfilter is not None
    assert pngenc is not None
    assert appsink is not None

    appsink.set_property("emit-signals", False)
    appsink.set_property("sync", False)
    appsink.set_property("max-buffers", 1)
    appsink.set_property("drop", True)
    uridecodebin.set_property("uri", input_.as_uri())

    pipeline.add(uridecodebin)
    pipeline.add(videoconvert)
    pipeline.add(videoscale)
    pipeline.add(capsfilter)
    pipeline.add(pngenc)
    pipeline.add(appsink)

    metadata: dict[str, typing.Any] = {'width': 0, 'height': 0}

    def probe_original_size(
            pad: Gst.Pad, _info: Gst.PadProbeInfo) -> Gst.PadProbeReturn:
        caps = pad.get_current_caps()
        if caps is None:
            return Gst.PadProbeReturn.OK

        structure = caps.get_structure(0)
        if structure.has_field("width") and structure.has_field("height"):
            metadata['width'] = structure.get_int("width")[1]
            metadata['height'] = structure.get_int("height")[1]
            return Gst.PadProbeReturn.REMOVE

        return Gst.PadProbeReturn.OK

    sink_pad = videoscale.get_static_pad("sink")
    assert sink_pad is not None
    sink_pad.add_probe(Gst.PadProbeType.EVENT_DOWNSTREAM, probe_original_size)

    def on_pad_added(_bin: Gst.Bin, pad: Gst.Pad) -> None:
        assert pad is not None
        sink_pad = videoconvert.get_static_pad("sink")
        assert sink_pad is not None
        if not sink_pad.is_linked():
            pad.link(sink_pad)

    handler_id = uridecodebin.connect("pad-added", on_pad_added)

    videoconvert.link(videoscale)
    videoscale.link(capsfilter)
    capsfilter.link(pngenc)
    pngenc.link(appsink)

    # https://gitlab.freedesktop.org/gstreamer/gstreamer/-/blob/1.26/subprojects/gst-plugins-base/gst/videoconvertscale/gstvideoconvertscale.h#L63
    lanczos_filter = 3
    videoscale.set_property("method", lanczos_filter)
    caps = Gst.Caps.from_string(
        f"video/x-raw,width={preview_size},"
        "pixel-aspect-ratio=1/1"
    )
    capsfilter.set_property("caps", caps)

    pipeline.set_state(Gst.State.PAUSED)

    def cleanup() -> None:
        pipeline.set_state(Gst.State.NULL)
        uridecodebin.disconnect(handler_id)
        for elem in pipeline_elements:
            if elem is not None:
                pipeline.remove(elem)
                elem.set_state(Gst.State.NULL)
        pipeline.run_dispose()

    state_change, _, _ = pipeline.get_state(Gst.CLOCK_TIME_NONE)
    if state_change != Gst.StateChangeReturn.SUCCESS:
        cleanup()
        raise Exception(f"\n{__name__}: State change was not successful")

    success, duration_ns = pipeline.query_duration(Gst.Format.TIME)
    if not success:
        duration_ns = 0

    # Take timestamp after 2 seconds or earlier, if duration is shorter
    duration_ms = duration_ns / 1e6
    metadata["duration"] = duration_ms
    timestamp_ms = 2000
    if timestamp_ms >= duration_ms:
        timestamp_ms = duration_ms * 0.5

    pipeline.seek_simple(
        Gst.Format.TIME,
        Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE,
        int(timestamp_ms) * Gst.MSECOND
    )

    pipeline.set_state(Gst.State.PLAYING)
    sample = appsink.emit("try-pull-sample", 2 * Gst.SECOND)

    if sample is None:
        cleanup()
        raise Exception(f"\n{__name__}: Failed to retrieve sample")

    buffer = sample.get_buffer()
    success, mapinfo = buffer.map(Gst.MapFlags.READ)

    if not success:
        cleanup()
        raise Exception(f"\n{__name__}: Failed to map buffer")

    bytes_ = bytes(mapinfo.data)
    buffer.unmap(mapinfo)

    cleanup()

    if output is not None:
        output.write_bytes(bytes_)
    return bytes_, metadata
