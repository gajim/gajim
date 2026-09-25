# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only


def pre_safe_import_module(api):
    api.add_runtime_module(api.module_name)
