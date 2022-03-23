# Welcome to Gajim

### Runtime Requirements

- python3.9 or higher
- python3-gi
- python3-gi-cairo
- gir1.2-gtk-3.0 (>=3.22)
- gir1.2-gtksource-4
- python3-nbxmpp (>=2.99.0)
- python3-openssl (>=16.2)
- python3-css-parser
- python3-keyring
- python3-precis-i18n
- python3-packaging
- python3-setuptools
- gir1.2-soup-2.4
- gir1.2-farstream-0.2, gir1.2-gstreamer-1.0 gir1.2-gst-plugins-base-1.0, gstreamer1.0-plugins-ugly, gstreamer1.0-libav, and gstreamer1.0-gtk3 for audio and video calls
- GLib (>=2.60.0)

### Optional Runtime Requirements

- python3-pil (pillow) for support of webp avatars
- python3-sentry-sdk for Sentry error reporting to dev.gajim.org (users decide whether to send reports or not)
- gir1.2-gspell-1 and hunspell-LANG where lang is your locale eg. en, fr etc
- gir1.2-secret-1 for GNOME Keyring or KDE support as password storage
- D-Bus running to have gajim-remote working
- gir1.2-gupnpigd-1.0 for better NAT traversing
- gir1.2-networkmanager-1.0 for network lose detection
- gir1.2-geoclue-2.0 for sharing your location
- gir1.2-gsound-1.0 for sound on Linux

### Compile-time Requirements

- python3-setuptools
- gettext

### Running Tests

`python -m unittest discover -s test`

### Installation Procedure

#### Packages

- [Arch Linux](https://www.archlinux.org/packages/community/any/gajim/)
- [Debian](https://packages.debian.org/stable/gajim)
- [Fedora](https://apps.fedoraproject.org/packages/gajim)
- [Ubuntu](https://packages.ubuntu.com/gajim)
- [FreeBSD](https://www.freshports.org/net-im/gajim/)

#### Flatpak

see [README](./flatpak/README.md)

#### Snapshots

- [Daily Linux](https://www.gajim.org/downloads/snap/)
- [Daily Windows](https://gajim.org/downloads/snap/win)

#### Linux

    pip install .

#### Mac

see [Wiki](https://dev.gajim.org/gajim/gajim/wikis/help/gajimmacosx#python3brew)

#### Developing

For developing you don't have to install Gajim.

After installing all dependencies execute

    ./launch.py

#### Windows

see [README](./win/README.md)

### Miscellaneous

#### Debugging

Execute gajim with `--verbose`

#### Links

- [FAQ](https://dev.gajim.org/gajim/gajim/wikis/help/gajimfaq)
- [Wiki](https://dev.gajim.org/gajim/gajim/wikis/home)

That is all, **enjoy**!

(C) 2003-2022
The Gajim Team
[https://gajim.org](https://gajim.org)

We use original art and parts of sounds and other art from Psi, Gossip, Gnomebaker, Gaim
and some icons from various gnome-icons (mostly Dropline Etiquette) we found at art.gnome.org.
If you think we're violating a license please inform us. Thank you.
