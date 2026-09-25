#!/usr/bin/env bash

# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

DIR="$( cd "$( dirname "$0" )" && pwd )"
source "$DIR"/_base.sh

function main {
    set_build_root
    unpack_msixbundle
}

main "$@";
