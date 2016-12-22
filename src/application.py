# -*- coding:utf-8 -*-
## src/application.py
##
## Copyright (C) 2016 Emmanuel Gil Peyrot <linkmauve AT linkmauve.fr>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

from gi.repository import GLib, Gio, Gtk
from common import logging_helpers


class GajimApplication(Gtk.Application):
    '''Main class handling activation and command line.'''

    def __init__(self):
        Gtk.Application.__init__(self, application_id='org.gajim.Gajim',
                                 flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.add_main_option('version', ord('V'), GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE,
                             _('Show the application\'s version'))
        self.add_main_option('quiet', ord('q'), GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE,
                             _('Show only critical errors'))
        self.add_main_option('separate', ord('s'), GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE,
                             _('Separate profile files completely (even '
                               'history db and plugins)'))
        self.add_main_option('verbose', ord('v'), GLib.OptionFlags.NONE,
                             GLib.OptionArg.NONE,
                             _('Print xml stanzas and other debug '
                               'information'))
        self.add_main_option('profile', ord('p'), GLib.OptionFlags.NONE,
                             GLib.OptionArg.STRING,
                             _('Use defined profile in configuration '
                               'directory'), 'NAME')
        self.add_main_option('config-path', ord('c'), GLib.OptionFlags.NONE,
                             GLib.OptionArg.STRING,
                             _('Set configuration directory'), 'PATH')
        self.add_main_option('loglevel', ord('l'), GLib.OptionFlags.NONE,
                             GLib.OptionArg.STRING,
                             _('Configure logging system'), 'LEVEL')

        self.profile = ''
        self.config_path = None
        self.profile_separation = False

    def do_startup(self):
        Gtk.Application.do_startup(self)

    def do_activate(self):
        Gtk.Application.do_activate(self)

    def do_command_line(self, command_line: Gio.ApplicationCommandLine) -> int:
        Gtk.Application.do_command_line(self, command_line)
        options = command_line.get_options_dict()
        if options.contains('quiet'):
            logging_helpers.set_quiet()
        if options.contains('separate'):
            self.profile_separation = True
        if options.contains('verbose'):
            logging_helpers.set_verbose()
        if options.contains('profile'):
            variant = options.lookup_value('profile')
            self.profile = variant.get_string()
        if options.contains('loglevel'):
            variant = options.lookup_value('loglevel')
            string = variant.get_string()
            logging_helpers.set_loglevels(string)
        if options.contains('config-path'):
            variant = options.lookup_value('config-path')
            self.config_path = variant.get_string()
        self.activate()
        return 0
