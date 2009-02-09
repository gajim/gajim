# -*- coding: utf-8 -*-
## src/disco.py
##
## Copyright (C) 2005-2006 Stéphan Kochen <stephan AT kochen.nl>
## Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2005-2008 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007 Stephan Erb <steve-e AT h3c.de>
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

# The appearance of the treeview, and parts of the dialog, are controlled by
# AgentBrowser (sub-)classes. Methods that probably should be overridden when
# subclassing are: (look at the docstrings and source for additional info)
# - def cleanup(self) *
# - def _create_treemodel(self) *
# - def _add_actions(self)
# - def _clean_actions(self)
# - def update_theme(self) *
# - def update_actions(self)
# - def default_action(self)
# - def _find_item(self, jid, node)
# - def _add_item(self, jid, node, item, force)
# - def _update_item(self, iter_, jid, node, item)
# - def _update_info(self, iter_, jid, node, identities, features, data)
# - def _update_error(self, iter_, jid, node)
#
# * Should call the super class for this method.
# All others do not have to call back to the super class. (but can if they want
# the functionality)
# There are more methods, of course, but this is a basic set.

import os
import types
import weakref
import gobject
import gtk
import pango

import dialogs
import tooltips
import gtkgui_helpers
import groups
import adhoc_commands
import search_window

from common import gajim
from common import xmpp
from common.exceptions import GajimGeneralException
from common import helpers

# Dictionary mapping category, type pairs to browser class, image pairs.
# This is a function, so we can call it after the classes are declared.
# For the browser class, None means that the service will only be browsable
# when it advertises disco as it's feature, False means it's never browsable.
def _gen_agent_type_info():
	return {
		# Defaults
		(0, 0):							(None, None),

		# Jabber server
		('server', 'im'):				(ToplevelAgentBrowser, 'jabber.png'),
		('services', 'jabber'):		(ToplevelAgentBrowser, 'jabber.png'),
		('hierarchy', 'branch'):	(AgentBrowser, 'jabber.png'),

		# Services
		('conference', 'text'):		(MucBrowser, 'conference.png'),
		('headline', 'rss'):			(AgentBrowser, 'rss.png'),
		('headline', 'weather'):	(False, 'weather.png'),
		('gateway', 'weather'):		(False, 'weather.png'),
		('_jid', 'weather'):			(False, 'weather.png'),
		('gateway', 'sip'):			(False, 'sip.png'),
		('directory', 'user'):		(None, 'jud.png'),
		('pubsub', 'generic'):		(PubSubBrowser, 'pubsub.png'),
		('pubsub', 'service'):		(PubSubBrowser, 'pubsub.png'),
		('proxy', 'bytestreams'):	(None, 'bytestreams.png'), # Socks5 FT proxy
		('headline', 'newmail'):	(ToplevelAgentBrowser, 'mail.png'),

		# Transports
		('conference', 'irc'):		(ToplevelAgentBrowser, 'irc.png'),
		('_jid', 'irc'):				(False, 'irc.png'),
		('gateway', 'aim'):			(False, 'aim.png'),
		('_jid', 'aim'):				(False, 'aim.png'),
		('gateway', 'gadu-gadu'):	(False, 'gadu-gadu.png'),
		('_jid', 'gadugadu'):		(False, 'gadu-gadu.png'),
		('gateway', 'http-ws'):		(False, 'http-ws.png'),
		('gateway', 'icq'):			(False, 'icq.png'),
		('_jid', 'icq'):				(False, 'icq.png'),
		('gateway', 'msn'):			(False, 'msn.png'),
		('_jid', 'msn'):				(False, 'msn.png'),
		('gateway', 'sms'):			(False, 'sms.png'),
		('_jid', 'sms'):				(False, 'sms.png'),
		('gateway', 'smtp'):			(False, 'mail.png'),
		('gateway', 'yahoo'):		(False, 'yahoo.png'),
		('_jid', 'yahoo'):			(False, 'yahoo.png'),
		('gateway', 'mrim'):			(False, 'mrim.png'),
		('_jid', 'mrim'):				(False, 'mrim.png'),
	}

# Category type to "human-readable" description string, and sort priority
_cat_to_descr = {
	'other':			(_('Others'),	2),
	'gateway':		(_('Transports'),	0),
	'_jid':			(_('Transports'),	0),
	#conference is a category for listing mostly groupchats in service discovery
	'conference':	(_('Conference'),	1),
}


class CacheDictionary:
	'''A dictionary that keeps items around for only a specific time.
	Lifetime is in minutes. Getrefresh specifies whether to refresh when
	an item is merely accessed instead of set aswell.'''
	def __init__(self, lifetime, getrefresh = True):
		self.lifetime = lifetime * 1000 * 60
		self.getrefresh = getrefresh
		self.cache = {}

	class CacheItem:
		'''An object to store cache items and their timeouts.'''
		def __init__(self, value):
			self.value = value
			self.source = None

		def __call__(self):
			return self.value

	def cleanup(self):
		for key in self.cache.keys():
			item = self.cache[key]
			if item.source:
				gobject.source_remove(item.source)
			del self.cache[key]

	def _expire_timeout(self, key):
		'''The timeout has expired, remove the object.'''
		if key in self.cache:
			del self.cache[key]
		return False

	def _refresh_timeout(self, key):
		'''The object was accessed, refresh the timeout.'''
		item = self.cache[key]
		if item.source:
			gobject.source_remove(item.source)
		if self.lifetime:
			source = gobject.timeout_add_seconds(self.lifetime/1000, self._expire_timeout, key)
			item.source = source

	def __getitem__(self, key):
		item = self.cache[key]
		if self.getrefresh:
			self._refresh_timeout(key)
		return item()

	def __setitem__(self, key, value):
		item = self.CacheItem(value)
		self.cache[key] = item
		self._refresh_timeout(key)

	def __delitem__(self, key):
		item = self.cache[key]
		if item.source:
			gobject.source_remove(item.source)
		del self.cache[key]

	def __contains__(self, key):
		return key in self.cache
	has_key = __contains__

_icon_cache = CacheDictionary(15)

def get_agent_address(jid, node = None):
	'''Returns an agent's address for displaying in the GUI.'''
	if node:
		return '%s@%s' % (node, str(jid))
	else:
		return str(jid)

class Closure(object):
	'''A weak reference to a callback with arguments as an object.

	Weak references to methods immediatly die, even if the object is still
	alive. Besides a handy way to store a callback, this provides a workaround
	that keeps a reference to the object instead.

	Userargs and removeargs must be tuples.'''
	def __init__(self, cb, userargs = (), remove = None, removeargs = ()):
		self.userargs = userargs
		self.remove = remove
		self.removeargs = removeargs
		if isinstance(cb, types.MethodType):
			self.meth_self = weakref.ref(cb.im_self, self._remove)
			self.meth_name = cb.func_name
		elif callable(cb):
			self.meth_self = None
			self.cb = weakref.ref(cb, self._remove)
		else:
			raise TypeError('Object is not callable')

	def _remove(self, ref):
		if self.remove:
			self.remove(self, *self.removeargs)

	def __call__(self, *args, **kwargs):
		if self.meth_self:
			obj = self.meth_self()
			cb = getattr(obj, self.meth_name)
		else:
			cb = self.cb()
		args = args + self.userargs
		return cb(*args, **kwargs)


class ServicesCache:
	'''Class that caches our query results. Each connection will have it's own
	ServiceCache instance.'''
	def __init__(self, account):
		self.account = account
		self._items = CacheDictionary(0, getrefresh = False)
		self._info = CacheDictionary(0, getrefresh = False)
		self._subscriptions = CacheDictionary(5, getrefresh=False)
		self._cbs = {}

	def cleanup(self):
		self._items.cleanup()
		self._info.cleanup()

	def _clean_closure(self, cb, type_, addr):
		# A closure died, clean up
		cbkey = (type_, addr)
		try:
			self._cbs[cbkey].remove(cb)
		except KeyError:
			return
		except ValueError:
			return
		# Clean an empty list
		if not self._cbs[cbkey]:
			del self._cbs[cbkey]

	def get_icon(self, identities = []):
		'''Return the icon for an agent.'''
		# Grab the first identity with an icon
		for identity in identities:
			try:
				cat, type_ = identity['category'], identity['type']
				info = _agent_type_info[(cat, type_)]
			except KeyError:
				continue
			filename = info[1]
			if filename:
				break
		else:
			# Loop fell through, default to unknown
			info = _agent_type_info[(0, 0)]
			filename = info[1]
		if not filename: # we don't have an image to show for this type
			filename = 'jabber.png'
		# Use the cache if possible
		if filename in _icon_cache:
			return _icon_cache[filename]
		# Or load it
		filepath = os.path.join(gajim.DATA_DIR, 'pixmaps', 'agents', filename)
		pix = gtk.gdk.pixbuf_new_from_file(filepath)
		# Store in cache
		_icon_cache[filename] = pix
		return pix

	def get_browser(self, identities=[], features=[]):
		'''Return the browser class for an agent.'''
		# First pass, we try to find a ToplevelAgentBrowser
		for identity in identities:
			try:
				cat, type_ = identity['category'], identity['type']
				info = _agent_type_info[(cat, type_)]
			except KeyError:
				continue
			browser = info[0]
			if browser and browser == ToplevelAgentBrowser:
				return browser

		# second pass, we haven't found a ToplevelAgentBrowser
		for identity in identities:
			try:
				cat, type_ = identity['category'], identity['type']
				info = _agent_type_info[(cat, type_)]
			except KeyError:
				continue
			browser = info[0]
			if browser:
				return browser
		# NS_BROWSE is deprecated, but we check for it anyways.
		# Some services list it in features and respond to
		# NS_DISCO_ITEMS anyways.
		# Allow browsing for unknown types aswell.
		if (not features and not identities) or \
		xmpp.NS_DISCO_ITEMS in features or xmpp.NS_BROWSE in features:
			return ToplevelAgentBrowser
		return None

	def get_info(self, jid, node, cb, force = False, nofetch = False, args = ()):
		'''Get info for an agent.'''
		addr = get_agent_address(jid, node)
		# Check the cache
		if addr in self._info:
			args = self._info[addr] + args
			cb(jid, node, *args)
			return
		if nofetch:
			return

		# Create a closure object
		cbkey = ('info', addr)
		cb = Closure(cb, userargs = args, remove = self._clean_closure,
				removeargs = cbkey)
		# Are we already fetching this?
		if cbkey in self._cbs:
			self._cbs[cbkey].append(cb)
		else:
			self._cbs[cbkey] = [cb]
			gajim.connections[self.account].discoverInfo(jid, node)

	def get_items(self, jid, node, cb, force = False, nofetch = False, args = ()):
		'''Get a list of items in an agent.'''
		addr = get_agent_address(jid, node)
		# Check the cache
		if addr in self._items:
			args = (self._items[addr],) + args
			cb(jid, node, *args)
			return
		if nofetch:
			return

		# Create a closure object
		cbkey = ('items', addr)
		cb = Closure(cb, userargs = args, remove = self._clean_closure,
				removeargs = cbkey)
		# Are we already fetching this?
		if cbkey in self._cbs:
			self._cbs[cbkey].append(cb)
		else:
			self._cbs[cbkey] = [cb]
			gajim.connections[self.account].discoverItems(jid, node)

	def agent_info(self, jid, node, identities, features, data):
		'''Callback for when we receive an agent's info.'''
		addr = get_agent_address(jid, node)

		# Store in cache
		self._info[addr] = (identities, features, data)

		# Call callbacks
		cbkey = ('info', addr)
		if cbkey in self._cbs:
			for cb in self._cbs[cbkey]:
				cb(jid, node, identities, features, data)
			# clean_closure may have beaten us to it
			if cbkey in self._cbs:
				del self._cbs[cbkey]

	def agent_items(self, jid, node, items):
		'''Callback for when we receive an agent's items.'''
		addr = get_agent_address(jid, node)

		# Store in cache
		self._items[addr] = items

		# Call callbacks
		cbkey = ('items', addr)
		if cbkey in self._cbs:
			for cb in self._cbs[cbkey]:
				cb(jid, node, items)
			# clean_closure may have beaten us to it
			if cbkey in self._cbs:
				del self._cbs[cbkey]

	def agent_info_error(self, jid):
		'''Callback for when a query fails. (even after the browse and agents
		namespaces)'''
		addr = get_agent_address(jid)

		# Call callbacks
		cbkey = ('info', addr)
		if cbkey in self._cbs:
			for cb in self._cbs[cbkey]:
				cb(jid, '', 0, 0, 0)
			# clean_closure may have beaten us to it
			if cbkey in self._cbs:
				del self._cbs[cbkey]

	def agent_items_error(self, jid):
		'''Callback for when a query fails. (even after the browse and agents
		namespaces)'''
		addr = get_agent_address(jid)

		# Call callbacks
		cbkey = ('items', addr)
		if cbkey in self._cbs:
			for cb in self._cbs[cbkey]:
				cb(jid, '', 0)
			# clean_closure may have beaten us to it
			if cbkey in self._cbs:
				del self._cbs[cbkey]

# object is needed so that @property works
class ServiceDiscoveryWindow(object):
	'''Class that represents the Services Discovery window.'''
	def __init__(self, account, jid = '', node = '',
			address_entry = False, parent = None):
		self.account = account
		self.parent = parent
		if not jid:
			jid = gajim.config.get_per('accounts', account, 'hostname')
			node = ''

		self.jid = None
		self.browser = None
		self.children = []
		self.dying = False
		self.node = None

		# Check connection
		if gajim.connections[account].connected < 2:
			dialogs.ErrorDialog(_('You are not connected to the server'),
_('Without a connection, you can not browse available services'))
			raise RuntimeError, 'You must be connected to browse services'

		# Get a ServicesCache object.
		try:
			self.cache = gajim.connections[account].services_cache
		except AttributeError:
			self.cache = ServicesCache(account)
			gajim.connections[account].services_cache = self.cache

		self.xml = gtkgui_helpers.get_glade('service_discovery_window.glade')
		self.window = self.xml.get_widget('service_discovery_window')
		self.services_treeview = self.xml.get_widget('services_treeview')
		self.model = None
		# This is more reliable than the cursor-changed signal.
		selection = self.services_treeview.get_selection()
		selection.connect_after('changed',
			self.on_services_treeview_selection_changed)
		self.services_scrollwin = self.xml.get_widget('services_scrollwin')
		self.progressbar = self.xml.get_widget('services_progressbar')
		self.banner = self.xml.get_widget('banner_agent_label')
		self.banner_icon = self.xml.get_widget('banner_agent_icon')
		self.banner_eventbox = self.xml.get_widget('banner_agent_eventbox')
		self.style_event_id = 0
		self.banner.realize()
		self.paint_banner()
		self.action_buttonbox = self.xml.get_widget('action_buttonbox')

		# Address combobox
		self.address_comboboxentry = None
		address_table = self.xml.get_widget('address_table')
		if address_entry:
			self.address_comboboxentry = self.xml.get_widget(
				'address_comboboxentry')
			self.address_comboboxentry_entry = self.address_comboboxentry.child
			self.address_comboboxentry_entry.set_activates_default(True)

			liststore = gtk.ListStore(str)
			self.address_comboboxentry.set_model(liststore)
			self.latest_addresses = gajim.config.get(
				'latest_disco_addresses').split()
			if jid in self.latest_addresses:
				self.latest_addresses.remove(jid)
			self.latest_addresses.insert(0, jid)
			if len(self.latest_addresses) > 10:
				self.latest_addresses = self.latest_addresses[0:10]
			for j in self.latest_addresses:
				self.address_comboboxentry.append_text(j)
			self.address_comboboxentry.child.set_text(jid)
		else:
			# Don't show it at all if we didn't ask for it
			address_table.set_no_show_all(True)
			address_table.hide()

		self._initial_state()
		self.xml.signal_autoconnect(self)
		self.travel(jid, node)
		self.window.show_all()

	@property
	def _get_account(self):
		return self.account

	@property
	def _set_account(self, value):
		self.account = value
		self.cache.account = value
		if self.browser:
			self.browser.account = value

	def _initial_state(self):
		'''Set some initial state on the window. Separated in a method because
		it's handy to use within browser's cleanup method.'''
		self.progressbar.hide()
		title_text = _('Service Discovery using account %s') % self.account
		self.window.set_title(title_text)
		self._set_window_banner_text(_('Service Discovery'))
		self.banner_icon.clear()
		self.banner_icon.hide() # Just clearing it doesn't work

	def _set_window_banner_text(self, text, text_after = None):
		theme = gajim.config.get('roster_theme')
		bannerfont = gajim.config.get_per('themes', theme, 'bannerfont')
		bannerfontattrs = gajim.config.get_per('themes', theme,
			'bannerfontattrs')

		if bannerfont:
			font = pango.FontDescription(bannerfont)
		else:
			font = pango.FontDescription('Normal')
		if bannerfontattrs:
			# B is attribute set by default
			if 'B' in bannerfontattrs:
				font.set_weight(pango.WEIGHT_HEAVY)
			if 'I' in bannerfontattrs:
				font.set_style(pango.STYLE_ITALIC)

		font_attrs = 'font_desc="%s"' % font.to_string()
		font_size = font.get_size()

		# in case there is no font specified we use x-large font size
		if font_size == 0:
			font_attrs = '%s size="large"' % font_attrs
		markup = '<span %s>%s</span>' % (font_attrs, text)
		if text_after:
			font.set_weight(pango.WEIGHT_NORMAL)
			markup = '%s\n<span font_desc="%s" size="small">%s</span>' % \
									(markup, font.to_string(), text_after)
		self.banner.set_markup(markup)

	def paint_banner(self):
		'''Repaint the banner with theme color'''
		theme = gajim.config.get('roster_theme')
		bgcolor = gajim.config.get_per('themes', theme, 'bannerbgcolor')
		textcolor = gajim.config.get_per('themes', theme, 'bannertextcolor')
		self.disconnect_style_event()
		if bgcolor:
			color = gtk.gdk.color_parse(bgcolor)
			self.banner_eventbox.modify_bg(gtk.STATE_NORMAL, color)
			default_bg = False
		else:
			default_bg = True

		if textcolor:
			color = gtk.gdk.color_parse(textcolor)
			self.banner.modify_fg(gtk.STATE_NORMAL, color)
			default_fg = False
		else:
			default_fg = True
		if default_fg or default_bg:
			self._on_style_set_event(self.banner, None, default_fg, default_bg)
		if self.browser:
			self.browser.update_theme()

	def disconnect_style_event(self):
		if self.style_event_id:
			self.banner.disconnect(self.style_event_id)
			self.style_event_id = 0

	def connect_style_event(self, set_fg = False, set_bg = False):
		self.disconnect_style_event()
		self.style_event_id = self.banner.connect('style-set',
					self._on_style_set_event, set_fg, set_bg)

	def _on_style_set_event(self, widget, style, *opts):
		''' set style of widget from style class *.Frame.Eventbox
			opts[0] == True -> set fg color
			opts[1] == True -> set bg color	'''

		self.disconnect_style_event()
		if opts[1]:
			bg_color = widget.style.bg[gtk.STATE_SELECTED]
			self.banner_eventbox.modify_bg(gtk.STATE_NORMAL, bg_color)
		if opts[0]:
			fg_color = widget.style.fg[gtk.STATE_SELECTED]
			self.banner.modify_fg(gtk.STATE_NORMAL, fg_color)
		self.banner.ensure_style()
		self.connect_style_event(opts[0], opts[1])

	def destroy(self, chain = False):
		'''Close the browser. This can optionally close its children and
		propagate to the parent. This should happen on actions like register,
		or join to kill off the entire browser chain.'''
		if self.dying:
			return
		self.dying = True

		# self.browser._get_agent_address() would break when no browser.
		addr = get_agent_address(self.jid, self.node)
		if addr in gajim.interface.instances[self.account]['disco']:
			del gajim.interface.instances[self.account]['disco'][addr]

		if self.browser:
			self.window.hide()
			self.browser.cleanup()
			self.browser = None
		self.window.destroy()

		for child in self.children[:]:
			child.parent = None
			if chain:
				child.destroy(chain = chain)
				self.children.remove(child)
		if self.parent:
			if self in self.parent.children:
				self.parent.children.remove(self)
			if chain and not self.parent.children:
				self.parent.destroy(chain = chain)
				self.parent = None
		else:
			self.cache.cleanup()

	def travel(self, jid, node):
		'''Travel to an agent within the current services window.'''
		if self.browser:
			self.browser.cleanup()
			self.browser = None
		# Update the window list
		if self.jid:
			old_addr = get_agent_address(self.jid, self.node)
			if old_addr in gajim.interface.instances[self.account]['disco']:
				del gajim.interface.instances[self.account]['disco'][old_addr]
		addr = get_agent_address(jid, node)
		gajim.interface.instances[self.account]['disco'][addr] = self
		# We need to store these, self.browser is not always available.
		self.jid = jid
		self.node = node
		self.cache.get_info(jid, node, self._travel)

	def _travel(self, jid, node, identities, features, data):
		'''Continuation of travel.'''
		if self.dying or jid != self.jid or node != self.node:
			return
		if not identities:
			if not self.address_comboboxentry:
				# We can't travel anywhere else.
				self.destroy()
			dialogs.ErrorDialog(_('The service could not be found'),
_('There is no service at the address you entered, or it is not responding. Check the address and try again.'))
			return
		klass = self.cache.get_browser(identities, features)
		if not klass:
			dialogs.ErrorDialog(_('The service is not browsable'),
_('This type of service does not contain any items to browse.'))
			return
		elif klass is None:
			klass = AgentBrowser
		self.browser = klass(self.account, jid, node)
		self.browser.prepare_window(self)
		self.browser.browse()

	def open(self, jid, node):
		'''Open an agent. By default, this happens in a new window.'''
		try:
			win = gajim.interface.instances[self.account]['disco']\
				[get_agent_address(jid, node)]
			win.window.present()
			return
		except KeyError:
			pass
		try:
			win = ServiceDiscoveryWindow(self.account, jid, node, parent=self)
		except RuntimeError:
			# Disconnected, perhaps
			return
		self.children.append(win)

	def on_service_discovery_window_destroy(self, widget):
		self.destroy()

	def on_close_button_clicked(self, widget):
		self.destroy()

	def on_address_comboboxentry_changed(self, widget):
		if self.address_comboboxentry.get_active() != -1:
			# user selected one of the entries so do auto-visit
			jid = self.address_comboboxentry.child.get_text().decode('utf-8')
			try:
				jid = helpers.parse_jid(jid)
			except helpers.InvalidFormat, s:
				pritext = _('Invalid Server Name')
				dialogs.ErrorDialog(pritext, str(s))
				return
			self.travel(jid, '')

	def on_go_button_clicked(self, widget):
		jid = self.address_comboboxentry.child.get_text().decode('utf-8')
		try:
			jid = helpers.parse_jid(jid)
		except helpers.InvalidFormat, s:
			pritext = _('Invalid Server Name')
			dialogs.ErrorDialog(pritext, str(s))
			return
		if jid == self.jid: # jid has not changed
			return
		if jid in self.latest_addresses:
			self.latest_addresses.remove(jid)
		self.latest_addresses.insert(0, jid)
		if len(self.latest_addresses) > 10:
			self.latest_addresses = self.latest_addresses[0:10]
		self.address_comboboxentry.get_model().clear()
		for j in self.latest_addresses:
			self.address_comboboxentry.append_text(j)
		gajim.config.set('latest_disco_addresses',
			' '.join(self.latest_addresses))
		gajim.interface.save_config()
		self.travel(jid, '')

	def on_services_treeview_row_activated(self, widget, path, col = 0):
		if self.browser:
			self.browser.default_action()

	def on_services_treeview_selection_changed(self, widget):
		if self.browser:
			self.browser.update_actions()


class AgentBrowser:
	'''Class that deals with browsing agents and appearance of the browser
	window. This class and subclasses should basically be treated as "part"
	of the ServiceDiscoveryWindow class, but had to be separated because this part
	is dynamic.'''
	def __init__(self, account, jid, node):
		self.account = account
		self.jid = jid
		self.node = node
		self._total_items = 0
		self.browse_button = None
		# This is for some timeout callbacks
		self.active = False

	def _get_agent_address(self):
		'''Returns the agent's address for displaying in the GUI.'''
		return get_agent_address(self.jid, self.node)

	def _set_initial_title(self):
		'''Set the initial window title based on agent address.'''
		self.window.window.set_title(_('Browsing %(address)s using account '
			'%(account)s') % {'address': self._get_agent_address(),
			'account': self.account})
		self.window._set_window_banner_text(self._get_agent_address())

	def _create_treemodel(self):
		'''Create the treemodel for the services treeview. When subclassing,
		note that the first two columns should ALWAYS be of type string and
		contain the JID and node of the item respectively.'''
		# JID, node, name, address
		self.model = gtk.ListStore(str, str, str, str)
		self.model.set_sort_column_id(3, gtk.SORT_ASCENDING)
		self.window.services_treeview.set_model(self.model)
		# Name column
		col = gtk.TreeViewColumn(_('Name'))
		renderer = gtk.CellRendererText()
		col.pack_start(renderer)
		col.set_attributes(renderer, text = 2)
		self.window.services_treeview.insert_column(col, -1)
		col.set_resizable(True)
		# Address column
		col = gtk.TreeViewColumn(_('JID'))
		renderer = gtk.CellRendererText()
		col.pack_start(renderer)
		col.set_attributes(renderer, text = 3)
		self.window.services_treeview.insert_column(col, -1)
		col.set_resizable(True)
		self.window.services_treeview.set_headers_visible(True)

	def _clean_treemodel(self):
		self.model.clear()
		for col in self.window.services_treeview.get_columns():
			self.window.services_treeview.remove_column(col)
		self.window.services_treeview.set_headers_visible(False)

	def _add_actions(self):
		'''Add the action buttons to the buttonbox for actions the browser can
		perform.'''
		self.browse_button = gtk.Button()
		image = gtk.image_new_from_stock(gtk.STOCK_OPEN, gtk.ICON_SIZE_BUTTON)
		label = gtk.Label(_('_Browse'))
		label.set_use_underline(True)
		hbox = gtk.HBox()
		hbox.pack_start(image, False, True, 6)
		hbox.pack_end(label, True, True)
		self.browse_button.add(hbox)
		self.browse_button.connect('clicked', self.on_browse_button_clicked)
		self.window.action_buttonbox.add(self.browse_button)
		self.browse_button.show_all()

	def _clean_actions(self):
		'''Remove the action buttons specific to this browser.'''
		if self.browse_button:
			self.browse_button.destroy()
			self.browse_button = None

	def _set_title(self, jid, node, identities, features, data):
		'''Set the window title based on agent info.'''
		# Set the banner and window title
		if 'name' in identities[0]:
			name = identities[0]['name']
			self.window._set_window_banner_text(self._get_agent_address(), name)

		# Add an icon to the banner.
		pix = self.cache.get_icon(identities)
		self.window.banner_icon.set_from_pixbuf(pix)
		self.window.banner_icon.show()

	def _clean_title(self):
		# Everything done here is done in window._initial_state
		# This is for subclasses.
		pass

	def prepare_window(self, window):
		'''Prepare the service discovery window. Called when a browser is hooked
		up with a ServiceDiscoveryWindow instance.'''
		self.window = window
		self.cache = window.cache

		self._set_initial_title()
		self._create_treemodel()
		self._add_actions()

		# This is a hack. The buttonbox apparently doesn't care about pack_start
		# or pack_end, so we repack the close button here to make sure it's last
		close_button = self.window.xml.get_widget('close_button')
		self.window.action_buttonbox.remove(close_button)
		self.window.action_buttonbox.pack_end(close_button)
		close_button.show_all()

		self.update_actions()

		self.active = True
		self.cache.get_info(self.jid, self.node, self._set_title)

	def cleanup(self):
		'''Cleanup when the window intends to switch browsers.'''
		self.active = False

		self._clean_actions()
		self._clean_treemodel()
		self._clean_title()

		self.window._initial_state()

	def update_theme(self):
		'''Called when the default theme is changed.'''
		pass

	def on_browse_button_clicked(self, widget = None):
		'''When we want to browse an agent:
		Open a new services window with a browser for the agent type.'''
		model, iter_ = self.window.services_treeview.get_selection().get_selected()
		if not iter_:
			return
		jid = model[iter_][0].decode('utf-8')
		if jid:
			node = model[iter_][1].decode('utf-8')
			self.window.open(jid, node)

	def update_actions(self):
		'''When we select a row:
		activate action buttons based on the agent's info.'''
		if self.browse_button:
			self.browse_button.set_sensitive(False)
		model, iter_ = self.window.services_treeview.get_selection().get_selected()
		if not iter_:
			return
		jid = model[iter_][0].decode('utf-8')
		node = model[iter_][1].decode('utf-8')
		if jid:
			self.cache.get_info(jid, node, self._update_actions, nofetch = True)

	def _update_actions(self, jid, node, identities, features, data):
		'''Continuation of update_actions.'''
		if not identities or not self.browse_button:
			return
		klass = self.cache.get_browser(identities, features)
		if klass:
			self.browse_button.set_sensitive(True)

	def default_action(self):
		'''When we double-click a row:
		perform the default action on the selected item.'''
		model, iter_ = self.window.services_treeview.get_selection().get_selected()
		if not iter_:
			return
		jid = model[iter_][0].decode('utf-8')
		node = model[iter_][1].decode('utf-8')
		if jid:
			self.cache.get_info(jid, node, self._default_action, nofetch = True)

	def _default_action(self, jid, node, identities, features, data):
		'''Continuation of default_action.'''
		if self.cache.get_browser(identities, features):
			# Browse if we can
			self.on_browse_button_clicked()
			return True
		return False

	def browse(self, force = False):
		'''Fill the treeview with agents, fetching the info if necessary.'''
		self.model.clear()
		self._total_items = self._progress = 0
		self.window.progressbar.show()
		self._pulse_timeout = gobject.timeout_add(250, self._pulse_timeout_cb)
		self.cache.get_items(self.jid, self.node, self._agent_items,
			force = force, args = (force,))

	def _pulse_timeout_cb(self, *args):
		'''Simple callback to keep the progressbar pulsing.'''
		if not self.active:
			return False
		self.window.progressbar.pulse()
		return True

	def _find_item(self, jid, node):
		'''Check if an item is already in the treeview. Return an iter to it
		if so, None otherwise.'''
		iter_ = self.model.get_iter_root()
		while iter_:
			cjid = self.model.get_value(iter_, 0).decode('utf-8')
			cnode = self.model.get_value(iter_, 1).decode('utf-8')
			if jid == cjid and node == cnode:
				break
			iter_ = self.model.iter_next(iter_)
		if iter_:
			return iter_
		return None

	def _agent_items(self, jid, node, items, force):
		'''Callback for when we receive a list of agent items.'''
		self.model.clear()
		self._total_items = 0
		gobject.source_remove(self._pulse_timeout)
		self.window.progressbar.hide()
		# The server returned an error
		if items == 0:
			if not self.window.address_comboboxentry:
				# We can't travel anywhere else.
				self.window.destroy()
			dialogs.ErrorDialog(_('The service is not browsable'),
_('This service does not contain any items to browse.'))
			return
		# We got a list of items
		self.window.services_treeview.set_model(None)
		for item in items:
			jid = item['jid']
			node = item.get('node', '')
			# If such an item is already here: don't add it
			if self._find_item(jid, node):
				continue
			self._total_items += 1
			self._add_item(jid, node, item, force)
		self.window.services_treeview.set_model(self.model)

	def _agent_info(self, jid, node, identities, features, data):
		'''Callback for when we receive info about an agent's item.'''
		iter_ = self._find_item(jid, node)
		if not iter_:
			# Not in the treeview, stop
			return
		if identities == 0:
			# The server returned an error
			self._update_error(iter_, jid, node)
		else:
			# We got our info
			self._update_info(iter_, jid, node, identities, features, data)
		self.update_actions()

	def _add_item(self, jid, node, item, force):
		'''Called when an item should be added to the model. The result of a
		disco#items query.'''
		self.model.append((jid, node, item.get('name', ''),
			get_agent_address(jid, node)))
		self.cache.get_info(jid, node, self._agent_info, force = force)

	def _update_item(self, iter_, jid, node, item):
		'''Called when an item should be updated in the model. The result of a
		disco#items query. (seldom)'''
		if 'name' in item:
			self.model[iter_][2] = item['name']

	def _update_info(self, iter_, jid, node, identities, features, data):
		'''Called when an item should be updated in the model with further info.
		The result of a disco#info query.'''
		name = identities[0].get('name', '')
		if name:
			self.model[iter_][2] = name

	def _update_error(self, iter_, jid, node):
		'''Called when a disco#info query failed for an item.'''
		pass


class ToplevelAgentBrowser(AgentBrowser):
	'''This browser is used at the top level of a jabber server to browse
	services such as transports, conference servers, etc.'''
	def __init__(self, *args):
		AgentBrowser.__init__(self, *args)
		self._progressbar_sourceid = None
		self._renderer = None
		self._progress = 0
		self.tooltip = tooltips.ServiceDiscoveryTooltip()
		self.register_button = None
		self.join_button = None
		self.execute_button = None
		self.search_button = None
		# Keep track of our treeview signals
		self._view_signals = []
		self._scroll_signal = None

	def _pixbuf_renderer_data_func(self, col, cell, model, iter_):
		'''Callback for setting the pixbuf renderer's properties.'''
		jid = model.get_value(iter_, 0)
		if jid:
			pix = model.get_value(iter_, 2)
			cell.set_property('visible', True)
			cell.set_property('pixbuf', pix)
		else:
			cell.set_property('visible', False)

	def _text_renderer_data_func(self, col, cell, model, iter_):
		'''Callback for setting the text renderer's properties.'''
		jid = model.get_value(iter_, 0)
		markup = model.get_value(iter_, 3)
		state = model.get_value(iter_, 4)
		cell.set_property('markup', markup)
		if jid:
			cell.set_property('cell_background_set', False)
			if state > 0:
				# 1 = fetching, 2 = error
				cell.set_property('foreground_set', True)
			else:
				# Normal/succes
				cell.set_property('foreground_set', False)
		else:
			theme = gajim.config.get('roster_theme')
			bgcolor = gajim.config.get_per('themes', theme, 'groupbgcolor')
			if bgcolor:
				cell.set_property('cell_background_set', True)
			cell.set_property('foreground_set', False)

	def _treemodel_sort_func(self, model, iter1, iter2):
		'''Sort function for our treemodel.'''
		# Compare state
		statecmp = cmp(model.get_value(iter1, 4), model.get_value(iter2, 4))
		if statecmp == 0:
			# These can be None, apparently
			descr1 = model.get_value(iter1, 3)
			if descr1:
				descr1 = descr1.decode('utf-8')
			descr2 = model.get_value(iter2, 3)
			if descr2:
				descr2 = descr2.decode('utf-8')
			# Compare strings
			return cmp(descr1, descr2)
		return statecmp

	def _show_tooltip(self, state):
		view = self.window.services_treeview
		pointer = view.get_pointer()
		props = view.get_path_at_pos(pointer[0], pointer[1])
		# check if the current pointer is at the same path
		# as it was before setting the timeout
		if props and self.tooltip.id == props[0]:
			# bounding rectangle of coordinates for the cell within the treeview
			rect = view.get_cell_area(props[0], props[1])
			# position of the treeview on the screen
			position = view.window.get_origin()
			self.tooltip.show_tooltip(state, rect.height, position[1] + rect.y)
		else:
			self.tooltip.hide_tooltip()

	# These are all callbacks to make tooltips work
	def on_treeview_leave_notify_event(self, widget, event):
		props = widget.get_path_at_pos(int(event.x), int(event.y))
		if self.tooltip.timeout > 0:
			if not props or self.tooltip.id == props[0]:
				self.tooltip.hide_tooltip()

	def on_treeview_motion_notify_event(self, widget, event):
		props = widget.get_path_at_pos(int(event.x), int(event.y))
		if self.tooltip.timeout > 0:
			if not props or self.tooltip.id != props[0]:
				self.tooltip.hide_tooltip()
		if props:
			row = props[0]
			iter_ = None
			try:
				iter_ = self.model.get_iter(row)
			except Exception:
				self.tooltip.hide_tooltip()
				return
			jid = self.model[iter_][0]
			state = self.model[iter_][4]
			# Not a category, and we have something to say about state
			if jid and state > 0 and \
					(self.tooltip.timeout == 0 or self.tooltip.id != props[0]):
				self.tooltip.id = row
				self.tooltip.timeout = gobject.timeout_add(500,
					self._show_tooltip, state)

	def on_treeview_event_hide_tooltip(self, widget, event):
		''' This happens on scroll_event, key_press_event
			and button_press_event '''
		self.tooltip.hide_tooltip()

	def _create_treemodel(self):
		# JID, node, icon, description, state
		# State means 2 when error, 1 when fetching, 0 when succes.
		view = self.window.services_treeview
		self.model = gtk.TreeStore(str, str, gtk.gdk.Pixbuf, str, int)
		self.model.set_sort_func(4, self._treemodel_sort_func)
		self.model.set_sort_column_id(4, gtk.SORT_ASCENDING)
		view.set_model(self.model)

		col = gtk.TreeViewColumn()
		# Icon Renderer
		renderer = gtk.CellRendererPixbuf()
		renderer.set_property('xpad', 6)
		col.pack_start(renderer, expand = False)
		col.set_cell_data_func(renderer, self._pixbuf_renderer_data_func)
		# Text Renderer
		renderer = gtk.CellRendererText()
		col.pack_start(renderer, expand = True)
		col.set_cell_data_func(renderer, self._text_renderer_data_func)
		renderer.set_property('foreground', 'dark gray')
		# Save this so we can go along with theme changes
		self._renderer = renderer
		self.update_theme()

		view.insert_column(col, -1)
		col.set_resizable(True)

		# Connect signals
		scrollwin = self.window.services_scrollwin
		self._view_signals.append(view.connect('leave-notify-event',
										self.on_treeview_leave_notify_event))
		self._view_signals.append(view.connect('motion-notify-event',
										self.on_treeview_motion_notify_event))
		self._view_signals.append(view.connect('key-press-event',
										self.on_treeview_event_hide_tooltip))
		self._view_signals.append(view.connect('button-press-event',
										self.on_treeview_event_hide_tooltip))
		self._scroll_signal = scrollwin.connect('scroll-event',
										self.on_treeview_event_hide_tooltip)

	def _clean_treemodel(self):
		# Disconnect signals
		view = self.window.services_treeview
		for sig in self._view_signals:
			view.disconnect(sig)
		self._view_signals = []
		if self._scroll_signal:
			scrollwin = self.window.services_scrollwin
			scrollwin.disconnect(self._scroll_signal)
			self._scroll_signal = None
		AgentBrowser._clean_treemodel(self)

	def _add_actions(self):
		AgentBrowser._add_actions(self)
		self.execute_button = gtk.Button()
		image = gtk.image_new_from_stock(gtk.STOCK_EXECUTE, gtk.ICON_SIZE_BUTTON)
		label = gtk.Label(_('_Execute Command'))
		label.set_use_underline(True)
		hbox = gtk.HBox()
		hbox.pack_start(image, False, True, 6)
		hbox.pack_end(label, True, True)
		self.execute_button.add(hbox)
		self.execute_button.connect('clicked', self.on_execute_button_clicked)
		self.window.action_buttonbox.add(self.execute_button)
		self.execute_button.show_all()

		self.register_button = gtk.Button(label=_("Re_gister"),
			use_underline=True)
		self.register_button.connect('clicked', self.on_register_button_clicked)
		self.window.action_buttonbox.add(self.register_button)
		self.register_button.show_all()

		self.join_button = gtk.Button()
		image = gtk.image_new_from_stock(gtk.STOCK_CONNECT, gtk.ICON_SIZE_BUTTON)
		label = gtk.Label(_('_Join'))
		label.set_use_underline(True)
		hbox = gtk.HBox()
		hbox.pack_start(image, False, True, 6)
		hbox.pack_end(label, True, True)
		self.join_button.add(hbox)
		self.join_button.connect('clicked', self.on_join_button_clicked)
		self.window.action_buttonbox.add(self.join_button)
		self.join_button.show_all()

		self.search_button = gtk.Button()
		image = gtk.image_new_from_stock(gtk.STOCK_FIND, gtk.ICON_SIZE_BUTTON)
		label = gtk.Label(_('_Search'))
		label.set_use_underline(True)
		hbox = gtk.HBox()
		hbox.pack_start(image, False, True, 6)
		hbox.pack_end(label, True, True)
		self.search_button.add(hbox)
		self.search_button.connect('clicked', self.on_search_button_clicked)
		self.window.action_buttonbox.add(self.search_button)
		self.search_button.show_all()

	def _clean_actions(self):
		if self.execute_button:
			self.execute_button.destroy()
			self.execute_button = None
		if self.register_button:
			self.register_button.destroy()
			self.register_button = None
		if self.join_button:
			self.join_button.destroy()
			self.join_button = None
		if self.search_button:
			self.search_button.destroy()
			self.search_button = None
		AgentBrowser._clean_actions(self)

	def on_search_button_clicked(self, widget = None):
		'''When we want to search something:
		open search window'''
		model, iter_ = self.window.services_treeview.get_selection().get_selected()
		if not iter_:
			return
		service = model[iter_][0].decode('utf-8')
		if service in gajim.interface.instances[self.account]['search']:
			gajim.interface.instances[self.account]['search'][service].present()
		else:
			gajim.interface.instances[self.account]['search'][service] = \
				search_window.SearchWindow(self.account, service)

	def cleanup(self):
		self.tooltip.hide_tooltip()
		AgentBrowser.cleanup(self)

	def update_theme(self):
		theme = gajim.config.get('roster_theme')
		bgcolor = gajim.config.get_per('themes', theme, 'groupbgcolor')
		if bgcolor:
			self._renderer.set_property('cell-background', bgcolor)
		self.window.services_treeview.queue_draw()

	def on_execute_button_clicked(self, widget = None):
		'''When we want to execute a command:
		open adhoc command window'''
		model, iter_ = self.window.services_treeview.get_selection().get_selected()
		if not iter_:
			return
		service = model[iter_][0].decode('utf-8')
		adhoc_commands.CommandWindow(self.account, service)

	def on_register_button_clicked(self, widget = None):
		'''When we want to register an agent:
		request information about registering with the agent and close the
		window.'''
		model, iter_ = self.window.services_treeview.get_selection().get_selected()
		if not iter_:
			return
		jid = model[iter_][0].decode('utf-8')
		if jid:
			gajim.connections[self.account].request_register_agent_info(jid)
			self.window.destroy(chain = True)

	def on_join_button_clicked(self, widget):
		'''When we want to join an IRC room or create a new MUC room:
		Opens the join_groupchat_window.'''
		model, iter_ = self.window.services_treeview.get_selection().get_selected()
		if not iter_:
			return
		service = model[iter_][0].decode('utf-8')
		if 'join_gc' not in gajim.interface.instances[self.account]:
			try:
				dialogs.JoinGroupchatWindow(self.account, service)
			except GajimGeneralException:
				pass
		else:
			gajim.interface.instances[self.account]['join_gc'].window.present()
		self.window.destroy(chain = True)

	def update_actions(self):
		if self.execute_button:
			self.execute_button.set_sensitive(False)
		if self.register_button:
			self.register_button.set_sensitive(False)
		if self.browse_button:
			self.browse_button.set_sensitive(False)
		if self.join_button:
			self.join_button.set_sensitive(False)
		if self.search_button:
			self.search_button.set_sensitive(False)
		model, iter_ = self.window.services_treeview.get_selection().get_selected()
		model, iter_ = self.window.services_treeview.get_selection().get_selected()
		if not iter_:
			return
		if not model[iter_][0]:
			# We're on a category row
			return
		if model[iter_][4] != 0:
			# We don't have the info (yet)
			# It's either unknown or a transport, register button should be active
			if self.register_button:
				self.register_button.set_sensitive(True)
			# Guess what kind of service we're dealing with
			if self.browse_button:
				jid = model[iter_][0].decode('utf-8')
				type_ = gajim.get_transport_name_from_jid(jid,
							use_config_setting = False)
				if type_:
					identity = {'category': '_jid', 'type': type_}
					klass = self.cache.get_browser([identity])
					if klass:
						self.browse_button.set_sensitive(True)
				else:
					# We couldn't guess
					self.browse_button.set_sensitive(True)
		else:
			# Normal case, we have info
			AgentBrowser.update_actions(self)

	def _update_actions(self, jid, node, identities, features, data):
		AgentBrowser._update_actions(self, jid, node, identities, features, data)
		if self.execute_button and xmpp.NS_COMMANDS in features:
			self.execute_button.set_sensitive(True)
		if self.search_button and xmpp.NS_SEARCH in features:
			self.search_button.set_sensitive(True)
		if self.register_button and xmpp.NS_REGISTER in features:
			# We can register this agent
			registered_transports = []
			jid_list = gajim.contacts.get_jid_list(self.account)
			for jid in jid_list:
				contact = gajim.contacts.get_first_contact_from_jid(
					self.account, jid)
				if _('Transports') in contact.groups:
					registered_transports.append(jid)
			if jid in registered_transports:
				self.register_button.set_label(_('_Edit'))
			else:
				self.register_button.set_label(_('Re_gister'))
			self.register_button.set_sensitive(True)
		if self.join_button and xmpp.NS_MUC in features:
			self.join_button.set_sensitive(True)

	def _default_action(self, jid, node, identities, features, data):
		if AgentBrowser._default_action(self, jid, node, identities, features, data):
			return True
		if xmpp.NS_REGISTER in features:
			# Register if we can't browse
			self.on_register_button_clicked()
			return True
		return False

	def browse(self, force = False):
		self._progress = 0
		AgentBrowser.browse(self, force = force)

	def _expand_all(self):
		'''Expand all items in the treeview'''
		# GTK apparently screws up here occasionally. :/
		#def expand_all(*args):
		#	self.window.services_treeview.expand_all()
		#	self.expanding = False
		#	return False
		#self.expanding = True
		#gobject.idle_add(expand_all)
		self.window.services_treeview.expand_all()

	def _update_progressbar(self):
		'''Update the progressbar.'''
		# Refresh this every update
		if self._progressbar_sourceid:
			gobject.source_remove(self._progressbar_sourceid)

		fraction = 0
		if self._total_items:
			self.window.progressbar.set_text(_("Scanning %(current)d / %(total)d.."
				) % {'current': self._progress, 'total': self._total_items})
			fraction = float(self._progress) / float(self._total_items)
			if self._progress >= self._total_items:
				# We show the progressbar for just a bit before hiding it.
				id_ = gobject.timeout_add_seconds(2, self._hide_progressbar_cb)
				self._progressbar_sourceid = id_
			else:
				self.window.progressbar.show()
				# Hide the progressbar if we're timing out anyways. (20 secs)
				id_ = gobject.timeout_add_seconds(20, self._hide_progressbar_cb)
				self._progressbar_sourceid = id_
		self.window.progressbar.set_fraction(fraction)

	def _hide_progressbar_cb(self, *args):
		'''Simple callback to hide the progressbar a second after we finish.'''
		if self.active:
			self.window.progressbar.hide()
		return False

	def _friendly_category(self, category, type_=None):
		'''Get the friendly category name and priority.'''
		cat = None
		if type_:
			# Try type-specific override
			try:
				cat, prio = _cat_to_descr[(category, type_)]
			except KeyError:
				pass
		if not cat:
			try:
				cat, prio = _cat_to_descr[category]
			except KeyError:
				cat, prio = _cat_to_descr['other']
		return cat, prio

	def _create_category(self, cat, type_=None):
		'''Creates a category row.'''
		cat, prio = self._friendly_category(cat, type_)
		return self.model.append(None, ('', '', None, cat, prio))

	def _find_category(self, cat, type_=None):
		'''Looks up a category row and returns the iterator to it, or None.'''
		cat = self._friendly_category(cat, type_)[0]
		iter_ = self.model.get_iter_root()
		while iter_:
			if self.model.get_value(iter_, 3).decode('utf-8') == cat:
				break
			iter_ = self.model.iter_next(iter_)
		if iter_:
			return iter_
		return None

	def _find_item(self, jid, node):
		iter_ = None
		cat_iter = self.model.get_iter_root()
		while cat_iter and not iter_:
			iter_ = self.model.iter_children(cat_iter)
			while iter_:
				cjid = self.model.get_value(iter_, 0).decode('utf-8')
				cnode = self.model.get_value(iter_, 1).decode('utf-8')
				if jid == cjid and node == cnode:
					break
				iter_ = self.model.iter_next(iter_)
			cat_iter = self.model.iter_next(cat_iter)
		if iter_:
			return iter_
		return None

	def _add_item(self, jid, node, item, force):
		# Row text
		addr = get_agent_address(jid, node)
		if 'name' in item:
			descr = "<b>%s</b>\n%s" % (item['name'], addr)
		else:
			descr = "<b>%s</b>" % addr
		# Guess which kind of service this is
		identities = []
		type_ = gajim.get_transport_name_from_jid(jid,
					use_config_setting = False)
		if type_:
			identity = {'category': '_jid', 'type': type_}
			identities.append(identity)
			cat_args = ('_jid', type_)
		else:
			# Put it in the 'other' category for now
			cat_args = ('other',)
		# Set the pixmap for the row
		pix = self.cache.get_icon(identities)
		# Put it in the right category
		cat = self._find_category(*cat_args)
		if not cat:
			cat = self._create_category(*cat_args)
		self.model.append(cat, (item['jid'], item.get('node', ''), pix, descr, 1))
		self._expand_all()
		# Grab info on the service
		self.cache.get_info(jid, node, self._agent_info, force = force)
		self._update_progressbar()

	def _update_item(self, iter_, jid, node, item):
		addr = get_agent_address(jid, node)
		if 'name' in item:
			descr = "<b>%s</b>\n%s" % (item['name'], addr)
		else:
			descr = "<b>%s</b>" % addr
		self.model[iter_][3] = descr

	def _update_info(self, iter_, jid, node, identities, features, data):
		addr = get_agent_address(jid, node)
		name = identities[0].get('name', '')
		if name:
			descr = "<b>%s</b>\n%s" % (name, addr)
		else:
			descr = "<b>%s</b>" % addr

		# Update progress
		self._progress += 1
		self._update_progressbar()

		# Search for an icon and category we can display
		pix = self.cache.get_icon(identities)
		for identity in identities:
			try:
				cat, type_ = identity['category'], identity['type']
			except KeyError:
				continue
			break

		# Check if we have to move categories
		old_cat_iter = self.model.iter_parent(iter_)
		old_cat = self.model.get_value(old_cat_iter, 3).decode('utf-8')
		if self.model.get_value(old_cat_iter, 3) == cat:
			# Already in the right category, just update
			self.model[iter_][2] = pix
			self.model[iter_][3] = descr
			self.model[iter_][4] = 0
			return
		# Not in the right category, move it.
		self.model.remove(iter_)

		# Check if the old category is empty
		if not self.model.iter_is_valid(old_cat_iter):
			old_cat_iter = self._find_category(old_cat)
		if not self.model.iter_children(old_cat_iter):
			self.model.remove(old_cat_iter)

		cat_iter = self._find_category(cat, type_)
		if not cat_iter:
			cat_iter = self._create_category(cat, type_)
		self.model.append(cat_iter, (jid, node, pix, descr, 0))
		self._expand_all()

	def _update_error(self, iter_, jid, node):
		self.model[iter_][4] = 2
		self._progress += 1
		self._update_progressbar()


class MucBrowser(AgentBrowser):
	def __init__(self, *args, **kwargs):
		AgentBrowser.__init__(self, *args, **kwargs)
		self.join_button = None

	def _create_treemodel(self):
		# JID, node, name, users_int, users_str, description, fetched
		# This is rather long, I'd rather not use a data_func here though.
		# Users is a string, because want to be able to leave it empty.
		self.model = gtk.ListStore(str, str, str, int, str, str, bool)
		self.model.set_sort_column_id(2, gtk.SORT_ASCENDING)
		self.window.services_treeview.set_model(self.model)
		# Name column
		col = gtk.TreeViewColumn(_('Name'))
		col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
		col.set_fixed_width(100)
		renderer = gtk.CellRendererText()
		col.pack_start(renderer)
		col.set_attributes(renderer, text = 2)
		col.set_sort_column_id(2)
		self.window.services_treeview.insert_column(col, -1)
		col.set_resizable(True)
		# Users column
		col = gtk.TreeViewColumn(_('Users'))
		renderer = gtk.CellRendererText()
		col.pack_start(renderer)
		col.set_attributes(renderer, text = 4)
		col.set_sort_column_id(3)
		self.window.services_treeview.insert_column(col, -1)
		col.set_resizable(True)
		# Description column
		col = gtk.TreeViewColumn(_('Description'))
		renderer = gtk.CellRendererText()
		col.pack_start(renderer)
		col.set_attributes(renderer, text = 5)
		col.set_sort_column_id(4)
		self.window.services_treeview.insert_column(col, -1)
		col.set_resizable(True)
		# Id column
		col = gtk.TreeViewColumn(_('Id'))
		renderer = gtk.CellRendererText()
		col.pack_start(renderer)
		col.set_attributes(renderer, text = 0)
		col.set_sort_column_id(0)
		self.window.services_treeview.insert_column(col, -1)
		col.set_resizable(True)
		self.window.services_treeview.set_headers_visible(True)
		self.window.services_treeview.set_headers_clickable(True)
		# Source id for idle callback used to start disco#info queries.
		self._fetch_source = None
		# Query failure counter
		self._broken = 0
		# Connect to scrollwindow scrolling
		self.vadj = self.window.services_scrollwin.get_property('vadjustment')
		self.vadj_cbid = self.vadj.connect('value-changed', self.on_scroll)
		# And to size changes
		self.size_cbid = self.window.services_scrollwin.connect(
			'size-allocate', self.on_scroll)

	def _clean_treemodel(self):
		if self.size_cbid:
			self.window.services_scrollwin.disconnect(self.size_cbid)
			self.size_cbid = None
		if self.vadj_cbid:
			self.vadj.disconnect(self.vadj_cbid)
			self.vadj_cbid = None
		AgentBrowser._clean_treemodel(self)

	def _add_actions(self):
		self.join_button = gtk.Button(label=_('_Join'), use_underline=True)
		self.join_button.connect('clicked', self.on_join_button_clicked)
		self.window.action_buttonbox.add(self.join_button)
		self.join_button.show_all()

	def _clean_actions(self):
		if self.join_button:
			self.join_button.destroy()
			self.join_button = None

	def on_join_button_clicked(self, *args):
		'''When we want to join a conference:
		Ask specific informations about the selected agent and close the window'''
		model, iter_ = self.window.services_treeview.get_selection().get_selected()
		if not iter_:
			return
		service = model[iter_][0].decode('utf-8')
		room = model[iter_][1].decode('utf-8')
		if 'join_gc' not in gajim.interface.instances[self.account]:
			try:
				dialogs.JoinGroupchatWindow(self.account, service)
			except GajimGeneralException:
				pass
		else:
			gajim.interface.instances[self.account]['join_gc'].window.present()
		self.window.destroy(chain = True)

	def update_actions(self):
		if self.join_button:
			sens = self.window.services_treeview.get_selection().count_selected_rows()
			self.join_button.set_sensitive(sens > 0)

	def default_action(self):
		self.on_join_button_clicked()

	def _start_info_query(self):
		'''Idle callback to start checking for visible rows.'''
		self._fetch_source = None
		self._query_visible()
		return False

	def on_scroll(self, *args):
		'''Scrollwindow callback to trigger new queries on scolling.'''
		# This apparently happens when inactive sometimes
		self._query_visible()

	def _query_visible(self):
		'''Query the next visible row for info.'''
		if self._fetch_source:
			# We're already fetching
			return
		view = self.window.services_treeview
		if not view.flags() & gtk.REALIZED:
			# Prevent a silly warning, try again in a bit.
			self._fetch_source = gobject.timeout_add(100, self._start_info_query)
			return
		# We have to do this in a pygtk <2.8 compatible way :/
		#start, end = self.window.services_treeview.get_visible_range()
		rect = view.get_visible_rect()
		iter_ = end = None
		# Top row
		try:
			sx, sy = view.tree_to_widget_coords(rect.x, rect.y)
			spath = view.get_path_at_pos(sx, sy)[0]
			iter_ = self.model.get_iter(spath)
		except TypeError:
			self._fetch_source = None
			return
		# Bottom row
		# Iter compare is broke, use the path instead
		try:
			ex, ey = view.tree_to_widget_coords(rect.x + rect.height,
				rect.y + rect.height)
			end = view.get_path_at_pos(ex, ey)[0]
			# end is the last visible, we want to query that aswell
			end = (end[0] + 1,)
		except TypeError:
			# We're at the end of the model, we can leave end=None though.
			pass
		while iter_ and self.model.get_path(iter_) != end:
			if not self.model.get_value(iter_, 6):
				jid = self.model.get_value(iter_, 0).decode('utf-8')
				node = self.model.get_value(iter_, 1).decode('utf-8')
				self.cache.get_info(jid, node, self._agent_info)
				self._fetch_source = True
				return
			iter_ = self.model.iter_next(iter_)
		self._fetch_source = None

	def _channel_altinfo(self, jid, node, items, name = None):
		'''Callback for the alternate disco#items query. We try to atleast get
		the amount of users in the room if the service does not support MUC
		dataforms.'''
		if items == 0:
			# The server returned an error
			self._broken += 1
			if self._broken >= 3:
				# Disable queries completely after 3 failures
				if self.size_cbid:
					self.window.services_scrollwin.disconnect(self.size_cbid)
					self.size_cbid = None
				if self.vadj_cbid:
					self.vadj.disconnect(self.vadj_cbid)
					self.vadj_cbid = None
				self._fetch_source = None
				return
		else:
			iter_ = self._find_item(jid, node)
			if iter_:
				if name:
					self.model[iter_][2] = name
				self.model[iter_][3] = len(items) # The number of users
				self.model[iter_][4] = str(len(items)) # The number of users
				self.model[iter_][6] = True
		self._fetch_source = None
		self._query_visible()

	def _add_item(self, jid, node, item, force):
		self.model.append((jid, node, item.get('name', ''), -1, '', '', False))
		if not self._fetch_source:
			self._fetch_source = gobject.idle_add(self._start_info_query)

	def _update_info(self, iter_, jid, node, identities, features, data):
		name = identities[0].get('name', '')
		for form in data:
			typefield = form.getField('FORM_TYPE')
			if typefield and typefield.getValue() == \
			'http://jabber.org/protocol/muc#roominfo':
				# Fill model row from the form's fields
				users = form.getField('muc#roominfo_occupants')
				descr = form.getField('muc#roominfo_description')
				if users:
					self.model[iter_][3] = int(users.getValue())
					self.model[iter_][4] = users.getValue()
				if descr:
					self.model[iter_][5] = descr.getValue()
				# Only set these when we find a form with additional info
				# Some servers don't support forms and put extra info in
				# the name attribute, so we preserve it in that case.
				self.model[iter_][2] = name
				self.model[iter_][6] = True
				break
		else:
			# We didn't find a form, switch to alternate query mode
			self.cache.get_items(jid, node, self._channel_altinfo, args = (name,))
			return
		# Continue with the next
		self._fetch_source = None
		self._query_visible()

	def _update_error(self, iter_, jid, node):
		# switch to alternate query mode
		self.cache.get_items(jid, node, self._channel_altinfo)

def PubSubBrowser(account, jid, node):
	''' Returns an AgentBrowser subclass that will display service discovery
	for particular pubsub service. Different pubsub services may need to
	present different data during browsing. '''
	# for now, only discussion groups are supported...
	# TODO: check if it has appropriate features to be such kind of service
	return DiscussionGroupsBrowser(account, jid, node)

class DiscussionGroupsBrowser(AgentBrowser):
	''' For browsing pubsub-based discussion groups service. '''
	def __init__(self, account, jid, node):
		AgentBrowser.__init__(self, account, jid, node)

		# this will become set object when we get subscriptions; None means
		# we don't know yet which groups are subscribed
		self.subscriptions = None

		# this will become our action widgets when we create them; None means
		# we don't have them yet (needed for check in callback)
		self.subscribe_button = None
		self.unsubscribe_button = None

		gajim.connections[account].send_pb_subscription_query(jid, self._subscriptionsCB)

	def _create_treemodel(self):
		''' Create treemodel for the window. '''
		# JID, node, name (with description) - pango markup, dont have info?, subscribed?
		self.model = gtk.TreeStore(str, str, str, bool, bool)
		# sort by name
		self.model.set_sort_column_id(2, gtk.SORT_ASCENDING)
		self.window.services_treeview.set_model(self.model)

		# Name column
		# Pango markup for name and description, description printed with
		# <small/> font
		renderer = gtk.CellRendererText()
		col = gtk.TreeViewColumn(_('Name'))
		col.pack_start(renderer)
		col.set_attributes(renderer, markup=2)
		col.set_resizable(True)
		self.window.services_treeview.insert_column(col, -1)
		self.window.services_treeview.set_headers_visible(True)

		# Subscription state
		renderer = gtk.CellRendererToggle()
		col = gtk.TreeViewColumn(_('Subscribed'))
		col.pack_start(renderer)
		col.set_attributes(renderer, inconsistent=3, active=4)
		col.set_resizable(False)
		self.window.services_treeview.insert_column(col, -1)

		# Node Column
		renderer = gtk.CellRendererText()
		col = gtk.TreeViewColumn(_('Node'))
		col.pack_start(renderer)
		col.set_attributes(renderer, markup=1)
		col.set_resizable(True)
		self.window.services_treeview.insert_column(col, -1)

	def _add_items(self, jid, node, items, force):
		for item in items:
			jid = item['jid']
			node = item.get('node', '')
			self._total_items += 1
			self._add_item(jid, node, item, force)

	def _in_list_foreach(self, model, path, iter_, node):
		if model[path][1] == node:
			self.in_list = True

	def _in_list(self, node):
		self.in_list = False
		self.model.foreach(self._in_list_foreach, node)
		return self.in_list

	def _add_item(self, jid, node, item, force):
		''' Called when we got basic information about new node from query.
		Show the item. '''
		name = item.get('name', '')

		if self.subscriptions is not None:
			dunno = False
			subscribed = node in self.subscriptions
		else:
			dunno = True
			subscribed = False

		name = gobject.markup_escape_text(name)
		name = '<b>%s</b>' % name

		node_splitted = node.split('/')
		parent_iter = None
		while len(node_splitted) > 1:
			parent_node = node_splitted.pop(0)
			parent_iter = self._get_child_iter(parent_iter, parent_node)
			node_splitted[0] = parent_node + '/' + node_splitted[0]
		if not self._in_list(node):
			self.model.append(parent_iter, (jid, node, name, dunno, subscribed))
			self.cache.get_items(jid, node, self._add_items, force = force,
				args = (force,))

	def _get_child_iter(self, parent_iter, node):
		child_iter = self.model.iter_children(parent_iter)
		while child_iter:
			if self.model[child_iter][1] == node:
				return child_iter
			child_iter = self.model.iter_next(child_iter)
		return None

	def _add_actions(self):
		self.post_button = gtk.Button(label=_('New post'), use_underline=True)
		self.post_button.set_sensitive(False)
		self.post_button.connect('clicked', self.on_post_button_clicked)
		self.window.action_buttonbox.add(self.post_button)
		self.post_button.show_all()

		self.subscribe_button = gtk.Button(label=_('_Subscribe'), use_underline=True)
		self.subscribe_button.set_sensitive(False)
		self.subscribe_button.connect('clicked', self.on_subscribe_button_clicked)
		self.window.action_buttonbox.add(self.subscribe_button)
		self.subscribe_button.show_all()

		self.unsubscribe_button = gtk.Button(label=_('_Unsubscribe'), use_underline=True)
		self.unsubscribe_button.set_sensitive(False)
		self.unsubscribe_button.connect('clicked', self.on_unsubscribe_button_clicked)
		self.window.action_buttonbox.add(self.unsubscribe_button)
		self.unsubscribe_button.show_all()

	def _clean_actions(self):
		if self.post_button is not None:
			self.post_button.destroy()
			self.post_button = None

		if self.subscribe_button is not None:
			self.subscribe_button.destroy()
			self.subscribe_button = None

		if self.unsubscribe_button is not None:
			self.unsubscribe_button.destroy()
			self.unsubscribe_button = None

	def update_actions(self):
		'''Called when user selected a row. Make subscribe/unsubscribe buttons
		sensitive appropriatelly.'''
		# we have nothing to do if we don't have buttons...
		if self.subscribe_button is None: return

		model, iter_ = self.window.services_treeview.get_selection().get_selected()
		if not iter_ or self.subscriptions is None:
			# no item selected or no subscriptions info, all buttons are insensitive
			self.post_button.set_sensitive(False)
			self.subscribe_button.set_sensitive(False)
			self.unsubscribe_button.set_sensitive(False)
		else:
			subscribed = model.get_value(iter_, 4) # 4 = subscribed?
			self.post_button.set_sensitive(subscribed)
			self.subscribe_button.set_sensitive(not subscribed)
			self.unsubscribe_button.set_sensitive(subscribed)

	def on_post_button_clicked(self, widget):
		'''Called when 'post' button is pressed. Open window to create post'''
		model, iter_ = self.window.services_treeview.get_selection().get_selected()
		if iter_ is None: return

		groupnode = model.get_value(iter_, 1)	# 1 = groupnode

		groups.GroupsPostWindow(self.account, self.jid, groupnode)

	def on_subscribe_button_clicked(self, widget):
		'''Called when 'subscribe' button is pressed. Send subscribtion request.'''
		model, iter_ = self.window.services_treeview.get_selection().get_selected()
		if iter_ is None: return

		groupnode = model.get_value(iter_, 1)	# 1 = groupnode

		gajim.connections[self.account].send_pb_subscribe(self.jid, groupnode, self._subscribeCB, groupnode)

	def on_unsubscribe_button_clicked(self, widget):
		'''Called when 'unsubscribe' button is pressed. Send unsubscription request.'''
		model, iter_ = self.window.services_treeview.get_selection().get_selected()
		if iter_ is None: return

		groupnode = model.get_value(iter_, 1) # 1 = groupnode

		gajim.connections[self.account].send_pb_unsubscribe(self.jid, groupnode, self._unsubscribeCB, groupnode)

	def _subscriptionsCB(self, conn, request):
		''' We got the subscribed groups list stanza. Now, if we already
		have items on the list, we should actualize them. '''
		try:
			subscriptions = request.getTag('pubsub').getTag('subscriptions')
		except Exception:
			return

		groups = set()
		for child in subscriptions.getTags('subscription'):
			groups.add(child['node'])

		self.subscriptions = groups

		# try to setup existing items in model
		model = self.window.services_treeview.get_model()
		for row in model:
			# 1 = group node
			# 3 = insensitive checkbox for subscribed
			# 4 = subscribed?
			groupnode = row[1]
			row[3]=False
			row[4]=groupnode in groups

		# we now know subscriptions, update button states
		self.update_actions()

		raise xmpp.NodeProcessed

	def _subscribeCB(self, conn, request, groupnode):
		'''We have just subscribed to a node. Update UI'''
		self.subscriptions.add(groupnode)

		model = self.window.services_treeview.get_model()
		for row in model:
			if row[1] == groupnode: # 1 = groupnode
				row[4]=True
				break

		self.update_actions()

		raise xmpp.NodeProcessed

	def _unsubscribeCB(self, conn, request, groupnode):
		'''We have just unsubscribed from a node. Update UI'''
		self.subscriptions.remove(groupnode)

		model = self.window.services_treeview.get_model()
		for row in model:
			if row[1] == groupnode: # 1 = groupnode
				row[4]=False
				break

		self.update_actions()

		raise xmpp.NodeProcessed

# Fill the global agent type info dictionary
_agent_type_info = _gen_agent_type_info()

# vim: se ts=3:
