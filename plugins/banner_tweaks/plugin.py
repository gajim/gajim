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
import gobject
import message_control
from common import gajim
from common import helpers

from plugins import GajimPlugin
from plugins.helpers import log, log_calls
from plugins.gui import GajimPluginConfigDialog

class BannerTweaksPlugin(GajimPlugin):

    @log_calls('BannerTweaksPlugin')
    def init(self):
        self.config_dialog = BannerTweaksPluginConfigDialog(self)

        self.gui_extension_points = {
            'chat_control_base_draw_banner': (self.chat_control_base_draw_banner_called,
                                              self.chat_control_base_draw_banner_deactivation)
        }

        self.config_default_values = {
            'show_banner_image': (True, 'If True, Gajim will display a status icon in the banner of chat windows.'),
            'show_banner_online_msg': (True, 'If True, Gajim will display the status message of the contact in the banner of chat windows.'),
            'show_banner_resource': (False, 'If True, Gajim will display the resource name of the contact in the banner of chat windows.'),
            'banner_small_fonts': (False, 'If True, Gajim will use small fonts for contact name and resource name in the banner of chat windows.'),
            'old_chat_avatar_height': (52, 'chat_avatar_height value before plugin was activated'),
        }

    @log_calls('BannerTweaksPlugin')
    def activate(self):
        self.config['old_chat_avatar_height'] = gajim.config.get('chat_avatar_height')
        #gajim.config.set('chat_avatar_height', 28)

    @log_calls('BannerTweaksPlugin')
    def deactivate(self):
        gajim.config.set('chat_avatar_height', self.config['old_chat_avatar_height'])

    @log_calls('BannerTweaksPlugin')
    def chat_control_base_draw_banner_called(self, chat_control):
        if not self.config['show_banner_online_msg']:
            chat_control.banner_status_label.hide()
            chat_control.banner_status_label.set_no_show_all(True)
            status_text = ''
            chat_control.banner_status_label.set_markup(status_text)

        if not self.config['show_banner_image']:
            if chat_control.TYPE_ID == message_control.TYPE_GC:
                banner_status_img = chat_control.xml.get_object(
                    'gc_banner_status_image')
            else:
                banner_status_img = chat_control.xml.get_object(
                    'banner_status_image')
            banner_status_img.clear()

        # TODO: part below repeats a lot of code from ChatControl.draw_banner_text()
        # This could be rewritten using re module: getting markup text from
        # banner_name_label and replacing some elements based on plugin config.
        # Would it be faster?
        if self.config['show_banner_resource'] or self.config['banner_small_fonts']:
            banner_name_label = chat_control.xml.get_object('banner_name_label')
            label_text = banner_name_label.get_label()

            contact = chat_control.contact
            jid = contact.jid

            name = contact.get_shown_name()
            if chat_control.resource:
                name += '/' + chat_control.resource
            elif contact.resource and self.config['show_banner_resource']:
                name += '/' + contact.resource

            if chat_control.TYPE_ID == message_control.TYPE_PM:
                name = _('%(nickname)s from group chat %(room_name)s') %\
                        {'nickname': name, 'room_name': chat_control.room_name}
            name = gobject.markup_escape_text(name)

            # We know our contacts nick, but if another contact has the same nick
            # in another account we need to also display the account.
            # except if we are talking to two different resources of the same contact
            acct_info = ''
            for account in gajim.contacts.get_accounts():
                if account == chat_control.account:
                    continue
                if acct_info: # We already found a contact with same nick
                    break
                for jid in gajim.contacts.get_jid_list(account):
                    other_contact_ = \
                            gajim.contacts.get_first_contact_from_jid(account, jid)
                    if other_contact_.get_shown_name() == chat_control.contact.get_shown_name():
                        acct_info = ' (%s)' % \
                                gobject.markup_escape_text(chat_control.account)
                        break

            font_attrs, font_attrs_small = chat_control.get_font_attrs()
            if self.config['banner_small_fonts']:
                font_attrs = font_attrs_small

            st = gajim.config.get('displayed_chat_state_notifications')
            cs = contact.chatstate
            if cs and st in ('composing_only', 'all'):
                if contact.show == 'offline':
                    chatstate = ''
                elif st == 'all' or cs == 'composing':
                    chatstate = helpers.get_uf_chatstate(cs)
                else:
                    chatstate = ''

                label_text = '<span %s>%s</span><span %s>%s %s</span>' % \
                    (font_attrs, name, font_attrs_small, acct_info, chatstate)
            else:
                # weight="heavy" size="x-large"
                label_text = '<span %s>%s</span><span %s>%s</span>' % \
                    (font_attrs, name, font_attrs_small, acct_info)

            banner_name_label.set_markup(label_text)

    @log_calls('BannerTweaksPlugin')
    def chat_control_base_draw_banner_deactivation(self, chat_control):
        pass
        #chat_control.draw_banner()

class BannerTweaksPluginConfigDialog(GajimPluginConfigDialog):
    def init(self):
        self.GTK_BUILDER_FILE_PATH = self.plugin.local_file_path(
                'config_dialog.ui')
        self.xml = gtk.Builder()
        self.xml.set_translation_domain('gajim_plugins')
        self.xml.add_objects_from_file(self.GTK_BUILDER_FILE_PATH,
                ['banner_tweaks_config_vbox'])
        self.config_vbox = self.xml.get_object('banner_tweaks_config_vbox')
        self.child.pack_start(self.config_vbox)

        self.show_banner_image_checkbutton = self.xml.get_object('show_banner_image_checkbutton')
        self.show_banner_online_msg_checkbutton = self.xml.get_object('show_banner_online_msg_checkbutton')
        self.show_banner_resource_checkbutton = self.xml.get_object('show_banner_resource_checkbutton')
        self.banner_small_fonts_checkbutton = self.xml.get_object('banner_small_fonts_checkbutton')

        self.xml.connect_signals(self)

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
