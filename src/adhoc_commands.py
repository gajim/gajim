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

# TODO: think if we need caching command list. it may be wrong if there will
# TODO: be entities that often change the list, it may be slow to fetch it
# TODO: every time

import gobject
import gtk

import common.xmpp as xmpp
import common.gajim as gajim

import gtkgui_helpers

class CommandWindow:
	'''Class for a window for single ad-hoc commands session. Note, that
	there might be more than one for one account/jid pair in one moment.

	TODO: maybe put this window into MessageWindow? consider this when
	TODO: it will be possible to manage more than one window of one
	TODO: account/jid pair in MessageWindowMgr.'''

	def __init__(self, account, jid):
		'''Create new window.'''

		# an account object
		self.account = gajim.connections[account]
		self.jid = jid

		self.pulse_id=None	# to satisfy self.setup_pulsing()
		self.commandlist=None	# a list of (commandname, commanddescription)

		# retrieving widgets from xml
		self.xml = gtkgui_helpers.get_glade('adhoc_commands_window.glade')
		self.window = self.xml.get_widget('adhoc_commands_window')
		for name in ('cancel_button', 'back_button', 'forward_button',
			'execute_button','stages_notebook',
			'retrieving_commands_stage_vbox',
			'command_list_stage_vbox','command_list_vbox',
			'sending_form_stage_vbox'):
			self.__dict__[name] = self.xml.get_widget(name)
		
		# setting initial stage
		self.stage1()

		# displaying the window
		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def on_adhoc_commands_window_destroy(self, window):
		''' The window dissappeared somehow... clean the environment,
		Stop pulsing.'''
		self.remove_pulsing()

# these functions are set up by appropriate stageX methods
	def stage_finish(self, *anything): pass
	def on_cancel_button_clicked(self, *anything): pass
	def on_back_button_clicked(self, *anything): pass
	def on_forward_button_clicked(self, *anything): pass
	def on_execute_button_clicked(self, *anything): pass
	def on_adhoc_commands_window_destroy(self, *anything): pass

# stage 1: waiting for command list
	def stage1(self):
		'''Prepare the first stage. Request command list,
		set appropriate state of widgets.'''
		# close old stage...
		self.stage_finish()

		# show the stage
		self.stages_notebook.set_current_page(
			self.stages_notebook.page_num(
				self.retrieving_commands_stage_vbox))

		# set widgets' state
		self.cancel_button.set_sensitive(True)
		self.back_button.set_sensitive(False)
		self.forward_button.set_sensitive(False)
		self.execute_button.set_sensitive(False)

		# request command list
		self.request_command_list()
		self.setup_pulsing(
			self.xml.get_widget('retrieving_commands_progressbar'))

		# setup the callbacks
		self.stage_finish = self.stage1_finish
		self.on_cancel_button_clicked = self.stage1_on_cancel_button_clicked

	def stage1_finish(self):
		self.remove_pulsing()

	def stage1_on_cancel_button_clicked(self, widget):
		# cancelling in this stage is not critical, so we don't
		# show any popups to user
		self.stage1_finish()
		self.window.destroy()

# stage 2: choosing the command to execute
	def stage2(self):
		'''Populate the command list vbox with radiobuttons
		(TODO: if there is more commands, maybe some kind of list?),
		set widgets' state.'''
		# close old stage
		self.stage_finish()

		assert len(self.commandlist)>0

		self.stages_notebook.set_current_page(
			self.stages_notebook.page_num(
				self.command_list_stage_vbox))

		self.cancel_button.set_sensitive(True)
		self.back_button.set_sensitive(False)
		self.forward_button.set_sensitive(True)
		self.execute_button.set_sensitive(False)

		# build the commands list radiobuttons
		first_radio = None
		for (commandnode, commandname) in self.commandlist:
			radio = gtk.RadioButton(first_radio, label=commandname)
			if first_radio is None: first_radio = radio
			self.command_list_vbox.pack_end(radio, expand=False)
		self.command_list_vbox.show_all()

		self.stage_finish = self.stage_finish
		self.on_cancel_button_clicked = self.stage2_on_cancel_button_clicked
		self.on_forward_button_clicked = self.stage2_on_forward_button_clicked

	def stage2_on_cancel_button_clicked(self):
		self.stage_finish()
		self.window.destroy()

	def stage2_on_forward_button_clicked(self):
		pass

# helpers to handle pulsing in progressbar
	def setup_pulsing(self, progressbar):
		'''Set the progressbar to pulse. Makes a custom
		function to repeatedly call progressbar.pulse() method.'''
		assert self.pulse_id is None
		assert isinstance(progressbar, gtk.ProgressBar)

		def callback():
			progressbar.pulse()
			return True	# important to keep callback be called back!

		# 12 times per second (80 miliseconds)
		self.pulse_id = gobject.timeout_add(80, callback)

	def remove_pulsing(self):
		'''Stop pulsing, useful when especially when removing widget.'''
		if self.pulse_id is not None:
			gobject.source_remove(self.pulse_id)
		self.pulse_id=None

# handling xml stanzas
	def request_command_list(self):
		'''Request the command list. Change stage on delivery.'''
		query = xmpp.Iq(typ='get', to=xmpp.JID(self.jid), xmlns=xmpp.NS_DISCO_ITEMS)
		query.setQuerynode(xmpp.NS_COMMANDS)

		def callback(response):
			'''Called on response to query.'''
			# is error => error stage
			error = response.getError()
			if error is not None:
				pass

			# no commands => no commands stage
			# commands => command selection stage
			items = response.getTag('query').getTags('item')
			if len(items)==0:
				self.commandlist = []
				self.stage2() # stageX, where X is the number for error page
			else:
				self.commandlist = [(t.getAttr('node'), t.getAttr('name')) for t in items]
				self.stage2()

		self.account.connection.SendAndCallForResponse(query, callback)
