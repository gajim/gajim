#!/usr/bin/env bash

# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

DIR="$( cd "$( dirname "$0" )" && pwd )"
source "$DIR"/new_build.sh

function main {
    install_pre_deps
    install_mingw_deps
    install_python_deps
    install_gajim
}

main "$@";
