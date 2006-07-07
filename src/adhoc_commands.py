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

from common import xmpp, gajim, dataforms

import gtkgui_helpers
import dataforms as dataformwidget

class CommandWindow:
	'''Class for a window for single ad-hoc commands session. Note, that
	there might be more than one for one account/jid pair in one moment.

	TODO: maybe put this window into MessageWindow? consider this when
	TODO: it will be possible to manage more than one window of one
	TODO: account/jid pair in MessageWindowMgr.

	TODO: gtk 2.10 has a special wizard-widget, consider using it...'''

	def __init__(self, account, jid):
		'''Create new window.'''

		# an account object
		self.account = gajim.connections[account]
		self.jid = jid

		self.pulse_id=None	# to satisfy self.setup_pulsing()
		self.commandlist=None	# a list of (commandname, commanddescription)

		# command's data
		self.commandnode = None
		self.sessionid = None
		self.dataform = None

		# retrieving widgets from xml
		self.xml = gtkgui_helpers.get_glade('adhoc_commands_window.glade')
		self.window = self.xml.get_widget('adhoc_commands_window')
		for name in ('cancel_button', 'back_button', 'forward_button',
			'execute_button','stages_notebook',
			'retrieving_commands_stage_vbox',
			'command_list_stage_vbox','command_list_vbox',
			'sending_form_stage_vbox','sending_form_progressbar',
			'no_commands_stage_vbox','error_stage_vbox',
			'error_description_label'):
			self.__dict__[name] = self.xml.get_widget(name)

		# creating data forms widget
		self.data_form_widget = dataformwidget.DataFormWidget()
		self.data_form_widget.show()
		self.sending_form_stage_vbox.pack_start(self.data_form_widget)

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
	def stage_cancel_button_clicked(self, *anything): assert False
	def stage_back_button_clicked(self, *anything): assert False
	def stage_forward_button_clicked(self, *anything): assert False
	def stage_execute_button_clicked(self, *anything): assert False
	def stage_adhoc_commands_window_destroy(self, *anything): assert False
	def stage_adhoc_commands_window_delete_event(self, *anything): assert False
	def do_nothing(self, *anything): return False

# widget callbacks
	def on_cancel_button_clicked(self, *anything):
		return self.stage_cancel_button_clicked(*anything)

	def on_back_button_clicked(self, *anything):
		return self.stage_back_button_clicked(*anything)

	def on_forward_button_clicked(self, *anything):
		return self.stage_forward_button_clicked(*anything)

	def on_execute_button_clicked(self, *anything):
		return self.stage_execute_button_clicked(*anything)

	def on_adhoc_commands_window_destroy(self, *anything):
		return self.stage_adhoc_commands_window_destroy(*anything)

	def on_adhoc_commands_window_delete_event(self, *anything):
		return self.stage_adhoc_commands_window_delete_event(self, *anything)

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
		self.stage_cancel_button_clicked = self.stage1_cancel_button_clicked
		self.stage_adhoc_commands_window_delete_event = self.stage1_adhoc_commands_window_delete_event
		self.stage_adhoc_commands_window_destroy = self.do_nothing

	def stage1_finish(self):
		self.remove_pulsing()

	def stage1_cancel_button_clicked(self, widget):
		# cancelling in this stage is not critical, so we don't
		# show any popups to user
		self.stage1_finish()
		self.window.destroy()

	def stage1_adhoc_commands_window_delete_event(self, widget):
		self.stage1_finish()
		return True

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
			radio.connect("toggled", self.on_command_radiobutton_toggled, commandnode)
			if first_radio is None:
				first_radio = radio
				self.commandnode = commandnode
			self.command_list_vbox.pack_end(radio, expand=False)
		self.command_list_vbox.show_all()

		self.stage_finish = self.stage2_finish
		self.stage_cancel_button_clicked = self.stage2_cancel_button_clicked
		self.stage_forward_button_clicked = self.stage2_forward_button_clicked
		self.stage_adhoc_commands_window_destroy = self.do_nothing
		self.stage_adhoc_commands_window_delete_event = self.do_nothing

	def stage2_finish(self):
		'''Remove widgets we created. Not needed when the window is destroyed.'''
		def remove_widget(widget):
			self.command_list_vbox.remove(widget)
		self.command_list_vbox.foreach(remove_widget)

	def stage2_cancel_button_clicked(self, widget):
		self.stage_finish()
		self.window.destroy()

	def stage2_forward_button_clicked(self, widget):
		self.stage3()

	def on_command_radiobutton_toggled(self, widget, commandnode):
		self.commandnode = commandnode

	def on_check_commands_1_button_clicked(self, widget):
		self.stage1()

# stage 3: command invocation
	def stage3(self):
		# close old stage
		self.stage_finish()

		assert isinstance(self.commandnode, unicode)

		self.stages_notebook.set_current_page(
			self.stages_notebook.page_num(
				self.sending_form_stage_vbox))

		self.cancel_button.set_sensitive(True)
		self.back_button.set_sensitive(False)
		self.forward_button.set_sensitive(False)
		self.execute_button.set_sensitive(False)

		self.stage3_submit_form()

		self.stage_finish = self.stage3_finish
		self.stage_cancel_button_clicked = self.stage3_cancel_button_clicked
		self.stage_back_button_clicked = self.stage3_back_button_clicked
		self.stage_forward_button_clicked = self.stage3_forward_button_clicked
		self.stage_execute_button_clicked = self.stage3_execute_button_clicked
		self.stage_adhoc_commands_window_destroy = self.do_nothing
		self.stage_adhoc_commands_window_delete_event = self.do_nothing

	def stage3_finish(self):
		pass

	def stage3_cancel_button_clicked(self, widget):
		pass

	def stage3_back_button_clicked(self, widget):
		self.stage3_submit_form('prev')

	def stage3_forward_button_clicked(self, widget):
		self.stage3_submit_form('next')

	def stage3_execute_button_clicked(self, widget):
		self.stage3_submit_form('execute')

	def stage3_submit_form(self, action='execute'):
		self.data_form_widget.set_sensitive(False)
		if self.data_form_widget.get_data_form() is None:
			self.data_form_widget.hide()
		self.sending_form_progressbar.show()
		self.setup_pulsing(self.sending_form_progressbar)
		self.send_command(action)

	def stage3_next_form(self, command):
		assert isinstance(command, xmpp.Node)

		self.remove_pulsing()
		self.sending_form_progressbar.hide()

		if self.sessionid is None:
			self.sessionid = command.getAttr('sessionid')

		self.dataform = dataforms.DataForm(node=command.getTag('x'))

		self.data_form_widget.set_sensitive(True)
		self.data_form_widget.set_data_form(self.dataform)
		self.data_form_widget.show()

		action = command.getTag('action')
		if action is None:
			# no action tag? that's last stage...
			self.cancel_button.set_sensitive(False)
			self.back_button.set_sensitive(False)
			self.forward_button.set_sensitive(False)
			self.execute_button.set_sensitive(True)
		else:
			# actions, actions, actions...
			self.cancel_button.set_sensitive(False)
			self.back_button.set_sensitive(action.getTag('prev') is not None)
			self.forward_button.set_sensitive(action.getTag('next') is not None)
			self.execute_button.set_sensitive(True)

# stage 4: no commands are exposed
	def stage4(self):
		'''Display the message. Wait for user to close the window'''
		# close old stage
		self.stage_finish()

		self.stages_notebook.set_current_page(
			self.stages_notebook.page_num(
				self.no_commands_stage_vbox))

		self.cancel_button.set_sensitive(True)
		self.back_button.set_sensitive(False)
		self.forward_button.set_sensitive(False)
		self.execute_button.set_sensitive(False)

		self.stage_finish = self.do_nothing
		self.stage_cancel_button_clicked = self.stage4_cancel_button_clicked
		self.stage_adhoc_commands_window_destroy = self.do_nothing
		self.stage_adhoc_commands_window_delete_event = self.do_nothing

	def stage4_cancel_button_clicked(self, widget):
		self.window.destroy()

	def on_check_commands_2_button_clicked(self, widget):
		self.stage1()

# stage 5: an error has occured
	def stage5(self, error):
		'''Display the error message. Wait for user to close the window'''
		# close old stage
		self.stage_finish()

		assert isinstance(error, unicode)

		self.stages_notebook.set_current_page(
			self.stages_notebook.page_num(
				self.error_stage_vbox))

		self.cancel_button.set_sensitive(True)
		self.back_button.set_sensitive(False)
		self.forward_button.set_sensitive(False)
		self.execute_button.set_sensitive(False)

		self.error_description_label.set_text(error)

		self.stage_finish = self.do_nothing
		self.stage_cancel_button_clicked = self.stage5_cancel_button_clicked
		self.stage_adhoc_commands_window_destroy = self.do_nothing
		self.stage_adhoc_commands_window_delete_event = self.do_nothing

	def stage5_cancel_button_clicked(self, widget):
		self.window.destroy()

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
			# TODO: move to connection_handlers.py
			# is error => error stage
			error = response.getError()
			if error is not None:
				# extracting error description from xmpp/protocol.py
				errorname=xmpp.NS_STANZAS + ' ' + str(error)
				errordesc=xmpp.ERRORS[errorname][2]
				self.stage5(errordesc.decode('utf-8'))
				return

			# no commands => no commands stage
			# commands => command selection stage
			items = response.getTag('query').getTags('item')
			if len(items)==0:
				self.commandlist = []
				self.stage4()
			else:
				self.commandlist = [(t.getAttr('node'), t.getAttr('name')) for t in items]
				self.stage2()

		self.account.connection.SendAndCallForResponse(query, callback)

	def send_command(self, action='execute'):
		'''Send the command with data form. Wait for reply.'''
		# create the stanza
		assert isinstance(self.commandnode, unicode)
		assert action in ('execute', 'prev', 'next', 'complete')

		stanza = xmpp.Iq(typ='set', to=self.jid)
		cmdnode = stanza.addChild('command', attrs={
				'xmlns':xmpp.NS_COMMANDS,
				'node':self.commandnode,
				'action':action
			})

		if self.sessionid is not None:
			cmdnode.setAttr('sessionid', self.sessionid)

		if self.data_form_widget.data_form is not None:
			cmdnode.addChild(node=dataforms.DataForm(tofill=self.data_form_widget.data_form))

		def callback(response):
			# TODO: error handling
			# TODO: move to connection_handlers.py
			self.stage3_next_form(response.getTag('command'))

		print stanza

		self.account.connection.SendAndCallForResponse(stanza, callback)
