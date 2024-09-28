#!/usr/bin/env bash
# Copyright 2016 Christoph Reiter
#
# SPDX-License-Identifier: GPL-2.0-or-later

DIR="$( cd "$( dirname "$0" )" && pwd )"
source "$DIR"/_base.sh

function main {
    set_build_root
    unpack_msixbundle
}

main "$@";
