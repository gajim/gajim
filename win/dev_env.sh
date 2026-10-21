#!/usr/bin/env bash

# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

set -e

DIR="$( cd "$( dirname "$0" )" && pwd )"
source "$DIR"/_base.sh

function main {
    install_pre_deps
    pacman --noconfirm -U https://repo.msys2.org/mingw/ucrt64/mingw-w64-ucrt-x86_64-pango-1.56.4-3-any.pkg.tar.zst
    pacman --noconfirm -S ${MINGW_DEPS}
    pip3 install -e . --group=dev
}

main;
