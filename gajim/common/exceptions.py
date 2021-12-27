# Copyright (C) 2005-2006 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2005-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2006 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2007 Brendan Taylor <whateley AT gmail.com>
#
# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

from gajim.common.i18n import _


class ServiceNotAvailable(Exception):
    """
    This exception is raised when we cannot use Gajim remotely'
    """

    def __init__(self):
        Exception.__init__(self)

    def __str__(self):
        return _('Service not available: Gajim is not running, or remote_control is False')


class SessionBusNotPresent(Exception):
    """
    This exception indicates that there is no session daemon
    """

    def __init__(self):
        Exception.__init__(self)

    def __str__(self):
        return _('Session bus is not available.\nTry reading %(url)s') % \
                {'url': 'https://dev.gajim.org/gajim/gajim/wikis/help/GajimDBus'}


class GajimGeneralException(Exception):
    """
    This exception is our general exception
    """

    def __init__(self, text=''):
        Exception.__init__(self)
        self.text = text

    def __str__(self):
        return self.text


class PluginsystemError(Exception):
    """
    Error in the pluginsystem
    """

    def __init__(self, text=''):
        Exception.__init__(self)
        self.text = text

    def __str__(self):
        return self.text


class FileError(Exception):
    pass
