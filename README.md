[[_TOC_]]

## Requirements

### Runtime Requirements

- [Python](https://www.python.org/) (>=3.10)
- [PyGObject](https://pypi.org/project/PyGObject/) (>=3.42.0)
- [pycairo](https://pypi.org/project/pycairo/)
- [cairo](https://gitlab.freedesktop.org/cairo/cairo) (>=1.16.0)
- [nbxmpp](https://pypi.org/project/nbxmpp/) (>=4.2.2)
- [cryptography](https://pypi.org/project/cryptography/) (>=3.4.8)
- [css-parser](https://pypi.org/project/css-parser/)
- [keyring](https://pypi.org/project/keyring/)
- [precis_i18n](https://pypi.org/project/precis-i18n/)
- [packaging](https://pypi.org/project/packaging/)
- [Pillow](https://pypi.org/project/Pillow/)
- [setuptools](https://pypi.org/project/setuptools/) (>=65.0.0)
- [Gtk3](https://gitlab.gnome.org/GNOME/gtk) (>=3.24.30)
- [GLib](https://gitlab.gnome.org/GNOME/glib) (>=2.60.0)
- [GtkSourceView](https://gitlab.gnome.org/GNOME/gtksourceview)
- [Pango](https://gitlab.gnome.org/GNOME/pango) (>=1.50.0)
- [sqlite](https://www.sqlite.org/) (>=3.33.0)
- [axolotl](https://pypi.org/project/python-axolotl/) (>=0.2.3)
- [qrcode](https://pypi.org/project/qrcode/) (>=7.3.1)

### Optional Runtime Requirements

- D-Bus running to have gajim-remote working
- [sentry-sdk](https://pypi.org/project/sentry-sdk/) for Sentry error reporting to dev.gajim.org (users decide whether to send reports or not)
- [gspell](https://gitlab.gnome.org/GNOME/gspell) and hunspell-LANG where lang is your locale eg. en, fr etc
- [libsecret](https://gitlab.gnome.org/GNOME/libsecret/) for GNOME Keyring or KDE support as password storage
- [GUPnP-IGD](https://gitlab.gnome.org/GNOME/gupnp) for better NAT traversing
- [NetworkManager](https://gitlab.freedesktop.org/NetworkManager/NetworkManager) for network lose detection
- [GeoClue](https://gitlab.freedesktop.org/geoclue/geoclue) for sharing your location
- [GSound](https://gitlab.gnome.org/GNOME/gsound) for sound on Linux
- [AppIndicator](https://github.com/AyatanaIndicators/libayatana-appindicator) for App Indicator on Wayland

#### For Video and Audio Calls

- [Farstream](https://gitlab.freedesktop.org/farstream/farstream)
- [GStreamer](https://gitlab.freedesktop.org/gstreamer/gstreamer)
- [gst-plugins-base](https://gitlab.freedesktop.org/gstreamer/gst-plugins-base)
- [gst-plugins-ugly](https://gitlab.freedesktop.org/gstreamer/gst-plugins-ugly)
- [gst-libav](https://gitlab.freedesktop.org/gstreamer/gst-libav)

### Build Requirements

- [setuptools](https://pypi.org/project/setuptools/) (>=65.0.0)
- [gettext](https://savannah.gnu.org/projects/gettext/)

To build Gajim a PEP517 build frontend like pip (https://pip.pypa.io/en/stable/) or build (https://pypa-build.readthedocs.io/en/stable/) must be used.

The build frontend takes care of installing all python build requirements. Beware `gettext` is not a python library and cannot be installed by the build frontend.

## Building

### Building the metadata files (Unix only)

```bash
./pep517build/build_metadata.py -o dist/metadata
```

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
./pep517build/install_metadata.py dist/metadata --prefix=/usr
```

## Tests

- `python -m unittest discover -s test`
- `python -m unittest ./test/dialogs/gui_file.py` (for testing GUI files)

## Packages and install instructions

### Packages

- [Arch Linux](https://www.archlinux.org/packages/community/any/gajim/)
- [Debian](https://packages.debian.org/stable/gajim)
- [Fedora](https://packages.fedoraproject.org/pkgs/gajim/)
- [Ubuntu](https://packages.ubuntu.com/gajim)
- [FreeBSD](https://www.freshports.org/net-im/gajim/)

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
    ./launch.py

### Windows

see [README](./win/README.md)

## Miscellaneous

### Debugging

Execute gajim with `--verbose`

### Links

- [FAQ](https://dev.gajim.org/gajim/gajim/wikis/help/gajimfaq)
- [Wiki](https://dev.gajim.org/gajim/gajim/wikis/home)

That is all, **enjoy**!

(C) 2003-2023
The Gajim Team
[https://gajim.org](https://gajim.org)

We use original art and parts of sounds and other art from Psi, Gossip, Gnomebaker, Gaim
and some icons from various gnome-icons (mostly Dropline Etiquette) we found at art.gnome.org.
If you think we're violating a license please inform us. Thank you.
