#!/usr/bin/env bash

set -e

DIR="$( cd "$( dirname "$0" )" && pwd )"
source "$DIR"/_base.sh

function main {
    pacman --noconfirm -S --needed \
        git \
        intltool \
        p7zip \
        wget \
        ${MINGW_PACKAGE_PREFIX}-python \
        ${MINGW_PACKAGE_PREFIX}-toolchain \
        ${MINGW_DEPS}

    pip3 install --upgrade precis-i18n
    pip3 install --upgrade $(echo "$PYTHON_REQUIREMENTS" | tr ["\\n"] [" "])
    pip3 install pygobject-stubs --no-cache-dir
}

main;
