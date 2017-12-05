# Welcome to Gajim


### Runtime Requirements

- python3.4 or higher
- python3-gi
- python3-gi-cairo
- gir1.2-gtk-3.0
- python3-nbxmpp
- python3-openssl (>=0.14)
- python3-pyasn1


### Optional Runtime Requirements

- python-pillow for support of webp avatars
- python3-crypto to enable End to end encryption
- python3-gnupg to enable GPG encryption
- For zeroconf (bonjour) you need dbus-glib, python-avahi
- gir1.2-gspell-1 and hunspell-LANG where lang is your locale eg. en, fr etc
- gir1.2-secret-1 for GNOME Keyring or KDE support as password storage
- D-Bus running to have gajim-remote working. Some distributions split dbus-x11, which is needed for dbus to work with Gajim. Version >= 0.80 is required.
- python3-dbus bindings (>=1.2.0)
- gir1.2-farstream-0.2, gir1.2-gstreamer-1.0 and gir1.2-gst-plugins-base-1.0 for audio and video calls
- gir1.2-gupnpigd-1.0 for better NAT traversing
- gir1.2-networkmanager-1.0 for network lose detection
- gir1.2-geoclue-2.0 for sharing your location
- python3-idna and python3-precis-i18n for correctly parsing JIDs

### Compile-time Requirements

- python-setuptools


### Installation Procedure

#### Packages

- [Arch](https://aur.archlinux.org/packages/gajim-git/)
- [Debian](https://packages.debian.org/source/experimental/gajim) (tested with Debian ``testing`` and ``unstable``)

#### Snapshots

- [Daily Linux](https://www.gajim.org/downloads/snap/?M=D)
- [Daily Windows](https://gajim.org/downloads/snap/win)

#### Linux

``./setup.py install --root=/``

or

``pip install .`` (python-pip is required)

#### Mac

see [Wiki](https://dev.gajim.org/gajim/gajim/wikis/help/gajimmacosx#python3brew)

#### Developing

For developing you dont have to install Gajim.

After installing all dependencys execute

``./launch.py``

#### Flatpak

see [README](./flatpak/README.md)

#### Windows

see [README](./win/README.md)

### Miscellaneous

#### Debugging

Execute gajim with --verbose

#### Links

- [FAQ](https://dev.gajim.org/gajim/gajim/wikis/help/gajimfaq)
- [Wiki](https://dev.gajim.org/gajim/gajim/wikis/home)



That is all, **enjoy**!

(C) 2003-2017
The Gajim Team
[https://gajim.org](https://gajim.org)


We use original art and parts of sounds and other art from Psi, Gossip, Gnomebaker, Gaim and some icons from various gnome-icons (mostly Dropline Etiquette) we found at art.gnome.org If you think we're violating a license please inform us. Thank you.