#!/bin/bash

runtime_version=50

cur_file_dir=$(dirname "${BASH_SOURCE[0]}")

flatpak-pip-generator.py \
    --optdep-groups "sentry" \
    --output ${cur_file_dir}/../flatpak/python3-modules.json \
    --prefer-wheels "cryptography,pillow,pysequoia" \
    --pyproject-file ${cur_file_dir}/../pyproject.toml \
    --runtime="org.gnome.Sdk//${runtime_version}"

