# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import Any

import argparse
import logging
import sys

from gi.repository import Gio
from gi.repository import GLib

LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
log = logging.getLogger()


OBJ_PATH = "/org/gajim/dbus/RemoteObject"
INTERFACE = "org.gajim.dbus.RemoteInterface"
SERVICE = "org.gajim.Gajim"

SIGNATURES = {
    "list_contacts": "(s)",
    "list_accounts": "()",
    "change_status": "(sss)",
    "send_chat_message": "(sss)",
    "send_groupchat_message": "(sss)",
    "account_info": "(s)",
    "get_status": "(s)",
    "get_status_message": "(s)",
    "get_unread_msgs_number": "()",
}


def call_method(args: argparse.Namespace) -> Any:
    arg_dict = vars(args)
    app_id = arg_dict.pop("app_id")
    command = arg_dict.pop("command")

    proxy = Gio.DBusProxy.new_for_bus_sync(
        Gio.BusType.SESSION,
        Gio.DBusProxyFlags.NONE,
        None,
        app_id,
        OBJ_PATH,
        INTERFACE,
        None,
    )

    arguments = tuple(arg_dict.values())
    signature = SIGNATURES[command]
    method = getattr(proxy, command)
    return method(signature, *arguments)


def create_arg_parser() -> argparse.ArgumentParser:

    account_help = "The account the command is executed for"

    parser = argparse.ArgumentParser(prog="gajim-remote")
    parser.add_argument("--app-id", default=SERVICE)

    subparsers = parser.add_subparsers(
        required=True, metavar="commands", dest="command"
    )

    subparser = subparsers.add_parser("list_contacts", help="Get all roster contacts")
    subparser.add_argument("account", type=str)

    subparser = subparsers.add_parser("list_accounts", help="Get the list of accounts")

    subparser = subparsers.add_parser("change_status", help="Change the status")
    subparser.add_argument("status", choices=["offline", "online", "away", "xa", "dnd"])
    subparser.add_argument("message", type=str)
    subparser.add_argument("account", type=str)

    subparser = subparsers.add_parser(
        "send_chat_message", help="Send a chat message to a contact"
    )
    subparser.add_argument("address", type=str, help="The XMPP address of the contact")
    subparser.add_argument("message", type=str, help="The message to be sent")
    subparser.add_argument("account", type=str, help=account_help)

    subparser = subparsers.add_parser(
        "send_groupchat_message", help="Send a chat message to a group chat"
    )
    subparser.add_argument(
        "address", type=str, help="The XMPP address of the group chat"
    )
    subparser.add_argument("message", type=str, help="The message to be sent")
    subparser.add_argument("account", type=str, help=account_help)

    subparser = subparsers.add_parser("account_info", help="Get account details")
    subparser.add_argument("account", type=str, help=account_help)

    subparser = subparsers.add_parser("get_status", help="Get the current status")
    subparser.add_argument("account", type=str, help=account_help)

    subparser = subparsers.add_parser(
        "get_status_message", help="Get the current status message"
    )
    subparser.add_argument("account", type=str, help=account_help)

    subparser = subparsers.add_parser(
        "get_unread_msgs_number", help="Get the unread message count"
    )

    return parser


def run() -> None:
    args = create_arg_parser().parse_args()
    try:
        result = call_method(args)
    except GLib.Error as error:
        quark = GLib.quark_try_string("g-dbus-error-quark")
        if error.matches(quark, Gio.DBusError.SERVICE_UNKNOWN):
            log.error(
                "Service not found. Check if Gajim is running. "
                "If Gajim is running under a custom profile use "
                "--app-id=org.gajim.Gajim.myprofilename"
            )

        else:
            log.exception("Failed to execute method")

        sys.exit(1)

    except Exception:
        log.exception("Failed to execute method")
        sys.exit(1)

    print(result)
