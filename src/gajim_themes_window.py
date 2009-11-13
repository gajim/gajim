# -*- coding:utf-8 -*-
## src/gajim_themes_window.py
##
## Copyright (C) 2003-2007 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
##                         Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006 Jean-Marie Traissard <jim AT lapin.org>
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

import gtk
import pango
import dialogs
import gtkgui_helpers

from common import gajim

class GajimThemesWindow:

	def __init__(self):
		self.xml = gtkgui_helpers.get_glade('gajim_themes_window.glade')
		self.window = self.xml.get_widget('gajim_themes_window')
		self.window.set_transient_for(gajim.interface.roster.window)

		self.options = ['account', 'group', 'contact', 'banner']
		self.options_combobox = self.xml.get_widget('options_combobox')
		self.textcolor_checkbutton = self.xml.get_widget('textcolor_checkbutton')
		self.background_checkbutton = self.xml.get_widget('background_checkbutton')
		self.textfont_checkbutton = self.xml.get_widget('textfont_checkbutton')
		self.text_colorbutton = self.xml.get_widget('text_colorbutton')
		self.background_colorbutton = self.xml.get_widget('background_colorbutton')
		self.text_fontbutton = self.xml.get_widget('text_fontbutton')
		self.bold_togglebutton = self.xml.get_widget('bold_togglebutton')
		self.italic_togglebutton = self.xml.get_widget('italic_togglebutton')
		self.themes_tree = self.xml.get_widget('themes_treeview')
		self.theme_options_vbox = self.xml.get_widget('theme_options_vbox')
		self.theme_options_table = self.xml.get_widget('theme_options_table')
		self.colorbuttons = {}
		for chatstate in ('inactive', 'composing', 'paused', 'gone',
		'muc_msg', 'muc_directed_msg'):
			self.colorbuttons[chatstate] = self.xml.get_widget(chatstate + \
				'_colorbutton')
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
		self.select_active_theme()
		self.current_option = self.options[0]
		self.set_theme_options(self.current_theme, self.current_option)

		self.xml.signal_autoconnect(self)
		self.window.connect('delete-event', self.on_themese_window_delete_event)
		self.themes_tree.get_selection().connect('changed',
				self.selection_changed)
		self.window.show_all()

	def on_themese_window_delete_event(self, widget, event):
		self.window.hide()
		return True # do NOT destroy the window

	def on_close_button_clicked(self, widget):
		if 'preferences' in gajim.interface.instances:
			gajim.interface.instances['preferences'].update_theme_list()
		self.window.hide()

	def on_theme_cell_edited(self, cell, row, new_name):
		model = self.themes_tree.get_model()
		iter_ = model.get_iter_from_string(row)
		old_name = model.get_value(iter_, 0).decode('utf-8')
		new_name = new_name.decode('utf-8')
		if old_name == new_name:
			return
		if old_name == 'default':
			dialogs.ErrorDialog(
				_('You cannot make changes to the default theme'),
			_('Please create a clean new theme with your desired name.'))
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
			for property_ in properties:
				option_name = option + property_
				gajim.config.set_per('themes', new_config_name, option_name,
					gajim.config.get_per('themes', old_config_name, option_name))
		gajim.config.del_per('themes', old_config_name)
		if old_config_name == gajim.config.get('roster_theme'):
			gajim.config.set('roster_theme', new_config_name)
		model.set_value(iter_, 0, new_name)
		self.current_theme = new_name

	def fill_themes_treeview(self):
		model = self.themes_tree.get_model()
		model.clear()
		for config_theme in gajim.config.get_per('themes'):
			theme = config_theme.replace('_', ' ')
			model.append([theme])

	def select_active_theme(self):
		model = self.themes_tree.get_model()
		iter_ = model.get_iter_root()
		active_theme = gajim.config.get('roster_theme').replace('_', ' ')
		while iter_:
			theme = model[iter_][0]
			if theme == active_theme:
				self.themes_tree.get_selection().select_iter(iter_)
				if active_theme == 'default':
					self.xml.get_widget('remove_button').set_sensitive(False)
					self.theme_options_vbox.set_sensitive(False)
					self.theme_options_table.set_sensitive(False)
				else:
					self.xml.get_widget('remove_button').set_sensitive(True)
					self.theme_options_vbox.set_sensitive(True)
					self.theme_options_table.set_sensitive(True)
				break
			iter_ = model.iter_next(iter_)

	def selection_changed(self, widget = None):
		(model, iter_) = self.themes_tree.get_selection().get_selected()
		selected = self.themes_tree.get_selection().get_selected_rows()
		if not iter_ or selected[1] == []:
			self.theme_options_vbox.set_sensitive(False)
			self.theme_options_table.set_sensitive(False)
			return
		self.current_theme = model.get_value(iter_, 0).decode('utf-8')
		self.current_theme = self.current_theme.replace(' ', '_')
		self.set_theme_options(self.current_theme)
		if self.current_theme == 'default':
			self.xml.get_widget('remove_button').set_sensitive(False)
			self.theme_options_vbox.set_sensitive(False)
			self.theme_options_table.set_sensitive(False)
		else:
			self.xml.get_widget('remove_button').set_sensitive(True)
			self.theme_options_vbox.set_sensitive(True)
			self.theme_options_table.set_sensitive(True)

	def on_add_button_clicked(self, widget):
		model = self.themes_tree.get_model()
		iter_ = model.append()
		i = 0
		# don't confuse translators
		theme_name = _('theme name')
		theme_name_ns = theme_name.replace(' ', '_')
		while theme_name_ns + unicode(i) in gajim.config.get_per('themes'):
			i += 1
		model.set_value(iter_, 0, theme_name + unicode(i))
		gajim.config.add_per('themes', theme_name_ns + unicode(i))
		self.themes_tree.get_selection().select_iter(iter_)
		col = self.themes_tree.get_column(0)
		path = model.get_path(iter_)
		self.themes_tree.set_cursor(path, col, True)

	def on_remove_button_clicked(self, widget):
		(model, iter_) = self.themes_tree.get_selection().get_selected()
		if not iter_:
			return
		if self.current_theme == gajim.config.get('roster_theme'):
			dialogs.ErrorDialog(
				_('You cannot delete your current theme'),
			_('Please first choose another for your current theme.'))
			return
		self.theme_options_vbox.set_sensitive(False)
		self.theme_options_table.set_sensitive(False)
		self.xml.get_widget('remove_button').set_sensitive(False)
		gajim.config.del_per('themes', self.current_theme)
		model.remove(iter_)

	def set_theme_options(self, theme, option = 'account'):
		self.no_update = True
		self.options_combobox.set_active(self.options.index(option))
		textcolor = gajim.config.get_per('themes', theme, option + 'textcolor')
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

		# get the font name before we set widgets and it will not be overriden
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

		for chatstate in ('inactive', 'composing', 'paused', 'gone',
		'muc_msg', 'muc_directed_msg'):
			color = gajim.config.get_per('themes', theme, 'state_' + chatstate + \
				'_color')
			self.colorbuttons[chatstate].set_color(gtk.gdk.color_parse(color))

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
		if not self.no_update:
			self._set_font()

	def on_italic_togglebutton_toggled(self, widget):
		if not self.no_update:
			self._set_font()

	def _set_color(self, state, widget, option):
		''' set color value in prefs and update the UI '''
		if state:
			color = widget.get_color()
			color_string = gtkgui_helpers.make_color_string(color)
		else:
			color_string = ''
		begin_option = ''
		if not option.startswith('state'):
			begin_option = self.current_option
		gajim.config.set_per('themes', self.current_theme,
			begin_option + option, color_string)
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
		a font string of type 'BI' '''
		font_props = [False, False, False]
		if font_attrs:
			if font_attrs.find('B') != -1:
				font_props[0] = True
			if font_attrs.find('I') != -1:
				font_props[1] = True
		self._toggle_font_widgets(font_props)

	def _get_font_attrs(self):
		''' get a string with letters of font attribures: 'BI' '''
		attrs = ''
		if self.bold_togglebutton.get_active():
			attrs += 'B'
		if self.italic_togglebutton.get_active():
			attrs += 'I'
		return attrs


	def _get_font_props(self, font_name):
		''' get tuple of font properties: Weight, Style '''
		font_props = [False, False, False]
		font_description = pango.FontDescription(font_name)
		if font_description.get_weight() != pango.WEIGHT_NORMAL:
			font_props[0] = True
		if font_description.get_style() != pango.STYLE_ITALIC:
			font_props[1] = True
		return font_props

	def on_inactive_colorbutton_color_set(self, widget):
		self.no_update = True
		self._set_color(True, widget, 'state_inactive_color')
		self.no_update = False

	def on_composing_colorbutton_color_set(self, widget):
		self.no_update = True
		self._set_color(True, widget, 'state_composing_color')
		self.no_update = False

	def on_paused_colorbutton_color_set(self, widget):
		self.no_update = True
		self._set_color(True, widget, 'state_paused_color')
		self.no_update = False

	def on_gone_colorbutton_color_set(self, widget):
		self.no_update = True
		self._set_color(True, widget, 'state_gone_color')
		self.no_update = False

	def on_muc_msg_colorbutton_color_set(self, widget):
		self.no_update = True
		self._set_color(True, widget, 'state_muc_msg_color')
		self.no_update = False

	def on_muc_directed_msg_colorbutton_color_set(self, widget):
		self.no_update = True
		self._set_color(True, widget, 'state_muc_directed_msg_color')
		self.no_update = False

# vim: se ts=3:
