# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import base64
import hashlib
import html as html_module
import json
import mimetypes
import re
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from nbxmpp import JID

from gajim.common import app
from gajim.common import configpaths
from gajim.common.const import VALUE_MISSING
from gajim.common.i18n import _
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.archive.models import Message
from gajim.common.styling import BaseHyperlink
from gajim.common.styling import Block
from gajim.common.styling import PlainBlock
from gajim.common.styling import PreBlock
from gajim.common.styling import process
from gajim.common.styling import QuoteBlock
from gajim.common.styling import Span
from gajim.common.util.preview import get_image_paths

_AVATAR_COLORS = [
    "#e57373",
    "#f06292",
    "#ba68c8",
    "#9575cd",
    "#7986cb",
    "#64b5f6",
    "#4fc3f7",
    "#4dd0e1",
    "#4db6ac",
    "#81c784",
    "#aed581",
    "#ffb74d",
    "#ffa726",
    "#ff7043",
    "#a1887f",
    "#90a4ae",
]

_SPAN_TAGS: dict[str, tuple[str, str]] = {
    "strong": ("<strong>", "</strong>"),
    "emphasis": ("<em>", "</em>"),
    "strike": ("<s>", "</s>"),
    "pre": ("<code>", "</code>"),
}

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link rel="stylesheet" href="{css_href}">
</head>
<body>
<!-- TL_DATA -->
<div id="tl-scrubber" class="tl-scrubber" aria-hidden="true">
  <div id="tl-inner" class="tl-inner">
    <div id="tl-bar" class="tl-bar"></div>
    <div id="tl-handle" class="tl-handle"></div>
    <div id="tl-tooltip" class="tl-tooltip"></div>
<!-- TL_TICKS -->
  </div>
</div>
<div id="lightbox" class="lightbox" hidden
     aria-modal="true" role="dialog" tabindex="-1">
  <div id="lightbox-backdrop" class="lightbox-backdrop"></div>
  <div id="lightbox-content" class="lightbox-content"></div>
</div>
<script src="{js_href}"></script>
<div id="anchor-top" class="scroll-anchor" aria-hidden="true"></div>
<div class="chat-container">
  <main class="message-list">
{messages}
  </main>
</div>
<div class="scroll-nav" aria-hidden="true">
  <button id="btn-top" type="button" title="Jump to top" hidden>&#8593;</button>
  <button id="btn-bottom" type="button" title="Jump to bottom" hidden>&#8595;</button>
</div>
<div id="anchor-bottom" class="scroll-anchor" aria-hidden="true"></div>
</body>
</html>
"""


def _avatar_color(name: str) -> str:
    idx = sum(ord(c) for c in name) % len(_AVATAR_COLORS)
    return _AVATAR_COLORS[idx]


def _svg_initials_data_uri(name: str, size: int = 40) -> str:
    """SVG data URI avatar — used only for overview sidebar <img> elements."""
    color = _avatar_color(name)
    initial = html_module.escape(name[0].upper()) if name else "?"
    font_size = size // 2
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}"'
        f' viewBox="0 0 {size} {size}">'
        f'<circle cx="{size // 2}" cy="{size // 2}" r="{size // 2}" fill="{color}"/>'
        f'<text x="50%" y="50%" dominant-baseline="central" text-anchor="middle"'
        f' fill="white" font-size="{font_size}"'
        f' font-family="sans-serif">{initial}</text>'
        f"</svg>"
    )
    b64 = base64.b64encode(svg.encode()).decode()
    return f"data:image/svg+xml;base64,{b64}"


def _initials_avatar_div(name: str, *, ref: bool = False) -> str:
    """CSS-based initials avatar — no base64, reuses browser layout."""
    color = _avatar_color(name)
    initial = html_module.escape(name[0].upper()) if name else "?"
    if ref:
        return (
            f'<div class="ref-avatar ref-avatar-initials"'
            f' style="background:{color}">{initial}</div>'
        )
    return (
        f'<div class="avatar avatar-initials"'
        f' style="background:{color}">{initial}</div>'
    )


def _detect_image_mime(data: bytes) -> str | None:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if b"<svg" in data[:256]:
        return "image/svg+xml"
    return None


def _get_avatar_sha(message: Message) -> str | None:
    try:
        account_name = app.settings.get_account_from_jid(message.account.jid)
    except ValueError:
        return None

    try:
        if message.direction == ChatDirection.OUTGOING:
            client = app.get_client(account_name)
            own_jid = JID.from_string(client.get_own_jid().bare)
            return app.storage.archive.get_contact_value(
                account_name, own_jid, "avatar_sha"
            )

        if message.type in (MessageType.GROUPCHAT, MessageType.PM):
            if message.occupant is not None:
                sha = message.occupant.avatar_sha
                if sha is not VALUE_MISSING:
                    return sha
                if message.occupant.real_remote is not None:
                    return app.storage.archive.get_contact_value(
                        account_name,
                        message.occupant.real_remote.jid,
                        "avatar_sha",
                    )
            return None

        return app.storage.archive.get_contact_value(
            account_name, message.remote.jid, "avatar_sha"
        )
    except Exception:
        return None


def _copy_avatar(sha: str, export_dir: Path) -> str | None:
    src = configpaths.get("AVATAR") / sha
    if not src.is_file():
        return None

    data = src.read_bytes()
    mime = _detect_image_mime(data)
    if mime is None:
        return None
    ext = {
        "image/jpeg": "jpg",
        "image/webp": "webp",
        "image/gif": "gif",
        "image/svg+xml": "svg",
    }.get(mime, "png")

    avatars_dir = export_dir / "avatars"
    avatars_dir.mkdir(exist_ok=True)

    dest_name = f"{sha}.{ext}"
    dest = avatars_dir / dest_name
    if not dest.exists():
        dest.write_bytes(data)

    return f"avatars/{dest_name}"


def _avatar_html(
    message: Message, name: str, export_dir: Path, *, ref: bool = False
) -> str:
    sha = _get_avatar_sha(message)
    if sha:
        rel_path = _copy_avatar(sha, export_dir)
        if rel_path is not None:
            name_esc = html_module.escape(name)
            css_class = "ref-avatar" if ref else "avatar"
            return (
                f'<img class="{css_class}" src="{rel_path}" alt="{name_esc}"'
                f' loading="lazy" decoding="async">'
            )
    return _initials_avatar_div(name, ref=ref)


_MEDIA_MAX_H = 400
_MEDIA_MIN_H = 50
_MEDIA_MAX_W = 400


def _get_media_dimensions(path: Path) -> tuple[int, int] | None:
    """Return (width, height) by reading only the image file header."""
    try:
        from gi.repository import GdkPixbuf

        info = GdkPixbuf.Pixbuf.get_file_info(str(path))
        if info[0] is not None and info[1] > 0 and info[2] > 0:
            return info[1], info[2]
    except Exception:
        pass
    return None


def _calc_display_size(width: int, height: int) -> tuple[int, int]:
    """Scale to fit within max dimensions, enforcing minimum height."""
    if height <= 0 or width <= 0:
        return _MEDIA_MAX_W, _MEDIA_MIN_H * 2
    scale = min(1.0, _MEDIA_MAX_H / height, _MEDIA_MAX_W / width)
    dw = max(1, round(width * scale))
    dh = max(_MEDIA_MIN_H, round(height * scale))
    return dw, dh


def _find_cached_file(url: str) -> Path | None:
    try:
        downloads_dir = configpaths.get("DOWNLOADS")
        thumb_dir = configpaths.get("DOWNLOADS_THUMB")
        urlparts = urlparse(url)
        orig_path, _ = get_image_paths(url, urlparts, 0, downloads_dir, thumb_dir)
        return orig_path if orig_path.exists() else None
    except Exception:
        return None


_AESGCM_URL_RE = re.compile(r"aesgcm://\S+")


def _media_html_for_cached(
    url: str, local_path: Path, export_dir: Path, description: str = ""
) -> str:
    """Return inline media HTML for a file already cached locally."""
    parsed_url = urlparse(url)
    mime_type, _ = mimetypes.guess_type(parsed_url.path)
    mime_type = mime_type or ""
    src = html_module.escape(_copy_attachment(local_path, export_dir))

    if mime_type.startswith("image/"):
        alt = html_module.escape(description or Path(parsed_url.path).name)
        dims = _get_media_dimensions(local_path)
        dw, dh = (
            _calc_display_size(*dims) if dims else (_MEDIA_MAX_W, _MEDIA_MAX_H * 3 // 4)
        )
        return (
            f'<div class="lazy-media" data-type="img" data-src="{src}" data-alt="{alt}"'
            f' style="aspect-ratio:{dw}/{dh}; max-width:{dw}px">'
            f'<noscript><img class="lazy-img" src="{src}" alt="{alt}"'
            f' loading="lazy"></noscript>'
            f"</div>"
        )
    if mime_type.startswith("video/"):
        mime_esc = html_module.escape(mime_type)
        return (
            f'<div class="lazy-media" data-type="video" data-src="{src}"'
            f' data-mime="{mime_esc}"'
            f' style="aspect-ratio:16/9; max-width:{_MEDIA_MAX_W}px">'
            f'<noscript><video class="media-preview" controls preload="none">'
            f'<source src="{src}" type="{mime_esc}"></video></noscript>'
            f"</div>"
        )
    if mime_type.startswith("audio/"):
        return (
            f'<audio class="media-preview" controls preload="metadata">'
            f'<source src="{src}" type="{html_module.escape(mime_type)}"></audio>'
        )
    fname = html_module.escape(Path(parsed_url.path).name or "file")
    return (
        f'<a class="file-link" href="{src}"'
        f' rel="noopener noreferrer" target="_blank">&#128206; {fname}</a>'
    )


def _aesgcm_media_from_text(text: str, export_dir: Path) -> str:
    """Find cached aesgcm:// files referenced in a message body text."""
    parts: list[str] = []
    seen: set[str] = set()
    for m in _AESGCM_URL_RE.finditer(text):
        url = m.group(0)
        if url in seen:
            continue
        seen.add(url)
        local_path = _find_cached_file(url)
        if local_path is None:
            continue
        parts.append(_media_html_for_cached(url, local_path, export_dir))
    return "\n".join(parts)


def _is_only_aesgcm_urls(text: str) -> bool:
    """True when the message body contains nothing but aesgcm:// URLs and whitespace."""
    return _AESGCM_URL_RE.sub("", text).strip() == ""


_LINK_SVG = (
    '<svg width="12" height="12" viewBox="0 0 24 24" fill="none"'
    ' stroke="currentColor" stroke-width="2.5"'
    ' stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>'
    '<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>'
    "</svg>"
)


def _link_buttons_html(urls: list[str]) -> str:
    if not urls:
        return ""
    parts: list[str] = []
    for url in urls:
        url_js = html_module.escape(json.dumps(url))
        title = html_module.escape(url)
        parts.append(
            f'<button class="media-link-btn" onclick="copyLink({url_js}, this)"'
            f' title="{title}" aria-label="Copy link">{_LINK_SVG}</button>'
        )
    return "".join(parts)


def _copy_attachment(local_path: Path, export_dir: Path) -> str:
    attachments_dir = export_dir / "attachments"
    attachments_dir.mkdir(exist_ok=True)
    dest = attachments_dir / local_path.name
    if not dest.exists():
        shutil.copy2(local_path, dest)
    return f"attachments/{local_path.name}"


def _fmt_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{size / (1024 * 1024 * 1024):.1f} GB"


def _media_html(message: Message, export_dir: Path) -> str:
    if not message.oob:
        return ""

    # Build a filename → size map from FileTransfer metadata.
    ft_sizes: dict[str, int] = {}
    try:
        for ft in message.filetransfers or []:
            if ft.name and ft.size:
                ft_sizes[ft.name] = ft.size
    except Exception:
        pass

    parts: list[str] = []
    for oob in message.oob:
        url = oob.url
        parsed_url = urlparse(url)

        # Use the URL path (not the full URL) for MIME detection so that the
        # decryption key in the aesgcm:// fragment doesn't corrupt the extension.
        mime_type, _ = mimetypes.guess_type(parsed_url.path)
        mime_type = mime_type or ""

        local_path = _find_cached_file(url)

        if local_path is None:
            # File not cached locally.
            raw_fname = Path(parsed_url.path).name or "file"
            fname_esc = html_module.escape(raw_fname)
            size = ft_sizes.get(raw_fname)
            size_str = f" · {_fmt_size(size)}" if size else ""

            if parsed_url.scheme == "aesgcm":
                # The browser cannot decrypt OMEMO-encrypted media; show a
                # lock badge instead of a download button.
                parts.append(
                    f'<span class="file-link">'
                    f"&#128274; {fname_esc}{html_module.escape(size_str)}</span>"
                )
            else:
                url_js = html_module.escape(json.dumps(url))
                fname_js = html_module.escape(json.dumps(raw_fname))
                parts.append(
                    f'<button class="file-link media-download"'
                    f' onclick="downloadMedia({url_js}, {fname_js}, this)">'
                    f"&#8681; {fname_esc}{html_module.escape(size_str)}</button>"
                )
            continue

        parts.append(
            _media_html_for_cached(url, local_path, export_dir, oob.description or "")
        )

    return "\n".join(parts)


_MIME_EXT_MAP = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/svg+xml": "svg",
}


def _copy_og_image(
    image_bytes: bytes, image_type: str | None, export_dir: Path
) -> str | None:
    """Write an OpenGraph thumbnail into <export_dir>/previews/ and return
    the relative path (or None on failure).
    """
    sha = hashlib.sha1(image_bytes).hexdigest()
    ext = _MIME_EXT_MAP.get((image_type or "").lower())
    if ext is None:
        # Fall back to sniffing the byte header (same as avatars).
        sniffed = _detect_image_mime(image_bytes)
        ext = _MIME_EXT_MAP.get(sniffed or "", "bin")
    previews_dir = export_dir / "previews"
    previews_dir.mkdir(exist_ok=True)
    dest = previews_dir / f"{sha}.{ext}"
    if not dest.exists():
        try:
            dest.write_bytes(image_bytes)
        except OSError:
            return None
    return f"previews/{dest.name}"


def _opengraph_html(message: Message, export_dir: Path) -> str:
    """Render OpenGraph link previews attached to a message as card blocks."""
    try:
        og_list = message.og
    except Exception:
        return ""
    if not og_list:
        return ""

    parts: list[str] = []
    for og in og_list:
        thumb_html = ""
        if og.image_bytes:
            rel = _copy_og_image(og.image_bytes, og.image_type, export_dir)
            if rel is not None:
                thumb_html = (
                    f'<img class="link-preview-thumb" src="{html_module.escape(rel)}"'
                    f' alt="" loading="lazy" decoding="async">'
                )

        title = html_module.escape(og.title or og.about)
        desc_html = ""
        if og.description:
            desc_html = (
                f'<div class="link-preview-desc">'
                f"{html_module.escape(og.description)}</div>"
            )
        host = ""
        try:
            host = urlparse(og.about).netloc
        except Exception:
            pass
        host_html = (
            f'<div class="link-preview-host">{html_module.escape(host)}</div>'
            if host
            else ""
        )

        parts.append(
            f'<a class="link-preview" href="{html_module.escape(og.about)}"'
            f' rel="noopener noreferrer" target="_blank">'
            f"{thumb_html}"
            f'<div class="link-preview-body">'
            f'<div class="link-preview-title">{title}</div>'
            f"{desc_html}{host_html}"
            f"</div></a>"
        )
    return "\n".join(parts)


# ── XEP-0393 → HTML ──────────────────────────────────────────────────────────


def _collect_events(
    spans: list[Span], uris: list[BaseHyperlink]
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    for span in spans:
        tags = _SPAN_TAGS.get(span.name)
        if tags is None:
            continue
        events.append(
            {
                "start": span.start,
                "end": span.end,
                "open": tags[0],
                "close": tags[1],
                "is_span": True,
            }
        )

    for uri in uris:
        if uri.uri.startswith("aesgcm://"):
            # aesgcm:// links cannot be opened in browsers; render as plain text.
            continue
        href = html_module.escape(uri.uri)
        events.append(
            {
                "start": uri.start,
                "end": uri.end,
                "open": f'<a href="{href}" rel="noopener noreferrer" target="_blank">',
                "close": "</a>",
                "is_span": False,
            }
        )

    # Sort by start; when equal, put the longer (outer) event first.
    events.sort(key=lambda e: (e["start"], e["start"] - e["end"]))
    return events


def _build_html(text: str, events: list[dict[str, Any]], start: int, end: int) -> str:
    parts: list[str] = []
    pos = start
    i = 0

    while i < len(events):
        ev = events[i]
        if ev["start"] >= end:
            break

        if ev["start"] > pos:
            parts.append(html_module.escape(text[pos : ev["start"]]))

        # Collect child events that fall within this event's character range.
        children: list[dict[str, Any]] = []
        j = i + 1
        while j < len(events) and events[j]["start"] < ev["end"]:
            children.append(events[j])
            j += 1

        if ev["is_span"]:
            open_delim = html_module.escape(text[ev["start"]])
            close_delim = html_module.escape(text[ev["end"] - 1])
            inner = _build_html(text, children, ev["start"] + 1, ev["end"] - 1)
            parts.append(
                f'<span class="fmt-marker">{open_delim}</span>'
                f"{ev['open']}{inner}{ev['close']}"
                f'<span class="fmt-marker">{close_delim}</span>'
            )
        else:
            inner = _build_html(text, children, ev["start"], ev["end"])
            parts.append(f"{ev['open']}{inner}{ev['close']}")

        pos = ev["end"]
        i = j

    if pos < end:
        parts.append(html_module.escape(text[pos:end]))

    return "".join(parts)


def _plain_block_to_html(block: PlainBlock) -> str:
    events = _collect_events(block.spans, block.uris)
    content = _build_html(block.text, events, 0, len(block.text))
    return f'<p class="message-text">{content}</p>'


def _pre_block_to_html(block: PreBlock) -> str:
    lines = block.text.splitlines()
    lang = lines[0][3:].strip() if lines else ""
    code_lines = lines[1:]
    if code_lines and code_lines[-1].strip() == "```":
        code_lines = code_lines[:-1]
    lang_attr = f' class="language-{html_module.escape(lang)}"' if lang else ""
    # Wrap each line in <span class="line"> so a CSS counter can render a
    # decorative line-number gutter via ::before. Pseudo-element content
    # never appears in textContent, so the copy button stays clean.
    inner = "".join(
        f'<span class="line">{html_module.escape(line)}</span>' for line in code_lines
    )
    return f"<pre><code{lang_attr}>{inner}</code></pre>"


def _quote_block_to_html(block: QuoteBlock) -> str:
    inner = "\n".join(_block_to_html(b) for b in block.blocks)
    return f"<blockquote>{inner}</blockquote>"


def _block_to_html(block: Block) -> str:
    if isinstance(block, PlainBlock):
        return _plain_block_to_html(block)
    if isinstance(block, PreBlock):
        return _pre_block_to_html(block)
    if isinstance(block, QuoteBlock):
        return _quote_block_to_html(block)
    return ""


def _styling_to_html(text: str) -> str:
    result = process(text)
    return "\n".join(_block_to_html(b) for b in result.blocks)


# ── Message rendering ─────────────────────────────────────────────────────────


def _get_nickname(message: Message) -> str:
    if message.direction == ChatDirection.OUTGOING:
        return _("You")

    if message.type in (MessageType.GROUPCHAT, MessageType.PM):
        if message.occupant is not None and message.occupant.nickname is not None:
            return message.occupant.nickname
        if message.resource is not None:
            return message.resource
        return _("Group Chat")

    return str(message.remote.jid)


def _ref_message_html(original_message: Message, export_dir: Path) -> str:
    referenced = original_message.get_referenced_message()
    if referenced is None:
        label = html_module.escape(_("The referenced message is not available."))
        return (
            '<div class="referenced-message">'
            '<div class="quote-bar"></div>'
            '<div class="ref-content">'
            f'<span class="ref-text">{label}</span>'
            "</div></div>"
        )

    display = referenced.get_last_correction() or referenced
    ref_name = _get_nickname(referenced)
    ref_ts = referenced.timestamp.astimezone().strftime("%H:%M")

    ref_text = display.text or ""
    lines = ref_text.split("\n")
    if len(lines) > 3:
        ref_text = "\n".join(lines[:3]) + " \u2026"

    name_esc = html_module.escape(ref_name)
    text_esc = html_module.escape(ref_text)
    ref_avatar = _avatar_html(referenced, ref_name, export_dir, ref=True)

    return (
        f'<a class="message-ref-link" href="#msg-{referenced.pk}">'
        f'<div class="referenced-message">'
        f'<div class="quote-bar"></div>'
        f'<div class="ref-content">'
        f'<div class="ref-meta">'
        f"{ref_avatar}"
        f'<span class="ref-name">{name_esc}</span>'
        f'<span class="ref-timestamp">{ref_ts}</span>'
        f"</div>"
        f'<div class="ref-text">{text_esc}</div>'
        f"</div></div>"
        f"</a>"
    )


def _edit_history_html(message: Message) -> str:
    """Render a <details> pen-icon + dropdown of message versions.

    Newest at top, original at bottom. Skips moderated/retracted revisions.
    Returns "" if the message was never edited.
    """
    try:
        corrections = message.corrections
    except Exception:
        return ""

    valid = [c for c in corrections if c.moderation is None and c.retraction is None]
    if not valid:
        return ""

    # Order: newest correction first, original last.
    versions = list(reversed(valid)) + [message]

    parts: list[str] = []
    for v in versions:
        ts = html_module.escape(v.timestamp.astimezone().strftime("%Y-%m-%d %H:%M:%S"))
        text = html_module.escape(v.text or "")
        parts.append(
            f'<div class="edit-version">'
            f'<span class="edit-time">{ts}</span>'
            f'<div class="edit-text">{text}</div>'
            f"</div>"
        )

    title = html_module.escape(_("Edited"))
    return (
        f'<details class="edit-history">'
        f'<summary class="edit-indicator" title="{title}">&#9998;</summary>'
        f'<div class="edit-versions">{"".join(parts)}</div>'
        f"</details>"
    )


def _reactions_html(message: Message) -> str:
    try:
        reactions = message.get_reactions()
    except Exception:
        return ""

    # Aggregate authors by emoji, mirroring the GTK reactions bar.
    aggregated: dict[str, list[str]] = defaultdict(list)
    for reaction in reactions:
        if not reaction.emojis:
            continue
        if reaction.direction == ChatDirection.OUTGOING:
            author = _("Me")
        elif reaction.occupant is not None and reaction.occupant.nickname is not None:
            author = reaction.occupant.nickname
        else:
            author = str(message.remote.jid)
        for emoji in reaction.emojis.split(";"):
            if emoji:
                aggregated[emoji].append(author)

    if not aggregated:
        return ""

    # Sort by count desc, then emoji (stable) — same order as the GTK bar.
    ordered = sorted(aggregated.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    parts: list[str] = []
    for emoji, authors in ordered:
        title = html_module.escape(", ".join(authors))
        emoji_esc = html_module.escape(emoji)
        parts.append(
            f'<span class="reaction" title="{title}">{emoji_esc}'
            f'<span class="reaction-count">{len(authors)}</span></span>'
        )
    return f'<div class="reactions">{"".join(parts)}</div>'


def _message_to_html(message: Message, export_dir: Path, msg_idx: int) -> str:
    name = _get_nickname(message)
    local_ts = message.timestamp.astimezone()
    timestamp = local_ts.strftime("%Y-%m-%d %H:%M:%S")
    date_iso = local_ts.date().isoformat()
    direction_class = (
        "outgoing-message"
        if message.direction == ChatDirection.OUTGOING
        else "incoming-message"
    )

    display = message.get_last_correction() or message

    avatar = _avatar_html(message, name, export_dir)
    name_esc = html_module.escape(name)

    ref_html = ""
    if display.reply is not None:
        ref_html = _ref_message_html(display, export_dir)

    media_html = _media_html(display, export_dir)

    # Collect OOB URLs already rendered by _media_html (to avoid duplicates).
    media_urls = list(dict.fromkeys(oob.url for oob in display.oob or []))
    oob_url_set = set(media_urls)

    # OMEMO messages carry the aesgcm:// URL only in the text body (no OOB).
    # Scan the text for such URLs, skipping any already handled via OOB.
    # rendered_urls grows to include aesgcm:// URLs found in the text body.
    rendered_urls: set[str] = set(oob_url_set)
    extra_media_html = ""
    text_aesgcm_urls: list[str] = []
    if display.text:
        for m in _AESGCM_URL_RE.finditer(display.text):
            u = m.group(0)
            if u not in rendered_urls:
                rendered_urls.add(u)
                text_aesgcm_urls.append(u)
        if text_aesgcm_urls:
            extra_media_html = _aesgcm_media_from_text(display.text, export_dir)

    media_urls.extend(text_aesgcm_urls)

    link_buttons = _link_buttons_html(media_urls)

    body_html = ""
    if display.text:
        # Suppress the redundant URL text when the body contains only URLs that
        # are already shown as inline media (aesgcm:// or regular OOB URLs).
        text_stripped = display.text.strip()
        only_rendered_urls = bool(rendered_urls) and all(
            part in rendered_urls for part in text_stripped.split() if part
        )
        if (media_html or extra_media_html) and (
            _is_only_aesgcm_urls(display.text) or only_rendered_urls
        ):
            body_html = ""
        else:
            body_html = _styling_to_html(display.text)

    og_html = _opengraph_html(display, export_dir)

    reactions_html = _reactions_html(message)
    edit_history_html = _edit_history_html(message)

    return (
        f'<article class="message-row {direction_class}"'
        f' id="msg-{message.pk}" data-msg-idx="{msg_idx}"'
        f' data-date="{date_iso}" data-sender="{name_esc}">\n'
        f'  <div class="avatar-box">{avatar}</div>\n'
        f'  <div class="message-content">\n'
        f'    <div class="meta-box">'
        f'<span class="nickname">{name_esc}</span>'
        f'<span class="timestamp">{timestamp}</span>'
        f"{edit_history_html}"
        f"{link_buttons}"
        f"</div>\n"
        f'    <div class="bottom-box">\n'
        f"      {ref_html}\n"
        f'      <div class="message-body">'
        f"{media_html}{extra_media_html}{body_html}{og_html}"
        f"</div>\n"
        f"      {reactions_html}\n"
        f"    </div>\n"
        f"  </div>\n"
        f"</article>"
    )


# ── Public API ────────────────────────────────────────────────────────────────


_ASSETS_DIR = Path(__file__).parent / "assets"


def write_shared_assets(export_dir: Path) -> None:
    shutil.copytree(_ASSETS_DIR, export_dir / "assets", dirs_exist_ok=True)


def generate_html(
    title: str,
    messages: list[Message],
    export_dir: Path,
    *,
    assets_prefix: str = "../assets",
) -> str:
    parts: list[str] = []
    # Track separators: {date, idx_in_parts, year_boundary}
    sep_entries: list[tuple[str, int, bool]] = []
    last_date = None
    last_year: int | None = None
    msg_idx = 0

    for message in messages:
        if message.call is not None:
            continue

        # Skip messages that were moderated or retracted. The DB query already
        # filters these; this is a defensive check in case a moderated message
        # slips through (e.g. via a different code path).
        if message.moderation is not None or message.retraction is not None:
            continue

        msg_date = message.timestamp.astimezone().date()
        if msg_date != last_date:
            last_date = msg_date
            date_str = html_module.escape(msg_date.strftime("%A, %B %-d, %Y"))
            is_year = msg_date.year != last_year
            if is_year:
                last_year = msg_date.year
            date_iso = msg_date.isoformat()
            sep_entries.append((date_iso, len(parts), is_year))
            parts.append(
                f'    <div class="date-separator" id="date-{date_iso}">'
                f"<span>{date_str}</span></div>"
            )

        parts.append(_message_to_html(message, export_dir, msg_idx))
        msg_idx += 1

    # Build pre-calculated timeline data: fractions based on item index.
    total = max(1, len(parts))
    tl_data: list[dict[str, Any]] = [
        {"date": date_iso, "frac": round(idx / total, 6), "year": is_year}
        for date_iso, idx, is_year in sep_entries
    ]

    title_esc = html_module.escape(title)

    html = _HTML_TEMPLATE.format(
        title=title_esc,
        css_href=f"{assets_prefix}/style.css",
        js_href=f"{assets_prefix}/history.js",
        messages="\n".join(parts),
    )

    tl_script = (
        '<script id="tl-data" type="application/json">\n'
        + json.dumps(tl_data)
        + "\n</script>\n"
    )
    html = html.replace("<!-- TL_DATA -->", tl_script, 1)

    # Render tick markup server-side — no runtime DOM building or JSON parsing.
    tick_parts: list[str] = []
    for entry in tl_data:
        cls = "tl-tick tl-year" if entry["year"] else "tl-tick"
        top_pct = entry["frac"] * 100
        year_label = ""
        if entry["year"]:
            year = int(entry["date"][:4])
            year_label = f'<span class="tl-label">{year}</span>'
        tick_parts.append(
            f'    <a class="{cls}" href="#date-{entry["date"]}"'
            f' style="top:{top_pct}%"><span class="tl-dot"></span>{year_label}</a>'
        )
    html = html.replace("<!-- TL_TICKS -->", "\n".join(tick_parts), 1)

    return html


def make_overview_avatar_src(
    sha: str | None,
    name: str,
    chat_dir: Path,
    export_dir: Path,
) -> str:
    """Return an avatar src for the overview sidebar.

    Copies the avatar file from Gajim's cache into chat_dir/avatars/ and
    returns a path relative to export_dir.  Falls back to an inline initials
    SVG when no cached avatar is available.
    """
    if sha:
        rel = _copy_avatar(sha, chat_dir)
        if rel:
            chat_rel = chat_dir.relative_to(export_dir)
            return f"{chat_rel.as_posix()}/{rel}"
    return _svg_initials_data_uri(name, 36)


_OVERVIEW_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link rel="stylesheet" href="{css_href}">
</head>
<body>
<div class="layout">
  <nav class="sidebar">
    <div class="sidebar-header">
      <h1 class="sidebar-title">{title}</h1>
      <p class="sidebar-info">{export_info}</p>
    </div>
    <div class="sidebar-search" hidden>
      <div class="search-input-wrap">
        <input type="search" id="search-input"
               placeholder="Search messages\u2026" autocomplete="off">
        <button id="search-clear" class="search-clear-btn"
                type="button" title="Clear">&#x2715;</button>
      </div>
      <button id="search-btn" type="button">Search</button>
      <div class="search-opts">
        <button class="search-opt" id="opt-highlight" type="button"
                title="Highlight All" aria-pressed="false"
                ><span class="opt-highlight">A</span></button>
        <button class="search-opt" id="opt-case" type="button"
                title="Match Case" aria-pressed="false"
                ><span class="opt-aa">Aa</span></button>
        <button class="search-opt" id="opt-diacritic" type="button"
                title="Match Diacritics" aria-pressed="false"
                ><span class="opt-diacritic">á</span></button>
        <button class="search-opt" id="opt-word" type="button"
                title="Whole Words" aria-pressed="false"
                ><span class="opt-word">ab</span></button>
        <button class="search-opt" id="opt-from-btn" type="button"
                title="From date" aria-pressed="false"
                ><span class="opt-date">&#8805;</span></button>
        <input type="date" id="opt-from-date" class="date-hidden">
        <button class="search-opt" id="opt-to-btn" type="button"
                title="To date" aria-pressed="false"
                ><span class="opt-date">&#8804;</span></button>
        <input type="date" id="opt-to-date" class="date-hidden">
        <button class="search-opt" id="opt-sender" type="button"
                title="Filter by sender" aria-pressed="false"
                ><span class="opt-sender">@</span></button>
      </div>
      <div class="sender-popup" id="sender-popup" hidden>
        <input type="search" id="sender-input"
               placeholder="Sender\u2026" autocomplete="off">
        <button id="sender-reset" type="button"
                title="Clear sender filter">&#x2715;</button>
      </div>
      <div class="search-nav" id="search-nav">
        <button class="nav-btn" id="prev-btn" type="button"
                title="Previous result" disabled>&#8249;</button>
        <span id="search-count"></span>
        <button class="nav-btn" id="next-btn" type="button"
                title="Next result" disabled>&#8250;</button>
      </div>
    </div>
    <ul class="chat-list" id="chat-list">
{chat_items}
    </ul>
  </nav>
  <main class="main-view">
    <iframe id="chat-frame" name="chat-frame"
            title="Chat History"{iframe_attrs}></iframe>
    <div class="empty-state" id="empty-state"{empty_hidden}>
      <p>{select_prompt}</p>
    </div>
  </main>
</div>
<script>window._currentPath = {current_path_js};</script>
<script src="{js_href}"></script>
</body>
</html>
"""


def generate_overview_html(
    chats: list[tuple[str, str, str, str]],
    *,
    assets_prefix: str = "assets",
) -> str:
    """Generate an overview HTML with a sidebar and iframe main view.

    chats: list of (display_name, jid_str, relative_html_path, avatar_src)
    """
    chat_items: list[str] = []
    for i, (name, _jid_str, rel_path, avatar_src) in enumerate(chats):
        name_esc = html_module.escape(name)
        path_esc = html_module.escape(rel_path)
        active = " active" if i == 0 else ""

        chat_items.append(
            f'      <li class="chat-item{active}">'
            f'<a class="chat-link" href="{path_esc}" target="chat-frame">'
            f'<img class="chat-avatar" src="{avatar_src}" alt="{name_esc}"'
            f' loading="lazy" decoding="async">'
            f'<span class="chat-name">{name_esc}</span>'
            f"</a>"
            f"</li>"
        )

    if chats:
        first_path = html_module.escape(chats[0][2])
        iframe_attrs = f' src="{first_path}"'
        empty_hidden = " hidden"
        current_path_js = json.dumps(chats[0][2])
    else:
        iframe_attrs = ""
        empty_hidden = ""
        current_path_js = "null"

    export_info = html_module.escape(
        _("Exported on {}").format(datetime.now().strftime("%Y-%m-%d %H:%M"))
    )

    return _OVERVIEW_TEMPLATE.format(
        title=html_module.escape(_("Chat History")),
        export_info=export_info,
        css_href=f"{assets_prefix}/overview.css",
        js_href=f"{assets_prefix}/overview.js",
        chat_items="\n".join(chat_items),
        select_prompt=html_module.escape(_("Select a chat from the sidebar")),
        iframe_attrs=iframe_attrs,
        empty_hidden=empty_hidden,
        current_path_js=current_path_js,
    )
