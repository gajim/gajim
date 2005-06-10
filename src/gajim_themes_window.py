##	dialogs.py
##
## Gajim Team:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Vincent Hanquez <tab@snarc.org>
##	- Nikos Kouremenos <kourem@gmail.com>
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

from common import i18n
_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain (APP, i18n.DIR)
gtk.glade.textdomain (APP)

GTKGUI_GLADE = 'gtkgui.glade'

class GajimThemesWindow:
	def on_close_button_clicked(self, widget):
		self.window.destroy()

	def __init__(self, plugin):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'gajim_themes_window', APP)
		self.window = self.xml.get_widget('gajim_themes_window')
		self.plugin = plugin
		self.xml.signal_autoconnect(self)
		self.window.show_all()
		
		
		color_widgets = {
			'account_text_colorbutton': 'accounttextcolor',
			'group_text_colorbutton': 'grouptextcolor',
			'user_text_colorbutton': 'contacttextcolor',
			'account_text_bg_colorbutton': 'accountbgcolor',
			'group_text_bg_colorbutton': 'groupbgcolor',
			'user_text_bg_colorbutton': 'contactbgcolor'
		}
		font_widgets = {
			'account_text_fontbutton': 'accountfont',
			'group_text_fontbutton': 'groupfont',
			'user_text_fontbutton': 'userfont'
		}
		
		'''
		fonts_colors_table = self.xml.get_widget('fonts_colors_table')
		if theme == 'custom':
			fonts_colors_table.show()
		else:
			fonts_colors_table.hide()
		for w in color_widgets:
			widg = self.xml.get_widget(w)
			if theme == 'custom':
				widg.set_color(gtk.gdk.color_parse(gajim.config.get(
					color_widgets[w])))
			else:
				widg.set_color(gtk.gdk.color_parse(self.theme_default[theme]\
					[color_widgets[w]]))
				self.on_roster_widget_color_set(widg, color_widgets[w])
		for w in font_widgets:
			widg = self.xml.get_widget(w)
			if theme == 'custom':
				widg.set_font_name(gajim.config.get(font_widgets[w]))
			else:
				widg.set_font_name(self.theme_default[theme][font_widgets[w]])
				self.on_widget_font_set(widg, font_widgets[w])
		'''
	
	def on_roster_widget_color_set(self, widget, text):
		color = widget.get_color()
		color_string = mk_color_string(color)
		gajim.config.set(text, color_string)
		self.plugin.roster.draw_roster()
		self.plugin.save_config()
	
	def on_account_text_colorbutton_color_set(self, widget):
		self.on_roster_widget_color_set(widget, 'accounttextcolor')
	
	def on_group_text_colorbutton_color_set(self, widget):
		self.on_roster_widget_color_set(widget, 'grouptextcolor')

	def on_user_text_colorbutton_color_set(self, widget):
		self.on_roster_widget_color_set(widget, 'contacttextcolor')

	def on_account_text_bg_colorbutton_color_set(self, widget):
		self.on_roster_widget_color_set(widget, 'accountbgcolor')
	
	def on_group_text_bg_colorbutton_color_set(self, widget):
		self.on_roster_widget_color_set(widget, 'groupbgcolor')
	
	def on_user_text_bg_colorbutton_color_set(self, widget):
		self.on_roster_widget_color_set(widget, 'contactbgcolor')
	
	def on_widget_font_set(self, widget, text):
		font_string = widget.get_font_name()
		gajim.config.set(text, font_string)
		self.plugin.roster.draw_roster()
		self.plugin.save_config()

	def on_account_text_fontbutton_font_set(self, widget):
		self.on_widget_font_set(widget, 'accountfont')

	def on_group_text_fontbutton_font_set(self, widget):
		self.on_widget_font_set(widget, 'groupfont')
	
	def on_user_text_fontbutton_font_set(self, widget):
		self.on_widget_font_set(widget, 'userfont')
