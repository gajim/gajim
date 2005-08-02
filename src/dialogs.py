##	dialogs.py
##
## Gajim Team:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Vincent Hanquez <tab@snarc.org>
##	- Nikos Kouremenos <kourem@gmail.com>
##  - Dimitur Kirov <dkirov@gmail.com>
##
##	Copyright (C) 2003-2005 Gajim Team
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 2 only.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##

import gtk
import gtk.glade
import gobject
import os

import gtkgui_helpers

from vcard import VcardWindow
from gajim_themes_window import GajimThemesWindow
from advanced import AdvancedConfigurationWindow
from gajim import Contact
from common import gajim
from common import i18n
from common import helpers

_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain (APP, i18n.DIR)
gtk.glade.textdomain (APP)

GTKGUI_GLADE = 'gtkgui.glade'

class EditGroupsDialog:
	'''Class for the edit group dialog window'''
	def __init__(self, user, account, plugin):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'edit_groups_dialog', APP)
		self.dialog = self.xml.get_widget('edit_groups_dialog')
		self.plugin = plugin
		self.account = account
		self.user = user
		self.changes_made = False
		self.list = self.xml.get_widget('groups_treeview')
		self.xml.get_widget('nickname_label').set_markup(
			_("Contact's name: <i>%s</i>") % user.name)
		self.xml.get_widget('jid_label').set_markup(
			_('JID: <i>%s</i>') % user.jid)
		
		self.xml.signal_autoconnect(self)
		self.init_list()

	def run(self):
		self.dialog.show_all()
		if self.changes_made:
			gajim.connections[self.account].update_contact(self.user.jid,
				self.user.name, self.user.groups)

	def on_edit_groups_dialog_response(self, widget, response_id):
		if response_id == gtk.RESPONSE_CLOSE:
			self.dialog.destroy()

	def update_contact(self):
		self.plugin.roster.remove_contact(self.user, self.account)
		self.plugin.roster.add_contact_to_roster(self.user.jid, self.account)
		gajim.connections[self.account].update_contact(self.user.jid,
			self.user.name, self.user.groups)

	def on_add_button_clicked(self, widget):
		group = self.xml.get_widget('group_entry').get_text()
		if not group:
			return
		# check if it already exists
		model = self.list.get_model()
		iter = model.get_iter_root()
		while iter:
			if model.get_value(iter, 0) == group:
				return
			iter = model.iter_next(iter)
		self.changes_made = True
		model.append((group, True))
		self.user.groups.append(group)
		self.update_contact()

	def group_toggled_cb(self, cell, path):
		self.changes_made = True
		model = self.list.get_model()
		if model[path][1] and len(self.user.groups) == 1: # we try to remove 
																		  # the last group
			ErrorDialog(_('Cannot remove last group'),
					_('At least one contact group must be present.')).get_response()
			return
		model[path][1] = not model[path][1]
		if model[path][1]:
			self.user.groups.append(model[path][0])
		else:
			self.user.groups.remove(model[path][0])
		self.update_contact()

	def init_list(self):
		store = gtk.ListStore(str, bool)
		self.list.set_model(store)
		for g in gajim.groups[self.account].keys():
			if g in [_('Transports'), _('not in the roster')]:
				continue
			iter = store.append()
			store.set(iter, 0, g)
			if g in self.user.groups:
				store.set(iter, 1, True)
			else:
				store.set(iter, 1, False)
		column = gtk.TreeViewColumn(_('Group'))
		self.list.append_column(column)
		renderer = gtk.CellRendererText()
		column.pack_start(renderer)
		column.set_attributes(renderer, text = 0)
		
		column = gtk.TreeViewColumn(_('In the group'))
		self.list.append_column(column)
		renderer = gtk.CellRendererToggle()
		column.pack_start(renderer)
		renderer.set_property('activatable', True)
		renderer.connect('toggled', self.group_toggled_cb)
		column.set_attributes(renderer, active = 1)

class PassphraseDialog:
	'''Class for Passphrase dialog'''
	def run(self):
		'''Wait for OK button to be pressed and return passphrase/password'''
		rep = self.window.run()
		if rep == gtk.RESPONSE_OK:
			passphrase = self.passphrase_entry.get_text()
		else:
			passphrase = -1
		save_passphrase_checkbutton = self.xml.\
			get_widget('save_passphrase_checkbutton')
		self.window.destroy()
		return passphrase, save_passphrase_checkbutton.get_active()

	def __init__(self, titletext, labeltext, checkbuttontext):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'passphrase_dialog', APP)
		self.window = self.xml.get_widget('passphrase_dialog')
		self.passphrase_entry = self.xml.get_widget('passphrase_entry')
		self.passphrase = -1
		self.window.set_title(titletext)
		self.xml.get_widget('message_label').set_text(labeltext)
		self.xml.get_widget('save_passphrase_checkbutton').set_label(
			checkbuttontext)
		self.xml.signal_autoconnect(self)
		self.window.show_all()

class ChooseGPGKeyDialog:
	'''Class for GPG key dialog'''
	def __init__(self, title_text, prompt_text, secret_keys, selected = None):
		#list : {keyID: userName, ...}
		xml = gtk.glade.XML(GTKGUI_GLADE, 'choose_gpg_key_dialog', APP)
		self.window = xml.get_widget('choose_gpg_key_dialog')
		self.window.set_title(title_text)
		self.keys_treeview = xml.get_widget('keys_treeview')
		prompt_label = xml.get_widget('prompt_label')
		prompt_label.set_text(prompt_text)
		model = gtk.ListStore(str, str)
		self.keys_treeview.set_model(model)
		#columns
		renderer = gtk.CellRendererText()
		self.keys_treeview.insert_column_with_attributes(-1, _('KeyID'),
			renderer, text = 0)
		renderer = gtk.CellRendererText()
		self.keys_treeview.insert_column_with_attributes(-1, _('Contact name'),
			renderer, text = 1)
		self.fill_tree(secret_keys, selected)
		self.window.show_all()

	def run(self):
		rep = self.window.run()
		if rep == gtk.RESPONSE_OK:
			selection = self.keys_treeview.get_selection()
			(model, iter) = selection.get_selected()
			keyID = [ model[iter][0], model[iter][1] ]
		else:
			keyID = None
		self.window.destroy()
		return keyID

	def fill_tree(self, list, selected):
		model = self.keys_treeview.get_model()
		for keyID in list.keys():
			iter = model.append((keyID, list[keyID]))
			if keyID == selected:
				path = model.get_path(iter)
				self.keys_treeview.set_cursor(path)


class ChangeStatusMessageDialog:
	def __init__(self, plugin, show):
		self.show = show
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'change_status_message_dialog', APP)
		self.window = self.xml.get_widget('change_status_message_dialog')
		uf_show = helpers.get_uf_show(show)
		self.window.set_title(_('%s Status Message') % uf_show)
		
		message_textview = self.xml.get_widget('message_textview')
		self.message_buffer = message_textview.get_buffer()
		msg = gajim.config.get('last_status_msg_' + show)
		if not msg:
			msg = ''
		msg = helpers.from_one_line(msg)
		self.message_buffer.set_text(msg)
		self.values = {'':''} # have an empty string selectable, so user can clear msg
		for msg in gajim.config.get_per('statusmsg'):
			self.values[msg] = gajim.config.get_per('statusmsg', msg, 'message')
		sorted_keys_list = helpers.get_sorted_keys(self.values)
		liststore = gtk.ListStore(str, str)
		message_comboboxentry = self.xml.get_widget('message_comboboxentry')
		message_comboboxentry.set_model(liststore)
		message_comboboxentry.set_text_column(0)
		message_comboboxentry.child.set_property('editable', False)
		for val in sorted_keys_list:
			message_comboboxentry.append_text(val)
		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def run(self):
		'''Wait for OK button to be pressed and return status messsage'''
		rep = self.window.run()
		if rep == gtk.RESPONSE_OK:
			beg, end = self.message_buffer.get_bounds()
			message = self.message_buffer.get_text(beg, end, 0).strip()
			msg = helpers.to_one_line(message)
			gajim.config.set('last_status_msg_' + self.show, msg)
		else:
			message = -1
		self.window.destroy()
		return message

	def on_message_comboboxentry_changed(self, widget, data = None):
		model = widget.get_model()
		active = widget.get_active()
		if active < 0:
			return None
		name = model[active][0]
		self.message_buffer.set_text(self.values[name])
	
	def on_change_status_message_dialog_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Return or \
		event.keyval == gtk.keysyms.KP_Enter:  # catch CTRL+ENTER
			if (event.state & gtk.gdk.CONTROL_MASK):
				self.window.response(gtk.RESPONSE_OK)

class AddNewContactWindow:
	'''Class for AddNewContactWindow'''
	def __init__(self, plugin, account, jid = None):
		self.plugin = plugin
		self.account = account
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'add_new_contact_window', APP)
		self.window = self.xml.get_widget('add_new_contact_window')
		self.uid_entry = self.xml.get_widget('uid_entry')
		self.protocol_combobox = self.xml.get_widget('protocol_combobox')
		self.jid_entry = self.xml.get_widget('jid_entry')
		self.nickname_entry = self.xml.get_widget('nickname_entry')
		if len(gajim.connections) >= 2:
			prompt_text =\
_('Please fill in the data of the contact you want to add in account %s') %account
		else:
			prompt_text = _('Please fill in the data of the contact you want to add')
		self.xml.get_widget('prompt_label').set_text(prompt_text)
		self.old_uid_value = ''
		liststore = gtk.ListStore(str, str)
		liststore.append(['Jabber', ''])
		self.agents = ['Jabber']
		jid_agents = []
		for j in gajim.contacts[account]:
			user = gajim.contacts[account][j][0]
			if _('Transports') in user.groups and user.show != 'offline' and \
					user.show != 'error':
				jid_agents.append(j)
		for a in jid_agents:
			if a.find('aim') > -1:
				name = 'AIM'
			elif a.find('icq') > -1:
				name = 'ICQ'
			elif a.find('msn') > -1:
				name = 'MSN'
			elif a.find('yahoo') > -1:
				name = 'Yahoo!'
			else:
				name = a
			iter = liststore.append([name, a])
			self.agents.append(name)
		
		self.protocol_combobox.set_model(liststore)
		self.protocol_combobox.set_active(0)
		self.fill_jid()
		if jid:
			self.jid_entry.set_text(jid)
			jid_splited = jid.split('@')
			if jid_splited[1] in jid_agents:
				uid = jid_splited[0].replace('%', '@')
				self.uid_entry.set_text(uid)
				self.protocol_combobox.set_active(jid_agents.index(jid_splited[1]) + 1)
			else:
				self.uid_entry.set_text(jid)
				self.protocol_combobox.set_active(0)
			self.set_nickname()

		self.group_comboboxentry = self.xml.get_widget('group_comboboxentry')
		liststore = gtk.ListStore(str)
		self.group_comboboxentry.set_model(liststore)
		for g in gajim.groups[account].keys():
			if g != _('not in the roster') and g != _('Transports'):
				self.group_comboboxentry.append_text(g)

		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def on_add_new_contact_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape: # ESCAPE
			self.window.destroy()

	def on_cancel_button_clicked(self, widget):
		'''When Cancel button is clicked'''
		self.window.destroy()

	def on_subscribe_button_clicked(self, widget):
		'''When Subscribe button is clicked'''
		jid = self.jid_entry.get_text()
		nickname = self.nickname_entry.get_text()
		if not jid:
			return
		if jid.find('@') < 0:
			ErrorDialog(_("Invalid user name"),
_('Contact names must be of the form "user@servername".')).get_response()
			return
		message_buffer = self.xml.get_widget('message_textview').get_buffer()
		start_iter = message_buffer.get_start_iter()
		end_iter = message_buffer.get_end_iter()
		message = message_buffer.get_text(start_iter, end_iter, 0)
		group = self.group_comboboxentry.child.get_text()
		self.plugin.roster.req_sub(self, jid, message, self.account,
			group = group, pseudo = nickname)
		if self.xml.get_widget('auto_authorize_checkbutton').get_active():
			gajim.connections[self.account].send_authorization(jid)
		self.window.destroy()
		
	def fill_jid(self):
		model = self.protocol_combobox.get_model()
		index = self.protocol_combobox.get_active()
		jid = self.uid_entry.get_text().strip()
		if index > 0: # it's not jabber but a transport
			jid = jid.replace('@', '%')
		agent = model[index][1]
		if agent:
			jid += '@' + agent
		self.jid_entry.set_text(jid)

	def on_protocol_combobox_changed(self, widget):
		self.fill_jid()

	def guess_agent(self):
		uid = self.uid_entry.get_text()
		model = self.protocol_combobox.get_model()
		
		#If login contains only numbers, it's probably an ICQ number
		if uid.isdigit():
			if 'ICQ' in self.agents:
				self.protocol_combobox.set_active(self.agents.index('ICQ'))
				return

	def set_nickname(self):
		uid = self.uid_entry.get_text()
		nickname = self.nickname_entry.get_text()
		if nickname == self.old_uid_value:
			self.nickname_entry.set_text(uid.split('@')[0])
			
	def on_uid_entry_changed(self, widget):
		uid = self.uid_entry.get_text()
		self.guess_agent()
		self.set_nickname()
		self.fill_jid()
		self.old_uid_value = uid.split('@')[0]

class AboutDialog:
	'''Class for about dialog'''
	def __init__(self):
		if gtk.pygtk_version < (2, 6, 0) or gtk.gtk_version < (2, 6, 0):
			InformationDialog(_('Gajim - a GTK+ Jabber client'),
				_('Version %s') % gajim.version).get_response()
			return

		dlg = gtk.AboutDialog()
		dlg.set_name('Gajim')
		dlg.set_version(gajim.version)
		s = u'Copyright \xa9 2003-2005 Gajim Team'
		dlg.set_copyright(s)
		text = open('../COPYING').read()
		dlg.set_license(text)

		dlg.set_comments(_('A GTK jabber client'))
		dlg.set_website('http://www.gajim.org')

		authors = ['Yann Le Boulanger <asterix@lagaule.org>', 'Vincent Hanquez <tab@snarc.org>', 'Nikos Kouremenos <kourem@gmail.com>', 'Alex Podaras <bigpod@gmail.com>', 'Gajim patchers']
		dlg.set_authors(authors)

		pixbuf = gtk.gdk.pixbuf_new_from_file(os.path.join(gajim.DATA_DIR, 'pixmaps/gajim_about.png'))			

		dlg.set_logo(pixbuf)
		dlg.set_translator_credits(_('translator_credits'))

		rep = dlg.run()
		dlg.destroy()

class Dialog(gtk.Dialog):
	def __init__(self, parent, title, buttons, default = None):
		gtk.Dialog.__init__(self, title, parent, gtk.DIALOG_DESTROY_WITH_PARENT | gtk.DIALOG_MODAL | gtk.DIALOG_NO_SEPARATOR)

		self.set_border_width(6)
		self.vbox.set_spacing(12)
		self.set_resizable(False)

		for stock, response in buttons:
			self.add_button(stock, response)

		if default is not None:
			self.set_default_response(default)
		else:
			self.set_default_response(buttons[-1][1])

	def get_button(self, index):
		buttons = self.action_area.get_children()
		return index < len(buttons) and buttons[index] or None


class HigDialog(Dialog):
	def __init__(self, parent, pritext, sectext, stockimage, buttons, default = None):
		"""GNOME higified version of the Dialog object. Inherit
		from here if possible when you need a new dialog."""
		Dialog.__init__(self, parent, "", buttons, default)

		# hbox separating dialog image and contents
		hbox = gtk.HBox()
		hbox.set_spacing(12)
		hbox.set_border_width(6)
		self.vbox.pack_start(hbox)

		# set up image
		if stockimage is not None:
			image = gtk.Image()
			image.set_from_stock(stockimage, gtk.ICON_SIZE_DIALOG)
			image.set_alignment(0.5, 0)
			hbox.pack_start(image, False, False)

		# set up main content area
		self.contents = gtk.VBox()
		self.contents.set_spacing(10)
		hbox.pack_start(self.contents)

		label = gtk.Label()
		label.set_markup("<span size=\"larger\" weight=\"bold\">" + pritext + "</span>\n\n" + sectext)
		label.set_line_wrap(True)
		label.set_alignment(0, 0)
		label.set_selectable(True)
		self.contents.pack_start(label)

	def get_response(self):
		self.show_all()
		response = gtk.Dialog.run(self)
		self.destroy()
		return response

class ConfirmationDialog(HigDialog):
	"""HIG compliant confirmation dialog."""
	def __init__(self, pritext, sectext=''):
		HigDialog.__init__(self, None, pritext, sectext,
			gtk.STOCK_DIALOG_WARNING, [ [gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL],
			[ gtk.STOCK_OK, gtk.RESPONSE_OK ] ])
			
class ConfirmationDialogCheck(ConfirmationDialog):
	'''HIG compliant confirmation dialog with checkbutton.'''
	def __init__(self, pritext, sectext='', checktext = ''):
		HigDialog.__init__(self, None, pritext, sectext,
			gtk.STOCK_DIALOG_WARNING, [ [gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL] ])
		# add ok button manually, because we need to focus on it 
		ok_button = self.add_button (gtk.STOCK_OK, gtk.RESPONSE_OK)
		self.checkbutton = gtk.CheckButton(checktext)
		self.vbox.pack_start(self.checkbutton, expand=False, fill=True)
		ok_button.grab_focus()
	# override this method not to destroy the dialog
	def get_response(self):
		self.show_all()
		response = gtk.Dialog.run(self)
		return response
	
	def is_checked(self):
		''' Get active state of the checkbutton '''
		return self.checkbutton.get_active()
		
class WarningDialog(HigDialog):
	def __init__(self, pritext, sectext=''):
		"""HIG compliant warning dialog."""
		HigDialog.__init__(
			self, None, pritext, sectext, gtk.STOCK_DIALOG_WARNING,
			[ [ gtk.STOCK_OK, gtk.RESPONSE_OK ] ]
		)

class InformationDialog(HigDialog):
	def __init__(self, pritext, sectext=''):
		"""HIG compliant info dialog."""
		HigDialog.__init__(
			self, None, pritext, sectext, gtk.STOCK_DIALOG_INFO,
			[ [ gtk.STOCK_OK, gtk.RESPONSE_OK ] ]
		)
class BaseTooltip:
	''' Base Tooltip . Usage:
		tooltip = BaseTooltip()
		.... 
		tooltip.show_tooltip('', window_postions, widget_postions)
		....
		if tooltip.timeout != 0:
			tooltip.hide_tooltip()
	'''
	def __init__(self):
		self.timeout = 0
		self.prefered_position = [0, 0]
		self.win = None
		self.id = None
		
	def populate(self, data):
		''' this method must be overriden by all extenders '''
		self.create_window()
		self.win.add(gtk.Label(data))
		
	def create_window(self):
		''' create a popup window each time tooltip is requested '''
		self.win = gtk.Window(gtk.WINDOW_POPUP)
		self.win.set_border_width(3)
		self.win.set_resizable(False)
		self.win.set_name('gtk-tooltips')
		
		
		self.win.set_events(gtk.gdk.POINTER_MOTION_MASK)
		self.win.connect_after('expose_event', self.expose)
		self.win.connect('size-request', self.size_request)
		self.win.connect('motion-notify-event', self.motion_notify_event)
	
	def motion_notify_event(self, widget, event):
		self.hide_tooltip()

	def size_request(self, widget, requisition):
		screen = self.win.get_screen()
		half_width = requisition.width / 2 + 1
		if self.prefered_position[0] < half_width:
			self.prefered_position[0] = 0
		elif self.prefered_position[0]  + requisition.width > screen.get_width() \
				+ half_width:
			self.prefered_position[0] = screen.get_width() - requisition.width
		else:
			self.prefered_position[0] -= half_width 
			screen.get_height()
		if self.prefered_position[1] + requisition.height > screen.get_height():
			# flip tooltip up
			self.prefered_position[1] -= requisition.height  + self.widget_height + 8
		if self.prefered_position[1] < 0:
			self.prefered_position[1] = 0
		self.win.move(self.prefered_position[0], self.prefered_position[1])

	def expose(self, widget, event):
		style = self.win.get_style()
		size = self.win.get_size()
		style.paint_flat_box(self.win.window, gtk.STATE_NORMAL, gtk.SHADOW_OUT, None,
			self.win, 'tooltip', 0, 0, -1, 1)
		style.paint_flat_box(self.win.window, gtk.STATE_NORMAL, gtk.SHADOW_OUT, None,
			self.win, 'tooltip', 0, size[1] - 1, -1, 1)
		style.paint_flat_box(self.win.window, gtk.STATE_NORMAL, gtk.SHADOW_OUT, None,
			self.win, 'tooltip', 0, 0, 1, -1)
		style.paint_flat_box(self.win.window, gtk.STATE_NORMAL, gtk.SHADOW_OUT, None,
			self.win, 'tooltip', size[0] - 1, 0, 1, -1)
		return True
	
	def show_tooltip(self, data, widget_pos, win_size):
		self.populate(data)
		new_x = win_size[0] + widget_pos[0] 
		new_y = win_size[1] + widget_pos[1] + 4
		self.prefered_position = [new_x, new_y]
		self.widget_height = widget_pos[1]
		self.win.ensure_style()
		self.win.show_all()

	def hide_tooltip(self):
		if(self.timeout > 0):
			gobject.source_remove(self.timeout)
			self.timeout = 0
		if self.win:
			self.win.destroy()
			self.win = None
		self.id = None

class StatusTable:
	''' Contains methods for creating status table. This 
	is used in Roster and NotificationArea tooltips	'''
	def __init__(self):
		self.current_row = 1
		self.table = None
		self.text_lable = None
		
	def create_table(self):
		self.table = gtk.Table(3, 1)
		self.table.set_property('column-spacing', 6)
		self.text_lable = gtk.Label()
		self.text_lable.set_line_wrap(True)
		self.text_lable.set_alignment(0, 0)
		self.text_lable.set_selectable(False)
		self.table.attach(self.text_lable, 1, 4, 1, 2)
		
	def get_status_info(self, resource, priority, show, status):
		str_status = resource + ' (' + str(priority) + ')'
		if status:
			status = status.strip()
			if status != '':
				if gtk.gtk_version < (2, 6, 0) or gtk.pygtk_version < (2, 6, 0):
					# FIXME: check and do the same if we have more than one \n 
					status = self.strip_text(status, 50)
				str_status += ' - ' + status
		return gtkgui_helpers.escape_for_pango_markup(str_status)
	
	# fix "too long status make the tooltip large than the screen" problem
	def strip_text(self, text, max_length):
		text = text.strip()
		if len(text) > max_length:
				text = text[:max_length - 3] + '...'
		return text
	
	def add_status_row(self, file_path, show, str_status):
		''' appends a new row with status icon to the table '''
		self.current_row += 1
		state_file = show.replace(' ', '_')
		files = []
		files.append(os.path.join(file_path, state_file + '.png'))
		files.append(os.path.join(file_path, state_file + '.gif'))
		image = gtk.Image()
		image.set_from_pixbuf(None)
		spacer = gtk.Label('   ')
		for file in files:
			if os.path.exists(file):
				image.set_from_file(file)
				break
		image.set_alignment(0.01, 1)
		self.table.attach(spacer, 1, 2, self.current_row, 
			self.current_row + 1, 0, 0, 0, 0)
		self.table.attach(image,2,3,self.current_row, 
			self.current_row + 1, 0, 0, 3, 0)
		image.set_alignment(0.01, 1)
		status_label = gtk.Label()
		status_label.set_markup(str_status)
		status_label.set_alignment(00, 0)
		self.table.attach(status_label, 3, 4, self.current_row,
			self.current_row + 1, gtk.EXPAND | gtk.FILL, 0, 0, 0)
	
class NotificationAreaTooltip(BaseTooltip, StatusTable):
	''' Tooltip that is shown in the notification area '''
	def __init__(self, plugin):
		self.plugin = plugin
		BaseTooltip.__init__(self)
		StatusTable.__init__(self)

	def populate(self, data):
		self.create_window()
		self.create_table()
		self.hbox = gtk.HBox()
		self.table.set_property('column-spacing', 1)
		text, single_line, accounts = '', '', []
		if gajim.contacts:
			for account in gajim.contacts.keys():
				status_idx = gajim.connections[account].connected
				# uncomment the following to hide offline accounts
				# if status_idx == 0: continue
				from common.connection import STATUS_LIST
				status = STATUS_LIST[status_idx]
				message = gajim.connections[account].status
				single_line = helpers.get_uf_show(status)
				if message is None:
					message = ''
				else:
					message = message.strip()
				if message != '':
					single_line += ': ' + message
				# the other solution is to hide offline accounts
				elif status == 'offline':
					message = helpers.get_uf_show(status)
				accounts.append({'name': account, 'status_line': single_line, 
						'show': status, 'message': message})
		unread_messages_no = self.plugin.roster.nb_unread
		if unread_messages_no > 1:
			text = _('Gajim - %s unread messages') % unread_messages_no
		elif unread_messages_no == 1:
			text = _('Gajim - 1 unread message')
		elif len(accounts) > 1:
			text = _('Gajim')
			self.current_row = 1
			self.table.resize(2,1)
			iconset = gajim.config.get('iconset')
			if not iconset:
				iconset = 'sun'
			file_path = os.path.join(gajim.DATA_DIR, 'iconsets', iconset, '16x16')
			for acct in accounts:
				mesage = gtkgui_helpers.escape_for_pango_markup(acct['message'])
				mesage = self.strip_text(mesage, 50)
				self.add_status_row(file_path, acct['show'], '<span weight="bold">' + 
					gtkgui_helpers.escape_for_pango_markup(acct['name']) + '</span>' 
					+ ' - ' + mesage)
					
		elif len(accounts) == 1:
			text = _('Gajim - %s') % accounts[0]['status_line']
		else:
			text = _('Gajim - %s') % helpers.get_uf_show('offline')
		self.text_lable.set_markup(text)
		self.hbox.add(self.table)
		self.win.add(self.hbox)
		
class RosterTooltip(BaseTooltip, StatusTable):
	''' Tooltip that is shown in the roster treeview '''
	def __init__(self, plugin):
		self.account = None
		self.plugin = plugin
		
		self.image = gtk.Image()
		self.image.set_alignment(0.5, 0.025)
		BaseTooltip.__init__(self)
		StatusTable.__init__(self)
		
	def populate(self, contacts):
		if not contacts or len(contacts) == 0:
			return
		self.create_window()
		self.hbox = gtk.HBox()
		#~ self.hbox.set_border_width(6)
		self.hbox.set_homogeneous(False)
		self.create_table()
		prim_contact = None # primary contact
		for contact in contacts:
			if prim_contact == None or contact.priority > prim_contact.priority:
				prim_contact = contact

		# try to find the image for the contact status
		state_file = prim_contact.show.replace(' ', '_')
		transport = self.plugin.roster.get_transport_name_by_jid(prim_contact.jid)
		if transport:
			file_path = os.path.join(gajim.DATA_DIR, 'iconsets', 'transports', 
				transport , '16x16')
		else:
			iconset = gajim.config.get('iconset')
			if not iconset:
				iconset = 'sun'
			file_path = os.path.join(gajim.DATA_DIR, 'iconsets', iconset, '16x16')

		files = []
		file_full_path = os.path.join(file_path, state_file)
		files.append(file_full_path + '.png')
		files.append(file_full_path + '.gif')
		self.image.set_from_pixbuf(None)
		for file in files:
			if os.path.exists(file):
				self.image.set_from_file(file)
				break
		
		info = '<span size="large" weight="bold">' + prim_contact.jid + '</span>'
		info += '\n<span weight="bold">' + _('Name: ') + '</span>' + \
			gtkgui_helpers.escape_for_pango_markup(prim_contact.name)
		info += '\n<span weight="bold">' + _('Subscription: ') + '</span>' + \
			gtkgui_helpers.escape_for_pango_markup(prim_contact.sub)

		if prim_contact.keyID:
			keyID = None
			if len(prim_contact.keyID) == 8:
				keyID = prim_contact.keyID
			elif len(prim_contact.keyID) == 16:
				keyID = prim_contact.keyID[8:]
			if keyID:
				info += '\n<span weight="bold">' + _('OpenPGP: ') + \
					'</span>' + gtkgui_helpers.escape_for_pango_markup(keyID)

		single_line, resource_str, multiple_resource= '', '', False
		num_resources = 0
		for contact in contacts:
			if contact.resource:
				num_resources += 1
		if num_resources > 1:
			self.current_row = 1
			self.table.resize(2,1)
			info += '\n<span weight="bold">' + _('Status: ') + '</span>'
			for contact in contacts:
				if contact.resource:
					status_line = self.get_status_info(contact.resource, contact.priority, 
						contact.show, contact.status)
					self.add_status_row(file_path, contact.show, status_line)
					
		else: # only one resource
			if contact.resource:
				info += '\n<span weight="bold">' + _('Resource: ') + \
					'</span>' + gtkgui_helpers.escape_for_pango_markup(
						contact.resource) + ' (' + str(contact.priority) + ')'
			if contact.show:
				info += '\n<span weight="bold">' + _('Status: ') + \
					'</span>' + helpers.get_uf_show(contact.show) 
				if contact.status:
					status = contact.status.strip()
					if status != '':
						# escape markup entities. Is it posible to have markup in status?
						info += ' - ' + gtkgui_helpers.escape_for_pango_markup(status)
		
		self.text_lable.set_markup(info)
		self.hbox.pack_start(self.image, False, False)
		self.hbox.pack_start(self.table, True, True)
		self.win.add(self.hbox)

class InputDialog:
	'''Class for Input dialog'''
	def __init__(self, title, label_str, input_str = None, is_modal = True, ok_handler = None):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'input_dialog', APP)
		self.dialog = xml.get_widget('input_dialog')
		label = xml.get_widget('label')
		self.input_entry = xml.get_widget('input_entry')
		self.dialog.set_title(title)
		label.set_text(label_str)
		if input_str:
			self.input_entry.set_text(input_str)
			self.input_entry.select_region(0, -1) # select all
		
		self.is_modal = is_modal
		if not is_modal and ok_handler is not None:
			self.ok_handler = ok_handler
			okbutton = xml.get_widget('okbutton')
			okbutton.connect('clicked', self.on_okbutton_clicked)
			cancelbutton = xml.get_widget('cancelbutton')
			cancelbutton.connect('clicked', self.on_cancelbutton_clicked)
			self.dialog.show_all()

	def on_okbutton_clicked(self,  widget):
		response = self.input_entry.get_text()
		self.dialog.destroy()
		self.ok_handler(response)
	
	def on_cancelbutton_clicked(self,  widget):
		self.dialog.destroy()

	def get_response(self):
		if self.is_modal:
			response = self.dialog.run()
			self.dialog.destroy()
		return response
	
class ErrorDialog(HigDialog):
	def __init__(self, pritext, sectext=''):
		"""HIG compliant error dialog."""
		HigDialog.__init__(
			self, None, pritext, sectext, gtk.STOCK_DIALOG_ERROR,
			[ [ gtk.STOCK_OK, gtk.RESPONSE_OK ] ]
		)


class SubscriptionRequestWindow:
	def __init__(self, plugin, jid, text, account):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'subscription_request_window', APP)
		self.window = xml.get_widget('subscription_request_window')
		self.plugin = plugin
		self.jid = jid
		self.account = account
		if len(gajim.connections) >= 2:
			prompt_text = _('Subscription request for account %s from %s')\
				% (account, self.jid)
		else:
			prompt_text = _('Subscription request from %s') % self.jid
		xml.get_widget('from_label').set_text(prompt_text)
		xml.get_widget('message_textview').get_buffer().set_text(text)
		xml.signal_autoconnect(self)
		self.window.show_all()

	def on_close_button_clicked(self, widget):
		self.window.destroy()
		
	def on_authorize_button_clicked(self, widget):
		'''accept the request'''
		gajim.connections[self.account].send_authorization(self.jid)
		self.window.destroy()
		if not gajim.contacts[self.account].has_key(self.jid):
			AddNewContactWindow(self.plugin, self.account, self.jid)

	def on_contact_info_button_clicked(self, widget):
		'''ask vcard'''
		if self.plugin.windows[self.account]['infos'].has_key(self.jid):
			self.plugin.windows[self.account]['infos'][self.jid].window.present()
		else:
			self.plugin.windows[self.account]['infos'][self.jid] = \
				VcardWindow(self.jid, self.plugin, self.account, True)
			#remove the publish / retrieve buttons
			vcard_xml = self.plugin.windows[self.account]['infos'][self.jid].xml
			hbuttonbox = vcard_xml.get_widget('information_hbuttonbox')
			children = hbuttonbox.get_children()
			hbuttonbox.remove(children[0])
			hbuttonbox.remove(children[1])
			vcard_xml.get_widget('nickname_label').set_text(self.jid)
			gajim.connections[self.account].request_vcard(self.jid)
	
	def on_deny_button_clicked(self, widget):
		'''refuse the request'''
		gajim.connections[self.account].refuse_authorization(self.jid)
		self.window.destroy()

class JoinGroupchatWindow:
	def __init__(self, plugin, account, server = '', room = ''):
		self.plugin = plugin
		self.account = account
		if gajim.connections[account].connected < 2:
			ErrorDialog(_('You are not connected to the server'),
_('You can not join a group chat unless you are connected.')).get_response()
			raise RuntimeError, 'You must be connected to join a groupchat'

		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'join_groupchat_window', APP)
		self.window = self.xml.get_widget('join_groupchat_window')
		self.xml.get_widget('server_entry').set_text(server)
		self.xml.get_widget('room_entry').set_text(room)
		self.xml.get_widget('nickname_entry').set_text(gajim.nicks[self.account])
		self.xml.signal_autoconnect(self)
		self.plugin.windows[account]['join_gc'] = self #now add us to open windows
		our_jid = gajim.config.get_per('accounts', self.account, 'name') + '@' + \
			gajim.config.get_per('accounts', self.account, 'hostname')
		if len(gajim.connections) > 1:
			title = _('Join Group Chat as %s') % our_jid
		else:
			title = _('Join Group Chat')
		self.window.set_title(title)

		self.recently_combobox = self.xml.get_widget('recently_combobox')
		liststore = gtk.ListStore(str)
		self.recently_combobox.set_model(liststore)
		cell = gtk.CellRendererText()
		self.recently_combobox.pack_start(cell, True)
		self.recently_combobox.add_attribute(cell, 'text', 0)
		self.recently_groupchat = gajim.config.get('recently_groupchat').split()
		for g in self.recently_groupchat:
			self.recently_combobox.append_text(g)
		if len(self.recently_groupchat) and server == '' and room == '':
			self.recently_combobox.set_active(0)
			self.xml.get_widget('room_entry').select_region(0, -1)

		self.window.show_all()

	def on_join_groupchat_window_destroy(self, widget):
		'''close window'''
		del self.plugin.windows[self.account]['join_gc'] # remove us from open windows

	def on_join_groupchat_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape: # ESCAPE
			widget.destroy()

	def on_recently_combobox_changed(self, widget):
		model = widget.get_model()
		iter = widget.get_active_iter()
		gid = model[iter][0]
		self.xml.get_widget('room_entry').set_text(gid.split('@')[0])
		self.xml.get_widget('server_entry').set_text(gid.split('@')[1])

	def on_cancel_button_clicked(self, widget):
		'''When Cancel button is clicked'''
		self.window.destroy()

	def on_join_button_clicked(self, widget):
		'''When Join button is clicked'''
		nickname = self.xml.get_widget('nickname_entry').get_text()
		room = self.xml.get_widget('room_entry').get_text()
		server = self.xml.get_widget('server_entry').get_text()
		password = self.xml.get_widget('password_entry').get_text()
		jid = '%s@%s' % (room, server)
		if jid in self.recently_groupchat:
			self.recently_groupchat.remove(jid)
		self.recently_groupchat.insert(0, jid)
		if len(self.recently_groupchat) > 10:
			self.recently_groupchat = self.recently_groupchat[0:10]
		gajim.config.set('recently_groupchat', ' '.join(self.recently_groupchat))
		
		self.plugin.roster.join_gc_room(self.account, jid, nickname, password)

		self.window.destroy()

class NewMessageDialog:
	def __init__(self, plugin, account):
		self.plugin = plugin
		self.account = account
		
		our_jid = gajim.config.get_per('accounts', self.account, 'name') + '@' + \
			gajim.config.get_per('accounts', self.account, 'hostname')
		if len(gajim.connections) > 1:
			title = _('New Message as %s') % our_jid
		else:
			title = _('New Message')
		prompt_text = _('Fill in the contact ID of the contact you would like\nto send a chat message to:')

		instance = InputDialog(title, prompt_text, is_modal = False, ok_handler = self.new_message_response)
			
	def new_message_response(self, jid):
		''' called when ok button is clicked '''
		if jid.find('@') == -1: # if no @ was given
			ErrorDialog(_('Invalid contact ID'),
	_('Contact ID must be of the form "username@servername".')).get_response()
			return

		self.plugin.roster.new_chat_from_jid(self.account, jid)

class ChangePasswordDialog:
	def __init__(self, plugin, account):
		# 'account' can be None if we are about to create our first one
		if not account or gajim.connections[account].connected < 2:
			ErrorDialog(_('You are not connected to the server'),
_('Without a connection, you can not change your password.')).get_response()
			raise RuntimeError, 'You are not connected to the server'
		self.plugin = plugin
		self.account = account
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'change_password_dialog', APP)
		self.dialog = self.xml.get_widget('change_password_dialog')
		self.password1_entry = self.xml.get_widget('password1_entry')
		self.password2_entry = self.xml.get_widget('password2_entry')

		self.dialog.show_all()

	def run(self):
		'''Wait for OK button to be pressed and return new password'''
		end = False
		while not end:
			rep = self.dialog.run()
			if rep == gtk.RESPONSE_OK:
				password1 = self.password1_entry.get_text()
				if not password1:
					ErrorDialog(_('Invalid password'),
							_('You must enter a password.')).get_response()
					continue
				password2 = self.password2_entry.get_text()
				if password1 != password2:
					ErrorDialog(_('Passwords do not match'),
							_('The passwords typed in both fields must be identical.')).get_response()
					continue
				message = password1
			else:
				message = -1
			end = True
		self.dialog.destroy()
		return message


class PopupNotificationWindow:
	def __init__(self, plugin, event_type, jid, account, msg_type = '', file_props = None):
		self.plugin = plugin
		self.account = account
		self.jid = jid
		self.msg_type = msg_type
		self.file_props = file_props
		
		xml = gtk.glade.XML(GTKGUI_GLADE, 'popup_notification_window', APP)
		self.window = xml.get_widget('popup_notification_window')
		close_button = xml.get_widget('close_button')
		event_type_label = xml.get_widget('event_type_label')
		event_description_label = xml.get_widget('event_description_label')
		eventbox = xml.get_widget('eventbox')
		
		event_type_label.set_markup('<b>' + event_type + '</b>')

		if self.jid in gajim.contacts[account]:
			txt = gajim.contacts[account][self.jid][0].name
		else:
			txt = self.jid

		event_description_label.set_text(txt)
		
		# set colors [ http://www.w3schools.com/html/html_colornames.asp ]
		self.window.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))
		if event_type == _('Contact Signed In'):
			limegreen = gtk.gdk.color_parse('limegreen')
			close_button.modify_bg(gtk.STATE_NORMAL, limegreen)
			eventbox.modify_bg(gtk.STATE_NORMAL, limegreen)
		elif event_type == _('Contact Signed Out'):
			red = gtk.gdk.color_parse('red')
			close_button.modify_bg(gtk.STATE_NORMAL, red)
			eventbox.modify_bg(gtk.STATE_NORMAL, red)
		elif event_type == _('New Message') or\
		event_type == _('New Single Message'):
			dodgerblue = gtk.gdk.color_parse('dodgerblue')
			close_button.modify_bg(gtk.STATE_NORMAL, dodgerblue)
			eventbox.modify_bg(gtk.STATE_NORMAL, dodgerblue)
			txt = _('From %s') % txt
		elif event_type == _('File Trasfer Request'):
			bg_color = gtk.gdk.color_parse('coral')
			close_button.modify_bg(gtk.STATE_NORMAL, bg_color)
			eventbox.modify_bg(gtk.STATE_NORMAL, bg_color)
			txt = _('From %s') % txt
		elif event_type in [_('File Transfer Completed'), _('File Transfer Stopped')]:
			bg_color = gtk.gdk.color_parse('coral')
			close_button.modify_bg(gtk.STATE_NORMAL, bg_color)
			eventbox.modify_bg(gtk.STATE_NORMAL, bg_color)
			
		# position the window to bottom-right of screen
		window_width, self.window_height = self.window.get_size()
		self.plugin.roster.popups_notification_height += self.window_height
		self.window.move(gtk.gdk.screen_width() - window_width,
			gtk.gdk.screen_height() - self.plugin.roster.popups_notification_height)
		
		xml.signal_autoconnect(self)
		self.window.show_all()
		gobject.timeout_add(5000, self.on_timeout)

	def on_close_button_clicked(self, widget):
		self.adjust_height_and_move_popup_notification_windows()

	def on_timeout(self):
		self.adjust_height_and_move_popup_notification_windows()
		
	def adjust_height_and_move_popup_notification_windows(self):
		#remove
		self.plugin.roster.popups_notification_height -= self.window_height
		self.window.destroy()
		
		if len(self.plugin.roster.popup_notification_windows) > 0:
			# we want to remove the first window added in the list
			self.plugin.roster.popup_notification_windows.pop(0) # remove 1st item
		
		# move the rest of popup windows
		self.plugin.roster.popups_notification_height = 0
		for window_instance in self.plugin.roster.popup_notification_windows:
			window_width, window_height = window_instance.window.get_size()
			self.plugin.roster.popups_notification_height += window_height
			window_instance.window.move(gtk.gdk.screen_width() - window_width,
		gtk.gdk.screen_height() - self.plugin.roster.popups_notification_height)

	def on_popup_notification_window_button_press_event(self, widget, event):
		# use Contact class, new_chat expects it that way
		# is it in the roster?
		if gajim.contacts[self.account].has_key(self.jid):
			contact = gajim.contacts[self.account][self.jid][0]
		else:
			keyID = ''
			attached_keys = gajim.config.get_per('accounts', self.account,
				'attached_gpg_keys').split()
			if jid in attached_keys:
				keyID = attached_keys[attached_keys.index(jid) + 1]
			contact = Contact(jid = self.jid, name = self.jid.split('@')[0],
				groups = [_('not in the roster')], show = 'not in the roster',
				status = _('not in the roster'), sub = 'none', keyID = keyID)
			gajim.contacts[self.account][self.jid] = [contact]
			self.plugin.roster.add_contact_to_roster(contact.jid,
				self.account)

		if self.msg_type == 'normal': # it's single message
			return # FIXME: I think I should not print here but in new_chat?
			contact = self.contacts[account][jid][0]
			SingleMessageWindow(self.plugin, self.account, contact, 
			action = 'receive', from_whom = jid, subject = subject, message = msg)
		
		elif self.msg_type == 'file': # it's file request
			self.plugin.windows['file_transfers'].show_file_request(
				self.account, contact, self.file_props)
		
		elif self.msg_type == 'file-completed': # it's file request # FIXME: comment
			sectext = '\t' + _('Filename: %s') % self.file_props['name'] 
			sectext += '\n\t' + _('Size: %s') % \
				gtkgui_helpers.convert_bytes(self.file_props['size'])
			sectext += '\n\t' +_('Sender: %s') % self.jid
			InformationDialog(_('File transfer completed'), sectext).get_response()
		
		elif self.msg_type == 'file-stopped': # it's file request # FIXME: comment
			sectext = '\t' + _('Filename: %s') % self.file_props['name']
			sectext += '\n\t' + _('Sender: %s') % self.jid
			ErrorDialog(_('File transfer stopped by the contact of the other side'), \
				sectext).get_response()
		
		else: # 'chat'
			self.plugin.roster.new_chat(contact, self.account)
			chats_window = self.plugin.windows[self.account]['chats'][self.jid]
			chats_window.set_active_tab(self.jid)
			chats_window.window.present()

		self.adjust_height_and_move_popup_notification_windows()


class SingleMessageWindow:
	'''SingleMessageWindow can send or show a received
	singled message depending on action argument'''
	def __init__(self, plugin, account, contact, action='', from_whom='',\
	subject='', message=''):
		self.plugin = plugin
		self.account = account
		self.contact = contact
		self.action = action

		self.subject = subject
		self.message = message
		
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'single_message_window', APP)
		self.window = self.xml.get_widget('single_message_window')
		self.count_chars_label = self.xml.get_widget('count_chars_label')
		self.from_label = self.xml.get_widget('from_label')
		self.from_entry = self.xml.get_widget('from_entry')
		self.to_label = self.xml.get_widget('to_label')
		self.to_entry = self.xml.get_widget('to_entry')
		self.subject_entry = self.xml.get_widget('subject_entry')
		self.message_textview = self.xml.get_widget('message_textview')
		self.message_tv_buffer = self.message_textview.get_buffer()
		self.send_button = self.xml.get_widget('send_button')
		self.reply_button = self.xml.get_widget('reply_button')
		self.send_and_close_button = self.xml.get_widget('send_and_close_button')
		self.message_tv_buffer.connect('changed', self.update_char_counter)
		
		self.to_entry.set_text(self.contact.jid)
		
		self.send_button.set_no_show_all(True)
		self.reply_button.set_no_show_all(True)
		self.send_and_close_button.set_no_show_all(True)
		self.to_label.set_no_show_all(True)
		self.to_entry.set_no_show_all(True)
		self.from_label.set_no_show_all(True)
		self.from_entry.set_no_show_all(True)
		
		self.prepare_widgets_for(self.action)

		if self.action == 'send':
			if self.message: # we come from a reply?
				self.message_textview.grab_focus()
			else: # we write a new message
				self.subject_entry.grab_focus()
		elif self.action == 'receive':
			self.from_whom = from_whom
			self.from_entry.set_text(self.from_whom)
			self.from_entry.set_property('editable', False)
			self.subject_entry.set_property('editable', False)
			self.message_textview.set_editable(False)
			self.reply_button.grab_focus()
		
		# set_text(None) raises TypeError exception
		if self.subject is None:
			self.subject = ''
		self.subject_entry.set_text(self.subject)
		self.message_tv_buffer.set_text(self.message)
		begin_iter = self.message_tv_buffer.get_start_iter()
		self.message_tv_buffer.place_cursor(begin_iter)

		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def prepare_widgets_for(self, action):
		our_jid = gajim.config.get_per('accounts', self.account, 'name') + '@' + \
			gajim.config.get_per('accounts', self.account, 'hostname')
		if len(gajim.connections) > 1:
			title = _('Single Message as %s') % our_jid
		else:
			title = _('Single Message')

		if action == 'send':
			title = _('Send %s') % title
			self.send_button.show()
			self.send_and_close_button.show()
			self.to_label.show()
			self.to_entry.show()
			self.reply_button.hide()
			self.from_label.hide()
			self.from_entry.hide()
		elif action == 'receive':
			title = _('Received %s') % title
			self.reply_button.show()
			self.from_label.show()
			self.from_entry.show()
			self.send_button.hide()
			self.send_and_close_button.hide()
			self.to_label.hide()
			self.to_entry.hide()
		
		self.window.set_title(title)

	def on_cancel_button_clicked(self, widget):
		self.window.destroy()

	def update_char_counter(self, widget):
		characters_no = self.message_tv_buffer.get_char_count()
		self.count_chars_label.set_text(str(characters_no))
	
	def send_single_message(self):
		to_whom_jid = self.to_entry.get_text()
		if to_whom_jid.find('@') == -1: # if no @ was given
			ErrorDialog(_('Invalid contact ID'),
		_('Contact ID must be of the form "username@servername".')).get_response()
			return
		subject = self.subject_entry.get_text()
		begin, end = self.message_tv_buffer.get_bounds()
		message = self.message_tv_buffer.get_text(begin, end)

		# FIXME: allow GPG message some day
		gajim.connections[self.account].send_message(to_whom_jid, message,
			keyID = None, type = 'normal', subject=subject)
		
		self.subject_entry.set_text('') # we sent ok, clear the subject
		self.message_tv_buffer.set_text('') # we sent ok, clear the textview

	def on_send_button_clicked(self, widget):
		self.send_single_message()

	def on_reply_button_clicked(self, widget):
		# we create a new blank window to send and we preset RE: and to jid
		self.subject = _('RE: %s') % self.subject
		self.message = _('\n\n\n== Original Message ==\n%s') % self.message
		self.window.destroy()
		SingleMessageWindow(self.plugin, self.account, self.contact,
			action = 'send',	from_whom = self.from_whom, subject = self.subject,
			message = self.message)

	def on_send_and_close_button_clicked(self, widget):
		self.send_single_message()
		self.window.destroy()

	def on_single_message_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape: # ESCAPE
			self.window.destroy()

class XMLConsoleWindow:
	def __init__(self, plugin, account):
		self.plugin = plugin
		self.account = account
		
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'xml_console_window', APP)
		self.window = self.xml.get_widget('xml_console_window')
		self.input_textview = self.xml.get_widget('input_textview')
		self.stanzas_log_textview = self.xml.get_widget('stanzas_log_textview')
		self.input_tv_buffer = self.input_textview.get_buffer()
		
		self.input_textview.modify_base(
			gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))
		self.input_textview.modify_text(
			gtk.STATE_NORMAL, gtk.gdk.color_parse('green'))
		
		
		#st = self.input_textview.get_style()
		
		
		#style = gtk.Style()
		#style.font_desc = st.font_desc
		
		#self.input_textview.set_name('input')
		#s = '''\
#style "console" { GtkTextView::cursor-color="%s" }
#widget "*.*.input" style : application "console"''' % '#FFFFFF'
		#gtk.rc_parse_string(s)
		
		
		self.stanzas_log_textview.modify_base(
			gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))
		self.stanzas_log_textview.modify_text(
			gtk.STATE_NORMAL, gtk.gdk.color_parse('green'))
		
		if len(gajim.connections) > 1:
			title = _('XML Console for %s') % self.account
		else:
			title = _('XML Console')
		
		self.window.set_title(title)
		
		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def on_send_button_clicked(self, widget):
		begin_iter, end_iter = self.input_tv_buffer.get_bounds()
		stanza = self.input_tv_buffer.get_text(begin_iter, end_iter)
		if stanza:
			gajim.connections[self.account].send_stanza(stanza)
			self.input_tv_buffer.set_text('') # we sent ok, clear the textview
	
	def on_presence_button_clicked(self, widget):
		self.input_tv_buffer.set_text(
		'<presence><show></show><status></status><priority></priority></presence>'
		)

	def on_iq_button_clicked(self, widget):
		self.input_tv_buffer.set_text(
			'<iq to="" type=""><query xmlns=""></query></iq>'
		)
	
	def on_message_button_clicked(self, widget):
		self.input_tv_buffer.set_text(
			'<message to="" type=""><body></body></message>'
		)

	def on_expander_activate(self, widget):
		if not widget.get_expanded(): # it's the opposite!
			# it's expanded!!
			self.input_textview.grab_focus()
	
	def on_xml_console_window_destroy(self, widget):
		# remove us from open windows
		del self.plugin.windows[self.account]['xml_console']
		widget.destroy()
		
class FileTransfersWindow:
	def __init__(self, plugin):
		self.files_props = {'r':{},'s':{}}
		self.plugin = plugin
		self.last_save_dir = None
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'file_transfers_window', APP)
		self.window = self.xml.get_widget('file_transfers_window')
		self.tree = self.xml.get_widget('transfers_list')
		self.stop_button = self.xml.get_widget('stop_button')
		self.pause_button = self.xml.get_widget('pause_restore_button')
		self.notify_ft_checkbox = \
			self.xml.get_widget('notify_ft_complete_checkbox')
		notify = gajim.config.get('notify_on_file_complete')
		if notify:
			self.notify_ft_checkbox.set_active(1)
		else:
			self.notify_ft_checkbox.set_active(0)
		self.model = gtk.ListStore(gtk.gdk.Pixbuf, str, str, str, str, str)
		self.tree.set_model(self.model)
		col = gtk.TreeViewColumn()
		
		render_pixbuf = gtk.CellRendererPixbuf()
		
		col.pack_start(render_pixbuf, expand = True)
		render_pixbuf.set_property('xpad', 3)
		render_pixbuf.set_property('ypad', 3)
		render_pixbuf.set_property('yalign', .0)
		#~ render_pixbuf.set_property('stock-size', gtk.ICON_SIZE_MENU)
		col.add_attribute(render_pixbuf, "pixbuf", 0)
		self.tree.append_column(col)
		
		col = gtk.TreeViewColumn(_('File'))
		renderer = gtk.CellRendererText()
		col.pack_start(renderer, expand=False)
		col.add_attribute(renderer, 'markup' , 1)
		renderer.set_property('yalign', 0.)
		renderer = gtk.CellRendererText()
		col.pack_start(renderer, expand=True)
		col.add_attribute(renderer, 'markup' , 2)
		renderer.set_property('xalign', 0.)
		renderer.set_property('yalign', 0.)
		col.set_expand(True)
		self.tree.append_column(col)
		
		col = gtk.TreeViewColumn(_('Progress'))
		renderer = gtk.CellRendererText()
		renderer.set_property('yalign', 0.)
		renderer.set_property('xalign', 0.)
		col.pack_start(renderer, expand = True)
		col.set_expand(False)
		col.add_attribute(renderer, 'text' , 3)
		self.tree.append_column(col)
		self.set_images()
		self.tree.get_selection().set_select_function(self.select_func)
		self.xml.signal_autoconnect(self)
		
	
		
	def show_file_request(self, account, contact, file_props):
		if file_props is None or not file_props.has_key('name'):
			return
		sec_text = '\t' + _('File: %s') % file_props['name']
		if file_props.has_key('size'):
			sec_text += '\n\t' + _('Size: %s') % \
				gtkgui_helpers.convert_bytes(file_props['size'])
		if file_props.has_key('mime-type'):
			sec_text += '\n\t' + _('Type: %s') % file_props['mime-type']
		if file_props.has_key('desc'):
			sec_text += '\n\t' + _('Description: %s') % file_props['desc']
		prim_text = _('%s wants to send you a file:') % contact.jid
		dialog = ConfirmationDialog(prim_text, sec_text)
		if dialog.get_response() == gtk.RESPONSE_OK:
			dialog = gtk.FileChooserDialog(title=_('Save File as...'), 
				action=gtk.FILE_CHOOSER_ACTION_SAVE, 
				buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, 
				gtk.STOCK_SAVE, gtk.RESPONSE_OK))
			dialog.set_current_name(file_props['name'])
			dialog.set_default_response(gtk.RESPONSE_OK)
			if self.last_save_dir and os.path.exists(self.last_save_dir) \
				and os.path.isdir(self.last_save_dir):
				dialog.set_current_folder(self.last_save_dir)
			response = dialog.run()
			if response == gtk.RESPONSE_OK:
				file_path = dialog.get_filename()
				(file_dir, file_name) = os.path.split(file_path)
				if file_dir:
					self.last_save_dir = file_dir
				file_props['file-name'] = file_path
				self.add_transfer(account, contact, file_props)
				gajim.connections[account].send_file_approval(file_props)
			else:
				gajim.connections[account].send_file_rejection(file_props)
			dialog.destroy()
		else:
			gajim.connections[account].send_file_rejection(file_props)
	
	def set_images(self):
		self.images = {}
		self.images['upload'] = self.window.render_icon(gtk.STOCK_GO_UP, 
			gtk.ICON_SIZE_MENU)
		self.images['download'] = self.window.render_icon(gtk.STOCK_GO_DOWN, 
			gtk.ICON_SIZE_MENU)
		self.images['stop'] = self.window.render_icon(gtk.STOCK_STOP, 
			gtk.ICON_SIZE_MENU)
		self.images['waiting'] = self.window.render_icon(gtk.STOCK_REFRESH, 
			gtk.ICON_SIZE_MENU)
		self.images['pause'] = self.window.render_icon(gtk.STOCK_MEDIA_PAUSE, 
			gtk.ICON_SIZE_MENU)
		self.images['ok'] = self.window.render_icon(gtk.STOCK_APPLY, 
			gtk.ICON_SIZE_MENU)
			
			
	
	def set_status(self, typ, sid, status):
		iter = self.get_iter_by_sid(typ, sid)
		if iter is not None:
			self.model.set(iter, 0, self.images[status])
			
	def set_progress(self, typ, sid, transfered_size, iter = None):
		if not self.files_props[typ].has_key(sid):
			return
		file_props = self.files_props[typ][sid]
		full_size = int(file_props['size'])
		if full_size == 0:
			percent = 0
		else:
			percent = round(float(transfered_size) / full_size * 100)
		if iter is None:
			iter = self.get_iter_by_sid(typ, sid)
		if iter is not None:
			text = str(percent) + '%\n' 
			if transfered_size == 0:
				text += '0'
			else:
				text += gtkgui_helpers.convert_bytes(transfered_size)
			text += '/' + gtkgui_helpers.convert_bytes(full_size)
			self.model.set(iter, 3, text)
			if percent == 100:
				self.set_status(typ, sid, 'ok')
		
	def get_iter_by_sid(self, typ, sid):
		iter = self.model.get_iter_root()
		while iter:
			if typ + sid == self.model.get_value(iter, 4):
				return iter
			iter = self.model.iter_next(iter)
		return None
		
	def add_transfer(self, account, contact, file_props):
		if file_props is None:
			return
		self.files_props[file_props['type']][file_props['sid']] = file_props
		iter = self.model.append()
		text_labels = '<b>' + _('Name: ') + '</b>\n' 
		text_labels += '<b>' + _('Sender: ') + '</b>' 
		text_props = file_props['name'] + '\n'
		text_props += contact.name
		self.model.set(iter, 1, text_labels, 2, text_props, 4, \
			file_props['type'] + file_props['sid'])
		self.set_progress(file_props['type'], file_props['sid'], 0, iter)
		self.set_status(file_props['type'], file_props['sid'], 'download')
		self.window.show_all()
	
	
	def on_transfers_list_enter_notify_event(self, widget, event):
		pass
	
	def on_transfers_list_leave_notify_event(self, widget, event):
		pass
	
	def on_transfers_list_row_activated(self, widget, path, col):
		# try to open the file
		pass
		
	def is_transfer_paused(self, file_props):
		if file_props.has_key('error') and file_props['error'] != 0:
			return False
		if file_props['completed'] or file_props['disconnect_cb'] is None:
			return False
		return file_props['paused']
		
	def is_transfer_active(self, file_props):
		if file_props.has_key('error') and file_props['error'] != 0:
			return False
		if file_props['completed'] or file_props['disconnect_cb'] is None:
			return False
		return not file_props['paused']
		
	def is_transfer_stoped(self, file_props):
		if file_props.has_key('error') and file_props['error'] != 0:
			return True
		if file_props['completed']:
			return True
		if file_props.has_key('disconnect_cb') and \
			file_props['disconnect_cb'] is not None:
			return False
		return True
	
	def select_func(self, path):
		is_selected = False
		current_iter = self.model.get_iter(path)
		selected = self.tree.get_selection().get_selected()
		if selected[1] != None:
			selected_path = self.model.get_path(selected[1])
			if selected_path == path:
				is_selected = True
		sid = self.model[current_iter][4]
		file_props = self.files_props[sid[0]][sid[1:]]
		if self.is_transfer_stoped(file_props):
			is_selected = True
		self.stop_button.set_property('sensitive', not is_selected)
		if is_selected:
			self.pause_button.set_property('sensitive', False)
		else:
			if self.is_transfer_active(file_props):
				self.pause_button.set_property('sensitive', True)
				self.pause_button.set_label(_('_Pause'))
			elif self.is_transfer_paused(file_props):
				self.pause_button.set_property('sensitive', True)
				self.pause_button.set_label(_('_Continue'))
			else:
				self.pause_button.set_property('sensitive', False)
			
		return True
	def on_clean_button_clicked(self, widget):
		selected = self.tree.get_selection().get_selected()
		if selected is None or selected[1] is None:
			return 
		s_iter = selected[1]
		sid = self.model[s_iter][4]
		file_props = self.files_props[sid[0]][sid[1:]]
		if not self.is_transfer_stoped(file_props):
			file_props['disconnect_cb']()
		self.model.remove(s_iter)
		
	def on_pause_restore_button_clicked(self, widget):
		selected = self.tree.get_selection().get_selected()
		if selected is None or selected[1] is None:
			return 
		s_iter = selected[1]
		sid = self.model[s_iter][4]
		file_props = self.files_props[sid[0]][sid[1:]]
		if self.is_transfer_paused(file_props):
			file_props['paused'] = False
			types = {'r' : 'download', 's' : 'upload'}
			self.set_status(file_props['type'], file_props['sid'], types[sid[0]])
			widget.set_label(_('Pause'))
		elif self.is_transfer_active(file_props):
			file_props['paused'] = True
			self.set_status(file_props['type'], file_props['sid'], 'pause')
			widget.set_label(_('_Continue'))
		
	def on_stop_button_clicked(self, widget):
		selected = self.tree.get_selection().get_selected()
		if selected is None or selected[1] is None:
			return 
		s_iter = selected[1]
		sid = self.model[s_iter][4]
		file_props = self.files_props[sid[0]][sid[1:]]
		if not self.is_transfer_stoped(file_props):
			file_props['disconnect_cb']()
		self.set_status(file_props['type'], file_props['sid'], 'stop')
		
	def on_notify_ft_complete_checkbox_toggled(self, widget):
		gajim.config.set('notify_on_file_complete', 
			widget.get_active())
		
	def on_file_transfers_dialog_delete_event(self, widget, event):
		self.window.hide()
		return True
	
