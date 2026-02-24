# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import itertools
import logging
import multiprocessing
import re
import threading
from concurrent.futures import Future
from functools import partial

from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app
from gajim.common.helpers import determine_proxy
from gajim.common.multiprocess.http import CancelledError
from gajim.common.multiprocess.url_preview import generate_url_preview
from gajim.common.open_graph_parser import OpenGraphData
from gajim.common.regex import IRI_RX
from gajim.common.types import ChatContactT

from gajim.gtk.preview.open_graph import OpenGraphPreviewWidget
from gajim.gtk.util.misc import check_finalize
from gajim.gtk.util.misc import container_remove_all

log = logging.getLogger("gajim.gtk.message_url_previews")

MAX_URL_PREVIEWS = 3


class _MISSING:
    pass


MISSING = _MISSING()


class MessageURLPreviews(Gtk.Box):
    def __init__(self) -> None:
        Gtk.Box.__init__(
            self, spacing=12, orientation=Gtk.Orientation.VERTICAL, visible=False
        )

        mp_context = multiprocessing.get_context("spawn")
        self._manager = mp_context.Manager()

        self._preview_timeout_id = None
        self._current_previews: dict[str, OpenGraphPreviewWidget] = {}
        self._dismissed_previews: set[str] = set()

        self._requests_in_progress: dict[str, threading.Event] = {}
        self._request_cache: dict[str, OpenGraphData | None] = {}

        self._contact: ChatContactT | None = None

    def get_open_graph_data(self) -> dict[str, OpenGraphData] | None:
        if not self._current_previews:
            return None

        data: dict[str, OpenGraphData] = {}
        for url, preview in self._current_previews.items():
            if og_data := preview.get_open_graph():
                data[url] = og_data

        return data

    def switch_contact(self, contact: ChatContactT) -> None:
        self.clear()
        self._contact = contact

    def clear(self) -> None:
        if self._preview_timeout_id is not None:
            GLib.source_remove(self._preview_timeout_id)
            self._preview_timeout_id = None

        for event in self._requests_in_progress.values():
            event.set()

        self._requests_in_progress.clear()
        self._current_previews.clear()
        self._dismissed_previews.clear()

        container_remove_all(self)

        self.set_visible(False)

    def generate_url_previews(self, text: str) -> None:
        if self._contact is None:
            return

        if self._contact.is_groupchat:
            if not app.settings.get("gc_enable_link_preview_default"):
                return
        else:
            if not app.settings.get("enable_link_preview_default"):
                return

        if self._contact.settings.get("encryption"):
            return

        if self._preview_timeout_id is not None:
            GLib.source_remove(self._preview_timeout_id)

        self._preview_timeout_id = GLib.timeout_add(500, self._find_urls, text)

    def _find_urls(self, text: str) -> None:
        self._preview_timeout_id = None

        # We use lists here to preserve a stable and consistent order
        matches = itertools.islice(re.finditer(IRI_RX, text), MAX_URL_PREVIEWS)
        urls = [match.group() for match in matches]

        # Remove dismissed urls if they are not present in the text anymore
        self._dismissed_previews = set(urls) & self._dismissed_previews

        # Ignore already dismissed urls
        for url in self._dismissed_previews:
            if url in urls:
                urls.remove(url)

        self._update_preview_list(urls)

    def _request_url_preview(self, url: str) -> None:
        log.info("Request preview for: %s", url)

        event = self._manager.Event()

        assert self._contact is not None
        proxy = determine_proxy(self._contact.account)

        try:
            future = app.process_pool.submit(
                generate_url_preview,
                url,
                event,
                None if proxy is None else proxy.get_uri(),
            )
        except Exception as error:
            log.warning("Unable to generate preview: %s %s", url, error)
            return

        future.add_done_callback(partial(GLib.idle_add, self._on_request_finished, url))

        self._requests_in_progress[url] = event

    def _on_request_finished(
        self, url: str, future: Future[OpenGraphData | None]
    ) -> None:
        log.info("Request finished for %s", url)
        self._requests_in_progress.pop(url, None)

        og_data = None
        try:
            og_data = future.result()
        except CancelledError:
            log.info("Request was cancelled: %s", url)
            # Don't set value to the request cache so we can query
            # later again

        except Exception as error:
            log.error("Error during request: %s", error)
            self._request_cache[url] = None

        else:
            self._request_cache[url] = og_data

        if og_data is None:
            log.warning("No opengraph data found for url: %s", url)

        self._update_preview(url, og_data)

    def _update_preview_list(self, urls: list[str]) -> None:
        self._remove_obsolete_previews(urls)
        self._add_previews(urls)

        for url in urls:
            if self._requests_in_progress.get(url):
                continue

            og_data = self._request_cache.get(url, MISSING)
            if isinstance(og_data, _MISSING):
                self._request_url_preview(url)
                continue

            self._update_preview(url, og_data)

        self.set_visible(bool(self._current_previews))

    def _add_previews(self, urls: list[str]) -> None:
        for url in urls:
            if url in self._current_previews:
                continue

            log.debug("Create preview widget for %s", url)
            preview = OpenGraphPreviewWidget(url)
            preview.connect("remove", self._on_remove_clicked, url)
            self.append(preview)
            self._current_previews[url] = preview

    def _remove_obsolete_previews(self, current_urls: list[str]) -> None:
        for url in list(self._current_previews.keys()):
            if url not in current_urls:
                preview = self._current_previews.pop(url)
                log.debug("Remove preview widget for %s", url)
                self.remove(preview)
                check_finalize(preview)

    def _update_preview(self, url: str, og_data: OpenGraphData | None) -> None:
        preview = self._current_previews.get(url)
        if preview is None:
            log.debug("No preview widget found")
            return

        if og_data is None:
            preview.set_error()
        else:
            preview.set_open_graph(og_data, minimal=True)

    def _on_remove_clicked(self, widget: OpenGraphPreviewWidget, url: str) -> None:
        self.remove(widget)
        self._current_previews.pop(url, None)
        self._dismissed_previews.add(url)
