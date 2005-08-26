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
from config import mk_color_string

from common import gajim
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
		
		self.xml.get_widget('banner_text_fontbutton').set_no_show_all(True)
		
		self.color_widgets = {
			'account_text_colorbutton': 'accounttextcolor',
			'group_text_colorbutton': 'grouptextcolor',
			'user_text_colorbutton': 'contacttextcolor',
			'banner_colorbutton': 'bannertextcolor',
			'account_text_bg_colorbutton': 'accountbgcolor',
			'group_text_bg_colorbutton': 'groupbgcolor',
			'user_text_bg_colorbutton': 'contactbgcolor',
			'banner_bg_colorbutton': 'bannerbgcolor',
		}
		self.font_widgets = {
			'account_text_fontbutton': 'accountfont',
			'group_text_fontbutton': 'groupfont',
			'user_text_fontbutton': 'contactfont',
		}

		self.themes_tree = self.xml.get_widget('themes_treeview')
		model = gtk.ListStore(str)
		self.themes_tree.set_model(model)
		col = gtk.TreeViewColumn(_('Theme'))
		self.themes_tree.append_column(col)
		renderer = gtk.CellRendererText()
		col.pack_start(renderer, True)
		col.set_attributes(renderer, text = 0)
		renderer.connect('edited', self.on_theme_cell_edited)
		renderer.set_property('editable', True)
		self.fill_themes_treeview()
		
		
		self.current_theme = gajim.config.get('roster_theme')
		self.set_widgets(self.current_theme)

		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def on_theme_cell_edited(self, cell, row, new_name):
		model = self.themes_tree.get_model()
		iter = model.get_iter_from_string(row)
		old_name = model.get_value(iter, 0).decode('utf-8')
		if old_name == new_name:
			return
		if new_name in gajim.config.get_per('themes'):
			#ErrorDialog()
			return
		gajim.config.add_per('themes', new_name)
		#Copy old theme values
		for option in self.color_widgets.values():
			gajim.config.set_per('themes', new_name, option,
				gajim.config.get_per('themes', old_name, option))
		for option in self.font_widgets.values():
			gajim.config.set_per('themes', new_name, option,
				gajim.config.get_per('themes', old_name, option))
		gajim.config.del_per('themes', old_name)
		model.set_value(iter, 0, new_name)
		self.plugin.windows['preferences'].update_preferences_window()

	def fill_themes_treeview(self):
		self.xml.get_widget('remove_button').set_sensitive(False)
		self.xml.get_widget('fonts_colors_table').set_sensitive(False)
		model = self.themes_tree.get_model()
		model.clear()
		for theme in gajim.config.get_per('themes'):
			iter = model.append([theme])
			if gajim.config.get('roster_theme') == theme:
				self.themes_tree.get_selection().select_iter(iter)
				self.xml.get_widget('remove_button').set_sensitive(True)
				self.xml.get_widget('fonts_colors_table').set_sensitive(True)
	
	def on_themes_treeview_cursor_changed(self, widget):
		(model, iter) = self.themes_tree.get_selection().get_selected()
		if not iter:
			return
		self.xml.get_widget('remove_button').set_sensitive(True)
		self.xml.get_widget('fonts_colors_table').set_sensitive(True)
		self.current_theme = model.get_value(iter, 0).decode('utf-8')
		self.set_widgets(self.current_theme)

	def on_add_button_clicked(self, widget):
		model = self.themes_tree.get_model()
		iter = model.append()
		i = 0
		while _('theme name') + unicode(i) in gajim.config.get_per('themes'):
			i += 1
		model.set_value(iter, 0, _('theme name') + unicode(i))
		gajim.config.add_per('themes', _('theme_name') + unicode(i))
		self.plugin.windows['preferences'].update_preferences_window()

	def on_remove_button_clicked(self, widget):
		(model, iter) = self.themes_tree.get_selection().get_selected()
		if not iter:
			return
		name = model.get_value(iter, 0).decode('utf-8')
		gajim.config.del_per('themes', name)
		model.remove(iter)
		self.plugin.windows['preferences'].update_preferences_window()

	def set_widgets(self, theme):
		for w in self.color_widgets:
			widg = self.xml.get_widget(w)
			widg.set_color(gtk.gdk.color_parse(gajim.config.get_per('themes',
				theme, self.color_widgets[w])))
		for w in self.font_widgets:
			widg = self.xml.get_widget(w)
			widg.set_font_name(gajim.config.get_per('themes', theme,
				self.font_widgets[w]))
	
	def on_roster_widget_color_set(self, widget, option):
		color = widget.get_color()
		color_string = mk_color_string(color)
		gajim.config.set_per('themes', self.current_theme, option, color_string)
		self.plugin.roster.repaint_themed_widgets()
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
	
	def on_banner_text_colorbutton_color_set(self, widget):
		self.on_roster_widget_color_set(widget, 'bannertextcolor')
	
	def on_banner_bg_colorbutton_color_set(self, widget):
		self.on_roster_widget_color_set(widget, 'bannerbgcolor')
	
	def on_widget_font_set(self, widget, option):
		font_string = widget.get_font_name()
		gajim.config.set_per('themes', self.current_theme, option, font_string)
		self.plugin.roster.draw_roster()
		self.plugin.save_config()

	def on_account_text_fontbutton_font_set(self, widget):
		self.on_widget_font_set(widget, 'accountfont')

	def on_group_text_fontbutton_font_set(self, widget):
		self.on_widget_font_set(widget, 'groupfont')
	
	def on_user_text_fontbutton_font_set(self, widget):
		self.on_widget_font_set(widget, 'contactfont')
