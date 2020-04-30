# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

'''
Helper code related to plug-ins management system.

:author: Mateusz Biliński <mateusz@bilinski.it>
:since: 30th May 2008
:copyright: Copyright (2008) Mateusz Biliński <mateusz@bilinski.it>
:license: GPL
'''

__all__ = ['log', 'log_calls']

from typing import List

import logging
import functools

from gajim.plugins import plugins_i18n
from gajim.gtk.util import Builder

log = logging.getLogger('gajim.plugin_system')
'''
Logger for code related to plug-in system.

:type: logging.Logger
'''

class GajimPluginActivateException(Exception):
    '''
    Raised when activation failed
    '''

class log_calls:
    '''
    Decorator class for functions to easily log when they are entered and left.
    '''

    filter_out_classes = ['GajimPluginConfig', 'PluginManager',
                          'GajimPluginConfigDialog', 'PluginsWindow']
    '''
    List of classes from which no logs should be emitted when methods are
    called, even though `log_calls` decorator is used.
    '''

    def __init__(self, classname=''):
        '''
        :Keywords:
          classname : str
            Name of class to prefix function name (if function is a method).
          log : logging.Logger
            Logger to use when outputting debug information on when function has
            been entered and when left. By default: `plugins.helpers.log`
            is used.
        '''

        self.full_func_name = ''
        '''
        Full name of function, with class name (as prefix) if given
        to decorator.

        Otherwise, it's only function name retrieved from function object
        for which decorator was called.

        :type: str
        '''
        self.log_this_class = True
        '''
        Determines whether wrapper of given function should log calls of this
        function or not.

        :type: bool
        '''

        if classname:
            self.full_func_name = classname+'.'

        if classname in self.filter_out_classes:
            self.log_this_class = False

    def __call__(self, f):
        '''
        :param f: function to be wrapped with logging statements

        :return: given function wrapped by *log.debug* statements
        :rtype: function
        '''

        self.full_func_name += f.__name__
        if self.log_this_class:
            @functools.wraps(f)
            def wrapper(*args, **kwargs):

                log.debug('%s() <entered>', self.full_func_name)
                result = f(*args, **kwargs)
                log.debug('%s() <left>', self.full_func_name)
                return result
        else:
            @functools.wraps(f)
            def wrapper(*args, **kwargs):
                result = f(*args, **kwargs)
                return result

        return wrapper


def get_builder(file_name: str, widgets: List[str] = None) -> Builder:
    return Builder(file_name,
                   widgets,
                   domain=plugins_i18n.DOMAIN,
                   gettext_=plugins_i18n._)
