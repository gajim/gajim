#!/bin/bash

cd ~/chroot2/home/asterix/gajim_snap_git

flatpak-builder \
    --require-changes \
    --install-deps-from=flathub \
    --user \
    --disable-rofiles-fuse \
    --force-clean gajim-fp \
    --gpg-sign=9FDE1F4FA30E8019342B36279A569BF2B79EE905 \
    --repo=/home/ftp/flatpak/ flatpak/org.gajim.Gajim.yaml &> /tmp/flatpak_build

cd ../gajim-plugins

find flatpak \
    -name *.yaml \
    -exec flatpak-builder\
    --require-changes \
    --disable-rofiles-fuse \
    --force-clean gajim-fp \
    --gpg-sign=9FDE1F4FA30E8019342B36279A569BF2B79EE905 \
    --repo=/home/ftp/flatpak/ {} \; &> /tmp/flatpak_plugins_build

flatpak \
    --gpg-sign=9FDE1F4FA30E8019342B36279A569BF2B79EE905 \
    --generate-static-deltas build-update-repo \
    --prune /home/ftp/flatpak/

ostree checkout \
    --repo=/home/ftp/flatpak \
    --user-mode \
    --union \
    --bareuseronly-dirs appstream/x86_64 /home/ftp/flatpak/appstream/x86_64
