# Install Gajim via Flatpak

**Prerequisites:**

You need to have `flatpak` and `flatpak-builder` installed. For this example, we use `git` for downloading/updating Gajim's sources.


### Download Gajim's sources

In this example, we do a `git clone` of the repository, so you need to have `git` installed. Alternatively, you can also download the sources from our Gitlab via webbrowser.

`git clone https://dev.gajim.org/gajim/gajim.git ~/Gajim`

`cd ~/Gajim`

*Note: Source tarballs and snapshots do _not_ include 'org.gajim.Gajim.json', which is necessary for installation via Flatpak.*


### Install Gajim and dependencies

Replace install path `~/Gajim/gajim_flatpak` with an install path of your choice.

*Note: Remove `--user` if you want a system-wide installation.*

1. `flatpak --user remote-add --from gnome https://sdk.gnome.org/gnome.flatpakrepo`
2. `flatpak --user install gnome org.gnome.Platform//3.28`
3. `flatpak --user install gnome org.gnome.Sdk//3.28`
4. `flatpak-builder --repo=gajim_flatpak_repo ~/Gajim/gajim_flatpak ~/Gajim/org.gajim.Gajim.json`
5. `flatpak --user remote-add --no-gpg-verify gajim_flatpak_repo ~/Gajim/gajim_flatpak_repo`
6. `flatpak --user install gajim_flatpak_repo org.gajim.Gajim`
7. `flatpak run org.gajim.Gajim`

Thats it, you are now running Gajim via Flatpak!


## How to update

### Update Gajim's sources

In this example, we use `git` to update the repository. You can also download the sources from our Gitlab via webbrowser.

`cd ~/Gajim`

`git pull --rebase`


### Remove previous Flatpak directory

`rm -r ~/Gajim/gajim_flatpak`


### Install and update Gajim

1. `flatpak-builder --repo=gajim_flatpak_repo ~/Gajim/gajim_flatpak ~/Gajim/org.gajim.Gajim.json`
2. `flatpak --user update`
3. `flatpak run org.gajim.Gajim`

Gajim is now updated.
