#!/usr/bin/env bash

# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

set -e

DIR="$( cd "$( dirname "$0" )" && pwd )"
source "$DIR"/build.sh

function main {
    install_pre_deps
    pacman --noconfirm -S ${MINGW_DEPS}
    pip3 install -e . --group=dev
}

main;
