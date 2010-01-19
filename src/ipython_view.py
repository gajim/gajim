#!/usr/bin/python
# -*- coding:utf-8 -*-
## src/ipython_view.py
##
## Copyright (C) 2008 Yann Leboulanger <asterix AT lagaule.org>
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
## Copyright (c) 2007, IBM Corporation
## All rights reserved.

## Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

## * Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
## * Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
## * Neither the name of the IBM Corporation nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

## THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

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

import gtk, gobject
import re
import sys
import os
import pango
from StringIO import StringIO

try:
  import IPython
except ImportError:
  IPython = None

class IterableIPShell:
  """
  Create an IPython instance. Does not start a blocking event loop,
  instead allow single iterations. This allows embedding in GTK+
  without blockage

  @ivar IP: IPython instance.
  @type IP: IPython.iplib.InteractiveShell
  @ivar iter_more: Indicates if the line executed was a complete command,
  or we should wait for more.
  @type iter_more: integer
  @ivar history_level: The place in history where we currently are
  when pressing up/down.
  @type history_level: integer
  @ivar complete_sep: Seperation delimeters for completion function.
  @type complete_sep: _sre.SRE_Pattern
  """
  def __init__(self,argv=[],user_ns=None,user_global_ns=None, cin=None,
		  cout=None,cerr=None, input_func=None):
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
    if input_func:
      IPython.iplib.raw_input_original = input_func
    if cin:
      IPython.Shell.Term.cin = cin
    if cout:
      IPython.Shell.Term.cout = cout
    if cerr:
      IPython.Shell.Term.cerr = cerr

    # This is to get rid of the blockage that accurs during
    # IPython.Shell.InteractiveShell.user_setup()
    IPython.iplib.raw_input = lambda x: None

    self.term = IPython.genutils.IOTerm(cin=cin, cout=cout, cerr=cerr)
    os.environ['TERM'] = 'dumb'
    excepthook = sys.excepthook
    self.IP = IPython.Shell.make_IPython(
      argv,user_ns=user_ns,
      user_global_ns=user_global_ns,
      embedded=True,
      shell_class=IPython.Shell.InteractiveShell)
    self.IP.system = lambda cmd: self.shell(self.IP.var_expand(cmd),
                                            header='IPython system call: ',
                                            verbose=self.IP.rc.system_verbose)
    sys.excepthook = excepthook
    self.iter_more = 0
    self.history_level = 0
    self.complete_sep =  re.compile('[\s\{\}\[\]\(\)]')

  def execute(self):
    """
    Execute the current line provided by the shell object
    """
    self.history_level = 0
    orig_stdout = sys.stdout
    sys.stdout = IPython.Shell.Term.cout
    try:
      line = self.IP.raw_input(None, self.iter_more)
      if self.IP.autoindent:
        self.IP.readline_startup_hook(None)
    except KeyboardInterrupt:
      self.IP.write('\nKeyboardInterrupt\n')
      self.IP.resetbuffer()
      # keep cache in sync with the prompt counter:
      self.IP.outputcache.prompt_count -= 1

      if self.IP.autoindent:
        self.IP.indent_current_nsp = 0
      self.iter_more = 0
    except:
      self.IP.showtraceback()
    else:
      self.iter_more = self.IP.push(line)
      if (self.IP.SyntaxTB.last_syntax_error and
          self.IP.rc.autoedit_syntax):
        self.IP.edit_syntax_error()
    if self.iter_more:
      self.prompt = str(self.IP.outputcache.prompt2).strip()
      if self.IP.autoindent:
        self.IP.readline_startup_hook(self.IP.pre_readline)
    else:
      self.prompt = str(self.IP.outputcache.prompt1).strip()
    sys.stdout = orig_stdout

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
    Returns an auto completed line and/or posibilities for completion

    @param line: Given line so far.
    @type line: string

    @return: Line completed as for as possible,
    and possible further completions.
    @rtype: tuple
    """
    split_line = self.complete_sep.split(line)
    possibilities = self.IP.complete(split_line[-1])

    try:
        __builtins__.all()
    except AttributeError:
        def all(iterable):
            for element in iterable:
                if not element:
                    return False
            return True

    def common_prefix(seq):
        """
		  Return the common prefix of a sequence of strings
		  """
        return "".join(c for i, c in enumerate(seq[0])
                if all(s.startswith(c, i) for s in seq))
    if possibilities:
      completed = line[:-len(split_line[-1])]+common_prefix(possibilities)
    else:
      completed = line
    return completed, possibilities


  def shell(self, cmd,verbose=0,debug=0,header=''):
    """
    Replacement method to allow shell commands without them blocking

    @param cmd: Shell command to execute.
    @type cmd: string
    @param verbose: Verbosity
    @type verbose: integer
    @param debug: Debug level
    @type debug: integer
    @param header: Header to be printed before output
    @type header: string
    """
    if verbose or debug: print header+cmd
    # flush stdout so we don't mangle python's buffering
    if not debug:
      input_, output = os.popen4(cmd)
      print output.read()
      output.close()
      input_.close()

class ConsoleView(gtk.TextView):
  """
  Specialized text view for console-like workflow

  @cvar ANSI_COLORS: Mapping of terminal colors to X11 names.
  @type ANSI_COLORS: dictionary

  @ivar text_buffer: Widget's text buffer.
  @type text_buffer: gtk.TextBuffer
  @ivar color_pat: Regex of terminal color pattern
  @type color_pat: _sre.SRE_Pattern
  @ivar mark: Scroll mark for automatic scrolling on input.
  @type mark: gtk.TextMark
  @ivar line_start: Start of command line mark.
  @type line_start: gtk.TextMark
  """

  ANSI_COLORS =  {'0;30': 'Black',     '0;31': 'Red',
                  '0;32': 'Green',     '0;33': 'Brown',
                  '0;34': 'Blue',      '0;35': 'Purple',
                  '0;36': 'Cyan',      '0;37': 'LightGray',
                  '1;30': 'DarkGray',  '1;31': 'DarkRed',
                  '1;32': 'SeaGreen',  '1;33': 'Yellow',
                  '1;34': 'LightBlue', '1;35': 'MediumPurple',
                  '1;36': 'LightCyan', '1;37': 'White'}

  def __init__(self):
    """
    Initialize console view
    """
    gtk.TextView.__init__(self)
    self.modify_font(pango.FontDescription('Mono'))
    self.set_cursor_visible(True)
    self.text_buffer = self.get_buffer()
    self.mark = self.text_buffer.create_mark('scroll_mark',
                                             self.text_buffer.get_end_iter(),
                                             False)
    for code in self.ANSI_COLORS:
      self.text_buffer.create_tag(code,
                                  foreground=self.ANSI_COLORS[code],
                                  weight=700)
    self.text_buffer.create_tag('0')
    self.text_buffer.create_tag('notouch', editable=False)
    self.color_pat = re.compile('\x01?\x1b\[(.*?)m\x02?')
    self.line_start = \
        self.text_buffer.create_mark('line_start',
                                     self.text_buffer.get_end_iter(), True)
    self.connect('key-press-event', self.onKeyPress)

  def write(self, text, editable=False):
    gobject.idle_add(self._write, text, editable)

  def _write(self, text, editable=False):
    """
    Write given text to buffer

    @param text: Text to append.
    @type text: string
    @param editable: If true, added text is editable.
    @type editable: boolean
    """
    segments = self.color_pat.split(text)
    segment = segments.pop(0)
    start_mark = self.text_buffer.create_mark(None,
                                              self.text_buffer.get_end_iter(),
                                              True)
    self.text_buffer.insert(self.text_buffer.get_end_iter(), segment)

    if segments:
      ansi_tags = self.color_pat.findall(text)
      for tag in ansi_tags:
        i = segments.index(tag)
        self.text_buffer.insert_with_tags_by_name(self.text_buffer.get_end_iter(),
                                             segments[i+1], tag)
        segments.pop(i)
    if not editable:
      self.text_buffer.apply_tag_by_name('notouch',
                                         self.text_buffer.get_iter_at_mark(start_mark),
                                         self.text_buffer.get_end_iter())
    self.text_buffer.delete_mark(start_mark)
    self.scroll_mark_onscreen(self.mark)


  def showPrompt(self, prompt):
    gobject.idle_add(self._showPrompt, prompt)

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
    gobject.idle_add(self._changeLine, text)

  def _changeLine(self, text):
    """
    Replace currently entered command line with given text

    @param text: Text to use as replacement.
    @type text: string
    """
    iter_ = self.text_buffer.get_iter_at_mark(self.line_start)
    iter_.forward_to_line_end()
    self.text_buffer.delete(self.text_buffer.get_iter_at_mark(self.line_start), iter_)
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
    gobject.idle_add(self._showReturned, text)

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
    self._write('\n'+text)
    if text:
      self._write('\n')
    self._showPrompt(self.prompt)
    self.text_buffer.move_mark(self.line_start,self.text_buffer.get_end_iter())
    self.text_buffer.place_cursor(self.text_buffer.get_end_iter())

  def onKeyPress(self, widget, event):
    """
    Key press callback used for correcting behavior for console-like
    interfaces. For example 'home' should go to prompt, not to begining of
    line

    @param widget: Widget that key press accored in.
    @type widget: gtk.Widget
    @param event: Event object
    @type event: gtk.gdk.Event

    @return: Return True if event should not trickle.
    @rtype: boolean
    """
    insert_mark = self.text_buffer.get_insert()
    insert_iter = self.text_buffer.get_iter_at_mark(insert_mark)
    selection_mark = self.text_buffer.get_selection_bound()
    selection_iter = self.text_buffer.get_iter_at_mark(selection_mark)
    start_iter = self.text_buffer.get_iter_at_mark(self.line_start)
    if event.keyval == gtk.keysyms.Home:
      if event.state == 0:
        self.text_buffer.place_cursor(start_iter)
        return True
      elif event.state == gtk.gdk.SHIFT_MASK:
        self.text_buffer.move_mark(insert_mark, start_iter)
        return True
    elif event.keyval == gtk.keysyms.Left:
      insert_iter.backward_cursor_position()
      if not insert_iter.editable(True):
        return True
    elif not event.string:
      pass
    elif start_iter.compare(insert_iter) <= 0 and \
          start_iter.compare(selection_iter) <= 0:
      pass
    elif start_iter.compare(insert_iter) > 0 and \
          start_iter.compare(selection_iter) > 0:
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
    pass

class IPythonView(ConsoleView, IterableIPShell):
  '''
  Sub-class of both modified IPython shell and L{ConsoleView} this makes
  a GTK+ IPython console.
  '''
  def __init__(self):
    """
    Initialize. Redirect I/O to console
    """
    ConsoleView.__init__(self)
    self.cout = StringIO()
    IterableIPShell.__init__(self, cout=self.cout,cerr=self.cout,
                             input_func=self.raw_input)
#    self.connect('key_press_event', self.keyPress)
    self.execute()
    self.cout.truncate(0)
    self.showPrompt(self.prompt)
    self.interrupt = False

  def raw_input(self, prompt=''):
    """
    Custom raw_input() replacement. Get's current line from console buffer

    @param prompt: Prompt to print. Here for compatability as replacement.
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

    @param widget: Widget that key press occured in.
    @type widget: gtk.Widget
    @param event: Event object.
    @type event: gtk.gdk.Event

    @return: True if event should not trickle.
    @rtype: boolean
    """
    if event.state & gtk.gdk.CONTROL_MASK and event.keyval == 99:
      self.interrupt = True
      self._processLine()
      return True
    elif event.keyval == gtk.keysyms.Return:
      self._processLine()
      return True
    elif event.keyval == gtk.keysyms.Up:
      self.changeLine(self.historyBack())
      return True
    elif event.keyval == gtk.keysyms.Down:
      self.changeLine(self.historyForward())
      return True
    elif event.keyval == gtk.keysyms.Tab:
      if not self.getCurrentLine().strip():
        return False
      completed, possibilities = self.complete(self.getCurrentLine())
      if len(possibilities) > 1:
        slice_ = self.getCurrentLine()
        self.write('\n')
        for symbol in possibilities:
          self.write(symbol+'\n')
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
    if rv: rv = rv.strip('\n')
    self.showReturned(rv)
    self.cout.truncate(0)


# vim: se ts=3:
