#!/usr/bin/env bash

set -e

function main {
    pacman --noconfirm -S --needed \
        git \
        mingw-w64-x86_64-python \
        mingw-w64-x86_64-python-gobject \
        mingw-w64-x86_64-python-pip \
        mingw-w64-x86_64-toolchain \
        mingw-w64-x86_64-adwaita-icon-theme \
        mingw-w64-x86_64-gtk3 \
        mingw-w64-x86_64-gtksourceview4 \
        mingw-w64-x86_64-python-setuptools-scm \
        mingw-w64-x86_64-python-cryptography \
        mingw-w64-x86_64-python-certifi \
        mingw-w64-x86_64-python-pillow \
        mingw-w64-x86_64-python-six \
        mingw-w64-x86_64-python-pygments \
        mingw-w64-x86_64-libwebp \
        mingw-w64-x86_64-goocanvas \
        mingw-w64-x86_64-gspell \
        mingw-w64-x86_64-hunspell \
        mingw-w64-x86_64-libsoup3 \

    PIP_REQUIREMENTS="\
git+https://dev.gajim.org/gajim/python-nbxmpp.git
python-axolotl
python-gnupg
keyring
css_parser
qrcode
"
pip3 install precis-i18n
pip3 install $(echo "$PIP_REQUIREMENTS" | tr ["\\n"] [" "])

}

main;
