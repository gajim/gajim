# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gajim.common.util.image import get_pillow_mime_types
from gajim.common.util.image import get_pixbuf_mime_types

# This is an excerpt of Media Types from
# https://www.iana.org/assignments/media-types/media-types.xhtml
# plus some additions
OTHER_MIME_TYPES = {
    # application/
    "application/calendar+json",
    "application/calendar+xml",
    "application/epub+zip",
    "application/json",
    "application/mp4",
    "application/msword",
    "application/ogg",
    "application/pdf",
    "application/pgp-encrypted",
    "application/pgp-signature",
    "application/postscript",
    "application/rtf",
    "application/vcard+json",
    "application/vcard+xml",
    "application/vnd.amazon.mobi8-ebook",
    "application/vnd.google-earth.kml+xml",
    "application/vnd.google-earth.kmz",
    # Start office
    "application/vnd.ms-access",
    "application/vnd.ms-excel",
    "application/vnd.ms-excel.addin.macroEnabled.12",
    "application/vnd.ms-excel.sheet.binary.macroEnabled.12",
    "application/vnd.ms-excel.sheet.macroEnabled.12",
    "application/vnd.ms-excel.template.macroEnabled.12",
    "application/vnd.ms-powerpoint",
    "application/vnd.ms-powerpoint.addin.macroEnabled.12",
    "application/vnd.ms-powerpoint.presentation.macroEnabled.12",
    "application/vnd.ms-powerpoint.slideshow.macroEnabled.12",
    "application/vnd.ms-powerpoint.template.macroEnabled.12",
    "application/vnd.ms-word.document.macroEnabled.12",
    "application/vnd.ms-word.template.macroEnabled.12",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.presentationml.slideshow",
    "application/vnd.openxmlformats-officedocument.presentationml.template",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.template",
    "application/vnd.openxmlformats-officedocument.vmlDrawing",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.template",
    # End office
    "application/vnd.sqlite3",
    "application/zip",
    # font/*
    "font/ttf",
    "font/woff",
    "font/woff2",
    # model/*
    "model/mtl",
    "model/obj",
    "model/stl",
    # text/*
    "text/calendar",
    "text/csv",
    "text/markdown",
    "text/rtf",
    "text/vcard",
}

AUDIO_MIME_TYPES = {
    "audio/aac",
    "audio/ac3",
    "audio/flac",
    "audio/mp3",
    "audio/mp4",
    "audio/mpeg",
    "audio/ogg",
    "audio/opus",
    "audio/vnd.wave",
    "audio/wav",
    "audio/wave",
    "audio/x-aac",
    "audio/x-flac",
    "audio/x-m4a",
    "audio/x-matroska",
    "audio/x-mp3",
    "audio/x-mpeg",
    "audio/x-ogg",
    "audio/x-wav",
}

VIDEO_MIME_TYPES = {
    "video/H264",
    "video/H265",
    "video/mp4",
    "video/mpeg4-generic",
    "video/ogg",
    "video/quicktime",
    "video/vc1",
    "video/VP8",
    "video/webm",
    "video/x-matroska",
    "video/x-msvideo",
}

_PIL_IMAGE_MIME_TYPES = get_pillow_mime_types()
_PIXBUF_IMAGE_MIME_TYPES = get_pixbuf_mime_types()
IMAGE_MIME_TYPES = _PIL_IMAGE_MIME_TYPES | _PIXBUF_IMAGE_MIME_TYPES

ALL_MIME_TYPES = (
    OTHER_MIME_TYPES | IMAGE_MIME_TYPES | AUDIO_MIME_TYPES | VIDEO_MIME_TYPES
)
