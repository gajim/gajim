# Install Gajim via Flatpak

## Install pre-built version

Make sure to follow the [setup guide](https://flatpak.org/setup/) before installing.

*Note: Remove `--user` if you want a system-wide installation.*

### Stable

```bash
flatpak install --user https://flathub.org/repo/appstream/org.gajim.Gajim.flatpakref
```

### Nightly/master

```bash
flatpak install --user https://ftp.gajim.org/flatpak/appstream/org.gajim.Gajim.Devel.flatpakref
```

[Migrate your profile data](#migrate-your-data) if you like.

### Install plugins

To list available stable/nightly plugins, run

```bash
flatpak search gajim.plugin
```

or

```bash
flatpak remote-ls gajim-nightly
```

respectively.

To install the stable/nightly version of PGP, for example, run

```bash
flatpak install --user flathub org.gajim.Gajim.Plugin.pgp
```

or

```bash
flatpak install --user gajim-nightly org.gajim.Gajim.Devel.Plugin.pgp
```

respectively.

Note that **you need to restart Gajim** for Plugins to be enabled.

## Install from source

**Prerequisites:**

You need to have `flatpak` and `flatpak-builder` installed. For this example, we use `git` for downloading/updating Gajim's sources.

### Download Gajim's sources

In this example, we do a `git clone` of the repository, so you need to have `git` installed.
Alternatively, you can also download the sources from our Gitlab via web browser.

```bash
git clone --recurse-submodules https://dev.gajim.org/gajim/gajim.git ~/Gajim
cd ~/Gajim
```

*Note: Source tarballs and snapshots do _not_ include 'org.gajim.Gajim.yaml', which is necessary for installation via Flatpak.*

### Install Gajim and dependencies

Replace install path `~/Gajim/gajim_flatpak` with an install path of your choice.

*Note: Remove `--user` if you want a system-wide installation.*

```bash
flatpak --user remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak-builder --user --repo=gajim_flatpak_repo --install-deps-from=flathub --force-clean ~/Gajim/gajim_flatpak ~/Gajim/flatpak/org.gajim.Gajim.yaml
flatpak --user remote-add --no-gpg-verify gajim_flatpak_repo gajim_flatpak_repo
flatpak --user install gajim_flatpak_repo org.gajim.Gajim
flatpak run org.gajim.Gajim
```

That's it, you are now running Gajim via Flatpak!

[Migrate your profile data](#migrate-your-data) if you like.

## How to update

### Update Gajim's sources

In this example, we use `git` to update the repository. You can also download the sources from our Gitlab via webbrowser.

```bash
cd ~/Gajim
git pull --rebase
```

### Install and update Gajim

```bash
flatpak-builder --repo=gajim_flatpak_repo --force-clean ~/Gajim/gajim_flatpak ~/Gajim/flatpak/org.gajim.Gajim.yaml
flatpak --user update
flatpak run org.gajim.Gajim
```

Gajim is now updated.

## Migrate your data

When switching to Flatpak you might want to migrate your user data (accounts, history, ...) from your previous installation. Just copy your user data from/to the following directories:

Copy `.local/share/gajim` -> `.var/app/org.gajim.Gajim/data/gajim`

Copy `.config/gajim` -> `.var/app/org.gajim.Gajim/config/gajim`
