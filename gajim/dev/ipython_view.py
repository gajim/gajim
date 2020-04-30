#!/usr/bin/python

# Copyright (C) 2008-2014 Yann Leboulanger <asterix AT lagaule.org>
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
#
# Copyright (c) 2007, IBM Corporation
# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:

# * Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
# * Neither the name of the IBM Corporation nor the names of its contributors
#   may be used to endorse or promote products derived from this software
#   without specific prior written permission.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

"""
Provides IPython console widget

@author: Eitan Isaacson
@organization: IBM Corporation
@copyright: Copyright (c) 2007 IBM Corporation
@license: BSD

All rights reserved. This program and the accompanying materials are made
available under the terms of the BSD which accompanies this distribution, and
is available at U{http://www.opensource.org/licenses/bsd-license.php}
"""

import re
import sys
import os
from io import StringIO
from functools import reduce
from pkg_resources import parse_version

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import GLib
from gi.repository import Pango

from pygments.token import Token

import IPython
from IPython.core.displayhook import DisplayHook
from IPython.core.display_trap import DisplayTrap



class MyPromptDisplayHook(DisplayHook):
    def __init__(self, shell, view):
        DisplayHook.__init__(self, shell=shell)
        self.view = view

    def write_output_prompt(self):
        tokens = self.shell.prompts.out_prompt_tokens()
        self.view.write('\n')
        self.view.write(tokens)


class IterableIPShell:
    """
    Create an IPython instance. Does not start a blocking event loop,
    instead allow single iterations. This allows embedding in GTK
    without blockage

    @ivar IP: IPython instance.
    @type IP: IPython.iplib.InteractiveShell
    @ivar iter_more: Indicates if the line executed was a complete command,
    or we should wait for more.
    @type iter_more: integer
    @ivar history_level: The place in history where we currently are
    when pressing up/down.
    @type history_level: integer
    @ivar complete_sep: Separation delimiters for completion function.
    @type complete_sep: _sre.SRE_Pattern
    """
    def __init__(self, argv=None, user_ns=None, user_global_ns=None, cin=None,
                 cout=None, cerr=None, input_func=None):
        """
        @param argv: Command line options for IPython
        @type argv: list
        @param user_ns: User namespace.
        @type user_ns: dictionary
        @param user_global_ns: User global namespace.
        @type user_global_ns: dictionary.
        @param cin: Console standard input.
        @type cin: IO stream
        @param cout: Console standard output.
        @type cout: IO stream
        @param cerr: Console standard error.
        @type cerr: IO stream
        @param input_func: Replacement for builtin raw_input()
        @type input_func: function
        """
        if argv is None:
            argv = []

        io = IPython.utils.io
        if input_func:
            IPython.terminal.interactiveshell.raw_input_original = input_func


        # This is to get rid of the blockage that occurs during
        # IPython.Shell.InteractiveShell.user_setup()
        io.raw_input = lambda x: None

        os.environ['TERM'] = 'dumb'
        excepthook = sys.excepthook

        from traitlets.config.loader import Config

        cfg = Config()
        cfg.InteractiveShell.colors = "Linux"

        # InteractiveShell's __init__ gets a reference of stdout and stderr
        # so we save the standard here to revert it after init
        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = cout, cerr

        # InteractiveShell inherits from SingletonConfigurable so use instance()
        self.IP = IPython.terminal.embed.InteractiveShellEmbed.instance(
            config=cfg, user_ns=user_ns, user_module=user_global_ns)

        # Set back stdout and stderr to what it was before
        sys.stdout, sys.stderr = old_stdout, old_stderr

        self.IP.system = lambda cmd: self.shell(self.IP.var_expand(cmd),
                                                header='IPython system call: ',
                                                local_ns=user_ns)

        self.IP.raw_input = input_func
        sys.excepthook = excepthook
        self.iter_more = 0
        self.history_level = 0
        self.complete_sep = re.compile(r'[\s\{\}\[\]\(\)]')
        self.updateNamespace({'exit': lambda: None})
        self.updateNamespace({'quit': lambda: None})

        # Workaround for updating namespace with sys.modules
        #
        self.__update_namespace()

        # Avoid using input splitter when not really needed.
        # Perhaps it could work even before 5.8.0
        # But it definitely does not work any more with >= 7.0.0
        self.no_input_splitter = parse_version(IPython.release.version) >= \
            parse_version('5.8.0')
        self.lines = []

    def __update_namespace(self):
        '''
        Update self.IP namespace for autocompletion with sys.modules
        '''
        for k, v in sys.modules.items():
            if '.' not in k:
                self.IP.user_ns.update({k: v})

    def execute(self):
        """
        Execute the current line provided by the shell object
        """
        self.history_level = 0
        orig_stdout = sys.stdout
        sys.stdout = IPython.utils.io.stdout

        orig_stdin = sys.stdin
        sys.stdin = IPython.utils.io.stdin
        self.prompt = self.generatePrompt(self.iter_more)

        self.IP.hooks.pre_prompt_hook()
        if self.iter_more:
            try:
                self.prompt = self.generatePrompt(True)
            except Exception:
                self.IP.showtraceback()
            if self.IP.autoindent:
                self.IP.rl_do_indent = True

        try:
            line = self.IP.raw_input(self.prompt)
        except KeyboardInterrupt:
            self.IP.write('\nKeyboardInterrupt\n')
            self.IP.input_splitter.reset()
        except Exception:
            self.IP.showtraceback()
        else:
            if self.no_input_splitter:
                self.lines.append(self.IP.raw_input(self.prompt))
                self.iter_more = self.IP.check_complete(
                    '\n'.join(self.lines))[0] == 'incomplete'
            else:
                self.IP.input_splitter.push(line)
                self.iter_more = self.IP.input_splitter.push_accepts_more()

            self.prompt = self.generatePrompt(self.iter_more)
            if not self.iter_more:
                if self.no_input_splitter:
                    source_raw = '\n'.join(self.lines)
                    self.lines = []
                else:
                    source_raw = self.IP.input_splitter.raw_reset()

                self.IP.run_cell(source_raw, store_history=True)
                self.IP.rl_do_indent = False
            else:
                # TODO: Auto-indent
                #
                self.IP.rl_do_indent = True

        sys.stdout = orig_stdout
        sys.stdin = orig_stdin

    def generatePrompt(self, is_continuation):
        '''
        Generate prompt depending on is_continuation value

        @param is_continuation
        @type is_continuation: boolean

        @return: The prompt string representation
        @rtype: string

        '''
        # TODO: Update to IPython 5.x and later
        prompt = "In [%d]: " % self.IP.execution_count

        return prompt

    def historyBack(self):
        """
        Provide one history command back

        @return: The command string.
        @rtype: string
        """
        self.history_level -= 1
        return self._getHistory()

    def historyForward(self):
        """
        Provide one history command forward

        @return: The command string.
        @rtype: string
        """
        self.history_level += 1
        return self._getHistory()

    def _getHistory(self):
        """
        Get the command string of the current history level

        @return: Historic command string.
        @rtype: string
        """
        try:
            rv = self.IP.user_ns['In'][self.history_level].strip('\n')
        except IndexError:
            self.history_level = 0
            rv = ''
        return rv

    def updateNamespace(self, ns_dict):
        """
        Add the current dictionary to the shell namespace

        @param ns_dict: A dictionary of symbol-values.
        @type ns_dict: dictionary
        """
        self.IP.user_ns.update(ns_dict)

    def complete(self, line):
        """
        Returns an auto completed line and/or possibilities for completion

        @param line: Given line so far.
        @type line: string

        @return: Line completed as for as possible,
        and possible further completions.
        @rtype: tuple
        """
        split_line = self.complete_sep.split(line)
        if split_line[-1]:
            possibilities = self.IP.complete(split_line[-1])
        else:
            completed = line
            possibilities = ['', []]
        if possibilities:
            def _commonPrefix(str1, str2):
                '''
                Reduction function. returns common prefix of two given strings.

                @param str1: First string.
                @type str1: string
                @param str2: Second string
                @type str2: string

                @return: Common prefix to both strings.
                @rtype: string
                '''
                for i in range(len(str1)):
                    if not str2.startswith(str1[:i + 1]):
                        return str1[:i]
                return str1

            if possibilities[1]:
                common_prefix = \
                    reduce(_commonPrefix, possibilities[1]) or line[-1]
                completed = line[:-len(split_line[-1])] + common_prefix
            else:
                completed = line
        else:
            completed = line
        return completed, possibilities[1]


class ConsoleView(Gtk.TextView):
    """
    Specialized text view for console-like workflow

    @cvar ANSI_COLORS: Mapping of terminal colors to X11 names.
    @type ANSI_COLORS: dictionary

    @ivar text_buffer: Widget's text buffer.
    @type text_buffer: Gtk.TextBuffer
    @ivar color_pat: Regex of terminal color pattern
    @type color_pat: _sre.SRE_Pattern
    @ivar mark: Scroll mark for automatic scrolling on input.
    @type mark: Gtk.TextMark
    @ivar line_start: Start of command line mark.
    @type line_start: Gtk.TextMark
    """

    ANSI_COLORS = {'0;30': 'Black', '0;31': 'Red',
                   '0;32': 'Green', '0;33': 'Brown',
                   '0;34': 'Blue', '0;35': 'Purple',
                   '0;36': 'Cyan', '0;37': 'LightGray',
                   '1;30': 'DarkGray', '1;31': 'DarkRed',
                   '1;32': 'SeaGreen', '1;33': 'Yellow',
                   '1;34': 'LightBlue', '1;35': 'MediumPurple',
                   '1;36': 'LightCyan', '1;37': 'White'}

    def __init__(self):
        """
        Initialize console view
        """
        GObject.GObject.__init__(self)
        self.override_font(Pango.FontDescription('Mono'))
        self.set_cursor_visible(True)
        self.text_buffer = self.get_buffer()
        self.mark = self.text_buffer.create_mark(
            'scroll_mark',
            self.text_buffer.get_end_iter(),
            False)
        for code in self.ANSI_COLORS:
            self.text_buffer.create_tag(code,
                                        foreground=self.ANSI_COLORS[code],
                                        weight=700)
        self.text_buffer.create_tag('0')
        self.text_buffer.create_tag('notouch', editable=False)
        self.color_pat = re.compile(r'\x01?\x1b\[(.*?)m\x02?')

        self.style_dict = {
            Token.Prompt: '0;32',
            Token.PromptNum: '1;32',
            Token.OutPrompt: '0;31',
            Token.OutPromptNum: '1;31',
        }

        self.line_start = \
            self.text_buffer.create_mark('line_start',
                                         self.text_buffer.get_end_iter(),
                                         True)
        self.connect('key-press-event', self.onKeyPress)

    def write(self, text, editable=False):
        if isinstance(text, str):
            GLib.idle_add(self._write, text, editable)
        else:
            GLib.idle_add(self._write5, text, editable)

    def _write5(self, text, editable=False):
        """
        Write given text to buffer

        @param text: Text to append.
        @type text: list of (token: string)
        @param editable: If true, added text is editable.
        @type editable: boolean
        """
        start_mark = self.text_buffer.create_mark(
            None, self.text_buffer.get_end_iter(), True)

        for token, segment in text:
            tag = self.style_dict[token]
            self.text_buffer.insert_with_tags_by_name(
                self.text_buffer.get_end_iter(), segment, tag)
        if not editable:
            self.text_buffer.apply_tag_by_name(
                'notouch',
                self.text_buffer.get_iter_at_mark(start_mark),
                self.text_buffer.get_end_iter())
        self.text_buffer.delete_mark(start_mark)
        self.scroll_mark_onscreen(self.mark)

    def _write(self, text, editable=False):
        """
        Write given text to buffer

        @param text: Text to append.
        @type text: string
        @param editable: If true, added text is editable.
        @type editable: boolean
        """
        if isinstance(text, list):
            self._write5(text, editable)
            return
        segments = self.color_pat.split(text)
        segment = segments.pop(0)
        start_mark = self.text_buffer.create_mark(
            None, self.text_buffer.get_end_iter(), True)
        self.text_buffer.insert(self.text_buffer.get_end_iter(), segment)

        if segments:
            ansi_tags = self.color_pat.findall(text)
            for tag in ansi_tags:
                i = segments.index(tag)
                self.text_buffer.insert_with_tags_by_name(
                    self.text_buffer.get_end_iter(), segments[i + 1], str(tag))
                segments.pop(i)
        if not editable:
            self.text_buffer.apply_tag_by_name(
                'notouch',
                self.text_buffer.get_iter_at_mark(start_mark),
                self.text_buffer.get_end_iter())

        self.text_buffer.delete_mark(start_mark)
        self.scroll_mark_onscreen(self.mark)

    def showPrompt(self, prompt):
        GLib.idle_add(self._showPrompt, prompt)

    def _showPrompt(self, prompt):
        """
        Print prompt at start of line

        @param prompt: Prompt to print.
        @type prompt: string
        """
        self._write(prompt)
        self.text_buffer.move_mark(self.line_start,
                                   self.text_buffer.get_end_iter())

    def changeLine(self, text):
        GLib.idle_add(self._changeLine, text)

    def _changeLine(self, text):
        """
        Replace currently entered command line with given text

        @param text: Text to use as replacement.
        @type text: string
        """
        iter_ = self.text_buffer.get_iter_at_mark(self.line_start)
        iter_.forward_to_line_end()
        self.text_buffer.delete(
            self.text_buffer.get_iter_at_mark(self.line_start), iter_)
        self._write(text, True)

    def getCurrentLine(self):
        """
        Get text in current command line

        @return: Text of current command line.
        @rtype: string
        """
        rv = self.text_buffer.get_slice(
            self.text_buffer.get_iter_at_mark(self.line_start),
            self.text_buffer.get_end_iter(), False)
        return rv

    def showReturned(self, text):
        GLib.idle_add(self._showReturned, text)

    def _showReturned(self, text):
        """
        Show returned text from last command and print new prompt

        @param text: Text to show.
        @type text: string
        """
        iter_ = self.text_buffer.get_iter_at_mark(self.line_start)
        iter_.forward_to_line_end()
        self.text_buffer.apply_tag_by_name(
            'notouch',
            self.text_buffer.get_iter_at_mark(self.line_start),
            iter_)
        self._write('\n' + text)
        if text:
            self._write('\n')
        self._showPrompt(self.prompt)
        self.text_buffer.move_mark(
            self.line_start, self.text_buffer.get_end_iter())
        self.text_buffer.place_cursor(self.text_buffer.get_end_iter())

        if self.IP.rl_do_indent:
            indentation = self.IP.input_splitter.indent_spaces * ' '
            self.text_buffer.insert_at_cursor(indentation)

    def onKeyPress(self, _widget, event):
        """
        Key press callback used for correcting behavior for console-like
        interfaces. For example 'home' should go to prompt, not to beginning of
        line

        @param widget: Widget that key press occurred in.
        @type widget: Gtk.Widget
        @param event: Event object
        @type event: Gdk.Event

        @return: Return True if event should not trickle.
        @rtype: boolean
        """
        insert_mark = self.text_buffer.get_insert()
        insert_iter = self.text_buffer.get_iter_at_mark(insert_mark)
        selection_mark = self.text_buffer.get_selection_bound()
        selection_iter = self.text_buffer.get_iter_at_mark(selection_mark)
        start_iter = self.text_buffer.get_iter_at_mark(self.line_start)
        if event.keyval == Gdk.KEY_Home:
            if event.get_state() == 0:
                self.text_buffer.place_cursor(start_iter)
                return True
            if event.get_state() == Gdk.ModifierType.SHIFT_MASK:
                self.text_buffer.move_mark(insert_mark, start_iter)
                return True

        if event.keyval == Gdk.KEY_Left:
            insert_iter.backward_cursor_position()
            if not insert_iter.editable(True):
                return True
        elif not event.string:
            pass
        elif (start_iter.compare(insert_iter) <= 0 and
                start_iter.compare(selection_iter) <= 0):
            pass
        elif (start_iter.compare(insert_iter) > 0 and
                start_iter.compare(selection_iter) > 0):
            self.text_buffer.place_cursor(start_iter)
        elif insert_iter.compare(selection_iter) < 0:
            self.text_buffer.move_mark(insert_mark, start_iter)
        elif insert_iter.compare(selection_iter) > 0:
            self.text_buffer.move_mark(selection_mark, start_iter)

        return self.onKeyPressExtend(event)

    def onKeyPressExtend(self, event):
        """
        For some reason we can't extend onKeyPress directly (bug #500900)
        """


class IPythonView(ConsoleView, IterableIPShell):
    '''
    Sub-class of both modified IPython shell and L{ConsoleView} this makes
    a GTK IPython console.
    '''
    def __init__(self):
        """
        Initialize. Redirect I/O to console
        """
        ConsoleView.__init__(self)
        self.cout = StringIO()
        IterableIPShell.__init__(self, cout=self.cout, cerr=self.cout,
                                 input_func=self.raw_input)

        displayhook = MyPromptDisplayHook(shell=self.IP, view=self)
        self.IP.displayhook = displayhook
        self.IP.display_trap = DisplayTrap(hook=displayhook)

        self.interrupt = False
        self.execute()
        self.prompt = self.generatePrompt(False)
        self.cout.truncate(0)
        self.showPrompt(self.prompt)

    def prompt_for_code(self):
        # IPython 5.0 calls prompt_for_code instead of raw_input
        return self.raw_input(self)

    def raw_input(self, _prompt=''):
        """
        Custom raw_input() replacement. Gets current line from console buffer

        @param prompt: Prompt to print. Here for compatibility as replacement.
        @type prompt: string

        @return: The current command line text.
        @rtype: string
        """
        if self.interrupt:
            self.interrupt = False
            raise KeyboardInterrupt
        return self.getCurrentLine()

    def onKeyPressExtend(self, event):
        """
        Key press callback with plenty of shell goodness, like history,
        autocompletions, etc

        @param widget: Widget that key press occurred in.
        @type widget: Gtk.Widget
        @param event: Event object.
        @type event: Gdk.Event

        @return: True if event should not trickle.
        @rtype: boolean
        """
        if (event.get_state() & Gdk.ModifierType.CONTROL_MASK and
                event.keyval == 99):
            self.interrupt = True
            self._processLine()
            return True
        if event.keyval == Gdk.KEY_Return:
            self._processLine()
            return True
        if event.keyval == Gdk.KEY_Up:
            self.changeLine(self.historyBack())
            return True
        if event.keyval == Gdk.KEY_Down:
            self.changeLine(self.historyForward())
            return True
        if event.keyval == Gdk.KEY_Tab:
            if not self.getCurrentLine().strip():
                return False
            completed, possibilities = self.complete(self.getCurrentLine())
            if len(possibilities) > 1:
                slice_ = self.getCurrentLine()
                self.write('\n')
                for symbol in possibilities:
                    self.write(symbol + '\n')
                self.showPrompt(self.prompt)
            self.changeLine(completed or slice_)
            return True

    def _processLine(self):
        """
        Process current command line
        """
        self.history_pos = 0
        self.execute()
        rv = self.cout.getvalue()
        if rv:
            rv = rv.strip('\n')
        self.showReturned(rv)
        self.cout.truncate(0)
        self.cout.seek(0)
