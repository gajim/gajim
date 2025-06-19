[[_TOC_]]

## Gajim

A fully-featured XMPP chat client.

Gajim aims to be an easy to use and fully-featured XMPP client.
Just chat with your friends or family, easily share pictures and 
thoughts or discuss the news with your groups.

## Requirements

### Runtime Requirements

- [libadwaita](https://gitlab.gnome.org/GNOME/libadwaita) (>=1.7.0)
- [cairo](https://gitlab.freedesktop.org/cairo/cairo) (>=1.16.0)
- [cryptography](https://pypi.org/project/cryptography/) (>=3.4.8)
- [css-parser](https://pypi.org/project/css-parser/)
- [emoji](https://pypi.org/project/emoji/) (>=2.6.0)
- [GLib](https://gitlab.gnome.org/GNOME/glib) (>=2.80.0)
- [Gtk4](https://gitlab.gnome.org/GNOME/gtk) (>=4.17.5)
- [GtkSourceView5](https://gitlab.gnome.org/GNOME/gtksourceview)
- [keyring](https://pypi.org/project/keyring/)
- [nbxmpp](https://pypi.org/project/nbxmpp/) (>=6.2.0)
- [omemo-dr](https://dev.gajim.org/gajim/omemo-dr) (>=1.0.0)
- [packaging](https://pypi.org/project/packaging/)
- [Pango](https://gitlab.gnome.org/GNOME/pango) (>=1.50.0)
- [Pillow](https://pypi.org/project/Pillow/) (>=9.1.0)
- [precis_i18n](https://pypi.org/project/precis-i18n/)
- [pycairo](https://pypi.org/project/pycairo/)
- [PyGObject](https://pypi.org/project/PyGObject/) (>=3.42.0)
- [Python](https://www.python.org/) (>=3.11)
- [qrcode](https://pypi.org/project/qrcode/) (>=7.3.1)
- [setuptools](https://pypi.org/project/setuptools/) (>=65.0.0)
- [SQLAlchemy](https://pypi.org/project/SQLAlchemy/) (>=2.0.0)
- [sqlite](https://www.sqlite.org/) (>=3.35.0)
- [PyWinRT](https://github.com/pywinrt/pywinrt) (Only on Windows)
- [windows-toasts](https://github.com/DatGuy1/Windows-Toasts) (Only on Windows)

### Optional Runtime Requirements

- D-Bus running to have gajim-remote working
- [sentry-sdk](https://pypi.org/project/sentry-sdk/) for Sentry error reporting to dev.gajim.org (users decide whether to send reports or not)
- [libspelling](https://gitlab.gnome.org/GNOME/libspelling) and hunspell-LANG where lang is your locale eg. en, fr etc
- [libsecret](https://gitlab.gnome.org/GNOME/libsecret/) for GNOME Keyring or KDE support as password storage
- [GUPnP-IGD](https://gitlab.gnome.org/GNOME/gupnp) for better NAT traversing
- [NetworkManager](https://gitlab.freedesktop.org/NetworkManager/NetworkManager) for network lose detection
- [GeoClue](https://gitlab.freedesktop.org/geoclue/geoclue) for sharing your location
- [GSound](https://gitlab.gnome.org/GNOME/gsound) for sound on Linux

#### For Video and Audio Calls

- [Farstream](https://gitlab.freedesktop.org/farstream/farstream)
- [GStreamer](https://gitlab.freedesktop.org/gstreamer/gstreamer)
- [gst-plugins-base](https://gitlab.freedesktop.org/gstreamer/gst-plugins-base)
- [gst-plugins-rs](https://gitlab.freedesktop.org/gstreamer/gst-plugins-rs) (for gst-plugin-gtk4)
- [gst-plugins-ugly](https://gitlab.freedesktop.org/gstreamer/gst-plugins-ugly)
- [gst-libav](https://gitlab.freedesktop.org/gstreamer/gst-libav)

#### For Voice Messages

- [GStreamer](https://gitlab.freedesktop.org/gstreamer/gstreamer)
- [gst-plugins-base](https://gitlab.freedesktop.org/gstreamer/gst-plugins-base)
- [gst-plugins-good](https://gitlab.freedesktop.org/gstreamer/gst-plugins-good)

### Build Requirements

- [setuptools](https://pypi.org/project/setuptools/) (>=65.0.0)
- [gettext](https://savannah.gnu.org/projects/gettext/)

To build Gajim a PEP517 build frontend like pip (https://pip.pypa.io/en/stable/) or build (https://pypa-build.readthedocs.io/en/stable/) must be used.

The build frontend takes care of installing all python build requirements. Beware `gettext` is not a python library and cannot be installed by the build frontend.

## Building

### Building the metadata files and translation

```bash
$ ./make.py build -h

usage: make.py build [-h] [--dist {unix,flatpak,flatpak-nightly,win}]
```

Afterwards metadata files can be found in `dist/metadata` folder. 

### Building the wheel

This is only necessary if you need the wheel, otherwise you can skip to the Installing section.

#### Using `build`

```bash
python -m build -w
```

#### Using `pip`

```bash
pip wheel --no-deps --use-pep517 -w dist .
```

## Installing

### Installing with `pip`

```bash
pip install .
```

### Installing the wheel

```bash
pip install dist/name_of_wheel.whl
```

### Installing the metadata files (Unix only)

```bash
$ ./make.py install -h

usage: make.py install [-h] [--dist {unix,flatpak,flatpak-nightly}] [--prefix PREFIX]

options:
  -h, --help            show this help message and exit
  --dist {unix,flatpak,flatpak-nightly}
                        Distribution
  --prefix PREFIX       The path prefix for installation (e.g. "/usr")
```

## Tests

- `python -m unittest discover -s test`
- `python -m unittest ./test/gtk/gui_file.py` (for testing GUI files)

## Packages and install instructions

### Packages

- [Arch Linux](https://www.archlinux.org/packages/extra/any/gajim/)
- [Debian](https://packages.debian.org/stable/gajim)
- [Fedora](https://packages.fedoraproject.org/pkgs/gajim/)
- [FreeBSD](https://www.freshports.org/net-im/gajim/)
- [openSUSE](https://software.opensuse.org/package/gajim)
- [Ubuntu](https://packages.ubuntu.com/gajim)

### Flatpak

see [README](./flatpak/README.md)

### Snapshots

- [Daily Linux](https://www.gajim.org/downloads/snap/)
- [Daily Windows](https://gajim.org/downloads/snap/win)

### Mac

see [Wiki](https://dev.gajim.org/gajim/gajim/-/wikis/help/Gajim-on-macOS)

## Developing

To create a virtualenv you can execute

    ./scripts/dev_env.sh

Be sure all install requirements are available.

Afterwards activate the virtual environment with

    source .venv/bin/activate

It is a good practice to run the development version with a user profile. This ensures that it does not interfere with other installations.

    ./launch.py --user-profile dev

### Windows

see [README](./win/README.md)

## Miscellaneous

### Debugging

Execute gajim with `--verbose`

### Links

- [FAQ](https://dev.gajim.org/gajim/gajim/wikis/help/gajimfaq)
- [Wiki](https://dev.gajim.org/gajim/gajim/wikis/home)

That is all, **enjoy**!

(C) 2003-2025
The Gajim Team
[https://gajim.org](https://gajim.org)

We use original art and parts of sounds and other art from Psi, Gossip, Gnomebaker, Gaim
and some icons from various gnome-icons (mostly Dropline Etiquette) we found at art.gnome.org.
If you think we're violating a license please inform us. Thank you.
