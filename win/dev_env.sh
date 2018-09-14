#!/usr/bin/env bash

set -e

function main {
    pacman --noconfirm -S --needed \
        git \
        mingw-w64-x86_64-python3 \
        mingw-w64-x86_64-python3-gobject \
        mingw-w64-x86_64-python3-pip \
        mingw-w64-x86_64-toolchain \
        mingw-w64-x86_64-gtk3 \
        mingw-w64-x86_64-python3-pyopenssl \
        mingw-w64-x86_64-python3-pillow

    PIP_REQUIREMENTS="\
certifi
git+https://dev.gajim.org/gajim/python-nbxmpp.git
git+https://dev.gajim.org/lovetox/pybonjour-python3.git
python-axolotl
python-gnupg
keyring
cssutils
"

pip3 install $(echo "$PIP_REQUIREMENTS" | tr ["\\n"] [" "])

}

main;
