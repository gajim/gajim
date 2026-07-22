# Install Gajim via Flatpak

## Install pre-built version

Make sure to follow the [setup guide](https://flatpak.org/setup/) before installing.

*Note: Remove `--user` if you want a system-wide installation.*

For file system access (e.g. for sending files), you may need to install additional 'xdg-desktop-portals'. Some examples:

* xdg-desktop-portal
* xdg-desktop-portal-kde
* xdg-desktop-portal-gtk
* xdg-desktop-portal-gnome

### Stable

```bash
flatpak install --user https://flathub.org/repo/appstream/org.gajim.Gajim.flatpakref
```

[Migrate your profile data](#migrate-your-data) if you like.

### Install plugins

To list available plugins, run

```bash
flatpak search gajim.plugin
```

To install e.g. the PGP plugin, run

```bash
flatpak install --user flathub org.gajim.Gajim.Plugin.pgp
```

Note that **you need to restart Gajim** for Plugins to be enabled.

## Build and Install Nightly

Make sure `flatpak-builder` is installed on your system.

```bash
./make.py flatpak
flatpak run org.gajim.Gajim.Devel
```

## Migrate your data

When switching to Flatpak you might want to migrate your user data (accounts, history, ...) from your previous installation. Just copy your user data from/to the following directories:

Copy `~/.local/share/gajim` -> `~/.var/app/org.gajim.Gajim/data/gajim`

Copy `~/.config/gajim` -> `~/.var/app/org.gajim.Gajim/config/gajim`


## Usage with custom installed CAs or self signed certs

Gajims HTTP library uses OpenSSL as TLS backend. It cannot see installed self signed certs or CAs on the host. To make them available use `flatpak override`.

e.g `flatpak override --user --filesystem=host-etc:ro --env=SSL_CERT_FILE=/run/host/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem org.gajim.Gajim`
