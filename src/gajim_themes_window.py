##	gajim_themes_window.py
##
## Gajim Team:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Vincent Hanquez <tab@snarc.org>
##	- Nikos Kouremenos <kourem@gmail.com>
##	- Dimitur Kirov <dkirov@gmail.com>
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
import pango
import dialogs
from config import mk_color_string

from common import gajim
from common import i18n
_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain (APP, i18n.DIR)
gtk.glade.textdomain (APP)

GTKGUI_GLADE = 'gtkgui.glade'

class GajimThemesWindow:

	def __init__(self):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'gajim_themes_window', APP)
		self.window = self.xml.get_widget('gajim_themes_window')
		
		self.options = ['account', 'group', 'contact', 'banner', 'lastmessage']
		self.options_combobox = self.xml.get_widget('options_combobox')
		self.textcolor_checkbutton = self.xml.get_widget('textcolor_checkbutton')
		self.background_checkbutton = self.xml.get_widget('background_checkbutton')
		self.textfont_checkbutton = self.xml.get_widget('textfont_checkbutton')
		self.text_colorbutton = self.xml.get_widget('text_colorbutton')
		self.background_colorbutton = self.xml.get_widget('background_colorbutton')
		self.text_fontbutton = self.xml.get_widget('text_fontbutton')
		self.bold_togglebutton = self.xml.get_widget('bold_togglebutton')
		self.italic_togglebutton = self.xml.get_widget('italic_togglebutton')
		self.underline_togglebutton = self.xml.get_widget('underline_togglebutton')
		self.themes_tree = self.xml.get_widget('themes_treeview')
		self.theme_options_vbox = self.xml.get_widget('theme_options_vbox')
		model = gtk.ListStore(str)
		self.themes_tree.set_model(model)
		col = gtk.TreeViewColumn(_('Theme'))
		self.themes_tree.append_column(col)
		renderer = gtk.CellRendererText()
		col.pack_start(renderer, True)
		col.set_attributes(renderer, text = 0)
		renderer.connect('edited', self.on_theme_cell_edited)
		renderer.set_property('editable', True)
		self.current_theme = gajim.config.get('roster_theme')
		self.no_update = False
		self.fill_themes_treeview()
		self.current_option = self.options[0]
		self.set_theme_options(self.current_theme, self.current_option)
		
		self.xml.signal_autoconnect(self)
		self.themes_tree.get_selection().connect('changed', 
				self.selection_changed)
		self.window.show_all()

	def on_close_button_clicked(self, widget):
		self.window.destroy()

	def on_theme_cell_edited(self, cell, row, new_name):
		model = self.themes_tree.get_model()
		iter = model.get_iter_from_string(row)
		old_name = model.get_value(iter, 0).decode('utf-8')
		new_name = new_name.decode('utf-8')
		if old_name == new_name:
			return
		new_config_name = new_name.replace(' ', '_')
		if new_config_name in gajim.config.get_per('themes'):
			return
		gajim.config.add_per('themes', new_config_name)
		# Copy old theme values
		old_config_name = old_name.replace(' ', '_')
		properties = ['textcolor', 'bgcolor', 'font', 'fontattrs']
		gajim.config.add_per('themes', new_config_name)
		for option in self.options:
			for property in properties:
				option_name = option + property
				gajim.config.set_per('themes', new_config_name, option_name,
					gajim.config.get_per('themes', old_config_name, option_name))
		gajim.config.del_per('themes', old_config_name)
		if old_config_name == gajim.config.get('roster_theme'):
			gajim.config.set('roster_theme', new_config_name)
		model.set_value(iter, 0, new_name)
		self.current_theme = new_name
		gajim.interface.windows['preferences'].update_preferences_window()

	def fill_themes_treeview(self):
		self.xml.get_widget('remove_button').set_sensitive(False)
		self.theme_options_vbox.set_sensitive(False)
		model = self.themes_tree.get_model()
		model.clear()
		for config_theme in gajim.config.get_per('themes'):
			theme = config_theme.replace('_', ' ')
			iter = model.append([theme])
			if gajim.config.get('roster_theme') == config_theme:
				self.themes_tree.get_selection().select_iter(iter)
				self.xml.get_widget('remove_button').set_sensitive(True)
				self.theme_options_vbox.set_sensitive(True)
	
	def selection_changed(self, widget = None):
		(model, iter) = self.themes_tree.get_selection().get_selected()
		selected = self.themes_tree.get_selection().get_selected_rows()
		if not iter or selected[1] == []:
			self.theme_options_vbox.set_sensitive(False)
			return
		self.xml.get_widget('remove_button').set_sensitive(True)
		self.theme_options_vbox.set_sensitive(True)
		self.current_theme = model.get_value(iter, 0).decode('utf-8')
		self.current_theme = self.current_theme.replace(' ', '_')
		self.set_theme_options(self.current_theme)

	def on_add_button_clicked(self, widget):
		model = self.themes_tree.get_model()
		iter = model.append()
		i = 0
		# don't confuse translators
		theme_name = _('theme name')
		theme_name_ns = theme_name.replace(' ', '_')
		while theme_name_ns + unicode(i) in gajim.config.get_per('themes'):
			i += 1
		model.set_value(iter, 0, theme_name + unicode(i))
		gajim.config.add_per('themes', theme_name_ns + unicode(i))
		self.themes_tree.get_selection().select_iter(iter)
		col = self.themes_tree.get_column(0)
		path = model.get_path(iter)
		self.themes_tree.set_cursor(path, col, True)
		gajim.interface.windows['preferences'].update_preferences_window()

	def on_remove_button_clicked(self, widget):
		(model, iter) = self.themes_tree.get_selection().get_selected()
		if not iter:
			return
		if self.current_theme == gajim.config.get('roster_theme'):
			dialogs.ErrorDialog(
				_('You cannot delete your current theme')).get_response()
			return
		self.theme_options_vbox.set_sensitive(False)
		gajim.config.del_per('themes', self.current_theme)
		model.remove(iter)
		gajim.interface.windows['preferences'].update_preferences_window()
	
	def set_theme_options(self, theme, option = 'account'):
		self.no_update = True
		self.options_combobox.set_active(self.options.index(option))
		textcolor = gajim.config.get_per('themes', theme, 
			option + 'textcolor')
		if textcolor:
			state = True
			self.text_colorbutton.set_color(gtk.gdk.color_parse(textcolor))
		else:
			state = False
		self.textcolor_checkbutton.set_active(state)
		self.text_colorbutton.set_sensitive(state)
		bgcolor = gajim.config.get_per('themes', theme, option + 'bgcolor')
		if bgcolor:
			state = True
			self.background_colorbutton.set_color(gtk.gdk.color_parse(
				bgcolor))
		else:
			state = False
		self.background_checkbutton.set_active(state)
		self.background_colorbutton.set_sensitive(state)
		
		#get the font name before we set widgets and it will not be overriden
		font_name = gajim.config.get_per('themes', theme, option + 'font')
		font_attrs = gajim.config.get_per('themes', theme, option + 'fontattrs')
		self._set_font_widgets(font_attrs)
		if font_name:
			state = True
			self.text_fontbutton.set_font_name(font_name)
		else:
			state = False
		self.textfont_checkbutton.set_active(state)
		self.text_fontbutton.set_sensitive(state)
		self.no_update = False
		gajim.interface.roster.change_roster_style(None)
		
	def on_textcolor_checkbutton_toggled(self, widget):
		state = widget.get_active()
		self.text_colorbutton.set_sensitive(state)
		self._set_color(state, self.text_colorbutton, 
			'textcolor')
	
	def on_background_checkbutton_toggled(self, widget):
		state = widget.get_active()
		self.background_colorbutton.set_sensitive(state)
		self._set_color(state, self.background_colorbutton, 
			'bgcolor')
		
	def on_textfont_checkbutton_toggled(self, widget):
		self.text_fontbutton.set_sensitive(widget.get_active())
		self._set_font()
	
	def on_text_colorbutton_color_set(self, widget):
		self._set_color(True, widget, 'textcolor')
			
	def on_background_colorbutton_color_set(self, widget):
		self._set_color(True, widget, 'bgcolor')
	
	def on_text_fontbutton_font_set(self, widget):
		self._set_font()
	
	def on_options_combobox_changed(self, widget):
		index = self.options_combobox.get_active()
		if index == -1:
			return
		self.current_option = self.options[index]
		self.set_theme_options(self.current_theme,
			self.current_option)
		
	def on_bold_togglebutton_toggled(self, widget):
		self._set_font()
	
	def on_italic_togglebutton_toggled(self, widget):
		self._set_font()
	
	def on_underline_togglebutton_toggled(self, widget):
		self._set_font()
	
	def _set_color(self, state, widget, option):
		''' set color value in prefs and update the UI '''
		if state:
			color = widget.get_color()
			color_string = mk_color_string(color)
		else:
			color_string = ''
		gajim.config.set_per('themes', self.current_theme, 
			self.current_option + option, color_string)
		# use faster functions for this
		if self.current_option == 'banner':
			gajim.interface.roster.repaint_themed_widgets()
			gajim.interface.save_config()
			return
		if self.no_update:
			return
		gajim.interface.roster.change_roster_style(self.current_option)
		gajim.interface.save_config()
		
	def _set_font(self):
		''' set font value in prefs and update the UI '''
		state = self.textfont_checkbutton.get_active()
		if state:
			font_string = self.text_fontbutton.get_font_name()
		else:
			font_string = ''
		gajim.config.set_per('themes', self.current_theme, 
			self.current_option + 'font', font_string)
		font_attrs = self._get_font_attrs()
		gajim.config.set_per('themes', self.current_theme, 
			self.current_option + 'fontattrs', font_attrs)
		# use faster functions for this
		if self.current_option == 'banner':
			gajim.interface.roster.repaint_themed_widgets()
		if self.no_update:
			return
		gajim.interface.roster.change_roster_style(self.current_option)
		gajim.interface.save_config()
	
	def _toggle_font_widgets(self, font_props):
		''' toggle font buttons with the bool values of font_props tuple'''
		self.bold_togglebutton.set_active(font_props[0])
		self.italic_togglebutton.set_active(font_props[1])
		self.underline_togglebutton.set_active(font_props[2])
	
	def _get_font_description(self):
		''' return a FontDescription from togglebuttons 
		states'''
		fd = pango.FontDescription()
		if self.bold_togglebutton.get_active():
			fd.set_weight(pango.WEIGHT_BOLD)
		if self.italic_togglebutton.get_active():
			fd.set_style(pango.STYLE_ITALIC)
		return fd
		
	def _set_font_widgets(self, font_attrs):
		''' set the correct toggle state of font style buttons by
		a font string of type 'BIU' '''
		font_props = [False, False, False]
		if font_attrs:
			if font_attrs.find('B') != -1:
				font_props[0] = True
			if font_attrs.find('I') != -1:
				font_props[1] = True
			if font_attrs.find('U') != -1:
				font_props[2] = True
		self._toggle_font_widgets(font_props)
		
	def _get_font_attrs(self):
		''' get a string with letters of font attribures: 'BUI' '''
		attrs = ''
		if self.bold_togglebutton.get_active():
			attrs += 'B'
		if self.italic_togglebutton.get_active():
			attrs += 'I'
		if self.underline_togglebutton.get_active():
			attrs += 'U'
		return attrs
		

	def _get_font_props(self, font_name):
		''' get tuple of font properties: Weight, Style, Underline '''
		font_props = [False, False, False]
		font_description = pango.FontDescription(font_name)
		if font_description.get_weight() != pango.WEIGHT_NORMAL:
			font_props[0] = True
		if font_description.get_style() != pango.STYLE_ITALIC:
			font_props[1] = True
		return font_props
