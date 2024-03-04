# Copyright (C) 2005-2006 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2005-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2006 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2007 Brendan Taylor <whateley AT gmail.com>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only


class GajimGeneralException(Exception):
    '''
    This exception is our general exception
    '''

    def __init__(self, text: str = '') -> None:
        Exception.__init__(self)
        self.text = text

    def __str__(self) -> str:
        return self.text


class PluginsystemError(Exception):
    '''
    Error in the pluginsystem
    '''

    def __init__(self, text: str = '') -> None:
        Exception.__init__(self)
        self.text = text

    def __str__(self) -> str:
        return self.text


class FileError(Exception):
    pass
