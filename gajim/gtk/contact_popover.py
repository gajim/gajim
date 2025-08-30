# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp import JID
from nbxmpp.modules.vcard4 import EmailProperty
from nbxmpp.modules.vcard4 import OrgProperty
from nbxmpp.modules.vcard4 import RoleProperty
from nbxmpp.modules.vcard4 import TelProperty
from nbxmpp.modules.vcard4 import TzProperty
from nbxmpp.modules.vcard4 import VCard

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.iana import get_zone_data
from gajim.common.modules.contacts import BareContact
from gajim.common.util.status import get_uf_show

from gajim.gtk.avatar import get_show_circle
from gajim.gtk.structs import AccountJidParam
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import convert_surface_to_texture
from gajim.gtk.util.misc import get_ui_string


@Gtk.Template(string=get_ui_string("contact_popover.ui"))
class ContactPopover(Gtk.Popover, EventHelper, SignalManager):
    __gtype_name__ = "ContactPopover"

    _avatar: Gtk.Image = Gtk.Template.Child()
    _name: Gtk.Label = Gtk.Template.Child()
    _role: Gtk.Label = Gtk.Template.Child()
    _org: Gtk.Label = Gtk.Template.Child()
    _info_listbox: Gtk.ListBox = Gtk.Template.Child()
    _subscription: ContactPopoverInfoRow = Gtk.Template.Child()
    _status: ContactPopoverInfoRow = Gtk.Template.Child()
    _status_message: ContactPopoverInfoRow = Gtk.Template.Child()
    _xmpp_address: ContactPopoverInfoRow = Gtk.Template.Child()
    _email: ContactPopoverInfoRow = Gtk.Template.Child()
    _tel: ContactPopoverInfoRow = Gtk.Template.Child()
    _timezone: ContactPopoverInfoRow = Gtk.Template.Child()

    def __init__(self, contact: BareContact) -> None:
        Gtk.Popover.__init__(self)
        EventHelper.__init__(self)
        SignalManager.__init__(self)

        self._contact = contact

        scale = self.get_scale_factor()

        texture = contact.get_avatar(AvatarSize.TOOLTIP, scale)
        self._avatar.set_pixel_size(AvatarSize.TOOLTIP)
        self._avatar.set_from_paintable(texture)

        self._name.set_label(contact.name)

        if not contact.is_self:
            if contact.subscription in ("none", "to"):
                self._subscription.set_label(
                    _("You don't share your status with this contact")
                )

            if contact.subscription == ("from"):
                self._subscription.set_label(
                    _("This contact does not share their status with you")
                )

        # Status
        surface = get_show_circle(
            self._contact.show, AvatarSize.SHOW_CIRCLE, self.get_scale_factor()
        )
        icon = convert_surface_to_texture(surface)
        status_text = get_uf_show(self._contact.show.value)
        if idle_time_text := self._get_idle_time():
            status_text += f" ({idle_time_text})"

        self._status.set_label(status_text)
        self._status.set_icon(icon)

        if self._contact.status:
            self._status_message.set_label(self._contact.status)

        self._xmpp_address.set_label(str(self._contact.jid), link_scheme="xmpp")

        client = app.get_client(contact.account)
        client.get_module("VCard4").request_vcard(
            jid=self._contact.jid, callback=self._on_vcard_received
        )

        app.plugin_manager.extension_point("contact_tooltip_populate", self, contact)

    def _on_vcard_received(self, jid: JID, vcard: VCard) -> None:
        for prop in vcard.get_properties():
            match prop:
                case RoleProperty():
                    self._role.set_label(prop.value)
                    self._role.set_visible(True)
                case OrgProperty():
                    self._org.set_label(prop.values[0])
                    self._org.set_visible(True)
                case EmailProperty():
                    self._email.set_label(prop.value, link_scheme="mailto")
                case TelProperty():
                    self._tel.set_label(prop.value, link_scheme="tel")
                case TzProperty():
                    self._timezone.set_label(self._get_timezone_label(prop))
                case _:
                    pass

    def _get_idle_time(self) -> str | None:
        if self._contact.idle_datetime is None:
            return None

        current = dt.datetime.now()
        if self._contact.idle_datetime.date() == current.date():
            format_string = app.settings.get("time_format")
            formatted = self._contact.idle_datetime.strftime(format_string)
        else:
            format_string = app.settings.get("date_time_format")
            formatted = self._contact.idle_datetime.strftime(format_string)
        return _("last seen: %s") % formatted

    def _get_timezone_label(self, prop: TzProperty) -> str:
        try:
            tzinfo = ZoneInfo(prop.value)
        except Exception:
            return ""

        dt_format = app.settings.get("date_time_format")
        remote_dt_str = dt.datetime.now(tz=tzinfo).strftime(dt_format)
        data = get_zone_data(prop.value)

        return f"{remote_dt_str} ({data.full_name})"

    @Gtk.Template.Callback()
    def _on_contact_details_clicked(self, _button: Gtk.Button) -> None:
        self.popdown()
        account_jid_params = AccountJidParam(
            account=self._contact.account, jid=self._contact.jid
        )
        app.window.activate_action(
            "win.chat-contact-info", account_jid_params.to_variant()
        )


@Gtk.Template(string=get_ui_string("contact_popover_info_row.ui"))
class ContactPopoverInfoRow(Gtk.ListBoxRow):
    __gtype_name__ = "ContactPopoverInfoRow"

    _image: Gtk.Image = Gtk.Template.Child()
    _label: Gtk.Label = Gtk.Template.Child()

    def __init__(self) -> None:
        Gtk.ListBoxRow.__init__(self)

        self._icon: Gdk.Paintable | None = None
        self._icon_name: str | None = None
        self._text: str = ""

    @GObject.Property(type=Gdk.Paintable)
    def icon(self) -> Gdk.Paintable | None:  # pyright: ignore
        return self._icon

    @icon.setter
    def icon(self, icon: Gdk.Paintable | None) -> None:
        self.set_icon(icon)

    @GObject.Property(type=str)
    def icon_name(self) -> str | None:  # pyright: ignore
        return self._icon_name

    @icon_name.setter
    def icon_name(self, icon_name: str | None) -> None:
        self.set_icon(icon_name)

    @GObject.Property(type=str)
    def text(self) -> str:  # pyright: ignore
        return self._text

    @text.setter
    def text(self, text: str) -> None:
        self.set_label(text)

    def set_icon(self, icon: str | Gdk.Paintable | None) -> None:
        self._icon_name = None
        self._icon = None
        if icon is None:
            self._image.set_from_icon_name(None)
            self._image.set_from_paintable(None)
            return

        if isinstance(icon, str):
            self._image.set_from_icon_name(icon)
            self._icon_name = icon
        else:
            self._image.set_from_paintable(icon)
            self._icon = icon

    def set_label(self, text: str, link_scheme: str | None = None) -> None:
        self._text = text
        self.set_visible(bool(text))

        if link_scheme:
            self._label.set_markup(f"<a href='{link_scheme}:{text}'>{text}</a>")
        else:
            self._label.set_text(text)

        self._label.set_selectable(bool(link_scheme))

        if len(text) > 30:
            self._label.set_tooltip_text(text)
