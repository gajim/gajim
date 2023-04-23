% gajim(1) | Manual
% Philipp Hörist, Daniel Brötzmann, Yann Leboulanger
% August 2022

# NAME

gajim - a fully-featured XMPP chat client

# SYNOPSIS

gajim -h\
gajim \--show\
gajim \--start-chat\
gajim [-q] [-v] [-w] [-l subsystem=level] [-p name] [-s] [-c directory] [\--gdebug] [\--cprofile]

# DESCRIPTION

**gajim** aims to be an easy to use and fully-featured XMPP client. Just chat with your friends or
family, easily share pictures and thoughts or discuss the news with your groups. Chat securely
with End-to-End encryption via OMEMO or OpenPGP.  gajim integrates well with your other devices:
simply continue conversations on your mobile device.

XMPP is the Extensible Messaging and Presence Protocol, a set of open technologies for instant
messaging, presence, multi-party chat, voice and video calls, collaboration, lightweight middle‐
ware, content syndication, and generalized routing of XML data. For more information on the XMPP
protocol see https://xmpp.org/about/.

# OPTIONS

`-h, --help`

: Show help options

`-V, --version`
: Show the application's version

`-q, --quiet`
: Show only critical errors

`-s, --separate`
: Separate profile files completely (even history database and plugins)

`-v, --verbose`
: Print XML stanzas and other debug information

`-p, --profile=NAME`
: Use defined profile in configuration directory

`-c, --config-path=PATH`
: Set configuration directory

`-l, --loglevel=SUBSYSTEM=LEVEL`
: Configure logging.

    SUBSYSTEM e.g. gajim.c.m\
    LEVEL (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Example: gajim.c.m=DEBUG

`-w, --warnings`
: Show all warnings

`--gdebug`
: Sets an environment variable so GLib debug messages are printed

`--cprofile`
: Profile application with cprofile

`--start-chat`
: Start a new chat

# FILES

$XDG_CACHE_HOME/gajim/
: The directory for cached data.

$XDG_CONFIG_HOME/gajim/
: The directory where settings and configurations are stored.

$XDG_DATA_HOME/gajim/
: The directory where all persistent data, e.g. the message database, is stored.

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
