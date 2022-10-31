# Welcome to Gajim

### Runtime Requirements

- [Python](https://www.python.org/) (>=3.9)
- [PyGObject](https://pypi.org/project/PyGObject/) (>=3.42.0)
- [pycairo](https://pypi.org/project/pycairo/)
- [cairo](https://gitlab.freedesktop.org/cairo/cairo) (>=1.16.0)
- [nbxmpp](https://pypi.org/project/nbxmpp/) (>=3.2.5)
- [pyOpenSSL](https://pypi.org/project/pyOpenSSL/) (>=16.2)
- [css-parser](https://pypi.org/project/css-parser/)
- [keyring](https://pypi.org/project/keyring/)
- [precis_i18n](https://pypi.org/project/precis-i18n/)
- [packaging](https://pypi.org/project/packaging/)
- [Pillow](https://pypi.org/project/Pillow/)
- [setuptools](https://pypi.org/project/setuptools/)
- [Gtk3](https://gitlab.com/gnome/gtk) (>=3.24.30)
- [GLib](https://gitlab.com/gnome/glib) (>=2.60.0)
- [GtkSourceView](https://gitlab.gnome.org/GNOME/gtksourceview)
- [Pango](https://gitlab.gnome.org/GNOME/pango) (>=1.50.0)
- [libsoup](https://gitlab.gnome.org/GNOME/libsoup/)
- [sqlite](https://www.sqlite.org/) (>=3.33.0)

### Optional Runtime Requirements

- D-Bus running to have gajim-remote working
- [sentry-sdk](https://pypi.org/project/sentry-sdk/) for Sentry error reporting to dev.gajim.org (users decide whether to send reports or not)
- [gspell](https://gitlab.gnome.org/GNOME/gspell) and hunspell-LANG where lang is your locale eg. en, fr etc
- [libsecret](https://gitlab.gnome.org/GNOME/libsecret/) for GNOME Keyring or KDE support as password storage
- [GUPnP-IGD](https://gitlab.gnome.org/GNOME/gupnp) for better NAT traversing
- [NetworkManager](https://gitlab.freedesktop.org/NetworkManager/NetworkManager) for network lose detection
- [GeoClue](https://gitlab.freedesktop.org/geoclue/geoclue) for sharing your location
- [GSound](https://gitlab.gnome.org/GNOME/gsound) for sound on Linux

#### For Video and Audio Calls

- [Farstream](https://gitlab.freedesktop.org/farstream/farstream)
- [GStreamer](https://gitlab.freedesktop.org/gstreamer/gstreamer)
- [gst-plugins-base](https://gitlab.freedesktop.org/gstreamer/gst-plugins-base)
- [gst-plugins-ugly](https://gitlab.freedesktop.org/gstreamer/gst-plugins-ugly)
- [gst-libav](https://gitlab.freedesktop.org/gstreamer/gst-libav)

### Compile-time Requirements

- [setuptools](https://pypi.org/project/setuptools/)
- [gettext](https://savannah.gnu.org/projects/gettext/)

### Running Tests

`python -m unittest discover -s test`

### Installation Procedure

#### Packages

- [Arch Linux](https://www.archlinux.org/packages/community/any/gajim/)
- [Debian](https://packages.debian.org/stable/gajim)
- [Fedora](https://packages.fedoraproject.org/pkgs/gajim/)
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

see [Wiki](https://dev.gajim.org/gajim/gajim/-/wikis/help/Gajim-on-macOS)

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
