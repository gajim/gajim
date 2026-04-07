# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from gi.repository import Gtk
from nbxmpp.modules.vcard4 import TzProperty
from nbxmpp.modules.vcard4 import VCard
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common import types
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact

from gajim.gtk.util.misc import get_ui_string


@Gtk.Template(string=get_ui_string("timezone_hint.ui"))
class TimezoneHint(Gtk.Box):
    __gtype_name__ = "TimezoneHint"

    _hint_label: Gtk.Label = Gtk.Template.Child()

    def __init__(self) -> None:
        Gtk.Box.__init__(self)

        self._contact: types.ChatContactT | None = None
        self._remote_timezone: ZoneInfo | None = None

        app.pulse_manager.add_callback(self._update_state)

    def switch_contact(self, contact: types.ChatContactT) -> None:
        self.set_visible(False)

        if self._contact is not None:
            self._contact.disconnect_all_from_obj(self)

        if not isinstance(contact, BareContact):
            self._contact = None
            self._remote_timezone = None
            return

        if contact.subscription != "both":
            return

        self._contact = contact
        self._contact.connect("chatstate-update", self._on_chatstate_update)

        client = app.get_client(contact.account)
        vcard = client.get_module("VCard4").request_vcard(
            jid=self._contact.jid,
            callback=self._on_vcard_received,
            max_cache_seconds=12 * 60 * 60,
        )
        if vcard is not None:
            self._process_vcard(vcard)

    def _on_chatstate_update(
        self, _contact: types.ChatContactT, _signal_name: str
    ) -> None:
        # Hide as soon as there is a chat state update (user is present)
        self.set_visible(False)

    def _on_vcard_received(self, jid: JID, vcard: VCard) -> None:
        self._process_vcard(vcard)

    def _process_vcard(self, vcard: VCard) -> None:
        tz_prop = None
        for prop in vcard.get_properties():
            if isinstance(prop, TzProperty):
                tz_prop = prop

        if tz_prop is None:
            return

        try:
            self._remote_timezone = ZoneInfo(tz_prop.value)
        except Exception:
            return

        self._update_state()

    def _update_state(self) -> None:
        if self._remote_timezone is None:
            return

        time = dt.datetime.now(self._remote_timezone)

        if time.hour > 5:
            # Show hint only between 0:00 and 6:00
            return

        time_string = time.strftime(app.settings.get("time_format"))
        assert self._contact is not None
        self._hint_label.set_markup(
            _("It's <b>%(time)s</b> for %(name)s")
            % {"time": time_string, "name": self._contact.name}
        )
        self.set_visible(True)
