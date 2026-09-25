# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only


class GajimGeneralException(Exception):
    """
    This exception is our general exception
    """

    def __init__(self, text: str = "") -> None:
        Exception.__init__(self)
        self.text = text

    def __str__(self) -> str:
        return self.text


class PluginsystemError(Exception):
    """
    Error in the pluginsystem
    """

    def __init__(self, text: str = "") -> None:
        Exception.__init__(self)
        self.text = text

    def __str__(self) -> str:
        return self.text


class FileError(Exception):
    pass
