#!/usr/bin/env bash

set -e

function main {
    pacman --noconfirm -S --needed \
        git \
        mingw-w64-x86_64-python3 \
        mingw-w64-x86_64-python3-gobject \
        mingw-w64-x86_64-python3-pip \
        mingw-w64-x86_64-toolchain \
        mingw-w64-x86_64-adwaita-icon-theme \
        mingw-w64-x86_64-gtk3 \
        mingw-w64-x86_64-python3-setuptools-scm \
        mingw-w64-x86_64-python3-cryptography \
        mingw-w64-x86_64-python3-certifi \
        mingw-w64-x86_64-python3-pyopenssl \
        mingw-w64-x86_64-python3-pillow \
        mingw-w64-x86_64-python3-six \
        mingw-w64-x86_64-python3-pygments \
        mingw-w64-x86_64-libwebp \
        mingw-w64-x86_64-goocanvas \
        mingw-w64-x86_64-gspell \
        mingw-w64-x86_64-hunspell \
        mingw-w64-x86_64-libsoup \

    PIP_REQUIREMENTS="\
git+https://dev.gajim.org/gajim/python-nbxmpp.git
git+https://dev.gajim.org/lovetox/pybonjour-python3.git
git+https://github.com/enthought/pywin32-ctypes.git
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
