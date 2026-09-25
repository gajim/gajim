#!/bin/bash

# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

runtime_version=51

cur_file_dir=$(dirname "${BASH_SOURCE[0]}")

flatpak-pip-generator.py \
    --optdep-groups "sentry" \
    --output ${cur_file_dir}/../flatpak/python3-modules.json \
    --prefer-wheels "cryptography,pillow,pysequoia" \
    --pyproject-file ${cur_file_dir}/../pyproject.toml \
    --runtime="org.gnome.Sdk//${runtime_version}"

