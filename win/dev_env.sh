#!/usr/bin/env bash

# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

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

    pip3 install -e .[sentry] --group=dev
}

main;
