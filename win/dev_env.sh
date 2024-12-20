#!/usr/bin/env bash

set -e

function main {
    pacman --noconfirm -S --needed \
        git \
        p7zip \
        wget \
        intltool \
        ${MINGW_PACKAGE_PREFIX}-toolchain \
        ${MINGW_PACKAGE_PREFIX}-python \
        ${MINGW_PACKAGE_PREFIX}-python-pip \
        ${MINGW_PACKAGE_PREFIX}-python-gobject \
        ${MINGW_PACKAGE_PREFIX}-python-certifi \
        ${MINGW_PACKAGE_PREFIX}-python-cryptography \
        ${MINGW_PACKAGE_PREFIX}-python-gssapi \
        ${MINGW_PACKAGE_PREFIX}-python-idna \
        ${MINGW_PACKAGE_PREFIX}-python-keyring \
        ${MINGW_PACKAGE_PREFIX}-python-packaging \
        ${MINGW_PACKAGE_PREFIX}-python-pillow \
        ${MINGW_PACKAGE_PREFIX}-python-protobuf \
        ${MINGW_PACKAGE_PREFIX}-python-pygments \
        ${MINGW_PACKAGE_PREFIX}-python-setuptools \
        ${MINGW_PACKAGE_PREFIX}-python-setuptools-scm \
        ${MINGW_PACKAGE_PREFIX}-python-six \
        ${MINGW_PACKAGE_PREFIX}-python-sqlalchemy \
        ${MINGW_PACKAGE_PREFIX}-gtk4 \
        ${MINGW_PACKAGE_PREFIX}-gtksourceview5 \
        ${MINGW_PACKAGE_PREFIX}-gstreamer \
        ${MINGW_PACKAGE_PREFIX}-gst-plugins-base \
        ${MINGW_PACKAGE_PREFIX}-gst-plugins-good \
        ${MINGW_PACKAGE_PREFIX}-gst-libav \
        ${MINGW_PACKAGE_PREFIX}-gst-python \
        ${MINGW_PACKAGE_PREFIX}-adwaita-icon-theme \
        ${MINGW_PACKAGE_PREFIX}-farstream \
        ${MINGW_PACKAGE_PREFIX}-libspelling \
        ${MINGW_PACKAGE_PREFIX}-hunspell \
        ${MINGW_PACKAGE_PREFIX}-libheif \
        ${MINGW_PACKAGE_PREFIX}-libnice \
        ${MINGW_PACKAGE_PREFIX}-libsoup3 \
        ${MINGW_PACKAGE_PREFIX}-libwebp \
        ${MINGW_PACKAGE_PREFIX}-sqlite3

    PIP_REQUIREMENTS="\
git+https://dev.gajim.org/gajim/python-nbxmpp.git
git+https://dev.gajim.org/gajim/omemo-dr.git
pygobject-stubs --no-cache-dir --config-settings=config=Gtk4,Gdk4,GtkSource5
python-gnupg
qrcode
css_parser
sentry-sdk
emoji
winrt-Windows.ApplicationModel
winrt-Windows.Foundation
winrt-Windows.UI
winrt-Windows.UI.ViewManagement
windows-toasts
"
pip3 install --upgrade precis-i18n
pip3 install --upgrade $(echo "$PIP_REQUIREMENTS" | tr ["\\n"] [" "])

}

main;
