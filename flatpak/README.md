Run the following steps from a directory containing the gajim source dir.

Install gajim flatpak repo
--------------------------

1. `flatpak --user remote-add --from gnome https://sdk.gnome.org/gnome.flatpakrepo`
1. `flatpak --user install gnome org.gnome.Platform//3.28`
1. `flatpak --user install gnome org.gnome.Sdk//3.28`
1. `flatpak-builder --repo=repo directory gajim/org.gajim.Gajim.json`
1. `flatpak --user remote-add --no-gpg-verify repo repo`
1. `flatpak --user install repo org.gajim.Gajim`
1. `flatpak run org.gajim.Gajim`

Update gajim flatpak repo
-------------------------

1. update your gajim source repository
1. `rm -r directory`
1. `flatpak-builder --repo=repo directory gajim/org.gajim.Gajim.json`
1. `flatpak --user update`

Note: remove `--user` if you want a system-wide installation
