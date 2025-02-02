# Copyright (C) 2009-2014 Yann Leboulanger <asterix AT lagaule.org>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import textwrap
from collections.abc import Callable
from collections.abc import Iterator
from datetime import datetime
from urllib.parse import quote

from gi.repository import Gio
from gi.repository import GLib
from nbxmpp import JID

from gajim.common import app
from gajim.common import types
from gajim.common.const import URIType
from gajim.common.const import XmppUriQuery
from gajim.common.i18n import _
from gajim.common.i18n import get_short_lang_code
from gajim.common.i18n import p_
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import can_add_to_roster
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.preview import Preview
from gajim.common.storage.archive.const import MessageState
from gajim.common.structs import URI
from gajim.common.structs import VariantMixin
from gajim.common.util.muc import is_affiliation_change_allowed
from gajim.common.util.muc import is_moderation_allowed
from gajim.common.util.muc import is_role_change_allowed
from gajim.common.util.text import escape_iri_path_segment
from gajim.common.util.uri import filesystem_path_from_uri

from gajim.gtk.const import MuteState
from gajim.gtk.structs import AccountJidParam
from gajim.gtk.structs import AddChatActionParams
from gajim.gtk.structs import ChatListEntryParam
from gajim.gtk.structs import DeleteMessageParam
from gajim.gtk.structs import ModerateAllMessagesParam
from gajim.gtk.structs import ModerateMessageParam
from gajim.gtk.structs import MuteContactParam

MenuValueT = None | str | GLib.Variant | VariantMixin
MenuItemListT = list[tuple[str, str, MenuValueT]]
UriMenuItemsT = list[tuple[str, list[str], str]]
UriMenuBuilderT = Callable[[URI, str], UriMenuItemsT]


class GajimMenu(Gio.Menu):
    def __init__(self):
        Gio.Menu.__init__(self)

    @classmethod
    def from_list(cls, menulist: MenuItemListT) -> GajimMenu:
        menu = cls()
        for item in menulist:
            menuitem = make_menu_item(*item)
            menu.append_item(menuitem)
        return menu

    def add_item(
        self, label: str, action: str, value: MenuValueT | None = None
    ) -> None:
        item = make_menu_item(label, action, value)
        self.append_item(item)

    def add_submenu(self, label: str) -> GajimMenu:
        menu = GajimMenu()
        self.append_submenu(label, menu)
        return menu


def make_menu_item(
    label: str, action: str | None = None, value: MenuValueT = None
) -> Gio.MenuItem:

    item = Gio.MenuItem.new(label)

    if value is None:
        item.set_action_and_target_value(action, None)
        return item

    item = Gio.MenuItem.new(label)
    if isinstance(value, str):
        item.set_action_and_target_value(action, GLib.Variant("s", value))
    elif isinstance(value, VariantMixin):
        item.set_action_and_target_value(action, value.to_variant())
    else:
        item.set_action_and_target_value(action, value)
    return item


def get_main_menu() -> GajimMenu:
    main_menu = GajimMenu()

    gajim_menu_items: MenuItemListT = [
        (_("_Start / Join Chat…"), "app.start-chat", GLib.Variant("as", ["", ""])),
        (_("Create _Group Chat…"), "app.create-groupchat", GLib.Variant("s", "")),
        (_("Pl_ugins"), "app.plugins", None),
        (_("_Preferences"), "app.preferences", None),
        (_("_Quit"), "app.quit", None),
    ]
    main_menu.append_submenu("_Gajim", GajimMenu.from_list(gajim_menu_items))

    main_menu.add_submenu(_("_Accounts"))

    view_menu_items: MenuItemListT = [
        (_("_Debug Console"), "app.xml-console", None),
        (_("_Toggle Menu Bar"), "win.toggle-menu-bar", None),
    ]
    main_menu.append_submenu(_("_View"), GajimMenu.from_list(view_menu_items))

    help_menu_items: MenuItemListT = [
        (_("_Wiki (Online)"), "app.content", None),
        (_("FA_Q (Online)"), "app.faq", None),
        (_("_Privacy Policy (Online)"), "app.privacy-policy", None),
        (_("Join Support Chat"), "app.join-support-chat", None),
        (_("_Keyboard Shortcuts"), "app.shortcuts", None),
        (_("_Features"), "app.features", None),
        (_("_About"), "app.about", None),
    ]
    main_menu.append_submenu(_("_Help"), GajimMenu.from_list(help_menu_items))

    return main_menu


def get_self_contact_menu(contact: types.BareContact) -> GajimMenu:
    account = contact.account
    jid = contact.jid

    menu = GajimMenu()

    menu.add_item(_("Profile"), f"app.{account}-profile", account)
    submenu = get_send_file_submenu()
    menu.append_submenu(_("Send File"), submenu)

    params = AccountJidParam(account=account, jid=jid)
    menu.add_item(_("Export History…"), "app.export-history", params)
    menu.add_item(_("Remove History…"), "app.remove-history", params)
    return menu


def get_singlechat_menu(contact: types.BareContact) -> GajimMenu:
    account = contact.account

    params = AccountJidParam(account=account, jid=contact.jid)

    menu = GajimMenu()

    submenu = get_send_file_submenu()
    menu.append_submenu(_("Send File"), submenu)
    menu.add_item(_("Block Contact…"), f"app.{account}-block-contact", params)

    # Disable because not maintained
    # menu.add_item(_("Start Voice Call…"), "win.start-voice-call")
    # menu.add_item(_("Start Video Call…"), "win.start-video-call")

    if can_add_to_roster(contact):
        params = AccountJidParam(account=account, jid=contact.jid)
        menu.add_item(_("Add Contact…"), "win.add-to-roster", params)

    if contact.is_in_roster:
        params = GLib.Variant("as", [account, str(contact.jid)])
        menu.add_item(_("Remove Contact…"), f"app.{account}-remove-contact", params)

    jids = [str(c.jid) for c in contact.get_resources()]
    if not jids:
        jids = [str(contact.jid)]

    menu.add_item(
        _("Execute Command…"),
        f"app.{account}-execute-command",
        GLib.Variant("(sas)", (account, jids)),
    )
    menu.add_item(_("Export History…"), "app.export-history", params)
    menu.add_item(_("Remove History…"), "app.remove-history", params)

    return menu


def get_private_chat_menu(contact: types.GroupchatParticipant) -> GajimMenu:
    menu = GajimMenu()

    value = GLib.Variant("as", [""])

    menu.add_item(_("Upload File…"), "win.send-file-httpupload", value)

    params = AccountJidParam(account=contact.account, jid=contact.jid)
    menu.add_item(_("Export History…"), "app.export-history", params)
    menu.add_item(_("Remove History…"), "app.remove-history", params)

    if can_add_to_roster(contact):
        menu.add_item(_("Add to Contact List…"), "win.add-to-roster", params)

    return menu


def get_send_file_submenu() -> GajimMenu:
    menu = GajimMenu()

    value = GLib.Variant("as", [""])

    menu.add_item(_("Upload File…"), "win.send-file-httpupload", value)
    # menu.add_item(_('Send File Directly…'), 'win.send-file-jingle', value)
    return menu


def get_groupchat_menu(contact: GroupchatContact) -> GajimMenu:
    menu = GajimMenu()

    menu.add_item(_("Change Nickname…"), "win.muc-change-nickname", None)
    menu.add_item(_("Request Voice"), "win.muc-request-voice", None)
    menu.add_item(_("Execute Command…"), "win.muc-execute-command", "")

    params = AccountJidParam(account=contact.account, jid=contact.jid)
    menu.add_item(_("Export History…"), "app.export-history", params)
    menu.add_item(_("Remove History…"), "app.remove-history", params)

    return menu


def get_account_menu(account: str) -> GajimMenu:

    client = app.get_client(account)
    server_jid = client.get_own_jid().domain
    assert server_jid is not None

    params = GLib.Variant("(sas)", (account, [server_jid]))

    menuitems: MenuItemListT = [
        (_("Profile"), f"app.{account}-profile", account),
        (_("Discover Services…"), f"app.{account}-services", account),
        (_("Execute Command…"), f"app.{account}-execute-command", params),
        (_("Server Info"), f"app.{account}-server-info", account),
    ]

    menu = GajimMenu.from_list(menuitems)

    advanced_menuitems: MenuItemListT = [
        (_("Manage Contact List"), f"app.{account}-manage-roster", account),
        (_("Archiving Preferences"), f"app.{account}-archive", account),
        (_("Blocking List"), f"app.{account}-blocking", account),
        (_("PEP Configuration"), f"app.{account}-pep-config", account),
        (_("Synchronize History…"), f"app.{account}-sync-history", account),
    ]

    menu.append_submenu(_("Advanced"), GajimMenu.from_list(advanced_menuitems))

    return menu


def build_accounts_menu() -> None:
    menubar = app.app.get_menubar()
    assert isinstance(menubar, Gio.Menu)
    # Accounts Submenu
    menu_position = 1

    acc_menu = menubar.get_item_link(menu_position, "submenu")
    assert isinstance(acc_menu, Gio.Menu)
    acc_menu.remove_all()

    accounts_list = sorted(app.settings.get_active_accounts())
    if not accounts_list:
        add_account_item = Gio.MenuItem.new(_("_Add Account…"), "app.accounts::")
        acc_menu.append_item(add_account_item)
        return

    if len(accounts_list) > 1:
        manage_accounts_item = Gio.MenuItem.new(
            _("_Manage Accounts…"), "app.accounts::"
        )
        acc_menu.append_item(manage_accounts_item)
        add_contact_item = Gio.MenuItem.new(_("Add _Contact…"), "app.add-contact::")
        acc_menu.append_item(add_contact_item)
        for acc in accounts_list:
            label = escape_mnemonic(app.get_account_label(acc))
            acc_menu.append_submenu(label, get_account_menu(acc))
    else:
        acc_menu = get_account_menu(accounts_list[0])
        manage_account_item = Gio.MenuItem.new(_("_Manage Account…"), "app.accounts::")
        acc_menu.insert_item(0, manage_account_item)
        add_contact_item = Gio.MenuItem.new(_("Add _Contact…"), "app.add-contact::")
        acc_menu.insert_item(1, add_contact_item)
        menubar.remove(menu_position)
        menubar.insert_submenu(menu_position, _("_Accounts"), acc_menu)


def get_encryption_menu() -> GajimMenu:

    menuitems: MenuItemListT = [
        (_("Disabled"), "win.set-encryption", ""),
        ("OMEMO", "win.set-encryption", "OMEMO"),
        ("OpenPGP", "win.set-encryption", "OpenPGP"),
        ("PGP", "win.set-encryption", "PGP"),
    ]

    return GajimMenu.from_list(menuitems)


def get_message_input_extra_context_menu() -> Gio.Menu:
    menuitems: MenuItemListT = [
        (_("Clear"), "win.input-clear", None),
        (_("Paste as Code Block"), "win.paste-as-code-block", None),
        (_("Paste as Quote"), "win.paste-as-quote", None),
    ]

    menu = GajimMenu.from_list(menuitems)
    extra_menu = Gio.Menu()
    extra_menu.append_section(None, menu)
    return extra_menu


def get_conv_action_context_menu(account: str, selected_text: str) -> Gio.Menu:
    menuitems: MenuItemListT = []

    selected_text_short = textwrap.shorten(selected_text, width=10, placeholder="…")

    uri_text = quote(selected_text.encode("utf-8"))

    # Wikipedia search
    if app.settings.get("always_english_wikipedia"):
        uri = f"https://en.wikipedia.org/wiki/" f"Special:Search?search={uri_text}"
    else:
        uri = (
            f"https://{get_short_lang_code()}.wikipedia.org/"
            f"wiki/Special:Search?search={uri_text}"
        )
    variant = GLib.Variant.new_strv([account, uri])
    menuitems.append((_("Read _Wikipedia Article"), "app.open-link", variant))

    # Dictionary search
    dictionary_title = _("Look it up in _Dictionary")
    dict_link = app.settings.get("dictionary_url")
    if dict_link == "WIKTIONARY":
        # Default is wikitionary.org
        if app.settings.get("always_english_wiktionary"):
            uri = f"https://en.wiktionary.org/wiki/" f"Special:Search?search={uri_text}"
        else:
            uri = (
                f"https://{get_short_lang_code()}.wiktionary.org/"
                f"wiki/Special:Search?search={uri_text}"
            )
    else:
        if dict_link.find("%s") == -1:
            # There has to be a '%s' in the url if it’s not WIKTIONARY
            dictionary_title = _('Dictionary URL is missing a "%s"')
        else:
            uri = dict_link % uri_text

    variant = GLib.Variant.new_strv([account, uri])
    menuitems.append((dictionary_title, "app.open-link", variant))

    # Generic search
    search_link = app.settings.get("search_engine")
    if search_link.find("%s") == -1:
        # There has to be a '%s' in the url
        search_title = _('Web Search URL is missing a "%s"')
    else:
        search_title = _("Web _Search for it")
        uri = search_link % uri_text

    variant = GLib.Variant.new_strv([account, uri])
    menuitems.append((search_title, "app.open-link", variant))

    # Open as URI
    variant = GLib.Variant.new_strv([account, f"https://{uri_text}"])
    menuitems.append((_("Open as _Link"), "app.open-link", variant))

    menu = GajimMenu.from_list(menuitems)
    extra_menu = Gio.Menu()
    extra_menu.append_section(
        _('Actions for "%s"') % escape_mnemonic(selected_text_short), menu
    )
    return extra_menu


def _xmpp_message_query_context_menu(uri: URI, account: str) -> UriMenuItemsT:
    jid = uri.data["jid"]
    # qparams = uri.query_params
    return [
        ("copy-text", [uri.source], _("Copy Link Location")),
        ("copy-text", [jid], _("Copy XMPP Address")),
        ("open-chat", [account, jid], _("Start Chat…")),
        # ^ TODO: pass qparams ^
        (f"{account}-add-contact", [account, jid], _("Add to Contact List…")),
    ]


def _xmpp_join_query_context_menu(uri: URI, account: str) -> UriMenuItemsT:
    return [
        ("copy-text", [uri.source], _("Copy Link Location")),
        ("copy-text", [uri.data["jid"]], _("Copy XMPP Address")),
        (
            "open-chat",
            [account, uri.data["jid"]],
            # ^ TODO: pass qparams ^
            _("Join Groupchat…"),
        ),
    ]


_xmpp_uri_context_menus: dict[XmppUriQuery, UriMenuBuilderT] = {
    XmppUriQuery.NONE: _xmpp_message_query_context_menu,
    XmppUriQuery.MESSAGE: _xmpp_message_query_context_menu,
    XmppUriQuery.JOIN: _xmpp_join_query_context_menu,
}


def _xmpp_uri_context_menu(uri: URI, account: str) -> UriMenuItemsT:
    return _xmpp_uri_context_menus[XmppUriQuery.from_str_or_none(uri.query_type)](
        uri, account
    )


def _web_uri_context_menu(uri: URI, _account: str) -> UriMenuItemsT:
    return [
        ("copy-text", [uri.source], _("Copy Link Location")),
        ("open-link", ["", uri.source], _("Open Link in Browser")),
    ]


def _mailto_uri_context_menu(uri: URI, _account: str) -> UriMenuItemsT:
    return [
        ("copy-text", [uri.source], _("Copy Link Location")),
        ("copy-text", [uri.data["addr"]], _("Copy Email Address")),
        ("open-link", ["", uri.source], _("Open Email Composer")),
    ]


def _geo_uri_context_menu(uri: URI, _account: str) -> UriMenuItemsT:
    return [
        ("copy-text", [uri.source], _("Copy Link Location")),
        ("open-link", ["", uri.source], _("Show Location")),
    ]


def _ambiguous_addr_context_menu(uri: URI, account: str) -> UriMenuItemsT:
    addr = uri.data["addr"]
    mailto = "mailto:" + escape_iri_path_segment(addr)
    return [
        ("copy-text", [addr], _("Copy XMPP Address/Email")),
        ("open-link", ["", mailto], _("Open Email Composer")),
        ("open-chat", [account, addr], _("Start Chat…")),
        (f"{account}-add-contact", [account, addr], _("Add to Contact List…")),
    ]


def _file_uri_context_menu(uri: URI, _account: str) -> UriMenuItemsT:
    canopen = app.settings.get("allow_open_file_uris")
    pathobj = filesystem_path_from_uri(uri.source)
    return [
        ("copy-text", [uri.source], _("Copy Link Location")),
        ("open-link" if canopen else "-", ["", uri.source], _("Open Path")),
        ("copy-text" if pathobj else "-", [str(pathobj)], _("Copy Path")),
    ]


def _tel_uri_context_menu(uri: URI, account: str) -> UriMenuItemsT:
    return [
        ("copy-text", [uri.source], _("Copy Link Location")),
        ("open-link", [account, uri.source], _("Dial Number")),
        # TODO:
        # ('copy-text', [uri.data['number']], _('Copy Number')),
    ]


def _other_uri_context_menu(uri: URI, account: str) -> UriMenuItemsT:
    return [
        ("copy-text", [uri.source], _("Copy Link Location")),
        ("open-link", [account, uri.source], _("Open Link")),
    ]


_uri_context_menus: dict[URIType, UriMenuBuilderT] = {
    URIType.XMPP: _xmpp_uri_context_menu,
    URIType.MAIL: _mailto_uri_context_menu,
    URIType.GEO: _geo_uri_context_menu,
    URIType.WEB: _web_uri_context_menu,
    URIType.FILE: _file_uri_context_menu,
    URIType.AT: _ambiguous_addr_context_menu,
    URIType.TEL: _tel_uri_context_menu,
    URIType.OTHER: _other_uri_context_menu,
}


def get_uri_context_menu(account: str, uri: URI) -> Gio.Menu:
    assert uri.type != URIType.INVALID  # it really begs to be a separate class

    menuitems: MenuItemListT = []

    for action, args, label in _uri_context_menus[uri.type](uri, account):
        if len(args) == 1:
            value = GLib.Variant.new_string(args[0])
        else:
            value = GLib.Variant.new_strv(args)

        menuitems.append(
            (label, f"app.{action}", value),
        )

    menu = GajimMenu.from_list(menuitems)
    extra_menu = Gio.Menu()
    extra_menu.append_section(None, menu)
    return extra_menu


def get_account_notifications_menu(account: str) -> GajimMenu:
    menuitems: MenuItemListT = [
        (
            _("Deny all subscription requests"),
            f"win.subscription-deny-all-{account}",
            None,
        ),
    ]
    return GajimMenu.from_list(menuitems)


def get_subscription_menu(account: str, jid: JID) -> GajimMenu:
    params = AddChatActionParams(account=account, jid=jid, type="chat", select=True)
    value = str(jid)
    menuitems: MenuItemListT = [
        (_("Start Chat"), "win.add-chat", params),
        (_("Details"), f"win.contact-info-{account}", value),
        (_("Block"), f"win.subscription-block-{account}", value),
        (_("Report"), f"win.subscription-report-{account}", value),
        (_("Deny"), f"win.subscription-deny-{account}", value),
    ]

    return GajimMenu.from_list(menuitems)


def get_start_chat_button_menu() -> GajimMenu:

    value = GLib.Variant("as", ["", ""])

    menuitems: MenuItemListT = [
        (_("Start Chat…"), "app.start-chat", value),
        (_("Create Group Chat…"), "app.create-groupchat", ""),
        (_("Add Contact…"), "app.add-contact", ""),
    ]

    return GajimMenu.from_list(menuitems)


def get_start_chat_row_menu(account: str, jid: JID) -> GajimMenu:
    params = AccountJidParam(account=account, jid=jid)
    menuitems: MenuItemListT = [
        (_("Forget this Group Chat"), "app.forget-groupchat", params),
    ]

    return GajimMenu.from_list(menuitems)


def get_chat_list_row_menu(
    workspace_id: str, account: str, jid: JID, pinned: bool
) -> GajimMenu:

    client = app.get_client(account)
    contact = client.get_module("Contacts").get_contact(jid)
    assert isinstance(contact, BareContact | GroupchatContact | GroupchatParticipant)

    menu = GajimMenu()

    params = ChatListEntryParam(
        workspace_id=workspace_id,
        source_workspace_id=workspace_id,
        account=account,
        jid=jid,
    )

    toggle_label = _("Unpin Chat") if pinned else _("Pin Chat")
    menu.add_item(toggle_label, "win.toggle-chat-pinned", params)

    submenu = menu.add_submenu(_("Move Chat"))
    if app.settings.get_workspace_count() > 1:
        for name, params in get_workspace_params(workspace_id, account, jid):
            submenu.add_item(name, "win.move-chat-to-workspace", params)

    params = ChatListEntryParam(
        workspace_id="", source_workspace_id=workspace_id, account=account, jid=jid
    )

    submenu.add_item(_("New Workspace"), "win.move-chat-to-workspace", params)

    if can_add_to_roster(contact):
        params = AccountJidParam(account=account, jid=jid)
        menu.add_item(_("Add to Contact List…"), "win.add-to-roster", params)

    if app.window.get_chat_unread_count(account, jid, include_silent=True):
        params = AccountJidParam(account=account, jid=jid)
        menu.add_item(_("Mark as read"), f"app.{account}-mark-as-read", params)

    if contact.is_muted:
        menu.add_item(
            _("Unmute Chat"),
            "app.mute-chat",
            MuteContactParam(account=account, jid=jid, state=MuteState.UNMUTE),
        )
    else:
        submenu = menu.add_submenu(_("Mute Chat"))
        for state, label in MuteState.iter():
            submenu.add_item(
                label,
                "app.mute-chat",
                MuteContactParam(account=account, jid=jid, state=state),
            )

    return menu


def get_workspace_params(
    current_workspace_id: str, account: str, jid: JID
) -> Iterator[tuple[str, ChatListEntryParam]]:

    for workspace_id in app.settings.get_workspaces():
        if workspace_id == current_workspace_id:
            continue
        name = app.settings.get_workspace_setting(workspace_id, "name")
        params = ChatListEntryParam(
            workspace_id=workspace_id,
            source_workspace_id=current_workspace_id,
            account=account,
            jid=jid,
        )
        yield name, params


def get_groupchat_admin_menu(
    self_contact: types.GroupchatParticipant, contact: types.GroupchatParticipant
) -> GajimMenu:

    menu = GajimMenu()

    if contact.real_jid is None:
        menu.add_item(_("Not Available"), "dummy", None)
        return menu

    action = "win.muc-change-affiliation"
    real_jid = str(contact.real_jid)

    if is_affiliation_change_allowed(self_contact, contact, "owner"):
        value = GLib.Variant("as", [real_jid, "owner"])
        menu.add_item(_("Make Owner"), action, value)

    if is_affiliation_change_allowed(self_contact, contact, "admin"):
        value = GLib.Variant("as", [real_jid, "admin"])
        menu.add_item(_("Make Admin"), action, value)

    if is_affiliation_change_allowed(self_contact, contact, "member"):
        value = GLib.Variant("as", [real_jid, "member"])
        menu.add_item(_("Make Member"), action, value)

    if is_affiliation_change_allowed(self_contact, contact, "none"):
        value = GLib.Variant("as", [real_jid, "none"])
        menu.add_item(_("Revoke Member"), action, value)

    if is_affiliation_change_allowed(self_contact, contact, "outcast"):
        menu.add_item(_("Ban…"), "win.muc-ban", real_jid)

    if not menu.get_n_items():
        menu.add_item(_("Not Available"), "dummy", None)

    return menu


def get_groupchat_mod_menu(
    self_contact: types.GroupchatParticipant, contact: types.GroupchatParticipant
) -> GajimMenu:

    menu = GajimMenu()

    if not contact.is_available:
        menu.add_item(_("Not Available"), "dummy", None)
        return menu

    contact_name = str(contact.name)

    if is_role_change_allowed(self_contact, contact):
        menu.add_item(_("Kick…"), "win.muc-kick", contact_name)

    action = "win.muc-change-role"

    if is_role_change_allowed(self_contact, contact):
        if contact.role.is_visitor:
            value = GLib.Variant("as", [contact_name, "participant"])
            menu.add_item(_("Grant Voice"), action, value)
        else:
            value = GLib.Variant("as", [contact_name, "visitor"])
            menu.add_item(_("Revoke Voice"), action, value)

    if not menu.get_n_items():
        menu.add_item(_("Not Available"), "dummy", None)

    return menu


def get_groupchat_participant_menu(
    account: str,
    self_contact: types.GroupchatParticipant,
    contact: types.GroupchatParticipant,
) -> GajimMenu:

    group_chat = self_contact.room
    disco = group_chat.get_disco()
    assert disco is not None
    muc_prefer_direct_msg = app.settings.get("muc_prefer_direct_msg")
    if disco.muc_is_nonanonymous and muc_prefer_direct_msg:
        assert contact.real_jid is not None
        dm_params = AddChatActionParams(
            account=account, jid=contact.real_jid, type="chat", select=True
        )
    else:
        dm_params = AddChatActionParams(
            account=account, jid=contact.jid, type="pm", select=True
        )

    value = str(contact.name)

    general_items: MenuItemListT = [
        (_("Direct Message…"), "win.add-chat", dm_params),
        (_("Details"), "win.muc-contact-info", value),
        (_("Execute Command…"), "win.muc-execute-command", value),
    ]

    real_contact = contact.get_real_contact()
    if real_contact is not None and can_add_to_roster(real_contact):
        value = GLib.Variant("as", [account, str(real_contact.jid)])
        action = f"app.{account}-add-contact"
        general_items.insert(1, (_("Add to Contact List…"), action, value))

    mod_menu = get_groupchat_mod_menu(self_contact, contact)
    admin_menu = get_groupchat_admin_menu(self_contact, contact)

    menu = GajimMenu.from_list(general_items)
    menu.append_section(_("Moderation"), mod_menu)
    menu.append_section(_("Administration"), admin_menu)
    return menu


def get_component_search_menu(jid: str | None, copy_text: str) -> GajimMenu:
    menuitems: MenuItemListT = [
        (_("Copy"), "app.copy-text", copy_text),
    ]

    if jid is not None:
        menuitems.append((_("Start Chat…"), "app.start-chat", jid))

    return GajimMenu.from_list(menuitems)


def get_chat_row_menu(
    contact: types.ChatContactT,
    name: str,
    text: str,
    timestamp: datetime,
    message_id: str | None,
    stanza_id: str | None,
    pk: int | None,
    corrected_pk: int | None,
    state: MessageState,
    is_moderated: bool,
    occupant_id: str | None,
) -> GajimMenu:

    menu_items: MenuItemListT = []

    # Text can be an empty string,
    # e.g. if a preview has not been loaded yet
    if text:
        timestamp_formatted = timestamp.strftime(app.settings.get("date_time_format"))

        copy_text = f"{timestamp_formatted} - {name}: "
        if text.startswith(("```", "> ")):
            # Prepend a line break in order to keep code block/quotes rendering
            copy_text += "\n"
        copy_text += text

        menu_items.append(
            (p_("Message row action", "Copy"), "win.copy-message", copy_text)
        )

        show_quote = True
        if isinstance(contact, GroupchatContact):
            if contact.is_joined and state == MessageState.ACKNOWLEDGED:
                self_contact = contact.get_self()
                assert self_contact is not None
                show_quote = not self_contact.role.is_visitor
            else:
                show_quote = False

        show_reply = True
        if isinstance(contact, GroupchatContact):
            if contact.is_joined and stanza_id is not None:
                self_contact = contact.get_self()
                assert self_contact is not None
                show_reply = not self_contact.role.is_visitor
            else:
                show_reply = False

        if not show_reply and show_quote:
            # Use XEP-0393 quotes if XEP-0461 message reply is not available
            menu_items.append((p_("Message row action", "Quote…"), "win.quote", text))

    show_correction = False
    if message_id is not None:
        show_correction = app.window.is_message_correctable(contact, message_id)
    if show_correction:
        menu_items.append(
            (p_("Message row action", "Correct…"), "win.correct-message", None)
        )

    if isinstance(contact, GroupchatContact) and contact.is_joined:
        resource_contact = contact.get_resource(name)
        self_contact = contact.get_self()
        assert self_contact is not None
        is_allowed = is_moderation_allowed(self_contact, resource_contact)

        disco_info = app.storage.cache.get_last_disco_info(contact.jid)
        assert disco_info is not None

        if (
            disco_info.has_message_moderation
            and stanza_id is not None
            and state == MessageState.ACKNOWLEDGED
            and not is_moderated
            and is_allowed
        ):

            ns = disco_info.moderation_namespace
            assert ns is not None
            param = ModerateMessageParam(
                account=contact.account,
                jid=contact.jid,
                stanza_id=stanza_id,
                namespace=ns,
            )
            menu_items.append(
                (p_("Message row action", "Moderate…"), "win.moderate-message", param)
            )

            if occupant_id is not None:
                param = ModerateAllMessagesParam(
                    account=contact.account,
                    jid=contact.jid,
                    occupant_id=occupant_id,
                    nickname=resource_contact.name,
                    namespace=ns,
                )
                menu_items.append(
                    (
                        p_("Message row action", "Moderate all messages…"),
                        "win.moderate-all-messages",
                        param,
                    )
                )

    menu_items.append(
        (
            p_("Message row action", "Select Messages…"),
            "win.activate-message-selection",
            GLib.Variant("u", corrected_pk or 0),
        )
    )

    if pk is not None and state == MessageState.ACKNOWLEDGED:
        param = DeleteMessageParam(account=contact.account, jid=contact.jid, pk=pk)

        menu_items.append(
            (
                p_("Message row action", "Delete Message Locally…"),
                "win.delete-message-locally",
                param,
            )
        )

    return GajimMenu.from_list(menu_items)


def get_preview_menu(preview: Preview) -> GajimMenu:
    menu_items: MenuItemListT = []

    download = (_("_Download"), "win.preview-download", preview.id)
    open_file = (_("_Open"), "win.preview-open", preview.id)
    save_as = (_("_Save as…"), "win.preview-save-as", preview.id)
    open_folder = (_("Open _Folder"), "win.preview-open-folder", preview.id)
    copy_link = (_("_Copy Link"), "win.preview-copy-link", preview.id)
    open_link = (_("Open Link in _Browser"), "win.preview-open-link", preview.id)

    if preview.is_geo_uri:
        menu_items.append(open_file)
        menu_items.append(copy_link)
        return GajimMenu.from_list(menu_items)

    if preview.orig_exists:
        menu_items.append(open_file)
        menu_items.append(save_as)
        menu_items.append(open_folder)
    else:
        if not preview.download_in_progress:
            menu_items.append(download)

    menu_items.append(copy_link)

    if not preview.is_aes_encrypted:
        menu_items.append(open_link)

    return GajimMenu.from_list(menu_items)


def get_format_menu() -> GajimMenu:

    menuitems: MenuItemListT = [
        (_("bold"), "win.input-bold", None),
        (_("italic"), "win.input-italic", None),
        (_("strike"), "win.input-strike", None),
    ]

    return GajimMenu.from_list(menuitems)


def get_workspace_menu(workspace_id: str) -> GajimMenu:
    remove_action = "win.dummy"
    if app.settings.get_workspace_count() > 1:
        remove_action = "win.remove-workspace"

    menuitems: MenuItemListT = [
        (_("Mark as read"), "win.mark-workspace-as-read", workspace_id),
        (_("Edit…"), "win.edit-workspace", workspace_id),
        (_("Remove"), remove_action, workspace_id),
    ]

    return GajimMenu.from_list(menuitems)


def get_manage_roster_menu(groups: list[str], single_selection: bool) -> GajimMenu:
    menu = GajimMenu()

    menuitems: MenuItemListT = [(_("New Group…"), "win.move-to-new-group", None)]

    for group in groups:
        menuitems.append((group, "win.move-to-group", group))

    menu.append_submenu(_("Move to Group"), GajimMenu.from_list(menuitems))

    menuitems: MenuItemListT = [(_("New Group…"), "win.add-to-new-group", None)]

    for group in groups:
        menuitems.append((group, "win.add-to-group", group))

    menu.append_submenu(_("Add to Group"), GajimMenu.from_list(menuitems))

    menu.add_item(_("Remove from Group"), "win.remove-from-group", None)
    if single_selection:
        menu.add_item(_("Rename…"), "win.change-name", None)

    menu.add_item(_("Remove from Contact List…"), "win.remove-from-roster", None)

    return menu


def get_manage_roster_import_menu(accounts: list[tuple[str, str]]) -> GajimMenu:
    menu = GajimMenu()
    menu.add_item(_("Import from File"), "win.import-from-file", None)

    if accounts:
        menuitems: MenuItemListT = []
        for account, label in accounts:
            menuitems.append((label, "win.import-from-account", account))

        menu.append_submenu(_("Import from Account"), GajimMenu.from_list(menuitems))
    else:
        menu.add_item(_("Import from Account"), "", None)

    return menu


def escape_mnemonic(label: str | None) -> str | None:
    if label is None:
        return None
    # Underscore inside a label means the next letter is a keyboard
    # shortcut. To show an underscore we have to use double underscore
    return label.replace("_", "__")
