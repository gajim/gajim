##	plugins/gtkgui.py
##
## Gajim Team:
## 	- Yann Le Boulanger <asterix@lagaule.org>
## 	- Vincent Hanquez <tab@snarc.org>
##		- Nikos Kouremenos <kourem@gmail.com>
##		- Alex Podaras <bigpod@gmail.com>
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
		print "unable to connect to localhost on port ", port
	else:
		evp = pickle.dumps(('EXEC_PLUGIN', '', 'gtkgui'))
		sock.send('<'+evp+'>')
		sock.close()
	sys.exit()

import pygtk
pygtk.require('2.0')
import gtk
import gtk.glade
import pango
import gobject
import os
import time
import sys
import Queue
import common.sleepy

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
			tree.queue_draw_area(cell_area.x, cell_area.y, cell_area.width, \
				cell_area.height)

	def animation_timeout(self, tree, image):
		if image.get_storage_type() == gtk.IMAGE_ANIMATION:
			self.redraw = 0
			image.get_data('iter').advance()
			model = tree.get_model()
			model.foreach(self.func, (image, tree))
			if self.redraw:
				gobject.timeout_add(image.get_data('iter').get_delay_time(), \
					self.animation_timeout, tree, image)
			else:
				image.set_data('iter', None)
				
	def on_render(self, window, widget, background_area,cell_area, \
		expose_area, flags):
		if not self.image:
			return
		pix_rect = gtk.gdk.Rectangle()
		pix_rect.x, pix_rect.y, pix_rect.width, pix_rect.height = \
			self.on_get_size(widget, cell_area)

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
				gobject.timeout_add(self.image.get_data('iter').get_delay_time(), \
					self.animation_timeout, widget, self.image)

			pix = self.image.get_data('iter').get_pixbuf()
		elif self.image.get_storage_type() == gtk.IMAGE_PIXBUF:
			pix = self.image.get_pixbuf()
		else:
			return
		window.draw_pixbuf(widget.style.black_gc, pix, \
			draw_rect.x-pix_rect.x, draw_rect.y-pix_rect.y, draw_rect.x, \
			draw_rect.y+2, draw_rect.width, draw_rect.height, \
			gtk.gdk.RGB_DITHER_NONE, 0, 0)

	def on_get_size(self, widget, cell_area):
		if not self.image:
			return 0, 0, 0, 0
		if self.image.get_storage_type() == gtk.IMAGE_ANIMATION:
			animation = self.image.get_animation()
			pix = animation.get_iter().get_pixbuf()
		elif self.image.get_storage_type() == gtk.IMAGE_PIXBUF:
			pix = self.image.get_pixbuf()
		else:
			return 0, 0, 0, 0
		pixbuf_width  = pix.get_width()
		pixbuf_height = pix.get_height()
		calc_width  = self.get_property("xpad") * 2 + pixbuf_width
		calc_height = self.get_property("ypad") * 2 + pixbuf_height
		x_offset = 0
		y_offset = 0
		if cell_area and pixbuf_width > 0 and pixbuf_height > 0:
			x_offset = self.get_property("xalign") * (cell_area.width - \
				calc_width -  self.get_property("xpad"))
			y_offset = self.get_property("yalign") * (cell_area.height - \
				calc_height -  self.get_property("ypad"))
		return x_offset, y_offset, calc_width, calc_height

gobject.type_register(ImageCellRenderer)

class User:
	"""Information concerning each users"""
	def __init__(self, *args):
		if len(args) == 0:
			self.jid = ''
			self.name = ''
			self.groups = []
			self.show = ''
			self.status = ''
			self.sub = ''
			self.ask = ''
			self.resource = ''
			self.priority = 1
			self.keyID = ''
		elif len(args) == 10:
			self.jid = args[0]
			self.name = args[1]
			self.groups = args[2]
			self.show = args[3]
			self.status = args[4]
			self.sub = args[5]
			self.ask = args[6]
			self.resource = args[7]
			self.priority = args[8]
			self.keyID = args[9]
		else: raise TypeError, _('bad arguments')

from tabbed_chat_window import *
from groupchat_window import *
from history_window import *
from roster_window import *
from systray import *
from dialogs import *
from config import *

from common import i18n

_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain(APP, i18n.DIR)
gtk.glade.textdomain(APP)

def usage():
	#TODO: use i18n
	print 'usage :', sys.argv[0], ' [OPTION]'
	print '  -p\tport on which the sock plugin listen'
	print '  -h, --help\tdisplay this help and exit'


GTKGUI_GLADE='plugins/gtkgui/gtkgui.glade'


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

	def launch_browser_mailer(self, kind, url):
		#kind = 'url' or 'mail'
		if self.config['openwith'] == 'gnome-open':
			app = 'gnome-open'
			args = ['gnome-open']
			args.append(url)
		elif self.config['openwith'] == 'kfmclient exec':
			app = 'kfmclient'
			args = ['kfmclient', 'exec']
		elif self.config['openwith'] == 'custom':
			if kind == 'url':
				conf = self.config['custombrowser']
			if kind == 'mail':
				conf = self.config['custommailapp']
			if conf == '': # if no app is configured
				return
			args = conf.split()
			app = args[0]
		args.append(url)
		if os.name == 'posix':
			os.spawnvp(os.P_NOWAIT, app, args)
		else:
			os.spawnv(os.P_NOWAIT, app, args)

	def play_timeout(self, pid):
		pidp, r = os.waitpid(pid, os.WNOHANG)
		return 0
			

	def play_sound(self, event):
		if not os.name == 'posix':
			return
		if not self.config[event]:
			return
		file = self.config[event + '_file']
		if not os.path.exists(file):
			return
		pid = os.fork()
		if pid == 0:
			argv = self.config['soundplayer'].split()
			argv.append(file)
			try: 
				os.execvp(argv[0], argv)
			except:
				print _("error while running %s :") % ' '.join(argv), \
					sys.exc_info()[1]
				os._exit(1)
		pidp, r = os.waitpid(pid, os.WNOHANG)
		if pidp == 0:
			gobject.timeout_add(10000, self.play_timeout, pid)

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
		Warning_dialog(msg)
	
	def handle_event_status(self, account, status):
		#('STATUS', account, status)
		self.roster.on_status_changed(account, status)
	
	def handle_event_notify(self, account, array):
		#('NOTIFY', account, (jid, status, message, resource, priority, keyID, 
		# role, affiliation, real_jid, reason, actor, statusCode))
		statuss = ['offline', 'error', 'online', 'chat', 'away', 'xa', 'dnd', 'invisible']
		old_show = 0
		jid = array[0].split('/')[0]
		keyID = array[5]
		resource = array[3]
		if not resource:
			resource = ''
		priority = array[4]
		if jid.find("@") <= 0:
			#It must be an agent
			ji = jid.replace('@', '')
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
			if user1:
				old_show = statuss.index(user1.show)
			else:
				user1 = self.roster.contacts[account][ji][0]
				if user1.show in statuss:
					old_show = statuss.index(user1.show)
				if (resources != [''] and (len(luser) != 1 or 
					luser[0].show != 'offline')) and not jid.find("@") <= 0:
					old_show = 0
					user1 = User(user1.jid, user1.name, user1.groups, user1.show, \
					user1.status, user1.sub, user1.ask, user1.resource, \
						user1.priority, user1.keyID)
					luser.append(user1)
				user1.resource = resource
			user1.show = array[1]
			user1.status = array[2]
			user1.priority = priority
			user1.keyID = keyID
		if jid.find("@") <= 0:
			#It must be an agent
			if self.roster.contacts[account].has_key(ji):
				#Update existing iter
				self.roster.redraw_jid(ji, account)
		elif self.roster.contacts[account].has_key(ji):
			#It isn't an agent
			self.roster.chg_user_status(user1, array[1], array[2], account)
			#play sound
			if old_show < 2 and statuss.index(user1.show) > 1 and \
				self.config['sound_contact_connected']:
				self.play_sound('sound_contact_connected')
			elif old_show > 1 and statuss.index(user1.show) < 2 and \
				self.config['sound_contact_disconnected']:
				self.play_sound('sound_contact_disconnected')
				
		elif self.windows[account]['gc'].has_key(ji):
			#it is a groupchat presence
			self.windows[account]['gc'][ji].chg_user_status(ji, resource, \
				array[1], array[2], array[6], array[7], array[8], array[9], \
				array[10], array[11], account)

	def handle_event_msg(self, account, array):
		#('MSG', account, (user, msg, time))
		jid = array[0].split('/')[0]
		if jid.find("@") <= 0:
			jid = jid.replace('@', '')
		if self.config['ignore_unknown_contacts'] and \
			not self.roster.contacts[account].has_key(jid):
			return
		first = 0
		if not self.windows[account]['chats'].has_key(jid) and \
			not self.queues[account].has_key(jid):
			first = 1
		self.roster.on_message(jid, array[1], array[2], account)
		if self.config['sound_first_message_received'] and first:
			self.play_sound('sound_first_message_received')
		if self.config['sound_next_message_received'] and not first:
			self.play_sound('sound_next_message_received')
		
	def handle_event_msgerror(self, account, array):
		#('MSGERROR', account, (user, error_code, error_msg, msg, time))
		jid = array[0].split('/')[0]
		if jid.find("@") <= 0:
			jid = jid.replace('@', '')
		self.roster.on_message(jid, _("error while sending") + " \"%s\" ( %s )"%\
			(array[3], array[2]), array[4], account)
		
	def handle_event_msgsent(self, account, array):
		#('MSG', account, (jid, msg, keyID))
		self.play_sound('sound_message_sent')
		
	def handle_event_subscribe(self, account, array):
		#('SUBSCRIBE', account, (jid, text))
		subscription_request_window(self, array[0], array[1], account)

	def handle_event_subscribed(self, account, array):
		#('SUBSCRIBED', account, (jid, resource))
		jid = array[0]
		if self.roster.contacts[account].has_key(jid):
			u = self.roster.contacts[account][jid][0]
			u.resource = array[1]
			self.roster.remove_user(u, account)
			if 'not in the roster' in u.groups:
				u.groups.remove('not in the roster')
			if len(u.groups) == 0:
				u.groups = ['general']
			self.roster.add_user_to_roster(u.jid, account)
			self.send('UPDUSER', account, (u.jid, u.name, u.groups))
		else:
			user1 = User(jid, jid, ['general'], 'online', \
				'online', 'to', '', array[1], 0, '')
			self.roster.contacts[account][jid] = [user1]
			self.roster.add_user_to_roster(jid, account)
		Information_dialog(_("You are now authorized by %s") % jid)

	def handle_event_unsubscribed(self, account, jid):
		Information_dialog(_("You are now unsubscribed by %s") % jid)

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
			Error_dialog(_("error contacting %s") % array[0])
		else:
			agent_registration_window(array[0], array[1], self, account)

	def handle_event_acc_ok(self, account, array):
		#('ACC_OK', account, (hostname, login, pasword, name, resource, prio,
		#use_proxy, proxyhost, proxyport))
		name = array[3]
		if self.windows['account_modification_window']:
			self.windows['account_modification_window'].account_is_ok(array[1])
		else:
			self.accounts[name] = {'name': array[1], \
				'hostname': array[0],\
				'password': array[2],\
				'resource': array[4],\
				'priority': array[5],\
				'use_proxy': array[6],\
				'proxyhost': array[7], \
				'proxyport': array[8]}
			self.send('CONFIG', None, ('accounts', self.accounts, 'GtkGui'))
		self.windows[name] = {'infos': {}, 'chats': {}, 'gc': {}}
		self.queues[name] = {}
		self.connected[name] = 0
		self.nicks[name] = array[1]
		self.roster.groups[name] = {}
		self.roster.contacts[name] = {}
		self.sleeper_state[name] = 0
		if self.windows.has_key('accounts_window'):
			self.windows['accounts_window'].init_accounts()
		self.roster.draw_roster()

	def handle_event_quit(self, p1, p2):
		self.roster.on_quit()

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
		jids = array[0].split('/')
		jid = jids[0]
		if not self.windows[account]['gc'].has_key(jid):
			return
		if len(jids) == 1:
			#message from server
			self.windows[account]['gc'][jid].print_conversation(array[1], jid, \
				tim = array[2])
		else:
			#message from someone
			self.windows[account]['gc'][jid].print_conversation(array[1], jid, \
				jids[1], array[2])
			if not self.windows[account]['gc'][jid].window.\
				get_property('is-active'):
				self.systray.add_jid(jid, account)

	def handle_event_gc_subject(self, account, array):
		#('GC_SUBJECT', account, (jid, subject))
		jids = array[0].split('/')
		jid = jids[0]
		if not self.windows[account]['gc'].has_key(jid):
			return
		self.windows[account]['gc'][jid].set_subject(jid, array[1])
		if len(jids) > 1:
			self.windows[account]['gc'][jid].print_conversation(\
				'%s has set the subject to %s' % (jids[1], array[1]), jid)

	def handle_event_bad_passphrase(self, account, array):
		Warning_dialog(_("Your GPG passphrase is wrong, so you are connected without your GPG key."))

	def handle_event_gpg_secrete_keys(self, account, keys):
		keys['None'] = 'None'
		if self.windows.has_key('gpg_keys'):
			self.windows['gpg_keys'].fill_tree(keys)

	def handle_event_roster_info(self, account, array):
		#('ROSTER_INFO', account, (jid, name, sub, ask, groups))
		jid = array[0]
		if not self.roster.contacts[account].has_key(jid):
			return
		users = self.roster.contacts[account][jid]
		if not (array[2] or array[3]):
			self.roster.remove_user(users[0], account)
			del self.roster.contacts[account][jid]
			#TODO if it was the only one in its group, remove the group
			return
		for user in users:
			name = array[1]
			if name:
				user.name = name
			user.sub = array[2]
			user.ask = array[3]
			user.groups = array[4]
		self.roster.redraw_jid(jid, account)

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
			elif ev[0] == 'MSGSENT':
				self.handle_event_msgsent(ev[1], ev[2])
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
			elif ev[0] == 'GC_SUBJECT':
				self.handle_event_gc_subject(ev[1], ev[2])
			elif ev[0] == 'BAD_PASSPHRASE':
				self.handle_event_bad_passphrase(ev[1], ev[2])
			elif ev[0] == 'GPG_SECRETE_KEYS':
				self.handle_event_gpg_secrete_keys(ev[1], ev[2])
			elif ev[0] == 'ROSTER_INFO':
				self.handle_event_roster_info(ev[1], ev[2])
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

	def autoconnect(self):
		"""auto connect at startup"""
		for a in self.accounts.keys():
			if self.accounts[a].has_key('autoconnect'):
				if self.accounts[a]['autoconnect']:
					self.roster.send_status(a, 'online', 'Online', 1)
		return 0

	def show_systray(self):
		self.systray.show_icon()
		self.systray_visible = 1

	def hide_systray(self):
		self.systray.hide_icon()
		self.systray_visible = 0
	
	def image_is_ok(self, image):
		if not os.path.exists(image):
			return False
		img = gtk.Image()
		try:
			img.set_from_file(image)
		except:
			return True
		if img.get_storage_type() == gtk.IMAGE_PIXBUF:
			pix = img.get_pixbuf()
		else:
			return False
		if pix.get_width() > 24 or pix.get_height() > 24:
			return False
		return True
		
	def make_pattern(self):
		# regexp meta characters are:  . ^ $ * + ? { } [ ] \ | ( )
		# one escapes the metachars with \
		# \S matches anything but ' ' '\t' '\n' '\r' '\f' and '\v'
		# \s matches any whitespace character
		# \w any alphanumeric character
		# \W any non-alphanumeric character
		# \b means word boundary. This is a zero-width assertion that
		# 					matches only at the beginning or end of a word.
		# ^ matches at the beginning of lines
		#
		# * means 0 or more times
		# + means 1 or more times
		# ? means 0 or 1 time
		# | means or
		# [^*] anything but '*'   (inside [] you don't have to escape metachars)
		# [^\s*] anything but whitespaces and '*'
		# (?<!\S) is a one char lookbehind assertion and asks for any leading whitespace
		# and mathces beginning of lines so we have correct formatting detection
		# even if the the text is just '*something*'
		# basic_pattern is one string literal.
		# I've put spaces to make the regexp look better.
		links = r'\bhttp://\S+|' r'\bhttps://\S+|' r'\bnews://\S+|' r'\bftp://\S+|' r'\bed2k://\S+|' r'\bwww\.\S+|' r'\bftp\.\S+|'
		#2nd one: at_least_one_char@at_least_one_char.at_least_one_char
		mail = r'\bmailto:\S+|' r'\b\S+@\S+\.\S+|'

		#detects eg. *b* *bold* *bold bold* test *bold*
		#doesn't detect (it's a feature :P) * bold* *bold * * bold * test*bold*
		formatting = r'(?<!\S)\*[^\s*]([^*]*[^\s*])?\*|' r'(?<!\S)/[^\s*]([^/]*[^\s*])?/|' r'(?<!\S)_[^\s*]([^_]*[^\s*])?_'

		self.basic_pattern = links + mail + formatting


	def __init__(self, quIN, quOUT):
		gtk.gdk.threads_init()
		#(asterix) I don't have pygtk 2.6 for the moment, so I cannot test
#		gtk.about_dialog_set_email_hook(self.launch_browser_mailer, 'mail')
#		gtk.about_dialog_set_url_hook(self.launch_browser_mailer, 'url')
		self.queueIN = quIN
		self.queueOUT = quOUT
		self.send('REG_MESSAGE', 'gtkgui', ['ROSTER', 'WARNING', 'STATUS', \
			'NOTIFY', 'MSG', 'MSGERROR', 'SUBSCRIBED', 'UNSUBSCRIBED', \
			'SUBSCRIBE', 'AGENTS', 'AGENT_INFO', 'REG_AGENT_INFO', 'QUIT', \
			'ACC_OK', 'CONFIG', 'MYVCARD', 'VCARD', 'LOG_NB_LINE', 'LOG_LINE', \
			'VISUAL', 'GC_MSG', 'GC_SUBJECT', 'BAD_PASSPHRASE', \
			'GPG_SECRETE_KEYS', 'ROSTER_INFO', 'MSGSENT'])
		self.default_config = {'autopopup':1,\
			'autopopupaway':1,\
			'ignore_unknown_contacts':0,\
			'showoffline':0,\
			'autoaway':1,\
			'autoawaytime':10,\
			'autoxa':1,\
			'autoxatime':20,\
			'ask_online_status':0,\
			'ask_offline_status':0,\
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
			'mergeaccounts': 0,\
			'usetabbedchat': 1,\
			'print_time': 'always',\
			'useemoticons': 1,\
			'emoticons': ':-)\tplugins/gtkgui/emoticons/smile.png\t(@)\tplugins/gtkgui/emoticons/pussy.png\t8)\tplugins/gtkgui/emoticons/coolglasses.png\t:(\tplugins/gtkgui/emoticons/unhappy.png\t:)\tplugins/gtkgui/emoticons/smile.png\t(})\tplugins/gtkgui/emoticons/hugleft.png\t:$\tplugins/gtkgui/emoticons/blush.png\t(Y)\tplugins/gtkgui/emoticons/yes.png\t:-@\tplugins/gtkgui/emoticons/angry.png\t:-D\tplugins/gtkgui/emoticons/biggrin.png\t(U)\tplugins/gtkgui/emoticons/brheart.png\t(F)\tplugins/gtkgui/emoticons/flower.png\t:-[\tplugins/gtkgui/emoticons/bat.png\t:>\tplugins/gtkgui/emoticons/biggrin.png\t(T)\tplugins/gtkgui/emoticons/phone.png\t:-S\tplugins/gtkgui/emoticons/frowing.png\t:-P\tplugins/gtkgui/emoticons/tongue.png\t(H)\tplugins/gtkgui/emoticons/coolglasses.png\t(D)\tplugins/gtkgui/emoticons/drink.png\t:-O\tplugins/gtkgui/emoticons/oh.png\t(C)\tplugins/gtkgui/emoticons/coffee.png\t({)\tplugins/gtkgui/emoticons/hugright.png\t(*)\tplugins/gtkgui/emoticons/star.png\tB-)\tplugins/gtkgui/emoticons/coolglasses.png\t(Z)\tplugins/gtkgui/emoticons/boy.png\t(E)\tplugins/gtkgui/emoticons/mail.png\t(N)\tplugins/gtkgui/emoticons/no.png\t(P)\tplugins/gtkgui/emoticons/photo.png\t(K)\tplugins/gtkgui/emoticons/kiss.png\t(R)\tplugins/gtkgui/emoticons/rainbow.png\t:-|\tplugins/gtkgui/emoticons/stare.png\t;-)\tplugins/gtkgui/emoticons/wink.png\t;-(\tplugins/gtkgui/emoticons/cry.png\t(6)\tplugins/gtkgui/emoticons/devil.png\t(L)\tplugins/gtkgui/emoticons/heart.png\t(W)\tplugins/gtkgui/emoticons/brflower.png\t:|\tplugins/gtkgui/emoticons/stare.png\t:O\tplugins/gtkgui/emoticons/oh.png\t;)\tplugins/gtkgui/emoticons/wink.png\t;(\tplugins/gtkgui/emoticons/cry.png\t:S\tplugins/gtkgui/emoticons/frowing.png\t;\'-(\tplugins/gtkgui/emoticons/cry.png\t:-(\tplugins/gtkgui/emoticons/unhappy.png\t8-)\tplugins/gtkgui/emoticons/coolglasses.png\t(B)\tplugins/gtkgui/emoticons/beer.png\t:D\tplugins/gtkgui/emoticons/biggrin.png\t(8)\tplugins/gtkgui/emoticons/music.png\t:@\tplugins/gtkgui/emoticons/angry.png\tB)\tplugins/gtkgui/emoticons/coolglasses.png\t:-$\tplugins/gtkgui/emoticons/blush.png\t:\'(\tplugins/gtkgui/emoticons/cry.png\t:->\tplugins/gtkgui/emoticons/biggrin.png\t:[\tplugins/gtkgui/emoticons/bat.png\t(I)\tplugins/gtkgui/emoticons/lamp.png\t:P\tplugins/gtkgui/emoticons/tongue.png\t(%)\tplugins/gtkgui/emoticons/cuffs.png\t(S)\tplugins/gtkgui/emoticons/moon.png',\
			'soundplayer': 'play',\
			'sound_first_message_received': 1,\
			'sound_first_message_received_file': 'sounds/message1.wav',\
			'sound_next_message_received': 0,\
			'sound_next_message_received_file': 'sounds/message2.wav',\
			'sound_contact_connected': 1,\
			'sound_contact_connected_file': 'sounds/connected.wav',\
			'sound_contact_disconnected': 1,\
			'sound_contact_disconnected_file': 'sounds/disconnected.wav',\
			'sound_message_sent': 1,\
			'sound_message_sent_file': 'sounds/sent.wav',\
			'openwith': 'gnome-open',\
			'custombrowser' : 'firefox',\
			'custommailapp' : 'mozilla-thunderbird -compose',\
			'x-position': 0,\
			'y-position': 0,\
			'width': 150,\
			'height': 400}
		self.send('ASK_CONFIG', None, ('GtkGui', 'GtkGui', self.default_config))
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
		for fname in files:
			if os.path.exists(fname):
				pix = gtk.gdk.pixbuf_new_from_file(fname)
				break
		if pix:
			gtk.window_set_default_icon(pix)
		self.roster = roster_window(self)
		gobject.timeout_add(100, self.read_queue)
		gobject.timeout_add(100, self.read_sleepy)
		self.sleeper = common.sleepy.Sleepy( \
			self.config['autoawaytime']*60, \
			self.config['autoxatime']*60)
		self.systray_visible = 0
		try:
			import trayicon
		except:
			self.config['trayicon'] = 0
			self.send('CONFIG', None, ('GtkGui', self.config, 'GtkGui'))
			self.systray = systrayDummy()
		else:
			self.systray = systray(self)
		if self.config['trayicon']:
			self.show_systray()
			
		if self.config['useemoticons']:
			"""initialize emoticons dictionary"""
			self.emoticons = dict()
			split_line = self.config['emoticons'].split('\t')
			for i in range(0, len(split_line)/2):
				emot_file = split_line[2*i+1]
				if not self.image_is_ok(emot_file):
					continue
				pix = gtk.gdk.pixbuf_new_from_file(emot_file)
				self.emoticons[split_line[2*i]] = pix

		self.make_pattern()
		
		# at least one character in 3 parts (before @, after @, after .)
		self.sth_at_sth_dot_sth_re = sre.compile(r'\S+@\S+\.\S+')
		
		emoticons_pattern = ''
		for emoticon in self.emoticons: # travel tru emoticons list
			emoticon_escaped = sre.escape(emoticon) # espace regexp metachars
			emoticons_pattern += emoticon_escaped + '|'# | means or in regexp

		self.emot_and_basic_pattern =\
			emoticons_pattern + self.basic_pattern
			
		print self.emot_and_basic_pattern

		gtk.gdk.threads_enter()
		self.autoconnect()
		gtk.main()
		gtk.gdk.threads_leave()

print _('plugin gtkgui loaded')
