#!/usr/bin/env python
##	plugins/gtkgui.py
##
## Gajim Team:
## 	- Yann Le Boulanger <asterix@crans.org>
## 	- Vincent Hanquez <tab@snarc.org>
##
##	Copyright (C) 2003 Gajim Team
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

def usage():
	#TODO: use i18n
	print "usage :", sys.argv[0], ' [OPTION]'
	print "  -p\tport on whitch the sock plugin listen"
	print "  -h, --help\tdisplay this help and exit"

if __name__ == "__main__":
	import getopt, pickle, sys, socket
	try:
		opts, args = getopt.getopt(sys.argv[1:], "p:h", ["help"])
	except getopt.GetoptError:
		# print help information and exit:
		usage()
		sys.exit(2)
	port = 8255
	for o, a in opts:
		if o == '-p':
			port = a
		if o in ("-h", "--help"):
			usage()
			sys.exit()
	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	try:
		sock.connect(('', 8255))
	except:
		#TODO: use i18n
		print "unable to connect to localhost on port "+str(port)
	else:
		evp = pickle.dumps(('EXEC_PLUGIN', '', 'gtkgui'))
		sock.send('<'+evp+'>')
		sock.close()
	sys.exit()

import pygtk
pygtk.require('2.0')
import gtk
from gtk import TRUE, FALSE
import gtk.glade,gobject
import os,string,time,Queue
import common.optparser,common.sleepy
from common import i18n
_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain (APP, i18n.DIR)
gtk.glade.textdomain (APP)

from dialogs import *
from config import *

GTKGUI_GLADE='plugins/gtkgui/gtkgui.glade'


class ImageCellRenderer(gtk.GenericCellRenderer):

	__gproperties__ = {
		"image": (gobject.TYPE_OBJECT, "Image", 
		"Image", gobject.PARAM_READWRITE),
	}
                     
	def __init__(self):
		self.__gobject_init__()
		self.image = None

	def do_set_property(self, pspec, value):
		setattr(self, pspec.name, value)

	def do_get_property(self, pspec):
		return getattr(self, pspec.name)

	def func(self, model, path, iter, (image, tree)):
		if model.get_value(iter, 0) == image:
			self.redraw = 1
			cell_area = tree.get_cell_area(path, tree.get_column(0))
			tree.queue_draw_area(cell_area.x, cell_area.y, cell_area.width, cell_area.height)

	def animation_timeout(self, tree, image):
		if image.get_storage_type() == gtk.IMAGE_ANIMATION:
			self.redraw = 0
			image.get_data('iter').advance()
			model = tree.get_model()
			model.foreach(self.func, (image, tree))
			if self.redraw:
				gobject.timeout_add(image.get_data('iter').get_delay_time(), self.animation_timeout, tree, image)
			else:
				image.set_data('iter', None)
				
	def on_render(self, window, widget, background_area,cell_area, \
		expose_area, flags):
		pix_rect = gtk.gdk.Rectangle()
		pix_rect.x, pix_rect.y, pix_rect.width, pix_rect.height = self.on_get_size(widget, cell_area)

		pix_rect.x += cell_area.x
		pix_rect.y += cell_area.y
		pix_rect.width  -= 2 * self.get_property("xpad")
		pix_rect.height -= 2 * self.get_property("ypad")

		draw_rect = cell_area.intersect(pix_rect)
		draw_rect = expose_area.intersect(draw_rect)

		if self.image.get_storage_type() == gtk.IMAGE_ANIMATION:
			if not self.image.get_data('iter'):
				animation = self.image.get_animation()
				self.image.set_data('iter', animation.get_iter())
				gobject.timeout_add(self.image.get_data('iter').get_delay_time(), self.animation_timeout, widget, self.image)

			pix = self.image.get_data('iter').get_pixbuf()
		elif self.image.get_storage_type() == gtk.IMAGE_PIXBUF:
			pix = self.image.get_pixbuf()
		if pix:
			window.draw_pixbuf(widget.style.black_gc, pix, \
				draw_rect.x-pix_rect.x, draw_rect.y-pix_rect.y, draw_rect.x, \
				draw_rect.y+2, draw_rect.width, draw_rect.height, \
            gtk.gdk.RGB_DITHER_NONE, 0, 0)

	def on_get_size(self, widget, cell_area):
		if self.image.get_storage_type() == gtk.IMAGE_ANIMATION:
			animation = self.image.get_animation()
			pix = animation.get_iter().get_pixbuf()
		elif self.image.get_storage_type() == gtk.IMAGE_PIXBUF:
			pix = self.image.get_pixbuf()
		pixbuf_width  = pix.get_width()
		pixbuf_height = pix.get_height()
		calc_width  = self.get_property("xpad") * 2 + pixbuf_width
		calc_height = self.get_property("ypad") * 2 + pixbuf_height
		x_offset = 0
		y_offset = 0
		if cell_area and pixbuf_width > 0 and pixbuf_height > 0:
			x_offset = self.get_property("xalign") * (cell_area.width - calc_width -  self.get_property("xpad"))
			y_offset = self.get_property("yalign") * (cell_area.height - calc_height -  self.get_property("ypad"))
		return x_offset, y_offset, calc_width, calc_height

gobject.type_register(ImageCellRenderer)


class user:
	"""Informations concerning each users"""
	def __init__(self, *args):
		if len(args) == 0:
			self.jid = ''
			self.name = ''
			self.groups = []
			self.show = ''
			self.status = ''
			self.sub = ''
			self.resource = ''
			self.priority = 0
			self.keyID = ''
		elif len(args) == 9:
			self.jid = args[0]
			self.name = args[1]
			self.groups = args[2]
			self.show = args[3]
			self.status = args[4]
			self.sub = args[5]
			self.resource = args[6]
			self.priority = args[7]
			self.keyID = args[8]
		else: raise TypeError, _('bad arguments')


class message_Window:
	"""Class for chat window"""
	def delete_event(self, widget):
		"""close window"""
		del self.plugin.windows[self.account]['chats'][self.user.jid]
	
	def print_conversation(self, txt, contact = None, tim = None):
		"""Print a line in the conversation :
		if contact is set to status : it's a status message
		if contact is set to another value : it's an outgoing message
		if contact is not set : it's an incomming message"""
		conversation = self.xml.get_widget('conversation')
		buffer = conversation.get_buffer()
		if not txt:
			txt = ""
		end_iter = buffer.get_end_iter()
		if not tim:
			tim = time.localtime()
		tims = time.strftime("[%H:%M:%S]", tim)
		buffer.insert(end_iter, tims + ' ')
		
		otxt = ''
		ttxt = ''
		if contact and contact == 'status':
			tag = 'status'
			ttxt = txt + '\n'
		else:
			if contact:
				tag = 'outgoing'
				name = self.plugin.nicks[self.account] 
			else:
				tag = 'incoming'
				name = self.user.name
				
			if string.find(txt, '/me ') == 0:
				ttxt = name + ' ' + txt[4:] + '\n'
			else:
				ttxt = '<' + name + '> '
				otxt = txt + '\n'

		buffer.insert_with_tags_by_name(end_iter, ttxt, tag)
		if len(otxt) > 0:
			buffer.insert(end_iter, otxt)
		
		#scroll to the end of the textview
		conversation.scroll_to_mark(buffer.get_mark('end'), 0.1, 0, 0, 0)
	
	def read_queue(self, q):
		"""read queue and print messages containted in it"""
		while not q.empty():
			evt = q.get()
			self.print_conversation(evt[0], tim = evt[1])
		del self.plugin.queues[self.account][self.user.jid]
		self.plugin.roster.redraw_jid(self.user.jid, self.account)
		self.plugin.systray.remove_jid(self.user.jid, self.account)
		showOffline = self.plugin.config['showoffline']
		if (self.user.show == 'offline' or self.user.show == 'error') and \
			not showOffline:
			if len(self.plugin.roster.contacts[self.account][self.user.jid]) == 1:
				self.plugin.roster.remove_user(self.user, self.account)

	def on_msg_key_press_event(self, widget, event):
		"""When a key is pressed :
		if enter is pressed without the shit key, message (if not empty) is sent
		and printed in the conversation"""
		if event.keyval == gtk.keysyms.Return:
			if (event.state & gtk.gdk.SHIFT_MASK):
				return 0
			txt_buffer = widget.get_buffer()
			start_iter = txt_buffer.get_start_iter()
			end_iter = txt_buffer.get_end_iter()
			txt = txt_buffer.get_text(start_iter, end_iter, 0)
			if txt != '':
				keyID = ''
				if self.xml.get_widget('toggle_gpg').get_active():
					keyID = self.keyID
				self.plugin.send('MSG', self.account, (self.user.jid, txt, keyID))
				txt_buffer.set_text('', -1)
				self.print_conversation(txt, self.user.jid)
				widget.grab_focus()
			return 1
		return 0

	def on_clear(self, widget):
		"""When clear button is pressed :
		clear the conversation"""
		buffer = self.xml.get_widget('conversation').get_buffer()
		deb, end = buffer.get_bounds()
		buffer.delete(deb, end)

	def on_history(self, widget):
		"""When history button is pressed : call log window"""
		if not self.plugin.windows['logs'].has_key(self.user.jid):
			self.plugin.windows['logs'][self.user.jid] = log_Window(self.plugin, self.user.jid)

	def on_focus(self, widget, event):
		"""When window get focus"""
		self.plugin.systray.remove_jid(self.user.jid, self.account)
	
	def __init__(self, user, plugin, account):
		self.user = user
		self.plugin = plugin
		self.account = account
		self.keyID = self.user.keyID
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'Chat', APP)
		self.window = self.xml.get_widget('Chat')
		self.window.set_title(user.name + " (" + account + ")")
		self.img = self.xml.get_widget('image')
		image = self.plugin.roster.pixbufs[user.show]
		if image.get_storage_type() == gtk.IMAGE_ANIMATION:
			self.img.set_from_animation(image.get_animation())
		elif image.get_storage_type() == gtk.IMAGE_PIXBUF:
			self.img.set_from_pixbuf(image.get_pixbuf())
		self.xml.get_widget('button_contact').set_label(user.name + ' <'\
			+ user.jid + '>')
		self.xml.get_widget('button_contact').set_resize_mode(gtk.RESIZE_QUEUE)
		if not self.keyID:
			self.xml.get_widget('toggle_gpg').set_sensitive(False)
		message = self.xml.get_widget('message')
		message.grab_focus()
		conversation = self.xml.get_widget('conversation')
		buffer = conversation.get_buffer()
		end_iter = buffer.get_end_iter()
		buffer.create_mark('end', end_iter, 0)
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_clear_clicked', self.on_clear)
		self.xml.signal_connect('on_focus', self.on_focus)
		self.xml.signal_connect('on_history_clicked', self.on_history)
		self.xml.signal_connect('on_msg_key_press_event', \
			self.on_msg_key_press_event)
		self.tagIn = buffer.create_tag("incoming")
		color = self.plugin.config['inmsgcolor']
		self.tagIn.set_property("foreground", color)
		self.tagOut = buffer.create_tag("outgoing")
		color = self.plugin.config['outmsgcolor']
		self.tagOut.set_property("foreground", color)
		self.tagStatus = buffer.create_tag("status")
		color = self.plugin.config['statusmsgcolor']
		self.tagStatus.set_property("foreground", color)
		#print queued messages
		if plugin.queues[account].has_key(user.jid):
			self.read_queue(plugin.queues[account][user.jid])
		if self.user.show != 'online':
			self.print_conversation(_("%s is now %s (%s)") % (user.name, \
				user.show, user.status), 'status')

class gc:
	def delete_event(self, widget):
		"""close window"""
		self.plugin.send('GC_STATUS', self.account, (self.nick, self.jid,\
			'offline', 'offline'))
		del self.plugin.windows[self.account]['gc'][self.jid]

	def on_close(self, widget):
		"""When Cancel button is clicked"""
		widget.get_toplevel().destroy()

	def get_role_iter(self, name):
		model = self.tree.get_model()
		fin = False
		iter = model.get_iter_root()
		if not iter:
			return None
		while not fin:
			account_name = model.get_value(iter, 1)
			if name == account_name:
				return iter
			iter = model.iter_next(iter)
			if not iter:
				fin = True
		return None

	def get_user_iter(self, jid):
		model = self.tree.get_model()
		fin = False
		role = model.get_iter_root()
		if not role:
			return None
		while not fin:
			fin2 = False
			user = model.iter_children(role)
			if not user:
				fin2=True
			while not fin2:
				if jid == model.get_value(user, 1):
					return user
				user = model.iter_next(user)
				if not user:
					fin2 = True
			role = model.iter_next(role)
			if not role:
				fin = True
		return None

	def remove_user(self, nick):
		"""Remove a user from the roster"""
		model = self.tree.get_model()
		iter = self.get_user_iter(nick)
		parent_iter = model.iter_parent(iter)
		model.remove(iter)
		if model.iter_n_children(parent_iter) == 0:
			model.remove(parent_iter)
	
	def add_user_to_roster(self, nick, show, role):
		model = self.tree.get_model()
		img = self.plugin.roster.pixbufs[show]
		role_iter = self.get_role_iter(role)
		if not role_iter:
			role_iter = model.append(None, (self.plugin.roster.pixbufs['closed']\
				, role))
		iter = model.append(role_iter, (img, nick))
		self.tree.expand_row((model.get_path(role_iter)), False)
		return iter
	
	def get_role(self, jid_iter):
		model = self.tree.get_model()
		path = model.get_path(jid_iter)[0]
		iter = model.get_iter(path)
		return model.get_value(iter, 1)

	def chg_user_status(self, nick, show, status, role, affiliation, jid, \
		reason, actor, statusCode, account):
		"""When a user change his status"""
		model = self.tree.get_model()
		if show == 'offline' or show == 'error':
			if statusCode == '307':
				self.print_conversation(_("%s has been kicked by %s: %s") % (nick, \
					actor, reason))
			self.remove_user(nick)
		else:
			iter = self.get_user_iter(nick)
			if not iter:
				iter = self.add_user_to_roster(nick, show, role)
			else:
				actual_role = self.get_role(iter)
				if role != actual_role:
					self.remove_user(nick)
					self.add_user_to_roster(nick, show, role)
				else:
					img = self.plugin.roster.pixbufs[show]
					model.set_value(iter, 0, img)

	def on_msg_key_press_event(self, widget, event):
		"""When a key is pressed :
		if enter is pressed without the shit key, message (if not empty) is sent
		and printed in the conversation"""
		if event.keyval == gtk.keysyms.Return:
			if (event.state & gtk.gdk.SHIFT_MASK):
				return 0
			txt_buffer = widget.get_buffer()
			start_iter = txt_buffer.get_start_iter()
			end_iter = txt_buffer.get_end_iter()
			txt = txt_buffer.get_text(start_iter, end_iter, 0)
			if txt != '':
				self.plugin.send('GC_MSG', self.account, (self.jid, txt))
				txt_buffer.set_text('', -1)
				widget.grab_focus()
			return 1
		return 0

	def print_conversation(self, txt, contact = None, tim = None):
		"""Print a line in the conversation :
		if contact is set : it's a message from someone
		if contact is not set : it's a message from the server"""
		conversation = self.xml.get_widget('conversation')
		buffer = conversation.get_buffer()
		if not txt:
			txt = ""
		end_iter = buffer.get_end_iter()
		if not tim:
			tim = time.localtime()
		tims = time.strftime("[%H:%M:%S]", tim)
		buffer.insert(end_iter, tims)
		if contact:
			if contact == self.nick:
				buffer.insert_with_tags_by_name(end_iter, '<'+contact+'> ', \
					'outgoing')
			else:
				buffer.insert_with_tags_by_name(end_iter, '<' + contact + '> ', \
					'incoming')
			buffer.insert(end_iter, txt+'\n')
		else:
			buffer.insert_with_tags_by_name(end_iter, txt+'\n', \
				'status')
		#scroll to the end of the textview
		conversation.scroll_to_mark(buffer.get_mark('end'), 0.1, 0, 0, 0)

	def kick(self, widget, room_jid, nick):
		"""kick a user"""
		self.plugin.send('SET_ROLE', self.account, (room_jid, nick, 'none'))

	def grant_voice(self, widget, room_jid, nick):
		"""grant voice privilege to a user"""
		self.plugin.send('SET_ROLE', self.account, (room_jid, nick, \
			'participant'))

	def revoke_voice(self, widget, room_jid, nick):
		"""revoke voice privilege to a user"""
		self.plugin.send('SET_ROLE', self.account, (room_jid, nick, 'visitor'))

	def grant_moderator(self, widget, room_jid, nick):
		"""grant moderator privilege to a user"""
		self.plugin.send('SET_ROLE', self.account, (room_jid, nick, 'moderator'))

	def revoke_moderator(self, widget, room_jid, nick):
		"""revoke moderator privilege to a user"""
		self.plugin.send('SET_ROLE', self.account, (room_jid, nick, \
			'participant'))

	def ban(self, widget, room_jid, nick):
		"""ban a user"""
		self.plugin.send('SET_AFFILIATION', self.account, (room_jid, nick, \
			'outcast'))

	def grant_membership(self, widget, room_jid, nick):
		"""grant membership privilege to a user"""
		self.plugin.send('SET_AFFILIATION', self.account, (room_jid, nick, \
			'member'))

	def revoke_membership(self, widget, room_jid, nick):
		"""revoke membership privilege to a user"""
		self.plugin.send('SET_AFFILIATION', self.account, (room_jid, nick, \
			'none'))

	def grant_admin(self, widget, room_jid, nick):
		"""grant administrative privilege to a user"""
		self.plugin.send('SET_AFFILIATION', self.account, (room_jid, nick, \
			'admin'))

	def revoke_admin(self, widget, room_jid, nick):
		"""revoke administrative privilege to a user"""
		self.plugin.send('SET_AFFILIATION', self.account, (room_jid, nick, \
			'member'))

	def grant_owner(self, widget, room_jid, nick):
		"""grant owner privilege to a user"""
		self.plugin.send('SET_AFFILIATION', self.account, (room_jid, nick, \
			'owner'))

	def revoke_owner(self, widget, room_jid, nick):
		"""revoke owner privilege to a user"""
		self.plugin.send('SET_AFFILIATION', self.account, (room_jid, nick, \
			'admin'))

	def mk_menu(self, event, iter):
		"""Make user's popup menu"""
		model = self.tree.get_model()
		nick = model.get_value(iter, 1)
#		jid = model.get_value(iter, 3)
#		path = model.get_path(iter)
#		user = self.contacts[account][jid][0]
		
		menu = gtk.Menu()
		item = gtk.MenuItem(_("MUC"))
		menu.append(item)
		
		menu_sub = gtk.Menu()
		item.set_submenu(menu_sub)
		item = gtk.MenuItem(_("Kick"))
		menu_sub.append(item)
		item.connect("activate", self.kick, self.jid, nick)
		item = gtk.MenuItem(_("Grant voice"))
		menu_sub.append(item)
		item.connect("activate", self.grant_voice, self.jid, nick)
		item = gtk.MenuItem(_("Revoke voice"))
		menu_sub.append(item)
		item.connect("activate", self.revoke_voice, self.jid, nick)
		item = gtk.MenuItem(_("Grant moderator"))
		menu_sub.append(item)
		item.connect("activate", self.grant_moderator, self.jid, nick)
		item = gtk.MenuItem(_("Revoke moderator"))
		menu_sub.append(item)
		item.connect("activate", self.revoke_moderator, self.jid, nick)
		
		item = gtk.MenuItem()
		menu_sub.append(item)

		item = gtk.MenuItem(_("Ban"))
		menu_sub.append(item)
		item.connect("activate", self.ban, self.jid, nick)
		item = gtk.MenuItem(_("Grant membership"))
		menu_sub.append(item)
		item.connect("activate", self.grant_membership, self.jid, nick)
		item = gtk.MenuItem(_("Revoke membership"))
		menu_sub.append(item)
		item.connect("activate", self.revoke_membership, self.jid, nick)
		item = gtk.MenuItem(_("Grant admin"))
		menu_sub.append(item)
		item.connect("activate", self.grant_admin, self.jid, nick)
		item = gtk.MenuItem(_("Revoke admin"))
		menu_sub.append(item)
		item.connect("activate", self.revoke_admin, self.jid, nick)
		item = gtk.MenuItem(_("Grant owner"))
		menu_sub.append(item)
		item.connect("activate", self.grant_owner, self.jid, nick)
		item = gtk.MenuItem(_("Revoke owner"))
		menu_sub.append(item)
		item.connect("activate", self.revoke_owner, self.jid, nick)
		
		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()
		menu.reposition()

	def on_focus(self, widget, event):
		"""When window get focus"""
		self.plugin.systray.remove_jid(self.jid, self.account)

	def on_treeview_event(self, widget, event):
		"""popup user's group's or agent menu"""
		if event.type == gtk.gdk.BUTTON_PRESS:
			if event.button == 3:
				try:
					path, column, x, y = self.tree.get_path_at_pos(int(event.x), \
						int(event.y))
				except TypeError:
					self.tree.get_selection().unselect_all()
					return gtk.FALSE
				model = self.tree.get_model()
				iter = model.get_iter(path)
				if len(path) == 2:
					self.mk_menu(event, iter)
				return gtk.TRUE
			if event.button == 1:
				try:
					path, column, x, y = self.tree.get_path_at_pos(int(event.x), \
						int(event.y))
				except TypeError:
					self.tree.get_selection().unselect_all()
		if event.type == gtk.gdk.KEY_RELEASE:
			if event.keyval == gtk.keysyms.Escape:
				self.tree.get_selection().unselect_all()
		return gtk.FALSE

	def on_row_activated(self, widget, path, col=0):
		"""When an iter is dubble clicked :
		open the chat window"""
		model = self.tree.get_model()
		iter = model.get_iter(path)
		if len(path) == 1:
			if (self.tree.row_expanded(path)):
				self.tree.collapse_row(path)
			else:
				self.tree.expand_row(path, False)

	def on_row_expanded(self, widget, iter, path):
		"""When a row is expanded :
		change the icon of the arrow"""
		model = self.tree.get_model()
		model.set_value(iter, 0, self.plugin.roster.pixbufs['opened'])
	
	def on_row_collapsed(self, widget, iter, path):
		"""When a row is collapsed :
		change the icon of the arrow"""
		model = self.tree.get_model()
		model.set_value(iter, 0, self.plugin.roster.pixbufs['closed'])

	def __init__(self, jid, nick, plugin, account):
		self.jid = jid
		self.nick = nick
		self.plugin = plugin
		self.account = account
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'Gc', APP)
		self.window = self.xml.get_widget('Gc')
		self.tree = self.xml.get_widget('list')

		store = gtk.TreeStore(gtk.Image, str)
		column = gtk.TreeViewColumn('contacts')#, ImageCellRenderer(), image=0)
		render_text = ImageCellRenderer()
		column.pack_start(render_text, expand = False)
		column.add_attribute(render_text, 'image', 0)
		render_text = gtk.CellRendererText()
		column.pack_start(render_text, expand = True)
		column.add_attribute(render_text, 'text', 1)

		self.tree.append_column(column)
		self.tree.set_model(store)

		col = gtk.TreeViewColumn()
		render = gtk.CellRendererPixbuf()
		col.pack_start(render, expand = False)
		self.tree.append_column(col)
		col.set_visible(FALSE)
		self.tree.set_expander_column(col)

		conversation = self.xml.get_widget('conversation')
		buffer = conversation.get_buffer()
		end_iter = buffer.get_end_iter()
		buffer.create_mark('end', end_iter, 0)
		self.tagIn = buffer.create_tag("incoming")
		color = self.plugin.config['inmsgcolor']
		self.tagIn.set_property("foreground", color)
		self.tagOut = buffer.create_tag("outgoing")
		color = self.plugin.config['outmsgcolor']
		self.tagOut.set_property("foreground", color)
		self.tagStatus = buffer.create_tag("status")
		color = self.plugin.config['statusmsgcolor']
		self.tagStatus.set_property("foreground", color)
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_focus', self.on_focus)
		self.xml.signal_connect('on_msg_key_press_event', \
			self.on_msg_key_press_event)
		self.xml.signal_connect('on_treeview_event', self.on_treeview_event)
		self.xml.signal_connect('on_row_activated', self.on_row_activated)
		self.xml.signal_connect('on_row_expanded', self.on_row_expanded)
		self.xml.signal_connect('on_row_collapsed', self.on_row_collapsed)

class log_Window:
	"""Class for bowser agent window :
	to know the agents on the selected server"""
	def delete_event(self, widget):
		"""close window"""
		del self.plugin.windows['logs'][self.jid]

	def on_close(self, widget):
		"""When Close button is clicked"""
		widget.get_toplevel().destroy()

	def on_earliest(self, widget):
		buffer = self.xml.get_widget('textview').get_buffer()
		start, end = buffer.get_bounds()
		buffer.delete(start, end)
		self.xml.get_widget('earliest_button').set_sensitive(False)
		self.xml.get_widget('previous_button').set_sensitive(False)
		self.xml.get_widget('forward_button').set_sensitive(True)
		self.xml.get_widget('latest_button').set_sensitive(True)
		end = 50
		if end > self.nb_line:
			end = self.nb_line
		self.plugin.send('LOG_GET_RANGE', None, (self.jid, 0, end))
		self.num_begin = self.nb_line

	def on_previous(self, widget):
		buffer = self.xml.get_widget('textview').get_buffer()
		start, end = buffer.get_bounds()
		buffer.delete(start, end)
		self.xml.get_widget('earliest_button').set_sensitive(True)
		self.xml.get_widget('previous_button').set_sensitive(True)
		self.xml.get_widget('forward_button').set_sensitive(True)
		self.xml.get_widget('latest_button').set_sensitive(True)
		begin = self.num_begin - 50
		if begin < 0:
			begin = 0
		end = begin + 50
		if end > self.nb_line:
			end = self.nb_line
		self.plugin.send('LOG_GET_RANGE', None, (self.jid, begin, end))
		self.num_begin = self.nb_line

	def on_forward(self, widget):
		buffer = self.xml.get_widget('textview').get_buffer()
		start, end = buffer.get_bounds()
		buffer.delete(start, end)
		self.xml.get_widget('earliest_button').set_sensitive(True)
		self.xml.get_widget('previous_button').set_sensitive(True)
		self.xml.get_widget('forward_button').set_sensitive(True)
		self.xml.get_widget('latest_button').set_sensitive(True)
		begin = self.num_begin + 50
		if begin > self.nb_line:
			begin = self.nb_line
		end = begin + 50
		if end > self.nb_line:
			end = self.nb_line
		self.plugin.send('LOG_GET_RANGE', None, (self.jid, begin, end))
		self.num_begin = self.nb_line

	def on_latest(self, widget):
		buffer = self.xml.get_widget('textview').get_buffer()
		start, end = buffer.get_bounds()
		buffer.delete(start, end)
		self.xml.get_widget('earliest_button').set_sensitive(True)
		self.xml.get_widget('previous_button').set_sensitive(True)
		self.xml.get_widget('forward_button').set_sensitive(False)
		self.xml.get_widget('latest_button').set_sensitive(False)
		begin = self.nb_line - 50
		if begin < 0:
			begin = 0
		self.plugin.send('LOG_GET_RANGE', None, (self.jid, begin, self.nb_line))
		self.num_begin = self.nb_line

	def new_line(self, infos):
		"""write a new line"""
		#infos = [num_line, date, type, data]
		if infos[0] < self.num_begin:
			self.num_begin = infos[0]
		if infos[0] == 0:
			self.xml.get_widget('earliest_button').set_sensitive(False)
			self.xml.get_widget('previous_button').set_sensitive(False)
		if infos[0] == self.nb_line:
			self.xml.get_widget('forward_button').set_sensitive(False)
			self.xml.get_widget('latest_button').set_sensitive(False)
		buffer = self.xml.get_widget('textview').get_buffer()
		start_iter = buffer.get_start_iter()
		end_iter = buffer.get_end_iter()
		tim = time.strftime("[%x %X] ", time.localtime(float(infos[1])))
		buffer.insert(start_iter, tim)
		if infos[2] == 'recv':
			msg = string.join(infos[3][0:], ':')
			msg = string.replace(msg, '\\n', '\n')
			buffer.insert_with_tags_by_name(start_iter, msg, 'incoming')
		elif infos[2] == 'sent':
			msg = string.join(infos[3][0:], ':')
			msg = string.replace(msg, '\\n', '\n')
			buffer.insert_with_tags_by_name(start_iter, msg, 'outgoing')
		else:
			msg = string.join(infos[3][1:], ':')
			msg = string.replace(msg, '\\n', '\n')
			buffer.insert_with_tags_by_name(start_iter, _('Status is now : ') + \
				infos[3][0]+' : ' + msg, 'status')
	
	def set_nb_line(self, nb_line):
		self.nb_line = nb_line
		self.num_begin = nb_line

	def __init__(self, plugin, jid):
		self.plugin = plugin
		self.jid = jid
		self.nb_line = 0
		self.num_begin = 0
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'Log', APP)
		self.window = self.xml.get_widget('Log')
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_close_clicked', self.on_close)
		self.xml.signal_connect('on_earliest_clicked', self.on_earliest)
		self.xml.signal_connect('on_previous_clicked', self.on_previous)
		self.xml.signal_connect('on_forward_clicked', self.on_forward)
		self.xml.signal_connect('on_latest_clicked', self.on_latest)
		buffer = self.xml.get_widget('textview').get_buffer()
		tagIn = buffer.create_tag("incoming")
		color = self.plugin.config['inmsgcolor']
		if not color:
			color = 'red'
		tagIn.set_property("foreground", color)
		tagOut = buffer.create_tag("outgoing")
		color = self.plugin.config['outmsgcolor']
		if not color:
			color = 'blue'
		tagOut.set_property("foreground", color)
		tagStatus = buffer.create_tag("status")
		color = self.plugin.config['statusmsgcolor']
		if not color:
			color = 'green'
		tagStatus.set_property("foreground", color)
		self.plugin.send('LOG_NB_LINE', None, jid)

class roster_Window:
	"""Class for main gtk window"""

	def get_account_iter(self, name):
		model = self.tree.get_model()
		fin = False
		account = model.get_iter_root()
		if not account:
			return None
		while not fin:
			account_name = model.get_value(account, 3)
			if name == account_name:
				return account
			account = model.iter_next(account)
			if not account:
				fin = True
		return None

	def get_group_iter(self, name, account):
		model = self.tree.get_model()
		root = self.get_account_iter(account)
		fin = False
		group = model.iter_children(root)
		if not group:
			fin = True
		while not fin:
			group_name = model.get_value(group, 3)
			if name == group_name:
				return group
			group = model.iter_next(group)
			if not group:
				fin = True
		return None

	def get_user_iter(self, jid, account):
		model = self.tree.get_model()
		acct = self.get_account_iter(account)
		found = []
		fin = False
		group = model.iter_children(acct)
		if not group:
			return found
		while not fin:
			fin2 = False
			user = model.iter_children(group)
			if not user:
				fin2=True
			while not fin2:
				if jid == model.get_value(user, 3):
					found.append(user)
				user = model.iter_next(user)
				if not user:
					fin2 = True
			group = model.iter_next(group)
			if not group:
				fin = True
		return found

	def add_account_to_roster(self, account):
		model = self.tree.get_model()
		if self.get_account_iter(account):
			return
		statuss = ['offline', 'online', 'away', 'xa', 'dnd', 'invisible']
		status = statuss[self.plugin.connected[account]]
		model.append(None, (self.pixbufs[status], account, 'account', account,\
			FALSE))

	def add_user_to_roster(self, jid, account):
		"""Add a user to the roster and add groups if they aren't in roster"""
		showOffline = self.plugin.config['showoffline']
		if not self.contacts[account].has_key(jid):
			return
		users = self.contacts[account][jid]
		user = users[0]
		if user.groups == []:
			if string.find(user.jid, "@") <= 0:
				user.groups.append('Agents')
			else:
				user.groups.append('general')

		if (user.show == 'offline' or user.show == 'error') and not showOffline\
			and not 'Agents' in user.groups and \
			not self.plugin.queues[account].has_key(user.jid):
			return

		model = self.tree.get_model()
		for g in user.groups:
			iterG = self.get_group_iter(g, account)
			if not iterG:
				IterAcct = self.get_account_iter(account)
				iterG = model.append(IterAcct, \
					(self.pixbufs['closed'], g, 'group', \
					g, FALSE))
			if not self.groups[account].has_key(g): #It can probably never append
				if account+g in self.hidden_lines:
					self.groups[account][g] = {'expand': False}
				else:
					self.groups[account][g] = {'expand': True}
			if not account in self.hidden_lines:
				self.tree.expand_row((model.get_path(iterG)[0]), False)

			typestr = 'user'
			if g == 'Agents':
				typestr = 'agent'

			model.append(iterG, (self.pixbufs[user.show], \
				user.name, typestr, user.jid, False))
			
			if self.groups[account][g]['expand']:
				self.tree.expand_row(model.get_path(iterG), False)
		self.redraw_jid(jid, account)
	
	def remove_user(self, user, account):
		"""Remove a user from the roster"""
		model = self.tree.get_model()
		for i in self.get_user_iter(user.jid, account):
			parent_i = model.iter_parent(i)
			model.remove(i)
			if model.iter_n_children(parent_i) == 0:
				model.remove(parent_i)

	def redraw_jid(self, jid, account):
		"""draw the correct pixbuf and name"""
		model = self.tree.get_model()
		iters = self.get_user_iter(jid, account)
		if len(iters) == 0:
			return
		users = self.contacts[account][jid]
		name = users[0].name
		if len(users) > 1:
			name += " (" + str(len(users)) + ")"
		prio = 0
		show = users[0].show
		for u in users:
			if u.priority > prio:
				prio = u.priority
				show = u.show
		for iter in iters:
			if self.plugin.queues[account].has_key(jid):
				img = self.pixbufs['message']
			else:
				img = self.pixbufs[show]
			model.set_value(iter, 0, img)
			model.set_value(iter, 1, name)
	
	def mkmenu(self):
		"""create the browse agents, add and join groupchat sub menus"""
		if len(self.plugin.accounts.keys()) > 0:
			self.xml.get_widget('add').set_sensitive(True)
			self.xml.get_widget('browse_agents').set_sensitive(True)
			self.xml.get_widget('join_gc').set_sensitive(True)
		else:
			self.xml.get_widget('add').set_sensitive(False)
			self.xml.get_widget('browse_agents').set_sensitive(False)
			self.xml.get_widget('join_gc').set_sensitive(False)
		if len(self.plugin.accounts.keys()) > 1:
			#add
			menu_sub = gtk.Menu()
			self.xml.get_widget('add').set_submenu(menu_sub)
			for a in self.plugin.accounts.keys():
				item = gtk.MenuItem(a)
				menu_sub.append(item)
				item.connect("activate", self.on_add, a)
			menu_sub.show_all()
			#agents
			menu_sub = gtk.Menu()
			self.xml.get_widget('browse_agents').set_submenu(menu_sub)
			for a in self.plugin.accounts.keys():
				item = gtk.MenuItem(a)
				menu_sub.append(item)
				item.connect("activate", self.on_browse, a)
			menu_sub.show_all()
			#join gc
			menu_sub = gtk.Menu()
			self.xml.get_widget('join_gc').set_submenu(menu_sub)
			for a in self.plugin.accounts.keys():
				item = gtk.MenuItem(a)
				menu_sub.append(item)
				item.connect("activate", self.on_join_gc, a)
			menu_sub.show_all()
		elif len(self.plugin.accounts.keys()) == 1:
			#add
			self.xml.get_widget('add').connect("activate", self.on_add, \
				self.plugin.accounts.keys()[0])
			#agents
			self.xml.get_widget('browse_agents').connect("activate", \
				self.on_browse, self.plugin.accounts.keys()[0])
			#join_gc
			self.xml.get_widget('join_gc').connect("activate", \
				self.on_join_gc, self.plugin.accounts.keys()[0])

	def draw_roster(self):
		"""Clear and draw roster"""
		self.mkmenu()
		self.tree.get_model().clear()
		for acct in self.contacts.keys():
			self.add_account_to_roster(acct)
			for jid in self.contacts[acct].keys():
				self.add_user_to_roster(jid, acct)
	
	def mklists(self, array, account):
		"""fill self.contacts and self.groups"""
		if not self.contacts.has_key(account):
			self.contacts[account] = {}
		if not self.groups.has_key(account):
			self.groups[account] = {}
		for jid in array.keys():
			jids = string.split(jid, '/')
			#get jid
			ji = jids[0]
			#get resource
			resource = ''
			if len(jids) > 1:
				resource = jids[1:]
			#get name
			name = array[jid]['name']
			if not name:
				if string.find(ji, "@") <= 0:
					name = ji
				else:
					name = string.split(jid, '@')[0]
			#get show
			show = array[jid]['show']
			if not show:
				show = 'offline'

			user1 = user(ji, name, array[jid]['groups'], show, \
				array[jid]['status'], array[jid]['sub'], resource, 0, '')
			#when we draw the roster, we can't have twice the same user with 
			# 2 resources
			self.contacts[account][ji] = [user1]
			for g in array[jid]['groups'] :
				if not g in self.groups[account].keys():
					if account+g in self.hidden_lines:
						self.groups[account][g] = {'expand': False}
					else:
						self.groups[account][g] = {'expand': True}

	def chg_user_status(self, user, show, status, account):
		"""When a user change his status"""
		showOffline = self.plugin.config['showoffline']
		model = self.tree.get_model()
		if (show == 'offline' or show == 'error') and not showOffline and \
			not self.plugin.queues[account].has_key(user.jid):
			if len(self.contacts[account][user.jid]) > 1:
				luser = self.contacts[account][user.jid]
				for u in luser:
					if u.resource == user.resource:
						luser.remove(u)
						self.redraw_jid(user.jid, account)
						break
			else:
				self.remove_user(user, account)
				iters = []
		else:
			if not self.get_user_iter(user.jid, account):
				self.add_user_to_roster(user.jid, account)
			self.redraw_jid(user.jid, account)
		users = self.contacts[account][user.jid]
		for u in users:
			if u.resource == user.resource:
				u.show = show
				u.status = status
				u.keyID = user.keyID
				break
		#Print status in chat window
		if self.plugin.windows[account]['chats'].has_key(user.jid):
			prio = 0
			sho = users[0].show
			for u in users:
				if u.priority > prio:
					prio = u.priority
					sho = u.show
			img = self.pixbufs[sho]
			if img.get_storage_type() == gtk.IMAGE_ANIMATION:
				self.plugin.windows[account]['chats'][user.jid].\
					img.set_from_animation(img.get_animation())
			elif img.get_storage_type() == gtk.IMAGE_PIXBUF:
				self.plugin.windows[account]['chats'][user.jid].\
					img.set_from_pixbuf(img.get_pixbuf())
			name = user.name
			if user.resource != '':
				name += '/'+user.resource
			self.plugin.windows[account]['chats'][user.jid].print_conversation(\
				_("%s is now %s (%s)") % (name, show, status), 'status')

	def on_info(self, widget, user, account):
		"""Call infoUser_Window class to display user's information"""
		if not self.plugin.windows[account]['infos'].has_key(user.jid):
			self.plugin.windows[account]['infos'][user.jid] = \
				infoUser_Window(user, self.plugin, account)

	def on_agent_logging(self, widget, jid, state, account):
		"""When an agent is requested to log in or off"""
		self.plugin.send('AGENT_LOGGING', account, (jid, state))

	def on_remove_agent(self, widget, jid, account):
		"""When an agent is requested to log in or off"""
		window = confirm_Window(_("Are you sure you want to remove the agent %s from your roster ?") % jid)
		if window.wait() == gtk.RESPONSE_OK:
			self.plugin.send('UNSUB_AGENT', account, jid)
			for u in self.contacts[account][jid]:
				self.remove_user(u, account)
			del self.contacts[account][u.jid]

	def on_rename(self, widget, iter, path, user):
		model = self.tree.get_model()
		model.set_value(iter, 1, user.name)
		model.set_value(iter, 4, True)
		self.tree.set_cursor(path, self.tree.get_column(0), True)
		
	def on_history(self, widget, user):
		"""When history button is pressed : call log window"""
		if not self.plugin.windows['logs'].has_key(user.jid):
			self.plugin.windows['logs'][user.jid] = log_Window(self.plugin, \
				user.jid)
	
	def mk_menu_user(self, event, iter):
		"""Make user's popup menu"""
		model = self.tree.get_model()
		jid = model.get_value(iter, 3)
		path = model.get_path(iter)
		acct_iter = model.get_iter((path[0]))
		account = model.get_value(acct_iter, 3)
		user = self.contacts[account][jid][0]
		
		menu = gtk.Menu()
		item = gtk.MenuItem(_("Start chat"))
		menu.append(item)
		item.connect("activate", self.on_row_activated, path)
		item = gtk.MenuItem(_("Rename"))
		menu.append(item)
		item.connect("activate", self.on_rename, iter, path, user)
		item = gtk.MenuItem()
		menu.append(item)
		item = gtk.MenuItem(_("Subscription"))
		menu.append(item)
		
		menu_sub = gtk.Menu()
		item.set_submenu(menu_sub)
		item = gtk.MenuItem(_("Resend authorization to"))
		menu_sub.append(item)
		item.connect("activate", self.authorize, jid, account)
		item = gtk.MenuItem(_("Rerequest authorization from"))
		menu_sub.append(item)
		item.connect("activate", self.req_sub, jid, \
			_('I would like to add you to my contact list, please.'), account)
		
		item = gtk.MenuItem()
		menu.append(item)
		item = gtk.MenuItem(_("Remove"))
		menu.append(item)
		item.connect("activate", self.on_req_usub, user, account)

		item = gtk.MenuItem()
		menu.append(item)
		item = gtk.MenuItem(_("Informations"))
		menu.append(item)
		item.connect("activate", self.on_info, user, account)
		item = gtk.MenuItem(_("History"))
		menu.append(item)
		item.connect("activate", self.on_history, user)

		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()
		menu.reposition()

	def mk_menu_g(self, event):
		"""Make group's popup menu"""
		menu = gtk.Menu()
		item = gtk.MenuItem(_("grp1"))
#		menu.append(item)
		item = gtk.MenuItem(_("grp2"))
#		menu.append(item)
		item = gtk.MenuItem(_("grp3"))
#		menu.append(item)
		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()
		menu.reposition()
	
	def mk_menu_agent(self, event, iter):
		"""Make agent's popup menu"""
		model = self.tree.get_model()
		jid = model.get_value(iter, 3)
		path = model.get_path(iter)
		acct_iter = model.get_iter((path[0]))
		account = model.get_value(acct_iter, 3)
		menu = gtk.Menu()
		item = gtk.MenuItem(_("Log on"))
		if self.contacts[account][jid][0].show != 'offline':
			item.set_sensitive(FALSE)
		menu.append(item)
		item.connect("activate", self.on_agent_logging, jid, 'available', account)

		item = gtk.MenuItem(_("Log off"))
		if self.contacts[account][jid][0].show == 'offline':
			item.set_sensitive(FALSE)
		menu.append(item)
		item.connect("activate", self.on_agent_logging, jid, 'unavailable', \
			account)

		item = gtk.MenuItem()
		menu.append(item)

		item = gtk.MenuItem(_("Remove"))
		menu.append(item)
		item.connect("activate", self.on_remove_agent, jid, account)

		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()
		menu.reposition()

	def on_edit_account(self, widget, account):
		if not self.plugin.windows.has_key('accountPreference'):
			infos = self.plugin.accounts[account]
			infos['accname'] = account
#			if self.plugin.accounts[account].has_key("name"):
			infos['jid'] = self.plugin.accounts[account]["name"] + \
				'@' +  self.plugin.accounts[account]["hostname"]
			self.plugin.windows['accountPreference'] = \
				accountPreference_Window(self.plugin, infos)

	def mk_menu_account(self, event, iter):
		"""Make account's popup menu"""
		model = self.tree.get_model()
		account = model.get_value(iter, 3)
		
		menu = gtk.Menu()
		item = gtk.MenuItem(_("Status"))
		menu.append(item)
		
		menu_sub = gtk.Menu()
		item.set_submenu(menu_sub)
		item = gtk.MenuItem(_("Online"))
		menu_sub.append(item)
		item.connect("activate", self.change_status, account, 'online')
		item = gtk.MenuItem(_("Away"))
		menu_sub.append(item)
		item.connect("activate", self.change_status, account, 'away')
		item = gtk.MenuItem(_("NA"))
		menu_sub.append(item)
		item.connect("activate", self.change_status, account, 'xa')
		item = gtk.MenuItem(_("DND"))
		menu_sub.append(item)
		item.connect("activate", self.change_status, account, 'dnd')
		item = gtk.MenuItem(_("Invisible"))
		menu_sub.append(item)
		item.connect("activate", self.change_status, account, 'invisible')
		item = gtk.MenuItem()
		menu_sub.append(item)
		item = gtk.MenuItem(_("Offline"))
		menu_sub.append(item)
		item.connect("activate", self.change_status, account, 'offline')
		
		item = gtk.MenuItem()
		menu.append(item)

		item = gtk.MenuItem(_("Edit account"))
		menu.append(item)
		item.connect("activate", self.on_edit_account, account)
		item = gtk.MenuItem(_("_Browse agents"))
		menu.append(item)
		item.connect("activate", self.on_browse, account)
		
		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()
		menu.reposition()
	
	def authorize(self, widget, jid, account):
		"""Authorize a user"""
		self.plugin.send('AUTH', account, jid)

	def req_sub(self, widget, jid, txt, account):
		"""Request subscription to a user"""
		self.plugin.send('SUB', account, (jid, txt))
		if not self.contacts[account].has_key(jid):
			user1 = user(jid, jid, ['general'], 'requested', \
				'requested', 'sub', '', 0, '')
			self.contacts[account][jid] = [user1]
			self.add_user_to_roster(jid, account)
	
	def on_treeview_event(self, widget, event):
		"""popup user's group's or agent menu"""
		if event.type == gtk.gdk.BUTTON_PRESS:
			if event.button == 3:
				try:
					path, column, x, y = self.tree.get_path_at_pos(int(event.x), \
						int(event.y))
				except TypeError:
					self.tree.get_selection().unselect_all()
					return
				model = self.tree.get_model()
				iter = model.get_iter(path)
				type = model.get_value(iter, 2)
				if type == 'group':
					self.mk_menu_g(event)
				elif type == 'agent':
					self.mk_menu_agent(event, iter)
				elif type == 'user':
					self.mk_menu_user(event, iter)
				elif type == 'account':
					self.mk_menu_account(event, iter)
				return gtk.TRUE
			if event.button == 1:
				try:
					path, column, x, y = self.tree.get_path_at_pos(int(event.x), \
						int(event.y))
				except TypeError:
					self.tree.get_selection().unselect_all()
		if event.type == gtk.gdk.KEY_RELEASE:
			if event.keyval == gtk.keysyms.Escape:
				self.tree.get_selection().unselect_all()
		return gtk.FALSE

	def on_req_usub(self, widget, user, account):
		"""Remove a user"""
		window = confirm_Window(_("Are you sure you want to remove %s (%s) from your roster ?") % (user.name, user.jid))
		if window.wait() == gtk.RESPONSE_OK:
			self.plugin.send('UNSUB', account, user.jid)
			for u in self.contacts[account][user.jid]:
				self.remove_user(u, account)
			del self.contacts[account][u.jid]

	def send_status(self, account, status, txt):
		if status != 'offline':
			save_pass = 0
			if self.plugin.accounts[account].has_key("savepass"):
				save_pass = self.plugin.accounts[account]["savepass"]
			if not save_pass and not self.plugin.connected[account]:
				passphrase = ''
				w = passphrase_Window('Enter your passphrase for your account %s' % account)
				passphrase = w.run()
				if passphrase == -1:
					return
				self.plugin.send('PASSPHRASE', account, passphrase)

			keyid = None
			save_gpg_pass = 0
			if self.plugin.accounts[account].has_key("savegpgpass"):
				save_gpg_pass = self.plugin.accounts[account]["savegpgpass"]
			if self.plugin.accounts[account].has_key("keyid"):
				keyid = self.plugin.accounts[account]["keyid"]
			if keyid and not self.plugin.connected[account] and \
				self.plugin.config['usegpg']:
				if save_gpg_pass:
					passphrase = self.plugin.accounts[account]['gpgpass']
				else:
					passphrase = ''
					w = passphrase_Window('Enter your passphrase for your the GPG key of your account %s' % account)
					passphrase = w.run()
					if passphrase == -1:
						passphrase = ''
				self.plugin.send('GPGPASSPHRASE', account, passphrase)
		self.plugin.send('STATUS', account, (status, txt))
		if status == 'online' and self.plugin.sleeper.getState() != \
			common.sleepy.STATE_UNKNOWN:
			self.plugin.sleeper_state[account] = 1
		else:
			self.plugin.sleeper_state[account] = 0

	def change_status(self, widget, account, status):
		if status != 'online' and status != 'offline':
			w = awayMsg_Window(self.plugin)
			txt = w.run()
			if txt == -1:
				return
		else:
			txt = status
		self.send_status(account, status, txt)

	def on_cb_changed(self, widget):
		"""When we change our status"""
		model = self.cb.get_model()
		active = self.cb.get_active()
		if active < 0:
			return
		accounts = self.plugin.accounts.keys()
		if len(accounts) == 0:
			warning_Window(_("You must setup an account before connecting to jabber network."))
			self.set_cb()
			return
		status = model[active][0]
		if status != 'online' and status != 'offline':
			w = awayMsg_Window(self.plugin)
			txt = w.run()
			if txt == -1:
				self.set_cb()
				return
		else:
			txt = status
		for acct in accounts:
			if self.plugin.accounts[acct].has_key('active'):
				if not self.plugin.accounts[acct]['active']:
					continue
			self.send_status(acct, status, txt)
	
	def set_cb(self):
		#table to change index in plugin.connected to index in combobox
		table = {0:5, 1:0, 2:1, 3:2, 4:3, 5:4}
		maxi = max(self.plugin.connected.values())
		#temporarily block signal in order not to send status that we show
		#in the combobox
		self.cb.handler_block(self.id_signal_cb)
		self.cb.set_active(table[maxi])
		self.cb.handler_unblock(self.id_signal_cb)
		statuss = ['offline', 'online', 'away', 'xa', 'dnd', 'invisible']
		self.plugin.systray.set_status(statuss[maxi])

	def on_status_changed(self, account, status):
		"""the core tells us that our status has changed"""
		if not self.contacts.has_key(account):
			return
		model = self.tree.get_model()
		accountIter = self.get_account_iter(account)
		if accountIter:
			model.set_value(accountIter, 0, self.pixbufs[status])
		statuss = ['offline', 'online', 'away', 'xa', 'dnd', 'invisible']
		if status == 'offline':
			for jid in self.contacts[account]:
				luser = self.contacts[account][jid]
				for user in luser:
					self.chg_user_status(user, 'offline', 'Disconnected', account)
		self.plugin.connected[account] = statuss.index(status)
		self.set_cb()

	def on_message(self, jid, msg, tim, account):
		"""when we receive a message"""
		if not self.contacts[account].has_key(jid):
			user1 = user(jid, jid, ['not in list'], \
				'not in list', 'not in list', 'none', '', 0, '')
			self.contacts[account][jid] = [user1]
			self.add_user_to_roster(jid, account)
		iters = self.get_user_iter(jid, account)
		if iters:
			path = self.tree.get_model().get_path(iters[0])
		else:
			path = None
		autopopup = self.plugin.config['autopopup']
		autopopupaway = self.plugin.config['autopopupaway']
		if (autopopup == 0 or ( not autopopupaway and \
			self.plugin.connected[account] > 1)) and not \
			self.plugin.windows[account]['chats'].has_key(jid):
			#We save it in a queue
			if not self.plugin.queues[account].has_key(jid):
				model = self.tree.get_model()
				self.plugin.queues[account][jid] = Queue.Queue(50)
				self.redraw_jid(jid, account)
				self.plugin.systray.add_jid(jid, account)
#			tim = time.strftime("[%H:%M:%S]")
			self.plugin.queues[account][jid].put((msg, tim))
			if not path:
				self.add_user_to_roster(jid, account)
				iters = self.get_user_iter(jid, account)
				path = self.tree.get_model().get_path(iters[0])
			self.tree.expand_row(path[0:1], FALSE)
			self.tree.expand_row(path[0:2], FALSE)
			self.tree.scroll_to_cell(path)
			self.tree.set_cursor(path)
		else:
			if not self.plugin.windows[account]['chats'].has_key(jid):
				self.plugin.windows[account]['chats'][jid] = \
					message_Window(self.contacts[account][jid][0], self.plugin, \
						account)
				if path:
					self.tree.expand_row(path[0:1], FALSE)
					self.tree.expand_row(path[0:2], FALSE)
					self.tree.scroll_to_cell(path)
					self.tree.set_cursor(path)
			self.plugin.windows[account]['chats'][jid].print_conversation(msg, \
				tim = tim)
			if not self.plugin.windows[account]['chats'][jid].window.\
				get_property('is-active'):
				self.plugin.systray.add_jid(jid, account)

	def on_prefs(self, widget):
		"""When preferences is selected :
		call the preference_Window class"""
		if not self.plugin.windows.has_key('preferences'):
			self.plugin.windows['preferences'] = preference_Window(self.plugin)

	def on_add(self, widget, account):
		"""When add user is selected :
		call the add class"""
		addContact_Window(self.plugin, account)

	def on_join_gc(self, widget, account):
		"""When Join Groupchat is selected :
		call the join_gc class"""
		if not self.plugin.windows.has_key('join_gc'):
			self.plugin.windows['join_gc'] = join_gc(self.plugin, account)

	def on_about(self, widget):
		"""When about is selected :
		call the about class"""
		if not self.plugin.windows.has_key('about'):
			self.plugin.windows['about'] = about_Window(self.plugin)

	def on_accounts(self, widget):
		"""When accounts is seleted :
		call the accounts class to modify accounts"""
		if not self.plugin.windows.has_key('accounts'):
			self.plugin.windows['accounts'] = accounts_Window(self.plugin)

	def close_all(self, dic):
		"""close all the windows in the given dictionary"""
		for w in dic.values():
			if type(w) == type({}):
				self.close_all(w)
			else:
				w.window.destroy()
	
	def on_quit(self, widget):
		"""When we quit the gtk plugin :
		tell that to the core and exit gtk"""
		self.plugin.config['hiddenlines'] = string.join(self.hidden_lines, '\t')
		self.plugin.send('CONFIG', None, ('GtkGui', self.plugin.config, 'GtkGui'))
		self.plugin.send('QUIT', None, ('gtkgui', 1))
		print _("plugin gtkgui stopped")
		self.close_all(self.plugin.windows)
		self.plugin.systray.t.destroy()
		gtk.main_quit()
#		gtk.gdk.threads_leave()

	def on_row_activated(self, widget, path, col=0):
		"""When an iter is dubble clicked :
		open the chat window"""
		model = self.tree.get_model()
		acct_iter = model.get_iter((path[0]))
		account = model.get_value(acct_iter, 3)
		iter = model.get_iter(path)
		type = model.get_value(iter, 2)
		jid = model.get_value(iter, 3)
		if (type == 'group') or (type == 'account'):
			if (self.tree.row_expanded(path)):
				self.tree.collapse_row(path)
			else:
				self.tree.expand_row(path, False)
		else:
			if self.plugin.windows[account]['chats'].has_key(jid):
				self.plugin.windows[account]['chats'][jid].window.present()
			elif self.contacts[account].has_key(jid):
				self.plugin.windows[account]['chats'][jid] = \
					message_Window(self.contacts[account][jid][0], self.plugin, \
						account)

	def on_row_expanded(self, widget, iter, path):
		"""When a row is expanded :
		change the icon of the arrow"""
		model = self.tree.get_model()
		acct_iter = model.get_iter((path[0]))
		account = model.get_value(acct_iter, 3)
		type = model.get_value(iter, 2)
		if type == 'group':
			model.set_value(iter, 0, self.pixbufs['opened'])
			jid = model.get_value(iter, 3)
			self.groups[account][jid]['expand'] = True
			if account+jid in self.hidden_lines:
				self.hidden_lines.remove(account+jid)
		elif type == 'account':
			if account in self.hidden_lines:
				self.hidden_lines.remove(account)
			for g in self.groups[account]:
				groupIter = self.get_group_iter(g, account)
				if groupIter and self.groups[account][g]['expand']:
					pathG = model.get_path(groupIter)
					self.tree.expand_row(pathG, False)
			
	
	def on_row_collapsed(self, widget, iter, path):
		"""When a row is collapsed :
		change the icon of the arrow"""
		model = self.tree.get_model()
		acct_iter = model.get_iter((path[0]))
		account = model.get_value(acct_iter, 3)
		type = model.get_value(iter, 2)
		if type == 'group':
			model.set_value(iter, 0, self.pixbufs['closed'])
			jid = model.get_value(iter, 3)
			self.groups[account][jid]['expand'] = False
			if not account+jid in self.hidden_lines:
				self.hidden_lines.append(account+jid)
		elif type == 'account':
			if not account in self.hidden_lines:
				self.hidden_lines.append(account)

	def on_editing_canceled (self, cell):
		"""editing have been canceled"""
		#TODO: get iter
		#model.set_value(iter, 4, False)
		pass

	def on_cell_edited (self, cell, row, new_text):
		"""When an iter is editer :
		if text has changed, rename the user"""
		model = self.tree.get_model()
		iter = model.get_iter_from_string(row)
		path = model.get_path(iter)
		acct_iter = model.get_iter((path[0]))
		account = model.get_value(acct_iter, 3)
		jid = model.get_value(iter, 3)
		old_text = self.contacts[account][jid][0].name
		if old_text != new_text:
			for u in self.contacts[account][jid]:
				u.name = new_text
			self.plugin.send('UPDUSER', account, (jid, new_text, \
				self.contacts[account][jid][0].groups))
		model.set_value(iter, 4, False)
		self.redraw_jid(jid, account)
		
	def on_browse(self, widget, account):
		"""When browse agent is selected :
		Call browse class"""
		if not self.plugin.windows[account].has_key('browser'):
			self.plugin.windows[account]['browser'] = \
				browseAgent_Window(self.plugin, account)

	def mkpixbufs(self):
		"""initialise pixbufs array"""
		iconstyle = self.plugin.config['iconstyle']
		if not iconstyle:
			iconstyle = 'sun'
		self.path = 'plugins/gtkgui/icons/' + iconstyle + '/'
		self.pixbufs = {}
		for state in ('online', 'chat', 'away', 'xa', 'dnd', 'invisible', \
			'offline', 'error', 'requested', 'message', 'opened', 'closed', \
			'not in list'):
			# try to open a pixfile with the correct method
			files = []
			files.append(self.path + state + '.gif')
			files.append(self.path + state + '.png')
			files.append(self.path + state + '.xpm')
			image = gtk.Image()
			image.show()
			self.pixbufs[state] = image
			for file in files:
				if not os.path.exists(file):
					continue
				if file.find('.gif') != -1:
					pix = gtk.gdk.PixbufAnimation(file)
					image.set_from_animation(pix)
				else:
					pix = gtk.gdk.pixbuf_new_from_file(file)
					image.set_from_pixbuf(pix)
				break
#		for state in ('online', 'away', 'xa', 'dnd', 'invisible', 'offline'):
#			self.xml.get_widget(state).set_image(self.pixbufs[state])

	def on_show_off(self, widget):
		"""when show offline option is changed :
		redraw the treeview"""
		self.plugin.config['showoffline'] = 1 - self.plugin.config['showoffline']
		self.plugin.send('CONFIG', None, ('GtkGui', self.plugin.config, 'GtkGui'))
		self.draw_roster()

	def iconCellDataFunc(self, column, renderer, model, iter, data=None):
		"""When a row is added, set properties for icon renderer"""
		if model.get_value(iter, 2) == 'account':
			renderer.set_property('cell-background', \
				self.plugin.config['accountbgcolor'])
			renderer.set_property('xalign', 0)
		elif model.get_value(iter, 2) == 'group':
			renderer.set_property('cell-background', \
				self.plugin.config['groupbgcolor'])
			renderer.set_property('xalign', 0.3)
		else:
			renderer.set_property('cell-background', \
				self.plugin.config['userbgcolor'])
			renderer.set_property('xalign', 1)
		renderer.set_property('width', 30)
	
	def nameCellDataFunc(self, column, renderer, model, iter, data=None):
		"""When a row is added, set properties for name renderer"""
		if model.get_value(iter, 2) == 'account':
			renderer.set_property('foreground', \
				self.plugin.config['accounttextcolor'])
			renderer.set_property('cell-background', \
				self.plugin.config['accountbgcolor'])
			renderer.set_property('font', self.plugin.config['accountfont'])
			renderer.set_property('xpad', 0)
		elif model.get_value(iter, 2) == 'group':
			renderer.set_property('foreground', \
				self.plugin.config['grouptextcolor'])
			renderer.set_property('cell-background', \
				self.plugin.config['groupbgcolor'])
			renderer.set_property('font', self.plugin.config['groupfont'])
			renderer.set_property('xpad', 8)
		else:
			renderer.set_property('foreground', \
				self.plugin.config['usertextcolor'])
			renderer.set_property('cell-background', \
				self.plugin.config['userbgcolor'])
			renderer.set_property('font', self.plugin.config['userfont'])
			renderer.set_property('xpad', 16)

	def compareIters(self, model, iter1, iter2, data = None):
		"""Compare two iters to sort them"""
		name1 = model.get_value(iter1, 1)
		name2 = model.get_value(iter2, 1)
		if not name1 or not name2:
			return 0
		type = model.get_value(iter1, 2)
		if type == 'group':
			if name1 == 'Agents':
				return 1
			if name2 == 'Agents':
				return -1
		if name1.lower() < name2.lower():
			return -1
		if name2.lower < name1.lower():
			return 1
		return 0

	def drag_data_get_data(self, treeview, context, selection, target_id, etime):
		treeselection = treeview.get_selection()
		model, iter = treeselection.get_selected()
		path = model.get_path(iter)
		data = ""
		if len(path) == 3:
			data = model.get_value(iter, 3)
		selection.set(selection.target, 8, data)

	def drag_data_received_data(self, treeview, context, x, y, selection, info,
		etime):
		model = treeview.get_model()
		data = selection.data
		if not data:
			return
		drop_info = treeview.get_dest_row_at_pos(x, y)
		if not drop_info:
			return
		path_dest, position = drop_info
		if position == gtk.TREE_VIEW_DROP_BEFORE and len(path_dest) == 2\
			and path_dest[1] == 0: #droped before the first group
			return
		if position == gtk.TREE_VIEW_DROP_BEFORE and len(path_dest) == 2:
			#droped before a group : we drop it in the previous group
			path_dest = (path_dest[0], path_dest[1]-1)
		iter_dest = model.get_iter(path_dest)
		iter_source = treeview.get_selection().get_selected()[1]
		path_source = model.get_path(iter_source)
		if len(path_dest) == 1: #droped on an account
			return
		if path_dest[0] != path_source[0]: #droped in another account
			return
		grp_source = model.get_value(model.iter_parent(iter_source), 3)
		account = model.get_value(model.get_iter(path_dest[0]), 3)
		if len(path_dest) == 2:
			grp_dest = model.get_value(iter_dest, 3)
		elif len(path_dest) == 3:
			grp_dest = model.get_value(model.iter_parent(iter_dest), 3)
		if grp_source != grp_dest:
			return
		for u in self.contacts[account][data]:
			u.groups.remove(grp_source)
			u.groups.append(grp_dest)
		self.plugin.send('UPDUSER', account, (u.jid, u.name, u.groups))
		parent_i = model.iter_parent(iter_source)
		if model.iter_n_children(parent_i) == 1: #this was the only child
			model.remove(parent_i)
		self.add_user_to_roster(data, account)
		if context.action == gtk.gdk.ACTION_MOVE:
			context.finish(True, True, etime)
		return

	def on_unrealize(self, widget, data=None):
		if self.plugin.config.has_key('saveposition'):
			if self.plugin.config['saveposition']:
				self.plugin.config['x-position'], self.plugin.config['y-position']=\
					widget.get_position()
				self.plugin.config['width'], self.plugin.config['height'] = \
					widget.get_size()

	def __init__(self, plugin):
		# FIXME : handle no file ...
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'Gajim', APP)
		self.tree = self.xml.get_widget('treeview')
		self.plugin = plugin
		window = self.xml.get_widget('Gajim')
		window.hide()
		if self.plugin.config.has_key('saveposition'):
			if self.plugin.config['saveposition']:
				if self.plugin.config.has_key('x-position') and \
					self.plugin.config.has_key('y-position'):
					window.move(self.plugin.config['x-position'], \
						self.plugin.config['y-position'])
				if self.plugin.config.has_key('width') and \
					self.plugin.config.has_key('height'):
					window.resize(self.plugin.config['width'], \
						self.plugin.config['height'])
		window.show_all()
		self.groups = {}
		self.contacts = {}
		for a in self.plugin.accounts.keys():
			self.contacts[a] = {}
			self.groups[a] = {}
		#(icon, name, type, jid, editable)
		model = gtk.TreeStore(gtk.Image, str, str, str, \
			gobject.TYPE_BOOLEAN)
		model.set_sort_func(1, self.compareIters)
		model.set_sort_column_id(1, gtk.SORT_ASCENDING)
		self.tree.set_model(model)
		self.mkpixbufs()

		liststore = gtk.ListStore(gobject.TYPE_STRING, gtk.Image)
		self.cb = gtk.ComboBox()
		self.xml.get_widget('vbox1').pack_end(self.cb, False)
		cell = ImageCellRenderer()
		self.cb.pack_start(cell, False)
		self.cb.add_attribute(cell, 'image', 1)
		cell = gtk.CellRendererText()
		self.cb.pack_start(cell, True)
		self.cb.add_attribute(cell, 'text', 0)
		for status in ['online', 'away', 'xa', 'dnd', 'invisible', 'offline']:
			iter = liststore.append([status, self.pixbufs[status]])
		self.cb.show_all()
		self.cb.set_model(liststore)
		self.cb.set_active(5)

		showOffline = self.plugin.config['showoffline']
		self.xml.get_widget('show_offline').set_active(showOffline)

		#columns
		col = gtk.TreeViewColumn()
		self.tree.append_column(col)
		render_pixbuf = ImageCellRenderer()
		col.pack_start(render_pixbuf, expand = False)
		col.add_attribute(render_pixbuf, 'image', 0)
		col.set_cell_data_func(render_pixbuf, self.iconCellDataFunc, None)

		render_text = gtk.CellRendererText()
		render_text.connect('edited', self.on_cell_edited)
		#need gtk2.4
		#render_text.connect('editing-canceled', self.on_editing_canceled)
		col.pack_start(render_text, expand = True)
		col.add_attribute(render_text, 'text', 1)
		col.add_attribute(render_text, 'editable', 4)
		col.set_cell_data_func(render_text, self.nameCellDataFunc, None)
		
		col = gtk.TreeViewColumn()
		render_pixbuf = gtk.CellRendererPixbuf()
		col.pack_start(render_pixbuf, expand = False)
		self.tree.append_column(col)
		col.set_visible(FALSE)
		self.tree.set_expander_column(col)

		#signals
		TARGETS = [('MY_TREE_MODEL_ROW', gtk.TARGET_SAME_WIDGET, 0)]
		self.tree.enable_model_drag_source( gtk.gdk.BUTTON1_MASK, TARGETS,
			gtk.gdk.ACTION_DEFAULT| gtk.gdk.ACTION_MOVE)
		self.tree.enable_model_drag_dest(TARGETS, gtk.gdk.ACTION_DEFAULT)
		self.tree.connect("drag_data_get", self.drag_data_get_data)
		self.tree.connect("drag_data_received", self.drag_data_received_data)
		self.xml.signal_connect('gtk_main_quit', self.on_quit)
		self.xml.signal_connect('on_Gajim_unrealize', self.on_unrealize)
		self.xml.signal_connect('on_preferences_activate', self.on_prefs)
		self.xml.signal_connect('on_accounts_activate', self.on_accounts)
		self.xml.signal_connect('on_show_offline_activate', self.on_show_off)
		self.xml.signal_connect('on_about_activate', self.on_about)
		self.xml.signal_connect('on_quit_activate', self.on_quit)
		self.xml.signal_connect('on_treeview_event', self.on_treeview_event)
		self.xml.signal_connect('on_status_changed', self.on_status_changed)
		self.id_signal_cb = self.cb.connect('changed', self.on_cb_changed)
		self.xml.signal_connect('on_row_activated', self.on_row_activated)
		self.xml.signal_connect('on_row_expanded', self.on_row_expanded)
		self.xml.signal_connect('on_row_collapsed', self.on_row_collapsed)

		self.hidden_lines = string.split(self.plugin.config['hiddenlines'], '\t')
		self.draw_roster()

class systrayDummy:
	"""Class when we don't want icon in the systray"""
	def add_jid(self, jid, account):
		pass
	def remove_jid(self, jid, account):
		pass
	def set_status(self, status):
		pass
	def __init__(self):
		self.t = gtk.Button()
	

class systray:
	"""Class for icon in the systray"""
	def set_img(self):
		if len(self.jids) > 0:
			status = 'message'
		else:
			status = self.status
		image = self.plugin.roster.pixbufs[status]
		if image.get_storage_type() == gtk.IMAGE_ANIMATION:
			self.img_tray.set_from_animation(image.get_animation())
		elif image.get_storage_type() == gtk.IMAGE_PIXBUF:
			self.img_tray.set_from_pixbuf(image.get_pixbuf())

	def add_jid(self, jid, account):
		list = [account, jid]
		if not list in self.jids:
			self.jids.append(list)
			self.set_img()

	def remove_jid(self, jid, account):
		list = [account, jid]
		if list in self.jids:
			self.jids.remove(list)
			self.set_img()

	def set_status(self, status):
		self.status = status
		self.set_img()

	def set_cb(self, widget, status):
		statuss = ['online', 'away', 'xa', 'dnd', 'invisible', 'vide', 'offline']
		self.cb.set_active(statuss.index(status))

	def start_chat(self, widget, account, jid):
		if self.plugin.windows[account]['chats'].has_key(jid):
			self.plugin.windows[account]['chats'][jid].window.present()
		elif self.plugin.roster.contacts[account].has_key(jid):
			self.plugin.windows[account]['chats'][jid] = \
				message_Window(self.plugin.roster.contacts[account][jid][0], \
				self.plugin, account)

	def mk_menu(self, event):
		menu = gtk.Menu()
		item = gtk.TearoffMenuItem()
		menu.append(item)
		
		item = gtk.MenuItem(_("Status"))
		menu.append(item)
		menu_sub = gtk.Menu()
		item.set_submenu(menu_sub)
		item = gtk.MenuItem(_("Online"))
		menu_sub.append(item)
		item.connect("activate", self.set_cb, 'online')
		item = gtk.MenuItem(_("Away"))
		menu_sub.append(item)
		item.connect("activate", self.set_cb, 'away')
		item = gtk.MenuItem(_("NA"))
		menu_sub.append(item)
		item.connect("activate", self.set_cb, 'xa')
		item = gtk.MenuItem(_("DND"))
		menu_sub.append(item)
		item.connect("activate", self.set_cb, 'dnd')
		item = gtk.MenuItem(_("Invisible"))
		menu_sub.append(item)
		item.connect("activate", self.set_cb, 'invisible')
		item = gtk.MenuItem()
		menu_sub.append(item)
		item = gtk.MenuItem(_("Offline"))
		menu_sub.append(item)
		item.connect("activate", self.set_cb, 'offline')
		
		item = gtk.MenuItem()
		menu.append(item)

		item = gtk.MenuItem(_("Chat with"))
		menu.append(item)
		menu_account = gtk.Menu()
		item.set_submenu(menu_account)
		for account in self.plugin.accounts.keys():
			item = gtk.MenuItem(account)
			menu_account.append(item)
			menu_group = gtk.Menu()
			item.set_submenu(menu_group)
			for group in self.plugin.roster.groups[account].keys():
				if group == 'Agents':
					continue
				item = gtk.MenuItem(group)
				menu_group.append(item)
				menu_user = gtk.Menu()
				item.set_submenu(menu_user)
				for users in self.plugin.roster.contacts[account].values():
					user = users[0]
					if group in user.groups and user.show != 'offline' and \
						user.show != 'error':
						item = gtk.MenuItem(string.replace(user.name, '_', '__'))
						menu_user.append(item)
						item.connect("activate", self.start_chat, account, user.jid)

		item = gtk.MenuItem()
		menu.append(item)

		item = gtk.MenuItem(_("Quit"))
		menu.append(item)
		item.connect("activate", self.plugin.roster.on_quit)
		
		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()
		menu.reposition()

	def on_clicked(self, widget, event):
		if event.type == gtk.gdk._2BUTTON_PRESS and event.button == 1:
			if len(self.jids) == 0:
				win = self.plugin.roster.xml.get_widget('Gajim')
				if self.iconified:
					win.deiconify()
				else:
					win.iconify()
			else:
				account = self.jids[0][0]
				jid = self.jids[0][1]
				if self.plugin.windows[account]['gc'].has_key(jid):
					self.plugin.windows[account]['gc'][jid].window.present()
				if self.plugin.windows[account]['chats'].has_key(jid):
					self.plugin.windows[account]['chats'][jid].window.present()
				else:
					self.plugin.windows[account]['chats'][jid] = message_Window(\
						self.plugin.roster.contacts[account][jid][0], self.plugin, \
						account)
		if event.button == 3:
			self.mk_menu(event)

	def state_changed(self, widget, event):
		if event.new_window_state & gtk.gdk.WINDOW_STATE_ICONIFIED:
			self.iconified = 1
		else:
			self.iconified = 0

	def __init__(self, plugin):
		self.plugin = plugin
		self.jids = []
		self.iconified = 0
		win = self.plugin.roster.xml.get_widget('Gajim')
		win.connect("window-state-event", self.state_changed)
		self.t = trayicon.TrayIcon("Gajim")
		eb = gtk.EventBox()
		eb.connect("button-press-event", self.on_clicked)
		self.tip = gtk.Tooltips()
		self.tip.set_tip(self.t, 'Gajim')
		self.img_tray = gtk.Image()
		eb.add(self.img_tray)
		self.t.add(eb)
		self.t.show_all()
		self.status = 'offline'
		self.set_img()

	
class plugin:
	"""Class called by the core in a new thread"""

	class accounts:
		"""Class where are stored the accounts and users in them"""
		def __init__(self):
			self.__accounts = {}

		def add_account(self, account, users=()):
			#users must be like (user1, user2)
			self.__accounts[account] = users

		def add_user_to_account(self, account, user):
			if self.__accounts.has_key(account):
				self.__accounts[account].append(user)
			else :
				return 1

		def get_accounts(self):
			return self.__accounts.keys();

		def get_users(self, account):
			if self.__accounts.has_key(account):
				return self.__accounts[account]
			else :
				return None

		def which_account(self, user):
			for a in self.__accounts.keys():
				if user in self.__accounts[a]:
					return a
			return None

	def send(self, event, account, data):
		self.queueOUT.put((event, account, data))

	def wait(self, what):
		"""Wait for a message from Core"""
		#TODO: timeout
		temp_q = Queue.Queue(50)
		while 1:
			if not self.queueIN.empty():
				ev = self.queueIN.get()
				if ev[0] == what and ev[2][0] == 'GtkGui':
					#Restore messages
					while not temp_q.empty():
						ev2 = temp_q.get()
						self.queueIN.put(ev2)
					return ev[2][1]
				else:
					#Save messages
					temp_q.put(ev)

	def handle_event_roster(self, account, data):
		#('ROSTER', account, (state, array))
		statuss = ['offline', 'online', 'away', 'xa', 'dnd', 'invisible']
		self.roster.on_status_changed(account, statuss[data[0]])
		self.roster.mklists(data[1], account)
		self.roster.draw_roster()
	
	def handle_event_warning(self, unused, msg):
		warning_Window(msg)
	
	def handle_event_status(self, account, status):
		#('STATUS', account, status)
		self.roster.on_status_changed(account, status)
	
	def handle_event_notify(self, account, array):
		#('NOTIFY', account, (jid, status, message, resource, priority, keyID, 
		# role, affiliation, real_jid, reason, actor, statusCode))
		jid = string.split(array[0], '/')[0]
		keyID = array[5]
		resource = array[3]
		if not resource:
			resource = ''
		priority = array[4]
		if string.find(jid, "@") <= 0:
			#It must be an agent
			ji = string.replace(jid, '@', '')
		else:
			ji = jid
		#Update user
		if self.roster.contacts[account].has_key(ji):
			luser = self.roster.contacts[account][ji]
			user1 = None
			resources = []
			for u in luser:
				resources.append(u.resource)
				if u.resource == resource:
					user1 = u
					break
			if not user1:
				user1 = self.roster.contacts[account][ji][0]
				if (resources != [''] and (len(luser) != 1 or 
					luser[0].show != 'offline')) and not string.find(jid, "@") <= 0:
					user1 = user(user1.jid, user1.name, user1.groups, \
						user1.show, user1.status, user1.sub, user1.resource, \
						user1.priority, user1.keyID)
					luser.append(user1)
				user1.resource = resource
			user1.show = array[1]
			user1.status = array[2]
			user1.priority = priority
			user1.keyID = keyID
		if string.find(jid, "@") <= 0:
			#It must be an agent
			if self.roster.contacts[account].has_key(ji):
				#Update existing iter
				self.roster.redraw_jid(ji, account)
		elif self.roster.contacts[account].has_key(ji):
			#It isn't an agent
			self.roster.chg_user_status(user1, array[1], array[2], account)
		elif self.windows[account]['gc'].has_key(ji):
			#it is a groupchat presence
			self.windows[account]['gc'][ji].chg_user_status(resource, array[1],\
				array[2], array[6], array[7], array[8], array[9], array[10], \
				array[11], account)

	def handle_event_msg(self, account, array):
		#('MSG', account, (user, msg, time))
		jid = string.split(array[0], '/')[0]
		if string.find(jid, "@") <= 0:
			jid = string.replace(jid, '@', '')
		self.roster.on_message(jid, array[1], array[2], account)
		
	def handle_event_msgerror(self, account, array):
		#('MSGERROR', account, (user, error_code, error_msg, msg, time))
		jid = string.split(array[0], '/')[0]
		if string.find(jid, "@") <= 0:
			jid = string.replace(jid, '@', '')
		self.roster.on_message(jid, _("error while sending") + " \"%s\" ( %s )"%\
			(array[3], array[2]), array[4], account)
		
	def handle_event_subscribe(self, account, array):
		#('SUBSCRIBE', account, (jid, text))
		authorize_Window(self, array[0], array[1], account)

	def handle_event_subscribed(self, account, array):
		#('SUBSCRIBED', account, (jid, nom, resource))
		jid = array[0]
		if self.roster.contacts[account].has_key(jid):
			u = self.roster.contacts[account][jid][0]
			u.name = array[1]
			u.resource = array[2]
			self.roster.redraw_jid(u.jid, account)
		else:
			user1 = user(jid, jid, ['general'], 'online', \
				'online', 'to', array[2], 0, '')
			self.roster.contacts[account][jid] = [user1]
			self.roster.add_user_to_roster(jid, account)
		warning_Window(_("You are now authorized by %s") % jid)

	def handle_event_unsubscribed(self, account, jid):
		#TODO: change icon
		warning_Window(_("You are now unsubscribed by %s") % jid)

	def handle_event_agents(self, account, agents):
		#('AGENTS', account, agents)
		if self.windows[account].has_key('browser'):
			self.windows[account]['browser'].agents(agents)

	def handle_event_agent_info(self, account, array):
		#('AGENT_INFO', account, (agent, identities, features, items))
		if self.windows[account].has_key('browser'):
			self.windows[account]['browser'].agent_info(array[0], array[1], \
				array[2], array[3])

	def handle_event_reg_agent_info(self, account, array):
		#('REG_AGENTS_INFO', account, (agent, infos))
		if not array[1].has_key('instructions'):
			warning_Window(_("error contacting %s") % array[0])
		else:
			agentRegistration_Window(array[0], array[1], self, account)

	def handle_event_acc_ok(self, account, array):
		#('ACC_OK', account, (hostname, login, pasword, name, ressource, prio,
		#use_proxy, proxyhost, proxyport))
		if self.windows['accountPreference']:
			self.windows['accountPreference'].destroy()
		name = array[3]
		self.accounts[array[3]] = {'name': array[1], \
					'hostname': array[0],\
					'password': array[2],\
					'ressource': array[4],\
					'priority': array[5],\
					'use_proxy': array[6],\
					'proxyhost': array[7], \
					'proxyport': array[8]}
		self.send('CONFIG', None, ('accounts', self.accounts, 'GtkGui'))
		self.windows[name] = {'infos': {}, 'chats': {}, 'gc': {}}
		self.queues[name] = {}
		self.connected[name] = 0
		self.roster.groups[name] = {}
		self.roster.contacts[name] = {}
		self.sleeper_state[a] = 0
		if self.windows.has_key('accounts'):
			self.windows['accounts'].init_accounts()
		self.roster.draw_roster()

	def handle_event_quit(self, p1, p2):
		self.roster.on_quit(self)

	def handle_event_myvcard(self, account, array):
		nick = ''
		if array.has_key('NICKNAME'):
			nick = array['NICKNAME']
		if nick == '':
			nick = self.accounts[account]['name']
		self.nicks[account] = nick

	def handle_event_vcard(self, account, array):
		if self.windows[account]['infos'].has_key(array['jid']):
			self.windows[account]['infos'][array['jid']].set_values(array)

	def handle_event_log_nb_line(self, account, array):
		#('LOG_NB_LINE', account, (jid, nb_line))
		if self.windows['logs'].has_key(array[0]):
			self.windows['logs'][array[0]].set_nb_line(array[1])
			begin = 0
			if array[1] > 50:
				begin = array[1] - 50
			self.send('LOG_GET_RANGE', None, (array[0], begin, array[1]))

	def handle_event_log_line(self, account, array):
		#('LOG_LINE', account, (jid, num_line, date, type, data))
		# if type = 'recv' or 'sent' data = [msg]
		# else type = jid and data = [status, away_msg]
		if self.windows['logs'].has_key(array[0]):
			self.windows['logs'][array[0]].new_line(array[1:])

	def handle_event_gc_msg(self, account, array):
		#('GC_MSG', account, (jid, msg, time))
		jids = string.split(array[0], '/')
		jid = jids[0]
		if not self.windows[account]['gc'].has_key(jid):
			return
		if len(jids) == 1:
			#message from server
			self.windows[account]['gc'][jid].print_conversation(array[1], \
				tim = array[2])
		else:
			#message from someone
			self.windows[account]['gc'][jid].print_conversation(array[1], \
				jids[1], array[2])
			if not self.windows[account]['gc'][jid].window.\
				get_property('is-active'):
				self.systray.add_jid(jid, account)

	def handle_event_bad_passphrase(self, account, array):
		pass

	def handle_event_gpg_secrete_keys(self, account, keys):
		keys['None'] = 'None'
		if self.windows.has_key('gpg_keys'):
			self.windows['gpg_keys'].fill_tree(keys)

	def read_queue(self):
		"""Read queue from the core and execute commands from it"""
		while self.queueIN.empty() == 0:
			ev = self.queueIN.get()
			if ev[0] == 'ROSTER':
				self.handle_event_roster(ev[1], ev[2])
			elif ev[0] == 'WARNING':
				self.handle_event_warning(ev[1], ev[2])
			elif ev[0] == 'STATUS':
				self.handle_event_status(ev[1], ev[2])
			elif ev[0] == 'NOTIFY':
				self.handle_event_notify(ev[1], ev[2])
			elif ev[0] == 'MSG':
				self.handle_event_msg(ev[1], ev[2])
			elif ev[0] == 'MSGERROR':
				self.handle_event_msgerror(ev[1], ev[2])
			elif ev[0] == 'SUBSCRIBE':
				self.handle_event_subscribe(ev[1], ev[2])
			elif ev[0] == 'SUBSCRIBED':
				self.handle_event_subscribed(ev[1], ev[2])
			elif ev[0] == 'UNSUBSCRIBED':
				self.handle_event_unsubscribed(ev[1], ev[2])
			elif ev[0] == 'AGENTS':
				self.handle_event_agents(ev[1], ev[2])
			elif ev[0] == 'AGENT_INFO':
				self.handle_event_agent_info(ev[1], ev[2])
			elif ev[0] == 'REG_AGENT_INFO':
				self.handle_event_reg_agent_info(ev[1], ev[2])
			elif ev[0] == 'ACC_OK':
				self.handle_event_acc_ok(ev[1], ev[2])
			elif ev[0] == 'QUIT':
				self.handle_event_quit(ev[1], ev[2])
			elif ev[0] == 'MYVCARD':
				self.handle_event_myvcard(ev[1], ev[2])
			elif ev[0] == 'VCARD':
				self.handle_event_vcard(ev[1], ev[2])
			elif ev[0] == 'LOG_NB_LINE':
				self.handle_event_log_nb_line(ev[1], ev[2])
			elif ev[0] == 'LOG_LINE':
				self.handle_event_log_line(ev[1], ev[2])
			elif ev[0] == 'GC_MSG':
				self.handle_event_gc_msg(ev[1], ev[2])
			elif ev[0] == 'BAD_PASSPHRASE':
				self.handle_event_bad_passphrase(ev[1], ev[2])
			elif ev[0] == 'GPG_SECRETE_KEYS':
				self.handle_event_gpg_secrete_keys(ev[1], ev[2])
		return 1
	
	def read_sleepy(self):	
		"""Check if we are idle"""
		if not self.sleeper.poll():
			return 1
		state = self.sleeper.getState()
		for account in self.accounts.keys():
			if not self.sleeper_state[account]:
				continue
			if state == common.sleepy.STATE_AWAKE and \
				self.sleeper_state[account] > 1:
				#we go online
				self.send('STATUS', account, ('online', 'Online'))
				self.sleeper_state[account] = 1
			elif state == common.sleepy.STATE_AWAY and \
				self.sleeper_state[account] == 1 and \
				self.config['autoaway']:
				#we go away
				self.send('STATUS', account, ('away', 'auto away (idle)'))
				self.sleeper_state[account] = 2
			elif state == common.sleepy.STATE_XAWAY and (\
				self.sleeper_state[account] == 2 or \
				self.sleeper_state[account] == 1) and \
				self.config['autoxa']:
				#we go extended away
				self.send('STATUS', account, ('xa', 'auto away (idle)'))
				self.sleeper_state[account] = 3
		return 1

	def __init__(self, quIN, quOUT):
		gtk.gdk.threads_init()
		self.queueIN = quIN
		self.queueOUT = quOUT
		self.send('REG_MESSAGE', 'gtkgui', ['ROSTER', 'WARNING', 'STATUS', \
			'NOTIFY', 'MSG', 'MSGERROR', 'SUBSCRIBED', 'UNSUBSCRIBED', \
			'SUBSCRIBE', 'AGENTS', 'AGENT_INFO', 'REG_AGENT_INFO', 'QUIT', \
			'ACC_OK', 'CONFIG', 'MYVCARD', 'VCARD', 'LOG_NB_LINE', 'LOG_LINE', \
			'VISUAL', 'GC_MSG', 'BAD_PASSPHRASE', 'GPG_SECRETE_KEYS'])
		self.send('ASK_CONFIG', None, ('GtkGui', 'GtkGui', {'autopopup':1,\
			'autopopupaway':1,\
			'showoffline':0,\
			'autoaway':1,\
			'autoawaytime':10,\
			'autoxa':1,\
			'autoxatime':20,\
			'last_msg':'',\
			'msg0_name':'Brb',\
			'msg0':'Back in some minutes.',\
			'msg1_name':'Eating',\
			'msg1':'I\'m eating, so leave me a message.',\
			'msg2_name':'Film',\
			'msg2':'I\'m watching a film.',\
			'trayicon':1,\
			'iconstyle':'sun',\
			'inmsgcolor':'#ff0000',\
			'outmsgcolor': '#0000ff',\
			'statusmsgcolor':'#1eaa1e',\
			'hiddenlines':'',\
			'accounttextcolor': '#ff0000',\
			'accountbgcolor': '#9fdfff',\
			'accountfont': 'Sans Bold 10',\
			'grouptextcolor': '#0000ff',\
			'groupbgcolor': '#ffffff',\
			'groupfont': 'Sans Italic 10',\
			'usertextcolor': '#000000',\
			'userbgcolor': '#ffffff',\
			'userfont': 'Sans 10',\
			'saveposition': 1,\
			'x-position': 0,\
			'y-position': 0,\
			'width': 150,\
			'height': 400}))
		self.config = self.wait('CONFIG')
		self.send('ASK_CONFIG', None, ('GtkGui', 'accounts'))
		self.accounts = self.wait('CONFIG')
		self.windows = {'logs':{}}
		self.queues = {}
		self.connected = {}
		self.nicks = {}
		self.sleeper_state = {} #whether we pass auto away / xa or not
		for a in self.accounts.keys():
			self.windows[a] = {'infos': {}, 'chats': {}, 'gc': {}}
			self.queues[a] = {}
			self.connected[a] = 0
			self.nicks[a] = self.accounts[a]['name']
			self.sleeper_state[a] = 0	#0:don't use sleeper for this account
												#1:online and use sleeper
												#2:autoaway and use sleeper
												#3:autoxa and use sleeper
			self.send('ASK_ROSTER', a, self.queueIN)
		#in pygtk2.4
		iconstyle = self.config['iconstyle']
		if not iconstyle:
			iconstyle = 'sun'
		path = 'plugins/gtkgui/icons/' + iconstyle + '/'
		files = [path + 'online.gif', path + 'online.png', path + 'online.xpm']
		pix = None
		for file in files:
			if os.path.exists(file):
				pix = gtk.gdk.pixbuf_new_from_file(file)
				break
		if pix:
			gtk.window_set_default_icon(pix)
		self.roster = roster_Window(self)
		gtk.timeout_add(100, self.read_queue)
		gtk.timeout_add(100, self.read_sleepy)
		#auto connect at startup
		for a in self.accounts.keys():
			if self.accounts[a].has_key('autoconnect'):
				if self.accounts[a]['autoconnect']:
					self.roster.send_status(a, 'online', 'Online')
		self.sleeper = common.sleepy.Sleepy( \
			self.config['autoawaytime']*60, \
			self.config['autoxatime']*60)
		if self.config['trayicon']:
			try:
				global trayicon
				import trayicon
			except:
				self.config['trayicon'] = 0
				self.send('CONFIG', None, ('GtkGui', self.config, 'GtkGui'))
				self.systray = systrayDummy()
			else:
				self.systray = systray(self)
		else:
			self.systray = systrayDummy()
		gtk.gdk.threads_enter()
		gtk.main()
		gtk.gdk.threads_leave()

print _("plugin gtkgui loaded")
