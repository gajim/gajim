# Copyright (C) 2016-2018 Philipp Hörist <philipp AT hoerist.com>
# Copyright (C) 2005-2006 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2005-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2008 Stephan Erb <steve-e AT h3c.de>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import typing
from typing import Any

import json
import pprint
import sys
import threading
import traceback
import webbrowser
from io import StringIO
from types import TracebackType
from urllib.parse import urlencode

import nbxmpp
from gi.repository import Gtk
from nbxmpp.http import HTTPRequest

import gajim
from gajim.common import app
from gajim.common.helpers import determine_proxy
from gajim.common.i18n import _
from gajim.common.util.http import create_http_request
from gajim.common.util.version import get_glib_version
from gajim.common.util.version import get_gobject_version
from gajim.common.util.version import get_os_name
from gajim.common.util.version import get_os_version
from gajim.common.util.version import get_soup_version

from gajim.gtk.builder import get_builder
from gajim.gtk.util import get_gtk_version
from gajim.gtk.util import SignalManager
from gajim.gtk.widgets import GajimAppWindow

try:
    import sentry_sdk
except Exception:
    # Sentry has a lot of side effects on import
    # make sure this optional dependency does not prevent
    # Gajim from starting
    if typing.TYPE_CHECKING:
        import sentry_sdk

_exception_in_progress = threading.Lock()

ISSUE_URL = "https://dev.gajim.org/gajim/gajim/issues/new"

ISSUE_TEXT = """## Versions:
- OS: {}
- GTK Version: {}
- PyGObject Version: {}
- GLib Version : {}
- libsoup Version: {}
- python-nbxmpp Version: {}
- Gajim Version: {}

## Traceback
```
{}
```
## Steps to reproduce the problem
..."""


def _hook(type_: type[BaseException], value: BaseException, tb: TracebackType) -> None:
    if not _exception_in_progress.acquire(False):
        # Exceptions have piled up, so we use the default exception
        # handler for such exceptions
        sys.__excepthook__(type_, value, tb)
        return

    window = ExceptionDialog(type_, value, tb)
    window.show()

    _exception_in_progress.release()


class ExceptionDialog(GajimAppWindow, SignalManager):
    def __init__(
        self, type_: type[BaseException], value: BaseException, tb: TracebackType
    ) -> None:
        GajimAppWindow.__init__(
            self,
            name="ExceptionDialog",
            title=_("Gajim - Error"),
            default_width=700,
            add_window_padding=False,
        )
        SignalManager.__init__(self)

        self._traceback_data = (type_, value, tb)
        self._sentry_available = app.is_installed("SENTRY_SDK")

        self._ui = get_builder("exception_dialog.ui")
        self.set_child(self._ui.exception_box)

        if not self._sentry_available:
            self._ui.user_feedback_box.set_visible(False)
            self._ui.infobar.set_reveal_child(True)

        self._ui.report_button.grab_focus()
        self.set_default_widget(self._ui.report_button)

        self._connect(self._ui.close_button, "clicked", self._on_close_clicked)
        self._connect(self._ui.report_button, "clicked", self._on_report_clicked)

        trace = StringIO()
        traceback.print_exception(type_, value, tb, None, trace)

        self._issue_text = self._get_issue_text(trace.getvalue())
        buffer_ = self._ui.exception_view.get_buffer()
        buffer_.set_text(self._issue_text)

        if self._sentry_available:
            self._ui.user_feedback_entry.grab_focus()

    def _on_report_clicked(self, _button: Gtk.Button) -> None:
        if self._sentry_available and determine_proxy() is None:
            # sentry-sdk supports a http-proxy arg but for now only use
            # sentry when no proxy is set, because we never tested if this
            # works. It's not worth it to potentially leak users identity just
            # because of error reporting.
            self._report_with_sentry()
        else:
            self._report_with_browser()

    def _report_with_browser(self):
        params = {"issue[description]": self._issue_text}
        url = f"{ISSUE_URL}?{urlencode(params)}"
        webbrowser.open(url, new=2)
        self.close()

    def _on_close_clicked(self, _button: Gtk.Button) -> None:
        self.close()

    @staticmethod
    def _get_issue_text(traceback_text: str) -> str:
        return ISSUE_TEXT.format(
            f"{get_os_name()} {get_os_version()}",
            get_gtk_version(),
            get_gobject_version(),
            get_glib_version(),
            get_soup_version(),
            nbxmpp.__version__,
            gajim.__version__,
            traceback_text,
        )

    def _report_with_sentry(self) -> None:
        if sentry_sdk.last_event_id() is None:
            # Sentry has not been initialized yet:
            # update sentry endpoint, init sentry, then capture exception
            self._request_sentry_endpoint()
            return

        self._capture_exception()
        self.close()

    def _request_sentry_endpoint(self) -> None:
        self._ui.report_button.set_sensitive(False)
        self._ui.close_button.set_sensitive(False)
        self._ui.report_spinner.set_visible(True)
        self._ui.report_spinner.start()

        request = create_http_request()
        request.send(
            "GET", "https://gajim.org/updates.json", callback=self._on_endpoint_received
        )

    def _parse_endpoint(self, request: HTTPRequest) -> str:
        if not request.is_complete():
            raise ValueError(
                "Failed to retrieve sentry endpoint: "
                f"{request.get_status()} {request.get_error()}"
            )

        try:
            data = json.loads(request.get_data())
        except Exception as error:
            raise ValueError(f"Json parsing error: {error}")

        endpoint = data.get("sentry_endpoint")
        if endpoint is None:
            raise ValueError("Sentry endpoint missing in response")

        return endpoint

    def _on_endpoint_received(self, request: HTTPRequest) -> None:
        try:
            endpoint = self._parse_endpoint(request)
        except ValueError as error:
            print(error)
            self._report_with_browser()

        else:
            self._init_sentry(endpoint)
            self._capture_exception()
            self.close()

    def _init_sentry(self, endpoint: str) -> None:
        sentry_sdk.init(
            dsn=endpoint,
            traces_sample_rate=0.0,
            max_breadcrumbs=0,
            release=gajim.__version__,
            default_integrations=False,
            shutdown_timeout=0,
            auto_session_tracking=False,
            before_send=self._before_send,  # pyright: ignore
            debug=False,
        )

        sentry_sdk.set_context(
            "os", {"name": get_os_name(), "version": get_os_version()}
        )

        sentry_sdk.set_context(
            "software",
            {
                "python-nbxmpp": nbxmpp.__version__,
                "GTK": get_gtk_version(),
                "GObject": get_gobject_version(),
                "GLib": get_glib_version(),
            },
        )

    def _capture_exception(self) -> None:
        sentry_sdk.set_context(
            "user_feedback", {"Feedback": self._ui.user_feedback_entry.get_text()}
        )
        sentry_sdk.capture_exception(self._traceback_data)

    def _before_send(self, event: dict[str, Any], hint: Any) -> dict[str, Any]:
        # Make sure the exception value is set, GitLab needs it.
        # The value is the arg which is passed to the Exception.
        # e.g. raise Exception('Error')
        try:
            value = event["exception"]["values"][0].get("value")
            if not value:
                event["exception"]["values"][0]["value"] = "Unknown"
        except Exception:
            pass

        # Remove the hostname of the machine
        event["server_name"] = "redacted"
        pprint.pprint(event)
        return event

    def _cleanup(self) -> None:
        self._disconnect_all()


def init() -> None:
    if sys.platform == "win32" or not sys.stderr.isatty():
        sys.excepthook = _hook
