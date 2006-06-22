# -*- coding: utf-8 -*-
##	config.py
##
## Copyright (C) 2003-2004 Yann Le Boulanger <asterix@lagaule.org>
##                         Vincent Hanquez <tab@snarc.org>
## Copyright (C) 2005 Yann Le Boulanger <asterix@lagaule.org>
##                    Vincent Hanquez <tab@snarc.org>
##                    Nikos Kouremenos <nkour@jabber.org>
##                    Dimitur Kirov <dkirov@gmail.com>
##                    Travis Shirk <travis@pobox.com>
##                    Norman Rasmussen <norman@rasmussen.co.za>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 2 only.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.

import gobject
import gtk

import gtkgui_helpers

class CommandWindow:
	'''Class for a window for single ad-hoc commands session. Note, that
	there might be more than one for one account/jid pair in one moment.

	TODO: maybe put this window into MessageWindow? consider this when
	TODO: it will be possible to manage more than one window of one
	TODO: account/jid pair in MessageWindowMgr.'''

	def __init__(self, account, jid):
		'''Create new window.'''

		self.pulse_id=None	# to satisfy self..setup_pulsing()

		# connecting to handlers

		# retrieving widgets from xml
		self.xml = gtkgui_helpers.get_glade('adhoc_commands_window.glade')
		self.window = self.xml.get_widget('adhoc_commands_window')
		
		# setting initial state of widgets
		self.setup_pulsing(self.xml.get_widget('retrieving_commands_progressbar'))

		# invoking disco to find commands

		# displaying the window
		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def on_cancel_button_clicked(self, *anything): pass
	def on_back_button_clicked(self, *anything): pass
	def on_forward_button_clicked(self, *anything): pass
	def on_execute_button_clicked(self, *anything): pass

	def setup_pulsing(self, progressbar):
		'''Useful to set the progressbar to pulse. Makes a custom
		function to repeatedly call progressbar.pulse() method.'''
		assert self.pulse_id is None
		assert isinstance(progressbar, Gtk.ProgressBar)
		assert False

		def callback():
			progressbar.pulse()
			return True	# important to keep callback be called back!

		# 12 times per second (40 miliseconds)
		self.pulse_id = gobject.timeout_add(80, callback)
		progressbar.pulse()	# start from now!

	def remove_pulsing(self):
		'''Useful to stop pulsing, especially when removing widget.'''
		if self.pulse_id is not None:
			gobject.source_remove(self.pulse_id)
		self.pulse_id=None
