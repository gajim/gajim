# Copyright (C) 2016-2018 Philipp Hörist <philipp AT hoerist.com>
# Copyright (C) 2005-2006 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2005-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2008 Stephan Erb <steve-e AT h3c.de>
#
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
from gi.repository import Gdk
from gi.repository import Gtk
from nbxmpp.http import HTTPRequest

import gajim
from gajim.common import app
from gajim.common.helpers import determine_proxy
from gajim.common.helpers import get_glib_version
from gajim.common.helpers import get_gobject_version
from gajim.common.helpers import get_os_name
from gajim.common.helpers import get_os_version
from gajim.common.helpers import get_soup_version
from gajim.common.i18n import _
from gajim.common.util.http import create_http_request

from gajim.gtk.builder import get_builder
from gajim.gtk.util import get_gtk_version

try:
    import sentry_sdk
except ImportError:
    pass

_exception_in_progress = threading.Lock()

ISSUE_URL = 'https://dev.gajim.org/gajim/gajim/issues/new'

ISSUE_TEXT = '''## Versions:
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
...'''


def _hook(type_: type[BaseException],
          value: BaseException,
          tb: TracebackType
          ) -> None:
    if not _exception_in_progress.acquire(False):
        # Exceptions have piled up, so we use the default exception
        # handler for such exceptions
        sys.__excepthook__(type_, value, tb)
        return

    ExceptionDialog(type_, value, tb)
    _exception_in_progress.release()


class ExceptionDialog(Gtk.ApplicationWindow):
    def __init__(self,
                 type_: type[BaseException],
                 value: BaseException,
                 tb: TracebackType
                 ) -> None:
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_resizable(True)
        self.set_default_size(700, -1)
        self.set_title(_('Gajim - Error'))

        self._traceback_data = (type_, value, tb)
        self._sentry_available = app.is_installed('SENTRY_SDK')

        self._ui = get_builder('exception_dialog.ui')
        self.add(self._ui.exception_box)

        if not self._sentry_available:
            self._ui.user_feedback_box.set_no_show_all(True)
            self._ui.infobar.set_no_show_all(False)
            self._ui.infobar.set_revealed(True)

        self._ui.report_button.grab_focus()
        self._ui.report_button.grab_default()

        trace = StringIO()
        traceback.print_exception(type_, value, tb, None, trace)

        self._issue_text = self._get_issue_text(trace.getvalue())
        buffer_ = self._ui.exception_view.get_buffer()
        buffer_.set_text(self._issue_text)

        self.connect('key-press-event', self._on_key_press)
        self._ui.connect_signals(self)
        self.show_all()

        if self._sentry_available:
            self._ui.user_feedback_entry.grab_focus()

    def _on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> None:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

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
        params = {'issue[description]': self._issue_text}
        url = f'{ISSUE_URL}?{urlencode(params)}'
        webbrowser.open(url, new=2)
        self.destroy()

    def _on_close_clicked(self, _button: Gtk.Button) -> None:
        self.destroy()

    @staticmethod
    def _get_issue_text(traceback_text: str) -> str:
        return ISSUE_TEXT.format(
            f'{get_os_name()} {get_os_version()}',
            get_gtk_version(),
            get_gobject_version(),
            get_glib_version(),
            get_soup_version(),
            nbxmpp.__version__,
            gajim.__version__,
            traceback_text)

    def _report_with_sentry(self) -> None:
        if sentry_sdk.last_event_id() is None:
            # Sentry has not been initialized yet:
            # update sentry endpoint, init sentry, then capture exception
            self._request_sentry_endpoint()
            return

        self._capture_exception()
        self.destroy()

    def _request_sentry_endpoint(self) -> None:
        self._ui.report_button.set_sensitive(False)
        self._ui.close_button.set_sensitive(False)
        self._ui.report_spinner.show()
        self._ui.report_spinner.start()

        request = create_http_request()
        request.send('GET', 'https://gajim.org/updates.json',
                     callback=self._on_endpoint_received)

    def _parse_endpoint(self, request: HTTPRequest) -> str:
        if not request.is_complete():
            raise ValueError('Failed to retrieve sentry endpoint: %s %s' % (
                request.get_status(), request.get_error()))

        try:
            data = json.loads(request.get_data())
        except Exception as error:
            raise ValueError('Json parsing error: %s' % error)

        endpoint = data.get('sentry_endpoint')
        if endpoint is None:
            raise ValueError('Sentry endpoint missing in response')

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
            self.destroy()

    def _init_sentry(self, endpoint: str) -> None:
        # pylint: disable=abstract-class-instantiated
        sentry_sdk.init(
            dsn=endpoint,
            traces_sample_rate=0.0,
            max_breadcrumbs=0,
            release=gajim.__version__,
            default_integrations=False,
            shutdown_timeout=0,
            auto_session_tracking=False,
            before_send=self._before_send,
            debug=False)

        sentry_sdk.set_context('os', {
            'name': get_os_name(),
            'version': get_os_version()})

        sentry_sdk.set_context('software', {
            'python-nbxmpp': nbxmpp.__version__,
            'GTK': get_gtk_version(),
            'GObject': get_gobject_version(),
            'GLib': get_glib_version()})

    def _capture_exception(self) -> None:
        sentry_sdk.set_context('user_feedback', {
            'Feedback': self._ui.user_feedback_entry.get_text()})
        sentry_sdk.capture_exception(self._traceback_data)

    def _before_send(self, event: dict[str, Any], hint: Any) -> dict[str, Any]:
        # Make sure the exception value is set, GitLab needs it.
        # The value is the arg which is passed to the Exception.
        # e.g. raise Exception('Error')
        try:
            value = event['exception']['values'][0].get('value')
            if not value:
                event['exception']['values'][0]['value'] = 'Unknown'
        except Exception:
            pass

        # Remove the hostname of the machine
        event['server_name'] = ''
        pprint.pprint(event)
        return event


def init() -> None:
    if sys.platform == 'win32' or not sys.stderr.isatty():
        sys.excepthook = _hook
