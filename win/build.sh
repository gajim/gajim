#!/usr/bin/env bash
# Copyright 2016 Christoph Reiter
#
# SPDX-License-Identifier: GPL-2.0-or-later

DIR="$( cd "$( dirname "$0" )" && pwd )"
source "$DIR"/_base.sh

function main {
    set_build_root
    install_pre_deps
    create_root
    install_mingw_deps
    install_python_deps
    post_install_deps
    install_gajim
    cleanup_install
    build_exe_installer
    build_msix_installer
}

main "$@";
