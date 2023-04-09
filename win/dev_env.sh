#!/usr/bin/env bash

set -e

function main {
    pacman --noconfirm -S --needed \
        git \
        ${MINGW_PACKAGE_PREFIX}-python \
        ${MINGW_PACKAGE_PREFIX}-python-gobject \
        ${MINGW_PACKAGE_PREFIX}-python-pip \
        ${MINGW_PACKAGE_PREFIX}-toolchain \
        ${MINGW_PACKAGE_PREFIX}-adwaita-icon-theme \
        ${MINGW_PACKAGE_PREFIX}-gtk3 \
        ${MINGW_PACKAGE_PREFIX}-gtksourceview4 \
        ${MINGW_PACKAGE_PREFIX}-python-setuptools-scm \
        ${MINGW_PACKAGE_PREFIX}-python-cryptography \
        ${MINGW_PACKAGE_PREFIX}-python-certifi \
        ${MINGW_PACKAGE_PREFIX}-python-pillow \
        ${MINGW_PACKAGE_PREFIX}-python-six \
        ${MINGW_PACKAGE_PREFIX}-python-pygments \
        ${MINGW_PACKAGE_PREFIX}-libwebp \
        ${MINGW_PACKAGE_PREFIX}-goocanvas \
        ${MINGW_PACKAGE_PREFIX}-gspell \
        ${MINGW_PACKAGE_PREFIX}-hunspell \
        ${MINGW_PACKAGE_PREFIX}-libsoup3 \

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
