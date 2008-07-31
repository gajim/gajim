# -*- coding: utf-8 -*-

## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim.  If not, see <http://www.gnu.org/licenses/>.
##

'''
Adjustable chat window banner.

Includes tweaks to make it compact.

Based on patch by pb in ticket  #4133:
http://trac.gajim.org/attachment/ticket/4133/gajim-chatbanneroptions-svn10008.patch

:author: Mateusz Biliński <mateusz@bilinski.it>
:since: 30 July 2008
:copyright: Copyright (2008) Mateusz Biliński <mateusz@bilinski.it>
:license: GPL
'''

import sys

import gtk
from common import i18n
from common import gajim

from plugins import GajimPlugin
from plugins.helpers import log, log_calls
from plugins.gui import GajimPluginConfigDialog

class BannerTweaksPlugin(GajimPlugin):
	name = u'Banner Tweaks'
	short_name = u'banner_tweaks'
	version = u'0.1'
	description = u'''Allows user to tweak chat window banner appearance (eg. make it compact).
	
Based on patch by pb in ticket #4133: 
http://trac.gajim.org/attachment/ticket/4133'''
	authors = [u'Mateusz Biliński <mateusz@bilinski.it>']
	homepage = u'http://blog.bilinski.it'
	
	@log_calls('BannerTweaksPlugin')
	def init(self):
		self.config_dialog = BannerTweaksPluginConfigDialog(self)
		
		self.gui_extension_points = {
			'chat_control_base_draw_banner' : (self.chat_control_base_draw_banner_called,
											   self.chat_control_base_draw_banner_deactivation)
		}
		
		self.config_default_values = {'show_banner_image': (True, _('If True, Gajim will display a status icon in the banner of chat windows.')),
									  'show_banner_online_msg': (True, _('If True, Gajim will display the status message of the contact in the banner of chat windows.')),
									  'show_banner_resource': (False, _('If True, Gajim will display the resource name of the contact in the banner of chat windows.')),
									  'banner_small_fonts': (False, _('If True, Gajim will use small fonts for contact name and resource name in the banner of chat windows.')),
									  'old_chat_avatar_height' : (52, _('chat_avatar_height value before plugin was activated')),
									  }
		
	def activate(self):
		self.config['old_chat_avatar_height'] = gajim.config.get('chat_avatar_height')
		#gajim.config.set('chat_avatar_height', 28)
		
	def deactivate(self):
		gajim.config.set('chat_avatar_height', self.config['old_chat_avatar_height'])
		
	def chat_control_base_draw_banner_called(self, chat_control):
		if not self.config['show_banner_online_msg']:
			chat_control.banner_status_label.hide()
			chat_control.banner_status_label.set_no_show_all(True)
			status_text = ''
			chat_control.banner_status_label.set_markup(status_text)
			
		if not self.config['show_banner_image']:
			banner_status_img = chat_control.xml.get_widget('banner_status_image')
			banner_status_img.clear()
			
	def chat_control_base_draw_banner_deactivation(self, chat_control):
		pass
		#chat_control.draw_banner()
		
	#@log_calls('BannerTweaksPlugin')
	#def connect_with_chat_control(self, chat_control):
		#d = {}
		#banner_status_img = chat_control.xml.get_widget('banner_status_image')
		#h_id = banner_status_img.connect('state-changed', self.on_banner_status_img_state_changed, chat_control)
		#d['banner_img_h_id'] = h_id
		
		#chat_control.banner_tweaks_plugin_data = d
	
	#@log_calls('BannerTweaksPlugin')
	#def disconnect_from_chat_control(self, chat_control):
		#pass
	
class BannerTweaksPluginConfigDialog(GajimPluginConfigDialog):
	def init(self):
		self.GLADE_FILE_PATH = self.plugin.local_file_path('config_dialog.glade')
		self.xml = gtk.glade.XML(self.GLADE_FILE_PATH, root='banner_tweaks_config_vbox', domain=i18n.APP)
		self.config_vbox = self.xml.get_widget('banner_tweaks_config_vbox')
		self.child.pack_start(self.config_vbox)
		
		self.show_banner_image_checkbutton = self.xml.get_widget('show_banner_image_checkbutton')
		self.show_banner_online_msg_checkbutton = self.xml.get_widget('show_banner_online_msg_checkbutton')
		self.show_banner_resource_checkbutton = self.xml.get_widget('show_banner_resource_checkbutton')
		self.banner_small_fonts_checkbutton = self.xml.get_widget('banner_small_fonts_checkbutton')
		
		self.xml.signal_autoconnect(self)
	
	def on_run(self):
		self.show_banner_image_checkbutton.set_active(self.plugin.config['show_banner_image'])
		self.show_banner_online_msg_checkbutton.set_active(self.plugin.config['show_banner_online_msg'])
		self.show_banner_resource_checkbutton.set_active(self.plugin.config['show_banner_resource'])
		self.banner_small_fonts_checkbutton.set_active(self.plugin.config['banner_small_fonts'])

	def on_show_banner_image_checkbutton_toggled(self, button):
		self.plugin.config['show_banner_image'] = button.get_active()
	
	def on_show_banner_online_msg_checkbutton_toggled(self, button):
		self.plugin.config['show_banner_online_msg'] = button.get_active()
	
	def on_show_banner_resource_checkbutton_toggled(self, button):
		self.plugin.config['show_banner_resource'] = button.get_active()
	
	def on_banner_small_fonts_checkbutton_toggled(self, button):
		self.plugin.config['banner_small_fonts'] = button.get_active()
	