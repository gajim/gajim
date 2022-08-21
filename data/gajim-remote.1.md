% gajim-remote(1) | Manual
% Philipp Hörist, Yann Leboulanger
% August 2022

# NAME

gajim-remote - a remote control utility for **gajim**(1)

# SYNOPSIS

gajim-remote -h\
gajim-remote *command* [arguments ...]

# DESCRIPTION

gajim-remote is an application to control and communicate with a running instance of **gajim**(1) via dbus.

# OPTIONS

`-h, --help`
: Display the help

`--app-id` APP_ID
: The application id of the running **gajim**(1) instance

# COMMANDS

`list_contacts` account
: Get all roster contacts

`list_accounts`
: Get the list of accounts

`change_status` {offline,online,away,xa,dnd} message account
: Change the status

`send_chat_message` address message account
: Send a chat message to a contact

`send_groupchat_message` address message account
: Send a chat message to a group chat

`account_info` account
: Get account details

`get_status` account
: Get the current status

`get_status_message` account
: Get the current status message

`get_unread_msgs_number`
: Get the unread message count

# BUGS

Please submit bugs at https://dev.gajim.org/gajim/gajim/issues.

# SUPPORT

You are welcome to join us at xmpp:gajim@conference.gajim.org?join.

# COPYRIGHT

gajim is free software; you can redistribute it and/or modify it under the
terms of the GNU General Public License as published by the
Free Software Foundation; version 3 only.

gajim is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
or FITNESS FOR A PARTICULAR PURPOSE.
See the GNU General Public License for more details.
