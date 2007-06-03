# -*- coding: utf-8 -*-
##	adhoc_commands.py
##
## Copyright (C) 2006 Yann Le Boulanger <asterix@lagaule.org>
##                    Nikos Kouremenos <nkour@jabber.org>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 2 only.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.

# FIXME: think if we need caching command list. it may be wrong if there will
# be entities that often change the list, it may be slow to fetch it every time

import gobject
import gtk

from common import xmpp, gajim, dataforms

import gtkgui_helpers
import dialogs
import dataforms_widget

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
		self.window.connect('delete-event', self.on_adhoc_commands_window_delete_event)
		for name in ('back_button', 'forward_button',
			'execute_button','close_button','stages_notebook',
			'retrieving_commands_stage_vbox',
			'command_list_stage_vbox','command_list_vbox',
			'sending_form_stage_vbox','sending_form_progressbar',
			'notes_label','no_commands_stage_vbox','error_stage_vbox',
			'error_description_label'):
			self.__dict__[name] = self.xml.get_widget(name)

		# creating data forms widget
		self.data_form_widget = dataforms_widget.DataFormWidget()
		self.data_form_widget.show()
		self.sending_form_stage_vbox.pack_start(self.data_form_widget)

		# setting initial stage
		self.stage1()

		# displaying the window
		self.xml.signal_autoconnect(self)
		self.window.show_all()

# these functions are set up by appropriate stageX methods
	def stage_finish(self, *anything): pass
	def stage_back_button_clicked(self, *anything): assert False
	def stage_forward_button_clicked(self, *anything): assert False
	def stage_execute_button_clicked(self, *anything): assert False
	def stage_close_button_clicked(self, *anything): assert False
	def stage_adhoc_commands_window_delete_event(self, *anything): assert False
	def do_nothing(self, *anything): return False

# widget callbacks
	def on_back_button_clicked(self, *anything):
		return self.stage_back_button_clicked(*anything)

	def on_forward_button_clicked(self, *anything):
		return self.stage_forward_button_clicked(*anything)

	def on_execute_button_clicked(self, *anything):
		return self.stage_execute_button_clicked(*anything)

	def on_close_button_clicked(self, *anything):
		return self.stage_close_button_clicked(*anything)

	def on_adhoc_commands_window_destroy(self, *anything):
		# TODO: do all actions that are needed to remove this object from memory...
		self.remove_pulsing()

	def on_adhoc_commands_window_delete_event(self, *anything):
		return self.stage_adhoc_commands_window_delete_event(self.window)

	def __del__(self):
		print "Object has been deleted."

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
		self.close_button.set_sensitive(True)
		self.back_button.set_sensitive(False)
		self.forward_button.set_sensitive(False)
		self.execute_button.set_sensitive(False)

		# request command list
		self.request_command_list()
		self.setup_pulsing(
			self.xml.get_widget('retrieving_commands_progressbar'))

		# setup the callbacks
		self.stage_finish = self.stage1_finish
		self.stage_close_button_clicked = self.stage1_close_button_clicked
		self.stage_adhoc_commands_window_delete_event = self.stage1_adhoc_commands_window_delete_event

	def stage1_finish(self):
		self.remove_pulsing()

	def stage1_close_button_clicked(self, widget):
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
		(FIXME: if there is more commands, maybe some kind of list?),
		set widgets' state.'''
		# close old stage
		self.stage_finish()

		assert len(self.commandlist)>0

		self.stages_notebook.set_current_page(
			self.stages_notebook.page_num(
				self.command_list_stage_vbox))

		self.close_button.set_sensitive(True)
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
			self.command_list_vbox.pack_start(radio, expand=False)
		self.command_list_vbox.show_all()

		self.stage_finish = self.stage2_finish
		self.stage_close_button_clicked = self.stage2_close_button_clicked
		self.stage_forward_button_clicked = self.stage2_forward_button_clicked
		self.stage_adhoc_commands_window_delete_event = self.do_nothing

	def stage2_finish(self):
		'''Remove widgets we created. Not needed when the window is destroyed.'''
		def remove_widget(widget):
			self.command_list_vbox.remove(widget)
		self.command_list_vbox.foreach(remove_widget)

	def stage2_close_button_clicked(self, widget):
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

		self.form_status = None

		self.stages_notebook.set_current_page(
			self.stages_notebook.page_num(
				self.sending_form_stage_vbox))

		self.close_button.set_sensitive(True)
		self.back_button.set_sensitive(False)
		self.forward_button.set_sensitive(False)
		self.execute_button.set_sensitive(False)

		self.stage3_submit_form()

		self.stage_finish = self.stage3_finish
		self.stage_back_button_clicked = self.stage3_back_button_clicked
		self.stage_forward_button_clicked = self.stage3_forward_button_clicked
		self.stage_execute_button_clicked = self.stage3_execute_button_clicked
		self.stage_close_button_clicked = self.stage3_close_button_clicked
		self.stage_adhoc_commands_window_delete_event = self.stage3_close_button_clicked

	def stage3_finish(self):
		pass

	def stage3_close_button_clicked(self, widget):
		''' We are in the middle of executing command. Ask user if he really want to cancel
		the process, then... cancel it. '''
		# this works also as a handler for window_delete_event, so we have to return appropriate
		# values
		if self.form_status == 'completed':
			if widget!=self.window:
				self.window.destroy()
			return False

		dialog = dialogs.HigDialog(self.window, gtk.DIALOG_DESTROY_WITH_PARENT | gtk.DIALOG_MODAL,
			gtk.BUTTONS_YES_NO, 'Cancel confirmation',
			'You are in process of executing command. Do you really want to cancel it?')
		dialog.popup()
		if dialog.get_response()==gtk.RESPONSE_YES:
			self.send_cancel()
			if widget==self.window:
				return False
			else:
				self.window.destroy()
			return False
		return True

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
		else:
			self.data_form_widget.data_form.type='submit'

		self.close_button.set_sensitive(True)
		self.back_button.set_sensitive(False)
		self.forward_button.set_sensitive(False)
		self.execute_button.set_sensitive(False)

		self.sending_form_progressbar.show()
		self.setup_pulsing(self.sending_form_progressbar)
		self.send_command(action)

	def stage3_next_form(self, command):
		assert isinstance(command, xmpp.Node)

		self.remove_pulsing()
		self.sending_form_progressbar.hide()

		if self.sessionid is None:
			self.sessionid = command.getAttr('sessionid')

		self.form_status = command.getAttr('status')

		self.commandnode = command.getAttr('node')
		if command.getTag('x') is not None:
			self.dataform = dataforms.ExtendForm(node=command.getTag('x'))

			self.data_form_widget.set_sensitive(True)
			try:
				self.data_form_widget.data_form=self.dataform
			except dataforms.Error:
				# FIXME: translate
				self.stage5(error='Service sent malformed data', senderror=True)
				return
			self.data_form_widget.show()
			if self.data_form_widget.title:
				self.window.set_title("%s - Ad-hoc Commands - Gajim" % \
					self.data_form_widget.title)
		else:
			self.data_form_widget.hide()

		action = command.getTag('action')
		if action is None:
			self.close_button.set_sensitive(True)
			self.back_button.set_sensitive(False)
			self.forward_button.set_sensitive(False)
			self.execute_button.set_sensitive(True)
		else:
			# actions, actions, actions...
			self.close_button.set_sensitive(True)
			self.back_button.set_sensitive(action.getTag('prev') is not None)
			self.forward_button.set_sensitive(action.getTag('next') is not None)
			self.execute_button.set_sensitive(True)

		if self.form_status == 'completed':
			self.close_button.set_sensitive(True)
			self.back_button.hide()
			self.forward_button.hide()
			self.execute_button.hide()
			self.close_button.show()
			self.stage_adhoc_commands_window_delete_event = self.stage3_close_button_clicked

		note = command.getTag('note')
		if note is not None:
			self.notes_label.set_text(note.getData().decode('utf-8'))
			self.notes_label.set_no_show_all(False)
			self.notes_label.show()
		else:
			self.notes_label.set_no_show_all(True)
			self.notes_label.hide()

# stage 4: no commands are exposed
	def stage4(self):
		'''Display the message. Wait for user to close the window'''
		# close old stage
		self.stage_finish()

		self.stages_notebook.set_current_page(
			self.stages_notebook.page_num(
				self.no_commands_stage_vbox))

		self.close_button.set_sensitive(True)
		self.back_button.set_sensitive(False)
		self.forward_button.set_sensitive(False)
		self.execute_button.set_sensitive(False)

		self.stage_finish = self.do_nothing
		self.stage_close_button_clicked = self.stage4_close_button_clicked
		self.stage_adhoc_commands_window_delete_event = self.do_nothing

	def stage4_close_button_clicked(self, widget):
		self.window.destroy()

	def on_check_commands_2_button_clicked(self, widget):
		self.stage1()

# stage 5: an error has occured
	def stage5(self, error=None, errorid=None, senderror=False):
		'''Display the error message. Wait for user to close the window'''
		# FIXME: sending error to responder
		# close old stage
		self.stage_finish()

		assert errorid is not None or error is not None

		if errorid is not None:
			# we've got error code, display appropriate message
			try:
				errorname = xmpp.NS_STANZAS + ' ' + str(errorid)
				errordesc = xmpp.ERRORS[errorname][2]
				error = errordesc.decode('utf-8')
				del errorname, errordesc
			except KeyError:	# when stanza doesn't have error description
				error = 'Service returned an error.'
		elif error is not None:
			# we've got error message
			pass
		else:
			# we don't know what's that, bailing out
			assert False

		self.stages_notebook.set_current_page(
			self.stages_notebook.page_num(
				self.error_stage_vbox))

		self.close_button.set_sensitive(True)
		self.back_button.hide()
		self.forward_button.hide()
		self.execute_button.hide()

		self.error_description_label.set_text(error)

		self.stage_finish = self.do_nothing
		self.stage_close_button_clicked = self.stage5_close_button_clicked
		self.stage_adhoc_commands_window_delete_event = self.do_nothing

	def stage5_close_button_clicked(self, widget):
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
			# FIXME: move to connection_handlers.py
			# is error => error stage
			error = response.getError()
			if error is not None:
				# extracting error description from xmpp/protocol.py
				self.stage5(errorid = error)
				return

			# no commands => no commands stage
			# commands => command selection stage
			query = response.getTag('query')
			if query:
				items = query.getTags('item')
			else:
				items = []
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
#			cmdnode.addChild(node=dataforms.DataForm(tofill=self.data_form_widget.data_form))
			# FIXME: simplified form to send
			
			cmdnode.addChild(node=self.data_form_widget.data_form)

		def callback(response):
			# FIXME: move to connection_handlers.py
			err = response.getError()
			if err is not None:
				self.stage5(errorid = err)
			else:
				self.stage3_next_form(response.getTag('command'))

		self.account.connection.SendAndCallForResponse(stanza, callback)

	def send_cancel(self):
		'''Send the command with action='cancel'. '''
		assert self.commandnode is not None
		if self.sessionid is not None and self.account.connection:
			# we already have sessionid, so the service sent at least one reply.
			stanza = xmpp.Iq(typ='set', to=self.jid)
			stanza.addChild('command', attrs={
					'xmlns':xmpp.NS_COMMANDS,
					'node':self.commandnode,
					'sessionid':self.sessionid,
					'action':'cancel'
				})

			self.account.connection.send(stanza)
		else:
			# we did not received any reply from service; FIXME: we should wait and
			# then send cancel; for now we do nothing
			pass
