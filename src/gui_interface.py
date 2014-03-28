# -*- coding:utf-8 -*-
## src/gajim.py
##
## Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2004-2005 Vincent Hanquez <tab AT snarc.org>
## Copyright (C) 2005 Alex Podaras <bigpod AT gmail.com>
##                    Norman Rasmussen <norman AT rasmussen.co.za>
##                    Stéphan Kochen <stephan AT kochen.nl>
## Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
##                         Alex Mauer <hawke AT hawkesnest.net>
## Copyright (C) 2005-2007 Travis Shirk <travis AT pobox.com>
##                         Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006 Junglecow J <junglecow AT gmail.com>
##                    Stefan Bethge <stefan AT lanpartei.de>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
##                    James Newton <redshodan AT gmail.com>
## Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
##                         Julien Pivotto <roidelapluie AT gmail.com>
##                         Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
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
import os
import sys
import re
import time
import math
from subprocess import Popen

from gi.repository import Gtk
from gi.repository import GdkPixbuf
from gi.repository import GLib

from common import i18n
from common import gajim

from common import dbus_support
if dbus_support.supported:
    from music_track_listener import MusicTrackListener
    from common import location_listener
    import dbus

import gtkgui_helpers

import dialogs
import notify
import message_control

from chat_control import ChatControlBase
from chat_control import ChatControl
from groupchat_control import GroupchatControl
from groupchat_control import PrivateChatControl

from atom_window import AtomWindow
from session import ChatControlSession

from common import sleepy

from nbxmpp import idlequeue
from nbxmpp import Hashes
from common.zeroconf import connection_zeroconf
from common import resolver
from common import caps_cache
from common import proxy65_manager
from common import socks5
from common import helpers
from common import dataforms
from common import passwords
from common import logging_helpers
from common.connection_handlers_events import OurShowEvent, \
    FileRequestErrorEvent, InformationEvent
from common.connection import Connection
from common import jingle
from common.file_props import FilesProp
from common import pep

import roster_window
import profile_window
import config
from threading import Thread
from common import ged

from common.configpaths import gajimpaths
config_filename = gajimpaths['CONFIG_FILE']

from common import optparser
parser = optparser.OptionsParser(config_filename)

import logging
log = logging.getLogger('gajim.interface')

class Interface:

################################################################################
### Methods handling events from connection
################################################################################

    def handle_event_db_error(self, unused, data):
        #('DB_ERROR', account, (title_text, section_text))
        if self.db_error_dialog:
            return
        self.db_error_dialog = dialogs.ErrorDialog(data[0], data[1])
        def destroyed(win):
            self.db_error_dialog = None
        self.db_error_dialog.connect('destroy', destroyed)

    def handle_event_information(self, obj):
        if obj.popup:
            if obj.level == 'error':
                cls = dialogs.ErrorDialog
            elif obj.level == 'warn':
                cls = dialogs.WarningDialog
            elif obj.level == 'info':
                cls = dialogs.InformationDialog
            else:
                return

            cls(obj.pri_txt, GLib.markup_escape_text(obj.sec_txt))

    def handle_ask_new_nick(self, account, room_jid):
        title = _('Unable to join group chat')
        prompt = _('Your desired nickname in group chat %s is in use or '
            'registered by another occupant.\nPlease specify another nickname '
            'below:') % room_jid
        check_text = _('Always use this nickname when there is a conflict')
        if 'change_nick_dialog' in self.instances:
            self.instances['change_nick_dialog'].add_room(account, room_jid,
                prompt)
        else:
            self.instances['change_nick_dialog'] = dialogs.ChangeNickDialog(
                account, room_jid, title, prompt)

    def handle_event_http_auth(self, obj):
        #('HTTP_AUTH', account, (method, url, transaction_id, iq_obj, msg))
        def response(account, answer):
            obj.conn.build_http_auth_answer(obj.stanza, answer)

        def on_yes(is_checked, obj):
            response(obj, 'yes')

        account = obj.conn.name
        sec_msg = _('Do you accept this request?')
        if gajim.get_number_of_connected_accounts() > 1:
            sec_msg = _('Do you accept this request on account %s?') % account
        if obj.msg:
            sec_msg = obj.msg + '\n' + sec_msg
        dialog = dialogs.YesNoDialog(_('HTTP (%(method)s) Authorization for '
            '%(url)s (id: %(id)s)') % {'method': obj.method, 'url': obj.url,
            'id': obj.iq_id}, sec_msg, on_response_yes=(on_yes, obj),
            on_response_no=(response, obj, 'no'))

    def handle_event_iq_error(self, obj):
        #('ERROR_ANSWER', account, (id_, fjid, errmsg, errcode))
        if str(obj.errcode) in ('400', '403', '406') and obj.id_:
            # show the error dialog
            ft = self.instances['file_transfers']
            sid = obj.id_
            if len(obj.id_) > 3 and obj.id_[2] == '_':
                sid = obj.id_[3:]
            file_props = FilesProp.getFileProp(obj.conn.name, sid)
            if file_props :
                if str(obj.errcode) == '400':
                    file_props.error = -3
                else:
                    file_props.error = -4
                gajim.nec.push_incoming_event(FileRequestErrorEvent(None,
                    conn=obj.conn, jid=obj.jid, file_props=file_props,
                    error_msg=obj.errmsg))
                obj.conn.disconnect_transfer(file_props)
                return
        elif str(obj.errcode) == '404':
            sid = obj.id_
            if len(obj.id_) > 3 and obj.id_[2] == '_':
                sid = obj.id_[3:]
            file_props = FilesProp.getFileProp(obj.conn.name, sid)
            if file_props:
                self.handle_event_file_send_error(obj.conn.name, (obj.fjid,
                    file_props))
                obj.conn.disconnect_transfer(file_props)
                return

        ctrl = self.msg_win_mgr.get_control(obj.fjid, obj.conn.name)
        if ctrl and ctrl.type_id == message_control.TYPE_GC:
            ctrl.print_conversation('Error %s: %s' % (obj.errcode, obj.errmsg))

    def handle_event_connection_lost(self, obj):
        # ('CONNECTION_LOST', account, [title, text])
        path = gtkgui_helpers.get_icon_path('gajim-connection_lost', 48)
        account = obj.conn.name
        notify.popup(_('Connection Failed'), account, account,
            'connection_failed', path, obj.title, obj.msg)

    def unblock_signed_in_notifications(self, account):
        gajim.block_signed_in_notifications[account] = False

    def handle_event_status(self, obj): # OUR status
        #('STATUS', account, show)
        account = obj.conn.name
        if obj.show in ('offline', 'error'):
            for name in list(self.instances[account]['online_dialog'].keys()):
                # .keys() is needed to not have a dictionary length changed
                # during iteration error
                self.instances[account]['online_dialog'][name].destroy()
                if name in self.instances[account]['online_dialog']:
                    # destroy handler may have already removed it
                    del self.instances[account]['online_dialog'][name]
            for request in self.gpg_passphrase.values():
                if request:
                    request.interrupt(account=account)
            if account in self.pass_dialog:
                self.pass_dialog[account].window.destroy()
        if obj.show == 'offline':
            gajim.block_signed_in_notifications[account] = True
        else:
            # 30 seconds after we change our status to sth else than offline
            # we stop blocking notifications of any kind
            # this prevents from getting the roster items as 'just signed in'
            # contacts. 30 seconds should be enough time
            GLib.timeout_add_seconds(30, self.unblock_signed_in_notifications,
                account)

        if account in self.show_vcard_when_connect and obj.show not in (
        'offline', 'error'):
            self.edit_own_details(account)

    def edit_own_details(self, account):
        jid = gajim.get_jid_from_account(account)
        if 'profile' not in self.instances[account]:
            self.instances[account]['profile'] = \
            profile_window.ProfileWindow(account, gajim.interface.roster.window)
            gajim.connections[account].request_vcard(jid)

    def handle_gc_error(self, gc_control, pritext, sectext):
        if gc_control and gc_control.autorejoin is not None:
            if gc_control.error_dialog:
                gc_control.error_dialog.destroy()
            def on_close(dummy):
                gc_control.error_dialog.destroy()
                gc_control.error_dialog = None
            gc_control.error_dialog = dialogs.ErrorDialog(pritext, sectext,
                on_response_ok=on_close, on_response_cancel=on_close)
            gc_control.error_dialog.set_modal(False)
            if gc_control.parent_win:
                gc_control.error_dialog.set_transient_for(
                    gc_control.parent_win.window)
        else:
            d = dialogs.ErrorDialog(pritext, sectext)
            if gc_control and gc_control.parent_win:
                d.set_transient_for(gc_control.parent_win.window)
            d.set_modal(False)

    def handle_gc_password_required(self, account, room_jid, nick):
        def on_ok(text):
            gajim.connections[account].join_gc(nick, room_jid, text)
            gajim.gc_passwords[room_jid] = text
            gc_control.error_dialog = None

        def on_cancel():
            # get and destroy window
            if room_jid in gajim.interface.minimized_controls[account]:
                self.roster.on_disconnect(None, room_jid, account)
            else:
                win = self.msg_win_mgr.get_window(room_jid, account)
                ctrl = self.msg_win_mgr.get_gc_control(room_jid, account)
                win.remove_tab(ctrl, 3)
            gc_control.error_dialog = None

        gc_control = self.msg_win_mgr.get_gc_control(room_jid, account)
        if gc_control:
            if gc_control.error_dialog:
                gc_control.error_dialog.destroy()

            gc_control.error_dialog = dialogs.InputDialog(_('Password Required'),
                _('A Password is required to join the room %s. Please type it.') % \
                room_jid, is_modal=False, ok_handler=on_ok,
                cancel_handler=on_cancel)
            gc_control.error_dialog.input_entry.set_visibility(False)

    def handle_event_gc_presence(self, obj):
        gc_control = obj.gc_control
        if obj.ptype == 'error':
            if obj.errcode == '503':
                # maximum user number reached
                self.handle_gc_error(gc_control,
                    _('Unable to join group chat'),
                    _('Maximum number of users for <b>%s</b> has been reached')\
                    % obj.room_jid)
            elif (obj.errcode == '401') or (obj.errcon == 'not-authorized'):
                # password required to join
                self.handle_gc_password_required(obj.conn.name, obj.room_jid,
                    obj.nick)
            elif (obj.errcode == '403') or (obj.errcon == 'forbidden'):
                # we are banned
                self.handle_gc_error(gc_control, _('Unable to join group chat'),
                    _('You are banned from group chat <b>%s</b>.') % \
                    obj.room_jid)
            elif (obj.errcode == '404') or (obj.errcon in ('item-not-found',
            'remote-server-not-found')):
                # group chat does not exist
                self.handle_gc_error(gc_control, _('Unable to join group chat'),
                    _('Group chat <b>%s</b> does not exist.') % obj.room_jid)
            elif (obj.errcode == '405') or (obj.errcon == 'not-allowed'):
                self.handle_gc_error(gc_control, _('Unable to join group chat'),
                    _('Group chat creation is restricted.'))
            elif (obj.errcode == '406') or (obj.errcon == 'not-acceptable'):
                self.handle_gc_error(gc_control, _('Unable to join group chat'),
                    _('Your registered nickname must be used in group chat '
                    '<b>%s</b>.') % obj.room_jid)
            elif (obj.errcode == '407') or (obj.errcon == \
            'registration-required'):
                self.handle_gc_error(gc_control, _('Unable to join group chat'),
                    _('You are not in the members list in groupchat %s.') % \
                    obj.room_jid)
            elif (obj.errcode == '409') or (obj.errcon == 'conflict'):
                self.handle_ask_new_nick(obj.conn.name, obj.room_jid)
            elif gc_control:
                gc_control.print_conversation('Error %s: %s' % (obj.errcode,
                    obj.errmsg))
            if gc_control and gc_control.autorejoin:
                gc_control.autorejoin = False

    def handle_event_gc_message(self, obj):
        if not obj.stanza.getTag('body'): # no <body>
            # It could be a voice request. See
            # http://www.xmpp.org/extensions/xep-0045.html#voiceapprove
            if obj.msg_obj.form_node:
                dialogs.SingleMessageWindow(obj.conn.name, obj.fjid,
                    action='receive', from_whom=obj.fjid,
                    subject='', message='', resource='', session=None,
                    form_node=obj.msg_obj.form_node)

    def handle_event_presence(self, obj):
        # 'NOTIFY' (account, (jid, status, status message, resource,
        # priority, # keyID, timestamp, contact_nickname))
        #
        # Contact changed show

        account = obj.conn.name
        jid = obj.jid
        show = obj.show
        status = obj.status
        resource = obj.resource or ''

        jid_list = gajim.contacts.get_jid_list(account)

        # unset custom status
        if (obj.old_show == 0 and obj.new_show > 1) or \
        (obj.old_show > 1 and obj.new_show == 0 and obj.conn.connected > 1):
            if account in self.status_sent_to_users and \
            jid in self.status_sent_to_users[account]:
                del self.status_sent_to_users[account][jid]

        if gajim.jid_is_transport(jid):
            # It must be an agent

            # transport just signed in/out, don't show
            # popup notifications for 30s
            account_jid = account + '/' + jid
            gajim.block_signed_in_notifications[account_jid] = True
            GLib.timeout_add_seconds(30, self.unblock_signed_in_notifications,
                account_jid)

        highest = gajim.contacts.get_contact_with_highest_priority(account, jid)
        is_highest = (highest and highest.resource == resource)

        ctrl = self.msg_win_mgr.get_control(jid, account)
        if ctrl and ctrl.session and len(obj.contact_list) > 1:
            ctrl.remove_session(ctrl.session)

    def handle_event_msgerror(self, obj):
        #'MSGERROR' (account, (jid, error_code, error_msg, msg, time[session]))
        account = obj.conn.name
        jids = obj.fjid.split('/', 1)
        jid = jids[0]

        session = obj.session

        gc_control = self.msg_win_mgr.get_gc_control(jid, account)
        if not gc_control and \
        jid in self.minimized_controls[account]:
            gc_control = self.minimized_controls[account][jid]
        if gc_control and gc_control.type_id != message_control.TYPE_GC:
            gc_control = None
        if gc_control:
            if len(jids) > 1: # it's a pm
                nick = jids[1]

                if session:
                    ctrl = session.control
                else:
                    ctrl = self.msg_win_mgr.get_control(obj.fjid, account)

                if not ctrl:
                    tv = gc_control.list_treeview
                    model = tv.get_model()
                    iter_ = gc_control.get_contact_iter(nick)
                    if iter_:
                        show = model[iter_][3]
                    else:
                        show = 'offline'
                    gc_c = gajim.contacts.create_gc_contact(room_jid=jid,
                        account=account, name=nick, show=show)
                    ctrl = self.new_private_chat(gc_c, account, session)

                ctrl.print_conversation(_('Error %(code)s: %(msg)s') % {
                    'code': obj.error_code, 'msg': obj.error_msg}, 'status')
                return

            gc_control.print_conversation(_('Error %(code)s: %(msg)s') % {
                'code': obj.error_code, 'msg': obj.error_msg}, 'status')
            if gc_control.parent_win and \
            gc_control.parent_win.get_active_jid() == jid:
                gc_control.set_subject(gc_control.subject)
            return

        if gajim.jid_is_transport(jid):
            jid = jid.replace('@', '')
        msg = obj.error_msg
        if obj.msg:
            msg = _('error while sending %(message)s ( %(error)s )') % {
                    'message': obj.msg, 'error': msg}
        if session:
            session.roster_message(jid, msg, obj.time_, msg_type='error')

    def handle_event_msgsent(self, obj):
        #('MSGSENT', account, (jid, msg, keyID))
        # do not play sound when standalone chatstate message (eg no msg)
        if obj.message and gajim.config.get_per('soundevents', 'message_sent',
        'enabled'):
            helpers.play_sound('message_sent')

    def handle_event_msgnotsent(self, obj):
        #('MSGNOTSENT', account, (jid, ierror_msg, msg, time, session))
        msg = _('error while sending %(message)s ( %(error)s )') % {
                'message': obj.message, 'error': obj.error}
        if not obj.session:
            # No session. This can happen when sending a message from
            # gajim-remote
            log.warning(msg)
            return
        obj.session.roster_message(obj.jid, msg, obj.time_, obj.conn.name,
            msg_type='error')

    def handle_event_subscribe_presence(self, obj):
        #('SUBSCRIBE', account, (jid, text, user_nick)) user_nick is JEP-0172
        account = obj.conn.name
        if helpers.allow_popup_window(account) or not self.systray_enabled:
            if obj.jid in self.instances[account]['sub_request']:
                self.instances[account]['sub_request'][obj.jid].window.destroy()
            self.instances[account]['sub_request'][obj.jid] = \
                dialogs.SubscriptionRequestWindow(obj.jid, obj.status, account,
                obj.user_nick)
            return

        self.add_event(account, obj.jid, 'subscription_request', (obj.status,
            obj.user_nick))

        if helpers.allow_showing_notification(account):
            path = gtkgui_helpers.get_icon_path('gajim-subscription_request',
                48)
            event_type = _('Subscription request')
            notify.popup(event_type, obj.jid, account, 'subscription_request',
                path, event_type, obj.jid)

    def handle_event_subscribed_presence(self, obj):
        #('SUBSCRIBED', account, (jid, resource))
        account = obj.conn.name
        if obj.jid in gajim.contacts.get_jid_list(account):
            c = gajim.contacts.get_first_contact_from_jid(account, obj.jid)
            c.resource = obj.resource
            self.roster.remove_contact_from_groups(c.jid, account,
                [_('Not in Roster'), _('Observers')], update=False)
        else:
            keyID = ''
            attached_keys = gajim.config.get_per('accounts', account,
                'attached_gpg_keys').split()
            if obj.jid in attached_keys:
                keyID = attached_keys[attached_keys.index(obj.jid) + 1]
            name = obj.jid.split('@', 1)[0]
            name = name.split('%', 1)[0]
            contact1 = gajim.contacts.create_contact(jid=obj.jid,
                account=account, name=name, groups=[], show='online',
                status='online', ask='to', resource=obj.resource, keyID=keyID)
            gajim.contacts.add_contact(account, contact1)
            self.roster.add_contact(obj.jid, account)
        dialogs.InformationDialog(_('Authorization accepted'),
            _('The contact "%s" has authorized you to see his or her status.')
            % obj.jid)

    def show_unsubscribed_dialog(self, account, contact):
        def on_yes(is_checked, list_):
            self.roster.on_req_usub(None, list_)
        list_ = [(contact, account)]
        dialogs.YesNoDialog(
                _('Contact "%s" removed subscription from you') % contact.jid,
                _('You will always see him or her as offline.\nDo you want to '
                        'remove him or her from your contact list?'),
                on_response_yes=(on_yes, list_))
            # FIXME: Per RFC 3921, we can "deny" ack as well, but the GUI does
            # not show deny

    def handle_event_unsubscribed_presence(self, obj):
        #('UNSUBSCRIBED', account, jid)
        account = obj.conn.name
        contact = gajim.contacts.get_first_contact_from_jid(account, obj.jid)
        if not contact:
            return

        if helpers.allow_popup_window(account) or not self.systray_enabled:
            self.show_unsubscribed_dialog(account, contact)
            return

        self.add_event(account, obj.jid, 'unsubscribed', contact)

        if helpers.allow_showing_notification(account):
            path = gtkgui_helpers.get_icon_path('gajim-unsubscribed', 48)
            event_type = _('Unsubscribed')
            notify.popup(event_type, obj.jid, account, 'unsubscribed', path,
                event_type, obj.jid)

    def handle_event_register_agent_info(self, obj):
        # ('REGISTER_AGENT_INFO', account, (agent, infos, is_form))
        # info in a dataform if is_form is True
        if obj.is_form or 'instructions' in obj.config:
            config.ServiceRegistrationWindow(obj.agent, obj.config,
                obj.conn.name, obj.is_form)
        else:
            dialogs.ErrorDialog(_('Contact with "%s" cannot be established') % \
                obj.agent, _('Check your connection or try again later.'))

    def handle_event_vcard(self, obj):
        # ('VCARD', account, data)
        '''vcard holds the vcard data'''
        our_jid = gajim.get_jid_from_account(obj.conn.name)
        if obj.jid == our_jid:
            if obj.nickname:
                gajim.nicks[obj.conn.name] = obj.nickname
            if obj.conn.name in self.show_vcard_when_connect:
                self.show_vcard_when_connect.remove(obj.conn.name)

    def handle_event_last_status_time(self, obj):
        # ('LAST_STATUS_TIME', account, (jid, resource, seconds, status))
        if obj.seconds < 0:
            # Ann error occured
            return
        account = obj.conn.name
        c = gajim.contacts.get_contact(account, obj.jid, obj.resource)
        if c: # c can be none if it's a gc contact
            if obj.status:
                c.status = obj.status
                self.roster.draw_contact(c.jid, account) # draw offline status
            last_time = time.localtime(time.time() - obj.seconds)
            if c.show == 'offline':
                c.last_status_time = last_time
            else:
                c.last_activity_time = last_time
            if self.roster.tooltip.id and self.roster.tooltip.win:
                self.roster.tooltip.update_last_time(last_time)

    def handle_event_gc_config(self, obj):
        #('GC_CONFIG', account, (jid, form_node))  config is a dict
        account = obj.conn.name
        if obj.jid in gajim.automatic_rooms[account]:
            if 'continue_tag' in gajim.automatic_rooms[account][obj.jid]:
                # We're converting chat to muc. allow participants to invite
                for f in obj.dataform.iter_fields():
                    if f.var == 'muc#roomconfig_allowinvites':
                        f.value = True
                    elif f.var == 'muc#roomconfig_publicroom':
                        f.value = False
                    elif f.var == 'muc#roomconfig_membersonly':
                        f.value = True
                    elif f.var == 'public_list':
                        f.value = False
                obj.conn.send_gc_config(obj.jid, obj.dataform.get_purged())
            else:
                # use default configuration
                obj.conn.send_gc_config(obj.jid, obj.form_node)
            # invite contacts
            # check if it is necessary to add <continue />
            continue_tag = False
            if 'continue_tag' in gajim.automatic_rooms[account][obj.jid]:
                continue_tag = True
            if 'invities' in gajim.automatic_rooms[account][obj.jid]:
                for jid in gajim.automatic_rooms[account][obj.jid]['invities']:
                    obj.conn.send_invite(obj.jid, jid,
                        continue_tag=continue_tag)
                    gc_control = self.msg_win_mgr.get_gc_control(obj.jid,
                        account)
                    if gc_control:
                        gc_control.print_conversation(
                            _('%(jid)s has been invited in this room') % {
                            'jid': jid}, graphics=False)
            del gajim.automatic_rooms[account][obj.jid]
        elif obj.jid not in self.instances[account]['gc_config']:
            self.instances[account]['gc_config'][obj.jid] = \
                config.GroupchatConfigWindow(account, obj.jid, obj.dataform)

    def handle_event_gc_affiliation(self, obj):
        #('GC_AFFILIATION', account, (room_jid, users_dict))
        account = obj.conn.name
        if obj.jid in self.instances[account]['gc_config']:
            self.instances[account]['gc_config'][obj.jid].\
                affiliation_list_received(obj.users_dict)

    def handle_event_gc_decline(self, obj):
        account = obj.conn.name
        gc_control = self.msg_win_mgr.get_gc_control(obj.room_jid, account)
        if gc_control:
            if obj.reason:
                gc_control.print_conversation(
                    _('%(jid)s declined the invitation: %(reason)s') % {
                    'jid': obj.jid_from, 'reason': obj.reason}, graphics=False)
            else:
                gc_control.print_conversation(
                    _('%(jid)s declined the invitation') % {
                    'jid': obj.jid_from}, graphics=False)

    def handle_event_gc_invitation(self, obj):
        #('GC_INVITATION', (room_jid, jid_from, reason, password, is_continued))
        account = obj.conn.name
        if helpers.allow_popup_window(account) or not self.systray_enabled:
            dialogs.InvitationReceivedDialog(account, obj.room_jid,
                obj.jid_from, obj.password, obj.reason,
                is_continued=obj.is_continued)
            return

        self.add_event(account, obj.jid_from, 'gc-invitation', (obj.room_jid,
            obj.reason, obj.password, obj.is_continued, obj.jid_from))

        if helpers.allow_showing_notification(account):
            path = gtkgui_helpers.get_icon_path('gajim-gc_invitation', 48)
            event_type = _('Groupchat Invitation')
            notify.popup(event_type, obj.jid_from, account, 'gc-invitation',
                path, event_type, obj.room_jid)

    def forget_gpg_passphrase(self, keyid):
        if keyid in self.gpg_passphrase:
            del self.gpg_passphrase[keyid]
        return False

    def handle_event_bad_gpg_passphrase(self, obj):
        #('BAD_PASSPHRASE', account, ())
        if obj.use_gpg_agent:
            sectext = _('You configured Gajim to use OpenPGP agent, but there '
                'is no OpenPGP agent running or it returned a wrong passphrase.'
                '\n')
            sectext += _('You are currently connected without your OpenPGP '
                'key.')
            dialogs.WarningDialog(_('Your passphrase is incorrect'), sectext)
        else:
            path = gtkgui_helpers.get_icon_path('gtk-dialog-warning', 48)
            account = obj.conn.name
            notify.popup('warning', account, account, 'warning', path,
                _('OpenPGP Passphrase Incorrect'),
                _('You are currently connected without your OpenPGP key.'))
        self.forget_gpg_passphrase(obj.keyID)

    def handle_event_client_cert_passphrase(self, obj):
        def on_ok(passphrase, checked):
            obj.conn.on_client_cert_passphrase(passphrase, obj.con, obj.port,
                obj.secure_tuple)

        def on_cancel():
            obj.conn.on_client_cert_passphrase('', obj.con, obj.port,
                obj.secure_tuple)

        dialogs.PassphraseDialog(_('Certificate Passphrase Required'),
            _('Enter the passphrase for the certificate for account %s') % \
            obj.conn.name, ok_handler=on_ok, cancel_handler=on_cancel)

    def handle_event_gpg_password_required(self, obj):
        #('GPG_PASSWORD_REQUIRED', account, (callback,))
        if obj.keyid in self.gpg_passphrase:
            request = self.gpg_passphrase[obj.keyid]
        else:
            request = PassphraseRequest(obj.keyid)
            self.gpg_passphrase[obj.keyid] = request
        request.add_callback(obj.conn.name, obj.callback)

    def handle_event_gpg_trust_key(self, obj):
        #('GPG_ALWAYS_TRUST', account, callback)
        def on_yes(checked):
            if checked:
                obj.conn.gpg.always_trust.append(obj.keyID)
            obj.callback(True)

        def on_no():
            obj.callback(False)

        dialogs.YesNoDialog(_('OpenPGP key not trusted'), _('The OpenPGP key '
            'used to encrypt this chat is not trusted. Do you really want to '
            'encrypt this message?'), checktext=_('_Do not ask me again'),
            on_response_yes=on_yes, on_response_no=on_no)

    def handle_event_password_required(self, obj):
        #('PASSWORD_REQUIRED', account, None)
        account = obj.conn.name
        if account in self.pass_dialog:
            return
        text = _('Enter your password for account %s') % account
        if passwords.USER_HAS_GNOMEKEYRING and \
        not passwords.USER_USES_GNOMEKEYRING:
            text += '\n' + _('Gnome Keyring is installed but not '
                'correctly started (environment variable probably not '
                'correctly set)')

        def on_ok(passphrase, save):
            if save:
                gajim.config.set_per('accounts', account, 'savepass', True)
                passwords.save_password(account, passphrase)
            obj.conn.set_password(passphrase)
            del self.pass_dialog[account]

        def on_cancel():
            self.roster.set_state(account, 'offline')
            self.roster.update_status_combobox()
            del self.pass_dialog[account]

        self.pass_dialog[account] = dialogs.PassphraseDialog(
            _('Password Required'), text, _('Save password'), ok_handler=on_ok,
            cancel_handler=on_cancel)

    def handle_oauth2_credentials(self, obj):
        account = obj.conn.name
        def on_ok(refresh):
            gajim.config.set_per('accounts', account, 'oauth2_refresh_token',
                refresh)
            st = gajim.config.get_per('accounts', account, 'last_status')
            msg = helpers.from_one_line(gajim.config.get_per('accounts',
                account, 'last_status_msg'))
            gajim.interface.roster.send_status(account, st, msg)
            del self.pass_dialog[account]

        def on_cancel():
            gajim.config.set_per('accounts', account, 'oauth2_refresh_token',
                '')
            self.roster.set_state(account, 'offline')
            self.roster.update_status_combobox()
            del self.pass_dialog[account]

        instruction = _('Please copy / paste the refresh token from the website'
            ' that has just been opened.')
        self.pass_dialog[account] = dialogs.InputTextDialog(
            _('Oauth2 Credentials'), instruction, is_modal=False,
            ok_handler=on_ok, cancel_handler=on_cancel)

    def handle_event_roster_info(self, obj):
        #('ROSTER_INFO', account, (jid, name, sub, ask, groups))
        account = obj.conn.name
        contacts = gajim.contacts.get_contacts(account, obj.jid)
        if (not obj.sub or obj.sub == 'none') and \
        (not obj.ask or obj.ask == 'none') and not obj.nickname and \
        not obj.groups:
            # contact removed us.
            if contacts:
                self.roster.remove_contact(obj.jid, account, backend=True)
                return
        elif not contacts:
            if obj.sub == 'remove':
                return
            # Add new contact to roster
            keyID = ''
            attached_keys = gajim.config.get_per('accounts', account,
                'attached_gpg_keys').split()
            if obj.jid in attached_keys:
                keyID = attached_keys[attached_keys.index(obj.jid) + 1]
            contact = gajim.contacts.create_contact(jid=obj.jid,
                account=account, name=obj.nickname, groups=obj.groups,
                show='offline', sub=obj.sub, ask=obj.ask, keyID=keyID)
            gajim.contacts.add_contact(account, contact)
            self.roster.add_contact(obj.jid, account)
        else:
            # If contact has changed (sub, ask or group) update roster
            # Mind about observer status changes:
            #   According to xep 0162, a contact is not an observer anymore when
            #   we asked for auth, so also remove him if ask changed
            old_groups = contacts[0].groups
            if obj.sub == 'remove':
                # another of our instance removed a contact. Remove it here too
                self.roster.remove_contact(obj.jid, account, backend=True)
                return
            update = False
            if contacts[0].sub != obj.sub or contacts[0].ask != obj.ask\
            or old_groups != obj.groups:
                # c.get_shown_groups() has changed. Reflect that in
                # roster_window
                self.roster.remove_contact(obj.jid, account, force=True)
                update = True
            for contact in contacts:
                contact.name = obj.nickname or ''
                contact.sub = obj.sub
                contact.ask = obj.ask
                contact.groups = obj.groups or []
            if update:
                self.roster.add_contact(obj.jid, account)
                # Refilter and update old groups
                for group in old_groups:
                    self.roster.draw_group(group, account)
                self.roster.draw_contact(obj.jid, account)
        if obj.jid in self.instances[account]['sub_request'] and obj.sub in (
        'from', 'both'):
            self.instances[account]['sub_request'][obj.jid].window.destroy()

    def handle_event_bookmarks(self, obj):
        # ('BOOKMARKS', account, [{name,jid,autojoin,password,nick}, {}])
        # We received a bookmark item from the server (JEP48)
        # Auto join GC windows if neccessary

        self.roster.set_actions_menu_needs_rebuild()
        invisible_show = gajim.SHOW_LIST.index('invisible')
        # do not autojoin if we are invisible
        if obj.conn.connected == invisible_show:
            return

        self.auto_join_bookmarks(obj.conn.name)

    def handle_event_file_send_error(self, account, array):
        jid = array[0]
        file_props = array[1]
        ft = self.instances['file_transfers']
        ft.set_status(file_props, 'stop')

        if helpers.allow_popup_window(account):
            ft.show_send_error(file_props)
            return

        self.add_event(account, jid, 'file-send-error', file_props)

        if helpers.allow_showing_notification(account):
            path = gtkgui_helpers.get_icon_path('gajim-ft_error', 48)
            event_type = _('File Transfer Error')
            notify.popup(event_type, jid, account, 'file-send-error', path,
                event_type, file_props.name)

    def handle_event_gmail_notify(self, obj):
        jid = obj.jid
        gmail_new_messages = int(obj.newmsgs)
        gmail_messages_list = obj.gmail_messages_list
        if not gajim.config.get('notify_on_new_gmail_email'):
            return
        path = gtkgui_helpers.get_icon_path('gajim-new_email_recv', 48)
        title = _('New mail on %(gmail_mail_address)s') % \
            {'gmail_mail_address': jid}
        text = i18n.ngettext('You have %d new mail conversation',
            'You have %d new mail conversations', gmail_new_messages,
            gmail_new_messages, gmail_new_messages)

        if gajim.config.get('notify_on_new_gmail_email_extra'):
            cnt = 0
            for gmessage in gmail_messages_list:
                # FIXME: emulate Gtalk client popups. find out what they
                # parse and how they decide what to show each message has a
                # 'From', 'Subject' and 'Snippet' field
                if cnt >= 5:
                    break
                senders = ',\n     '.join(reversed(gmessage['From']))
                text += _('\n\nFrom: %(from_address)s\nSubject: '
                    '%(subject)s\n%(snippet)s') % {'from_address': senders,
                    'subject': gmessage['Subject'],
                    'snippet': gmessage['Snippet']}
                cnt += 1

        command = gajim.config.get('notify_on_new_gmail_email_command')
        if command:
            Popen(command, shell=True)

        if gajim.config.get_per('soundevents', 'gmail_received', 'enabled'):
            helpers.play_sound('gmail_received')
        notify.popup(_('New E-mail'), jid, obj.conn.name, 'gmail',
            path_to_image=path, title=title, text=text)

    def handle_event_file_request_error(self, obj):
        # ('FILE_REQUEST_ERROR', account, (jid, file_props, error_msg))
        ft = self.instances['file_transfers']
        ft.set_status(obj.file_props, 'stop')
        errno = obj.file_props.error

        if helpers.allow_popup_window(obj.conn.name):
            if errno in (-4, -5):
                ft.show_stopped(obj.jid, obj.file_props, obj.error_msg)
            else:
                ft.show_request_error(obj.file_props)
            return

        if errno in (-4, -5):
            msg_type = 'file-error'
        else:
            msg_type = 'file-request-error'

        self.add_event(obj.conn.name, obj.jid, msg_type, obj.file_props)

        if helpers.allow_showing_notification(obj.conn.name):
            # check if we should be notified
            path = gtkgui_helpers.get_icon_path('gajim-ft_error', 48)
            event_type = _('File Transfer Error')
            notify.popup(event_type, obj.jid, obj.conn.name, msg_type, path,
                title=event_type, text=obj.file_props.name)

    def handle_event_file_request(self, obj):
        account = obj.conn.name
        if obj.jid not in gajim.contacts.get_jid_list(account):
            keyID = ''
            attached_keys = gajim.config.get_per('accounts', account,
                'attached_gpg_keys').split()
            if obj.jid in attached_keys:
                keyID = attached_keys[attached_keys.index(obj.jid) + 1]
            contact = gajim.contacts.create_not_in_roster_contact(jid=obj.jid,
                account=account, keyID=keyID)
            gajim.contacts.add_contact(account, contact)
            self.roster.add_contact(obj.jid, account)
        contact = gajim.contacts.get_first_contact_from_jid(account, obj.jid)
        if obj.file_props.session_type == 'jingle':
            request = obj.stanza.getTag('jingle').getTag('content')\
                        .getTag('description').getTag('request')
            if request:
                # If we get a request instead
                ft_win = self.instances['file_transfers']
                ft_win.add_transfer(account, contact, obj.file_props)
                return
        if helpers.allow_popup_window(account):
            self.instances['file_transfers'].show_file_request(account, contact,
                obj.file_props)
            return
        self.add_event(account, obj.jid, 'file-request', obj.file_props)
        if helpers.allow_showing_notification(account):
            path = gtkgui_helpers.get_icon_path('gajim-ft_request', 48)
            txt = _('%s wants to send you a file.') % gajim.get_name_from_jid(
                account, obj.jid)
            event_type = _('File Transfer Request')
            notify.popup(event_type, obj.jid, account, 'file-request',
                path_to_image=path, title=event_type, text=txt)

    def handle_event_file_error(self, title, message):
        dialogs.ErrorDialog(title, message)

    def handle_event_file_progress(self, account, file_props):
        if time.time() - self.last_ftwindow_update > 0.5:
            # update ft window every 500ms
            self.last_ftwindow_update = time.time()
            self.instances['file_transfers'].set_progress(file_props.type_,
                    file_props.sid, file_props.received_len)

    def __compare_hashes(self, account, file_props):
        session = gajim.connections[account].get_jingle_session(jid=None,
            sid=file_props.sid)
        ft_win = self.instances['file_transfers']
        if not file_props.hash_:
            # We disn't get the hash, sender probably don't support that
            jid = file_props.sender
            self.popup_ft_result(account, jid, file_props)
            ft_win.set_status(file_props, 'ok')
        h = Hashes()
        try:
            file_ = open(file_props.file_name, 'r')
        except:
            return
        hash_ = h.calculateHash(file_props.algo, file_)
        file_.close()
        # If the hash we received and the hash of the file are the same,
        # then the file is not corrupt
        jid = file_props.sender
        if file_props.hash_ == hash_:
            GLib.idle_add(self.popup_ft_result, account, jid, file_props)
            GLib.idle_add(ft_win.set_status, file_props, 'ok')
        else:
            # wrong hash, we need to get the file again!
            file_props.error = -10
            GLib.idle_add(self.popup_ft_result, account, jid, file_props)
            GLib.idle_add(ft_win.set_status, file_props, 'hash_error')
        # End jingle session
        if session:
            session.end_session()

    def handle_event_file_rcv_completed(self, account, file_props):
        ft = self.instances['file_transfers']
        if file_props.error == 0:
            ft.set_progress(file_props.type_, file_props.sid,
                file_props.received_len)
        else:
            ft.set_status(file_props, 'stop')
        if file_props.stalled or file_props.paused:
            return

        if file_props.type_ == 'r' and file_props.hash_: # we receive a file
            gajim.socks5queue.remove_receiver(file_props.sid, True, True)
            # we compare hashes
            if file_props.session_type == 'jingle':
                # Compare hashes in a new thread
                self.hashThread = Thread(target=self.__compare_hashes,
                    args=(account, file_props))
                self.hashThread.start()
        else: # we send a file
            jid = file_props.receiver
            gajim.socks5queue.remove_sender(file_props.sid, True, True)
            self.popup_ft_result(account, jid, file_props)

    def popup_ft_result(self, account, jid, file_props):
        ft = self.instances['file_transfers']
        if helpers.allow_popup_window(account):
            if file_props.error == 0:
                if gajim.config.get('notify_on_file_complete'):
                    ft.show_completed(jid, file_props)
            elif file_props.error == -1:
                ft.show_stopped(jid, file_props,
                        error_msg=_('Remote contact stopped transfer'))
            elif file_props.error == -6:
                ft.show_stopped(jid, file_props,
                    error_msg=_('Error opening file'))
            elif file_props.error == -10:
                ft.show_hash_error(jid, file_props, account)
            elif file_props.error == -12:
                ft.show_stopped(jid, file_props,
                    error_msg=_('SSL certificate error'))
            return

        msg_type = ''
        event_type = ''
        if file_props.error == 0 and gajim.config.get(
        'notify_on_file_complete'):
            msg_type = 'file-completed'
            event_type = _('File Transfer Completed')
        elif file_props.error in (-1, -6):
            msg_type = 'file-stopped'
            event_type = _('File Transfer Stopped')
        elif file_props.error  == -10:
            msg_type = 'file-hash-error'
            event_type = _('File Transfer Failed')

        if event_type == '':
            # FIXME: ugly workaround (this can happen Gajim sent, Gaim recvs)
            # this should never happen but it does. see process_result() in
            # socks5.py
            # who calls this func (sth is really wrong unless this func is also
            # registered as progress_cb
            return

        if msg_type:
            self.add_event(account, jid, msg_type, file_props)

        if file_props is not None:
            if file_props.type_ == 'r':
                # get the name of the sender, as it is in the roster
                sender = file_props.sender.split('/')[0]
                name = gajim.contacts.get_first_contact_from_jid(account,
                    sender).get_shown_name()
                filename = os.path.basename(file_props.file_name)
                if event_type == _('File Transfer Completed'):
                    txt = _('You successfully received %(filename)s from '
                        '%(name)s.') % {'filename': filename, 'name': name}
                    img_name = 'gajim-ft_done'
                elif event_type == _('File Transfer Stopped'):
                    txt = _('File transfer of %(filename)s from %(name)s '
                        'stopped.') % {'filename': filename, 'name': name}
                    img_name = 'gajim-ft_stopped'
                else: # ft hash error
                    txt = _('File transfer of %(filename)s from %(name)s '
                        'failed.') % {'filename': filename, 'name': name}
                    img_name = 'gajim-ft_stopped'
            else:
                receiver = file_props.receiver
                if hasattr(receiver, 'jid'):
                    receiver = receiver.jid
                receiver = receiver.split('/')[0]
                # get the name of the contact, as it is in the roster
                name = gajim.contacts.get_first_contact_from_jid(account,
                    receiver).get_shown_name()
                filename = os.path.basename(file_props.file_name)
                if event_type == _('File Transfer Completed'):
                    txt = _('You successfully sent %(filename)s to %(name)s.')\
                        % {'filename': filename, 'name': name}
                    img_name = 'gajim-ft_done'
                elif event_type == _('File Transfer Stopped'):
                    txt = _('File transfer of %(filename)s to %(name)s '
                        'stopped.') % {'filename': filename, 'name': name}
                    img_name = 'gajim-ft_stopped'
                else: # ft hash error
                    txt = _('File transfer of %(filename)s to %(name)s '
                        'failed.') % {'filename': filename, 'name': name}
                    img_name = 'gajim-ft_stopped'
            path = gtkgui_helpers.get_icon_path(img_name, 48)
        else:
            txt = ''
            path = ''

        if gajim.config.get('notify_on_file_complete') and \
        (gajim.config.get('autopopupaway') or \
        gajim.connections[account].connected in (2, 3)):
            # we want to be notified and we are online/chat or we don't mind
            # bugged when away/na/busy
            notify.popup(event_type, jid, account, msg_type, path_to_image=path,
                    title=event_type, text=txt)

    def ask_offline_status(self, account):
        for contact in gajim.contacts.iter_contacts(account):
            gajim.connections[account].request_last_status_time(contact.jid,
                contact.resource)

    def handle_event_signed_in(self, obj):
        """
        SIGNED_IN event is emitted when we sign in, so handle it
        """
        # ('SIGNED_IN', account, ())
        # block signed in notifications for 30 seconds
        account = obj.conn.name
        gajim.block_signed_in_notifications[account] = True
        state = self.sleeper.getState()
        connected = obj.conn.connected
        if gajim.config.get('ask_offline_status_on_connection'):
            # Ask offline status in 1 minute so w'are sure we got all online
            # presences
            GLib.timeout_add_seconds(60, self.ask_offline_status, account)
        if state != sleepy.STATE_UNKNOWN and connected in (2, 3):
            # we go online or free for chat, so we activate auto status
            gajim.sleeper_state[account] = 'online'
        elif not ((state == sleepy.STATE_AWAY and connected == 4) or \
        (state == sleepy.STATE_XA and connected == 5)):
            # If we are autoaway/xa and come back after a disconnection, do
            # nothing
            # Else disable autoaway
            gajim.sleeper_state[account] = 'off'

        if obj.conn.archiving_supported:
            # Start merging logs from server
            obj.conn.request_modifications_page(gajim.config.get_per('accounts',
                account, 'last_archiving_time'))
            gajim.config.set_per('accounts', account, 'last_archiving_time',
                time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))

        invisible_show = gajim.SHOW_LIST.index('invisible')
        # We cannot join rooms if we are invisible
        if connected == invisible_show:
            return
        # send currently played music
        if obj.conn.pep_supported and dbus_support.supported and \
        gajim.config.get_per('accounts', account, 'publish_tune'):
            self.enable_music_listener()
        # enable location listener
        if obj.conn.pep_supported and dbus_support.supported and \
        gajim.config.get_per('accounts', account, 'publish_location'):
            location_listener.enable()


    def handle_event_metacontacts(self, obj):
        gajim.contacts.define_metacontacts(obj.conn.name, obj.meta_list)

    def handle_atom_entry(self, obj):
        AtomWindow.newAtomEntry(obj.atom_entry)

    def handle_event_failed_decrypt(self, obj):
        details = _('Unable to decrypt message from %s\nIt may have been '
            'tampered with.') % obj.fjid
        dialogs.WarningDialog(_('Unable to decrypt message'), details)

    def handle_event_zc_name_conflict(self, obj):
        def on_ok(new_name):
            gajim.config.set_per('accounts', obj.conn.name, 'name', new_name)
            show = obj.conn.old_show
            status = obj.conn.status
            obj.conn.username = new_name
            obj.conn.change_status(show, status)
        def on_cancel():
            obj.conn.change_status('offline', '')

        dlg = dialogs.InputDialog(_('Username Conflict'),
            _('Please type a new username for your local account'),
            input_str=obj.alt_name, is_modal=True, ok_handler=on_ok,
            cancel_handler=on_cancel, transient_for=self.roster.window)

    def handle_event_resource_conflict(self, obj):
        # ('RESOURCE_CONFLICT', account, ())
        # First we go offline, but we don't overwrite status message
        account = obj.conn.name
        conn = obj.conn
        self.roster.send_status(account, 'offline', conn.status)
        def on_ok(new_resource):
            gajim.config.set_per('accounts', account, 'resource', new_resource)
            self.roster.send_status(account, conn.old_show, conn.status)
        proposed_resource = conn.server_resource
        proposed_resource += gajim.config.get('gc_proposed_nick_char')
        dlg = dialogs.ResourceConflictDialog(_('Resource Conflict'),
            _('You are already connected to this account with the same '
            'resource. Please type a new one'), resource=proposed_resource,
            ok_handler=on_ok)

    def handle_event_jingleft_cancel(self, obj):
        ft = self.instances['file_transfers']
        file_props = None
        # get the file_props of our session
        file_props = FilesProp.getFileProp(obj.conn.name, obj.sid)
        ft.set_status(file_props, 'stop')
        file_props.error = -4 # is it the right error code?
        ft.show_stopped(obj.jid, file_props, 'Peer cancelled ' +
                            'the transfer')

    def handle_event_jingle_incoming(self, obj):
        # ('JINGLE_INCOMING', account, peer jid, sid, tuple-of-contents==(type,
        # data...))
        # TODO: conditional blocking if peer is not in roster

        account = obj.conn.name
        content_types = set(c[0] for c in obj.contents)

        # check type of jingle session
        if 'audio' in content_types or 'video' in content_types:
            # a voip session...
            # we now handle only voip, so the only thing we will do here is
            # not to return from function
            pass
        else:
            # unknown session type... it should be declined in common/jingle.py
            return

        ctrl = (self.msg_win_mgr.get_control(obj.fjid, account)
            or self.msg_win_mgr.get_control(obj.jid, account))
        if ctrl:
            if 'audio' in content_types:
                ctrl.set_audio_state('connection_received', obj.sid)
            if 'video' in content_types:
                ctrl.set_video_state('connection_received', obj.sid)

        dlg = dialogs.VoIPCallReceivedDialog.get_dialog(obj.fjid, obj.sid)
        if dlg:
            dlg.add_contents(content_types)
            return

        if helpers.allow_popup_window(account):
            dialogs.VoIPCallReceivedDialog(account, obj.fjid, obj.sid,
                content_types)
            return

        self.add_event(account, obj.jid, 'jingle-incoming', (obj.fjid, obj.sid,
                content_types))

        if helpers.allow_showing_notification(account):
            # TODO: we should use another pixmap ;-)
            txt = _('%s wants to start a voice chat.') % \
                gajim.get_name_from_jid(account, obj.fjid)
            path = gtkgui_helpers.get_icon_path('gajim-mic_active', 48)
            event_type = _('Voice Chat Request')
            notify.popup(event_type, obj.fjid, account, 'jingle-incoming',
                    path_to_image=path, title=event_type, text=txt)

    def handle_event_jingle_connected(self, obj):
        # ('JINGLE_CONNECTED', account, (peerjid, sid, media))
        if obj.media in ('audio', 'video'):
            account = obj.conn.name
            ctrl = (self.msg_win_mgr.get_control(obj.fjid, account)
                or self.msg_win_mgr.get_control(obj.jid, account))
            if ctrl:
                if obj.media == 'audio':
                    ctrl.set_audio_state('connected', obj.sid)
                else:
                    ctrl.set_video_state('connected', obj.sid)

    def handle_event_jingle_disconnected(self, obj):
        # ('JINGLE_DISCONNECTED', account, (peerjid, sid, reason))
        account = obj.conn.name
        ctrl = (self.msg_win_mgr.get_control(obj.fjid, account)
            or self.msg_win_mgr.get_control(obj.jid, account))
        if ctrl:
            if obj.media is None:
                ctrl.stop_jingle(sid=obj.sid, reason=obj.reason)
            elif obj.media == 'audio':
                ctrl.set_audio_state('stop', sid=obj.sid, reason=obj.reason)
            elif obj.media == 'video':
                ctrl.set_video_state('stop', sid=obj.sid, reason=obj.reason)
        dialog = dialogs.VoIPCallReceivedDialog.get_dialog(obj.fjid, obj.sid)
        if dialog:
            if obj.media is None:
                dialog.dialog.destroy()
            else:
                dialog.remove_contents((obj.media, ))

    def handle_event_jingle_error(self, obj):
        # ('JINGLE_ERROR', account, (peerjid, sid, reason))
        account = obj.conn.name
        ctrl = (self.msg_win_mgr.get_control(obj.fjid, account)
            or self.msg_win_mgr.get_control(obj.jid, account))
        if ctrl:
            ctrl.set_audio_state('error', reason=obj.reason)

    def handle_event_roster_item_exchange(self, obj):
        # data = (action in [add, delete, modify], exchange_list, jid_from)
        dialogs.RosterItemExchangeWindow(obj.conn.name, obj.action,
            obj.exchange_items_list, obj.fjid)

    def handle_event_ssl_error(self, obj):
        # ('SSL_ERROR', account, (text, errnum, cert, sha1_fingerprint, sha256_fingerprint))
        account = obj.conn.name
        server = gajim.config.get_per('accounts', account, 'hostname')

        def on_ok(is_checked):
            del self.instances[account]['online_dialog']['ssl_error']
            if is_checked[0]:
                # Check if cert is already in file
                certs = ''
                if os.path.isfile(gajim.MY_CACERTS):
                    f = open(gajim.MY_CACERTS)
                    certs = f.read()
                    f.close()
                if obj.cert in certs:
                    dialogs.ErrorDialog(_('Certificate Already in File'),
                        _('This certificate is already in file %s, so it\'s '
                        'not added again.') % gajim.MY_CACERTS)
                else:
                    f = open(gajim.MY_CACERTS, 'a')
                    f.write(server + '\n')
                    f.write(obj.cert + '\n\n')
                    f.close()
            gajim.config.set_per('accounts', account, 'ssl_fingerprint_sha1',
                obj.fingerprint_sha1)
            gajim.config.set_per('accounts', account, 'ssl_fingerprint_sha256',
                obj.fingerprint_sha256)
            if is_checked[1]:
                ignore_ssl_errors = gajim.config.get_per('accounts', account,
                    'ignore_ssl_errors').split()
                ignore_ssl_errors.append(str(obj.error_num))
                gajim.config.set_per('accounts', account, 'ignore_ssl_errors',
                    ' '.join(ignore_ssl_errors))
            obj.conn.ssl_certificate_accepted()

        def on_cancel():
            del self.instances[account]['online_dialog']['ssl_error']
            obj.conn.disconnect(on_purpose=True)
            gajim.nec.push_incoming_event(OurShowEvent(None, conn=obj.conn,
                show='offline'))

        pritext = _('Error verifying SSL certificate')
        sectext = _('There was an error verifying the SSL certificate of your '
            'jabber server: %(error)s\nDo you still want to connect to this '
            'server?') % {'error': obj.error_text}
        if obj.error_num in (18, 27):
            checktext1 = _('Add this certificate to the list of trusted '
            'certificates.\nSHA1 fingerprint of the certificate:\n%s'
            '\nSHA256 fingerprint of the certificate:\n%s') % \
            (obj.fingerprint_sha1, obj.fingerprint_sha256)
        else:
            checktext1 = ''
        checktext2 = _('Ignore this error for this certificate.')
        if 'ssl_error' in self.instances[account]['online_dialog']:
            self.instances[account]['online_dialog']['ssl_error'].destroy()
        self.instances[account]['online_dialog']['ssl_error'] = \
            dialogs.SSLErrorDialog(obj.conn.name, obj.certificate, pritext,
            sectext, checktext1, checktext2, on_response_ok=on_ok,
            on_response_cancel=on_cancel)
        self.instances[account]['online_dialog']['ssl_error'].set_title(
            _('SSL Certificate Verification for %s') % account)

    def handle_event_fingerprint_error(self, obj):
        # ('FINGERPRINT_ERROR', account, (new_fingerprint_sha1,new_fingerprint_sha256,))
        account = obj.conn.name
        def on_yes(is_checked):
            del self.instances[account]['online_dialog']['fingerprint_error']
            gajim.config.set_per('accounts', account, 'ssl_fingerprint_sha1',
                obj.new_fingerprint_sha1)
            gajim.config.set_per('accounts', account, 'ssl_fingerprint_sha256',
                obj.new_fingerprint_sha256)
            # Reset the ignored ssl errors
            gajim.config.set_per('accounts', account, 'ignore_ssl_errors', '')
            obj.conn.ssl_certificate_accepted()

        def on_no():
            del self.instances[account]['online_dialog']['fingerprint_error']
            obj.conn.disconnect(on_purpose=True)
            gajim.nec.push_incoming_event(OurShowEvent(None, conn=obj.conn,
                show='offline'))

        pritext = _('SSL certificate error')
        sectext = _('It seems the SSL certificate of account %(account)s has '
            'changed or your connection is being hacked.\n\nOld SHA-1 fingerprint: '
            '%(old_sha1)s\nOld SHA-256 fingerprint: %(old_sha256)s\n\n'
            'New SHA-1 fingerprint: %(new_sha1)s\nNew SHA-256 fingerprint: '
            '%(new_sha256)s\n\nDo you still want to connect '
            'and update the fingerprint of the certificate?') % \
            {'account': account, 
            'old_sha1': gajim.config.get_per('accounts', account, 'ssl_fingerprint_sha1'),
            'old_sha256': gajim.config.get_per('accounts', account, 'ssl_fingerprint_sha256'),
            'new_sha1': obj.new_fingerprint_sha1,
            'new_sha256': obj.new_fingerprint_sha256}
        if 'fingerprint_error' in self.instances[account]['online_dialog']:
            self.instances[account]['online_dialog']['fingerprint_error'].\
                destroy()
        self.instances[account]['online_dialog']['fingerprint_error'] = \
            dialogs.CheckFingerprintDialog(pritext, sectext, on_response_yes=on_yes,
            on_response_no=on_no, account=obj.conn.name,
            certificate=obj.certificate)

    def handle_event_plain_connection(self, obj):
        # ('PLAIN_CONNECTION', account, (connection))
        def on_ok(is_checked):
            if not is_checked[0]:
                if is_checked[1]:
                    gajim.config.set_per('accounts', obj.conn.name,
                        'action_when_plaintext_connection', 'disconnect')
                on_cancel()
                return
            # On cancel call del self.instances, so don't call it another time
            # before
            del self.instances[obj.conn.name]['online_dialog']\
                ['plain_connection']
            if is_checked[1]:
                gajim.config.set_per('accounts', obj.conn.name,
                    'action_when_plaintext_connection', 'connect')
            obj.conn.connection_accepted(obj.xmpp_client, 'plain')

        def on_cancel():
            del self.instances[obj.conn.name]['online_dialog']\
                ['plain_connection']
            obj.conn.disconnect(on_purpose=True)
            gajim.nec.push_incoming_event(OurShowEvent(None, conn=obj.conn,
                show='offline'))

        if 'plain_connection' in self.instances[obj.conn.name]['online_dialog']:
            self.instances[obj.conn.name]['online_dialog']['plain_connection'].\
                destroy()
        self.instances[obj.conn.name]['online_dialog']['plain_connection'] = \
            dialogs.PlainConnectionDialog(obj.conn.name, on_ok, on_cancel)

    def handle_event_insecure_ssl_connection(self, obj):
        # ('INSECURE_SSL_CONNECTION', account, (connection, connection_type))
        def on_ok(is_checked):
            if not is_checked[0]:
                on_cancel()
                return
            del self.instances[obj.conn.name]['online_dialog']['insecure_ssl']
            if is_checked[1]:
                gajim.config.set_per('accounts', obj.conn.name,
                    'warn_when_insecure_ssl_connection', False)
            if obj.conn.connected == 0:
                # We have been disconnecting (too long time since window is
                # opened)
                # re-connect with auto-accept
                obj.conn.connection_auto_accepted = True
                show, msg = obj.conn.continue_connect_info[:2]
                self.roster.send_status(obj.conn.name, show, msg)
                return
            obj.conn.connection_accepted(obj.xmpp_client, obj.conn_type)

        def on_cancel():
            del self.instances[obj.conn.name]['online_dialog']['insecure_ssl']
            obj.conn.disconnect(on_purpose=True)
            gajim.nec.push_incoming_event(OurShowEvent(None, conn=obj.conn,
                show='offline'))

        pritext = _('Insecure connection')
        sectext = _('You are about to send your password on an insecure '
            'connection. You should install PyOpenSSL to prevent that. Are you '
            'sure you want to do that?')
        checktext1 = _('Yes, I really want to connect insecurely')
        checktext2 = _('_Do not ask me again')
        if 'insecure_ssl' in self.instances[obj.conn.name]['online_dialog']:
            self.instances[obj.conn.name]['online_dialog']['insecure_ssl'].\
                destroy()
        self.instances[obj.conn.name]['online_dialog']['insecure_ssl'] = \
            dialogs.ConfirmationDialogDoubleCheck(pritext, sectext, checktext1,
            checktext2, on_response_ok=on_ok, on_response_cancel=on_cancel,
            is_modal=False)

    def handle_event_insecure_password(self, obj):
        # ('INSECURE_PASSWORD', account, ())
        def on_ok(is_checked):
            if not is_checked[0]:
                on_cancel()
                return
            del self.instances[obj.conn.name]['online_dialog']\
                ['insecure_password']
            if is_checked[1]:
                gajim.config.set_per('accounts', obj.conn.name,
                    'warn_when_insecure_password', False)
            if obj.conn.connected == 0:
                # We have been disconnecting (too long time since window is
                # opened)
                # re-connect with auto-accept
                obj.conn.connection_auto_accepted = True
                show, msg = obj.conn.continue_connect_info[:2]
                self.roster.send_status(obj.conn.name, show, msg)
                return
            obj.conn.accept_insecure_password()

        def on_cancel():
            del self.instances[obj.conn.name]['online_dialog']\
                ['insecure_password']
            obj.conn.disconnect(on_purpose=True)
            gajim.nec.push_incoming_event(OurShowEvent(None, conn=obj.conn,
                show='offline'))

        pritext = _('Insecure connection')
        sectext = _('You are about to send your password unencrypted on an '
            'insecure connection. Are you sure you want to do that?')
        checktext1 = _('Yes, I really want to connect insecurely')
        checktext2 = _('_Do not ask me again')
        if 'insecure_password' in self.instances[obj.conn.name]\
        ['online_dialog']:
            self.instances[obj.conn.name]['online_dialog']\
                ['insecure_password'].destroy()
        self.instances[obj.conn.name]['online_dialog']['insecure_password'] = \
            dialogs.ConfirmationDialogDoubleCheck(pritext, sectext, checktext1,
            checktext2, on_response_ok=on_ok, on_response_cancel=on_cancel,
            is_modal=False)

    def create_core_handlers_list(self):
        self.handlers = {
            'DB_ERROR': [self.handle_event_db_error],
            'FILE_SEND_ERROR': [self.handle_event_file_send_error],
            'atom-entry-received': [self.handle_atom_entry],
            'bad-gpg-passphrase': [self.handle_event_bad_gpg_passphrase],
            'bookmarks-received': [self.handle_event_bookmarks],
            'client-cert-passphrase': [
                self.handle_event_client_cert_passphrase],
            'connection-lost': [self.handle_event_connection_lost],
            'failed-decrypt': [(self.handle_event_failed_decrypt, ged.GUI2)],
            'file-request-error': [self.handle_event_file_request_error],
            'file-request-received': [self.handle_event_file_request],
            'fingerprint-error': [self.handle_event_fingerprint_error],
            'gc-invitation-received': [self.handle_event_gc_invitation],
            'gc-decline-received': [self.handle_event_gc_decline],
            'gc-presence-received': [self.handle_event_gc_presence],
            'gc-message-received': [self.handle_event_gc_message],
            'gmail-notify': [self.handle_event_gmail_notify],
            'gpg-password-required': [self.handle_event_gpg_password_required],
            'gpg-trust-key': [self.handle_event_gpg_trust_key],
            'http-auth-received': [self.handle_event_http_auth],
            'information': [self.handle_event_information],
            'insecure-password': [self.handle_event_insecure_password],
            'insecure-ssl-connection': \
                [self.handle_event_insecure_ssl_connection],
            'iq-error-received': [self.handle_event_iq_error],
            'jingle-connected-received': [self.handle_event_jingle_connected],
            'jingle-disconnected-received': [
                self.handle_event_jingle_disconnected],
            'jingle-error-received': [self.handle_event_jingle_error],
            'jingle-request-received': [self.handle_event_jingle_incoming],
            'jingleFT-cancelled-received': [self.handle_event_jingleft_cancel],
            'last-result-received': [self.handle_event_last_status_time],
            'message-error': [self.handle_event_msgerror],
            'message-not-sent': [self.handle_event_msgnotsent],
            'message-sent': [self.handle_event_msgsent],
            'metacontacts-received': [self.handle_event_metacontacts],
            'muc-admin-received': [self.handle_event_gc_affiliation],
            'muc-owner-received': [self.handle_event_gc_config],
            'oauth2-credentials-required': [self.handle_oauth2_credentials],
            'our-show': [self.handle_event_status],
            'password-required': [self.handle_event_password_required],
            'plain-connection': [self.handle_event_plain_connection],
            'presence-received': [self.handle_event_presence],
            'register-agent-info-received': [self.handle_event_register_agent_info],
            'roster-info': [self.handle_event_roster_info],
            'roster-item-exchange-received': \
                [self.handle_event_roster_item_exchange],
            'signed-in': [self.handle_event_signed_in],
            'ssl-error': [self.handle_event_ssl_error],
            'stream-conflict-received': [self.handle_event_resource_conflict],
            'subscribe-presence-received': [
                self.handle_event_subscribe_presence],
            'subscribed-presence-received': [
                self.handle_event_subscribed_presence],
            'unsubscribed-presence-received': [
                self.handle_event_unsubscribed_presence],
            'vcard-received': [self.handle_event_vcard],
            'zeroconf-name-conflict': [self.handle_event_zc_name_conflict],
        }

    def register_core_handlers(self):
        """
        Register core handlers in Global Events Dispatcher (GED).

        This is part of rewriting whole events handling system to use GED.
        """
        for event_name, event_handlers in self.handlers.items():
            for event_handler in event_handlers:
                prio = ged.GUI1
                if type(event_handler) == tuple:
                    prio = event_handler[1]
                    event_handler = event_handler[0]
                gajim.ged.register_event_handler(event_name, prio,
                    event_handler)

################################################################################
### Methods dealing with gajim.events
################################################################################

    def add_event(self, account, jid, type_, event_args):
        """
        Add an event to the gajim.events var
        """
        # We add it to the gajim.events queue
        # Do we have a queue?
        jid = gajim.get_jid_without_resource(jid)
        no_queue = len(gajim.events.get_events(account, jid)) == 0
        # type_ can be gc-invitation file-send-error file-error
        #  file-request-error file-request file-completed file-stopped
        #  file-hash-error jingle-incoming
        # event_type can be in advancedNotificationWindow.events_list
        event_types = {'file-request': 'ft_request',
            'file-completed': 'ft_finished'}
        event_type = event_types.get(type_)
        show_in_roster = notify.get_show_in_roster(event_type, account, jid)
        show_in_systray = notify.get_show_in_systray(event_type, account, jid)
        event = gajim.events.create_event(type_, event_args,
            show_in_roster=show_in_roster,
            show_in_systray=show_in_systray)
        gajim.events.add_event(account, jid, event)

        self.roster.show_title()
        if no_queue: # We didn't have a queue: we change icons
            if not gajim.contacts.get_contact_with_highest_priority(account,
            jid):
                if type_ == 'gc-invitation':
                    self.roster.add_groupchat(jid, account, status='offline')
                else:
                    # add contact to roster ("Not In The Roster") if he is not
                    self.roster.add_to_not_in_the_roster(account, jid)
            else:
                self.roster.draw_contact(jid, account)

        # Select the big brother contact in roster, it's visible because it has
        # events.
        family = gajim.contacts.get_metacontacts_family(account, jid)
        if family:
            nearby_family, bb_jid, bb_account = \
                gajim.contacts.get_nearby_family_and_big_brother(family,
                account)
        else:
            bb_jid, bb_account = jid, account
        self.roster.select_contact(bb_jid, bb_account)

    def handle_event(self, account, fjid, type_):
        w = None
        ctrl = None
        session = None

        resource = gajim.get_resource_from_jid(fjid)
        jid = gajim.get_jid_without_resource(fjid)

        if type_ in ('printed_gc_msg', 'printed_marked_gc_msg', 'gc_msg'):
            w = self.msg_win_mgr.get_window(jid, account)
            if jid in self.minimized_controls[account]:
                self.roster.on_groupchat_maximized(None, jid, account)
                return
            else:
                ctrl = self.msg_win_mgr.get_gc_control(jid, account)

        elif type_ in ('printed_chat', 'chat', ''):
            # '' is for log in/out notifications

            if type_ != '':
                event = gajim.events.get_first_event(account, fjid, type_)
                if not event:
                    event = gajim.events.get_first_event(account, jid, type_)
                if not event:
                    return

            if type_ == 'printed_chat':
                ctrl = event.parameters[2]
            elif type_ == 'chat':
                session = event.parameters[8]
                ctrl = session.control
            elif type_ == '':
                ctrl = self.msg_win_mgr.get_control(fjid, account)

            if not ctrl:
                highest_contact = gajim.contacts.\
                    get_contact_with_highest_priority(account, jid)
                # jid can have a window if this resource was lower when he sent
                # message and is now higher because the other one is offline
                if resource and highest_contact.resource == resource and \
                not self.msg_win_mgr.has_window(jid, account):
                    # remove resource of events too
                    gajim.events.change_jid(account, fjid, jid)
                    resource = None
                    fjid = jid
                contact = None
                if resource:
                    contact = gajim.contacts.get_contact(account, jid, resource)
                if not contact:
                    contact = highest_contact

                ctrl = self.new_chat(contact, account, resource=resource,
                    session=session)

                gajim.last_message_time[account][jid] = 0 # long time ago

            w = ctrl.parent_win
        elif type_ in ('printed_pm', 'pm'):
            # assume that the most recently updated control we have for this
            # party is the one that this event was in
            event = gajim.events.get_first_event(account, fjid, type_)
            if not event:
                event = gajim.events.get_first_event(account, jid, type_)
            if not event:
                return

            if type_ == 'printed_pm':
                ctrl = event.parameters[2]
            elif type_ == 'pm':
                session = event.parameters[8]

            if session and session.control:
                ctrl = session.control
            elif not ctrl:
                room_jid = jid
                nick = resource
                gc_contact = gajim.contacts.get_gc_contact(account, room_jid,
                    nick)
                if gc_contact:
                    show = gc_contact.show
                else:
                    show = 'offline'
                    gc_contact = gajim.contacts.create_gc_contact(
                        room_jid=room_jid, account=account, name=nick,
                        show=show)

                if not session:
                    session = gajim.connections[account].make_new_session(
                        fjid, None, type_='pm')

                self.new_private_chat(gc_contact, account, session=session)
                ctrl = session.control

            w = ctrl.parent_win
        elif type_ in ('normal', 'file-request', 'file-request-error',
        'file-send-error', 'file-error', 'file-stopped', 'file-completed',
        'file-hash-error', 'jingle-incoming'):
            # Get the first single message event
            event = gajim.events.get_first_event(account, fjid, type_)
            if not event:
                # default to jid without resource
                event = gajim.events.get_first_event(account, jid, type_)
                if not event:
                    return
                # Open the window
                self.roster.open_event(account, jid, event)
            else:
                # Open the window
                self.roster.open_event(account, fjid, event)
        elif type_ == 'gmail':
            url = gajim.connections[account].gmail_url
            if url:
                helpers.launch_browser_mailer('url', url)
        elif type_ == 'gc-invitation':
            event = gajim.events.get_first_event(account, jid, type_)
            data = event.parameters
            dialogs.InvitationReceivedDialog(account, data[0], jid, data[2],
                    data[1], data[3])
            gajim.events.remove_events(account, jid, event)
            self.roster.draw_contact(jid, account)
        elif type_ == 'subscription_request':
            event = gajim.events.get_first_event(account, jid, type_)
            data = event.parameters
            dialogs.SubscriptionRequestWindow(jid, data[0], account, data[1])
            gajim.events.remove_events(account, jid, event)
            self.roster.draw_contact(jid, account)
        elif type_ == 'unsubscribed':
            event = gajim.events.get_first_event(account, jid, type_)
            contact = event.parameters
            self.show_unsubscribed_dialog(account, contact)
            gajim.events.remove_events(account, jid, event)
            self.roster.draw_contact(jid, account)
        if w:
            w.set_active_tab(ctrl)
            w.window.get_window().focus(Gtk.get_current_event_time())
            # Using isinstance here because we want to catch all derived types
            if isinstance(ctrl, ChatControlBase):
                tv = ctrl.conv_textview
                tv.scroll_to_end()

################################################################################
### Methods dealing with emoticons
################################################################################

    def image_is_ok(self, image):
        if not os.path.exists(image):
            return False
        img = Gtk.Image()
        try:
            img.set_from_file(image)
        except Exception:
            return False
        t = img.get_storage_type()
        if t != Gtk.ImageType.PIXBUF and t != Gtk.ImageType.ANIMATION:
            return False
        return True

    @property
    def basic_pattern_re(self):
        if not self._basic_pattern_re:
            self._basic_pattern_re = re.compile(self.basic_pattern,
                re.IGNORECASE)
        return self._basic_pattern_re

    @property
    def emot_and_basic_re(self):
        if not self._emot_and_basic_re:
            self._emot_and_basic_re = re.compile(self.emot_and_basic,
                    re.IGNORECASE + re.UNICODE)
        return self._emot_and_basic_re

    @property
    def sth_at_sth_dot_sth_re(self):
        if not self._sth_at_sth_dot_sth_re:
            self._sth_at_sth_dot_sth_re = re.compile(self.sth_at_sth_dot_sth)
        return self._sth_at_sth_dot_sth_re

    @property
    def invalid_XML_chars_re(self):
        if not self._invalid_XML_chars_re:
            self._invalid_XML_chars_re = re.compile(self.invalid_XML_chars)
        return self._invalid_XML_chars_re

    def make_regexps(self):
        # regexp meta characters are:  . ^ $ * + ? { } [ ] \ | ( )
        # one escapes the metachars with \
        # \S matches anything but ' ' '\t' '\n' '\r' '\f' and '\v'
        # \s matches any whitespace character
        # \w any alphanumeric character
        # \W any non-alphanumeric character
        # \b means word boundary. This is a zero-width assertion that
        #    matches only at the beginning or end of a word.
        # ^ matches at the beginning of lines
        #
        # * means 0 or more times
        # + means 1 or more times
        # ? means 0 or 1 time
        # | means or
        # [^*] anything but '*' (inside [] you don't have to escape metachars)
        # [^\s*] anything but whitespaces and '*'
        # (?<!\S) is a one char lookbehind assertion and asks for any leading
        #         whitespace
        # and mathces beginning of lines so we have correct formatting detection
        # even if the the text is just '*foo*'
        # (?!\S) is the same thing but it's a lookahead assertion
        # \S*[^\s\W] --> in the matching string don't match ? or ) etc.. if at
        #                the end
        # so http://be) will match http://be and http://be)be) will match
        # http://be)be

        legacy_prefixes = r"((?<=\()(www|ftp)\.([A-Za-z0-9\.\-_~:/\?#\[\]@!\$"\
            r"&'\(\)\*\+,;=]|%[A-Fa-f0-9]{2})+(?=\)))"\
            r"|((www|ftp)\.([A-Za-z0-9\.\-_~:/\?#\[\]@!\$&'\(\)\*\+,;=]"\
            r"|%[A-Fa-f0-9]{2})+"\
            r"\.([A-Za-z0-9\.\-_~:/\?#\[\]@!\$&'\(\)\*\+,;=]|%[A-Fa-f0-9]{2})+)"
        # NOTE: it's ok to catch www.gr such stuff exist!

        # FIXME: recognize xmpp: and treat it specially
        links = r"((?<=\()[A-Za-z][A-Za-z0-9\+\.\-]*:"\
            r"([\w\.\-_~:/\?#\[\]@!\$&'\(\)\*\+,;=]|%[A-Fa-f0-9]{2})+"\
            r"(?=\)))|(\w[\w\+\.\-]*:([^<>\s]|%[A-Fa-f0-9]{2})+)"

        # 2nd one: at_least_one_char@at_least_one_char.at_least_one_char
        mail = r'\bmailto:\S*[^\s\W]|' r'\b\S+@\S+\.\S*[^\s\W]'

        # detects eg. *b* *bold* *bold bold* test *bold* *bold*! (*bold*)
        # doesn't detect (it's a feature :P) * bold* *bold * * bold * test*bold*
        formatting = r'|(?<!\w)' r'\*[^\s*]' r'([^*]*[^\s*])?' r'\*(?!\w)|'\
            r'(?<!\S)' r'/[^\s/]' r'([^/]*[^\s/])?' r'/(?!\S)|'\
            r'(?<!\w)' r'_[^\s_]' r'([^_]*[^\s_])?' r'_(?!\w)'

        basic_pattern = links + '|' + mail + '|' + legacy_prefixes

        link_pattern = basic_pattern
        self.link_pattern_re = re.compile(link_pattern, re.I | re.U)

        if gajim.config.get('ascii_formatting'):
            basic_pattern += formatting
        self.basic_pattern = basic_pattern

        emoticons_pattern = ''
        if gajim.config.get('emoticons_theme'):
            # When an emoticon is bordered by an alpha-numeric character it is
            # NOT expanded.  e.g., foo:) NO, foo :) YES, (brb) NO, (:)) YES, etc
            # We still allow multiple emoticons side-by-side like :P:P:P
            # sort keys by length so :qwe emot is checked before :q
            keys = sorted(self.emoticons, key=len, reverse=True)
            emoticons_pattern_prematch = ''
            emoticons_pattern_postmatch = ''
            emoticon_length = 0
            for emoticon in keys: # travel thru emoticons list
                emoticon_escaped = re.escape(emoticon) # espace regexp metachars
                # | means or in regexp
                emoticons_pattern += emoticon_escaped + '|'
                if (emoticon_length != len(emoticon)):
                    # Build up expressions to match emoticons next to others
                    emoticons_pattern_prematch  = \
                        emoticons_pattern_prematch[:-1]  + ')|(?<='
                    emoticons_pattern_postmatch = \
                        emoticons_pattern_postmatch[:-1] + ')|(?='
                    emoticon_length = len(emoticon)
                emoticons_pattern_prematch += emoticon_escaped  + '|'
                emoticons_pattern_postmatch += emoticon_escaped + '|'
            # We match from our list of emoticons, but they must either have
            # whitespace, or another emoticon next to it to match successfully
            # [\w.] alphanumeric and dot (for not matching 8) in (2.8))
            emoticons_pattern = '|' + '(?:(?<![\w.]' + \
                emoticons_pattern_prematch[:-1] + '))' + '(?:' + \
                emoticons_pattern[:-1] + ')' + '(?:(?![\w]' + \
                emoticons_pattern_postmatch[:-1] + '))'

        # because emoticons match later (in the string) they need to be after
        # basic matches that may occur earlier
        self.emot_and_basic = basic_pattern + emoticons_pattern

        # needed for xhtml display
        self.emot_only = emoticons_pattern

        # at least one character in 3 parts (before @, after @, after .)
        self.sth_at_sth_dot_sth = r'\S+@\S+\.\S*[^\s)?]'

        # Invalid XML chars
        self.invalid_XML_chars = '[\x00-\x08]|[\x0b-\x0c]|[\x0e-\x1f]|'\
            '[\ud800-\udfff]|[\ufffe-\uffff]'

    def popup_emoticons_under_button(self, button, parent_win):
        """
        Popup the emoticons menu under button, located in parent_win
        """
        gtkgui_helpers.popup_emoticons_under_button(self.emoticons_menu,
            button, parent_win)

    def prepare_emoticons_menu(self):
        menu = Gtk.Menu()
        def emoticon_clicked(w, str_):
            if self.emoticon_menuitem_clicked:
                self.emoticon_menuitem_clicked(str_)
                # don't keep reference to CB of object
                # this will prevent making it uncollectable
                self.emoticon_menuitem_clicked = None
        def selection_done(widget):
            # remove reference to CB of object, which will
            # make it uncollectable
            self.emoticon_menuitem_clicked = None
        counter = 0
        # Calculate the side lenght of the popup to make it a square
        size = int(round(math.sqrt(len(self.emoticons_images))))
        for image in self.emoticons_images:
            # In Gtk 3.6, Gtk.MenuItem() doesn't contain a label child
            item = Gtk.MenuItem('q')
            img = Gtk.Image()
            if isinstance(image[1], GdkPixbuf.PixbufAnimation):
                img.set_from_animation(image[1])
            else:
                img.set_from_pixbuf(image[1])
            c = item.get_child()
            item.remove(c)
            item.add(img)
            item.connect('activate', emoticon_clicked, image[0])
            # add tooltip with ascii
            item.set_tooltip_text(image[0])
            menu.attach(item, counter % size, counter % size + 1,
                counter / size, counter / size + 1)
            counter += 1
        menu.connect('selection-done', selection_done)
        menu.show_all()
        return menu

    def _init_emoticons(self, path, need_reload = False):
        #initialize emoticons dictionary and unique images list
        self.emoticons_images = list()
        self.emoticons = dict()
        self.emoticons_animations = dict()

        sys.path.insert(0, path)
        import emoticons
        try:
            if need_reload:
                # we need to reload else that doesn't work when changing
                # emoticons set
                import imp
                imp.reload(emoticons)
            emots = emoticons.emoticons
        except Exception as e:
            return True
        for emot_filename in emots:
            emot_file = os.path.join(path, emot_filename)
            if not self.image_is_ok(emot_file):
                continue
            for emot in emots[emot_filename]:
                emot = emot
                # This avoids duplicated emoticons with the same image eg. :)
                # and :-)
                if not emot_file in self.emoticons.values():
                    if emot_file.endswith('.gif'):
                        pix = GdkPixbuf.PixbufAnimation.new_from_file(emot_file)
                    else:
                        pix = GdkPixbuf.Pixbuf.new_from_file_at_size(emot_file,
                            16, 16)
                    self.emoticons_images.append((emot, pix))
                self.emoticons[emot.upper()] = emot_file
        del emoticons
        sys.path.remove(path)

    def init_emoticons(self, need_reload = False):
        emot_theme = gajim.config.get('emoticons_theme')
        if not emot_theme:
            return

        transient_for = None
        if 'preferences' in gajim.interface.instances:
            transient_for = gajim.interface.instances['preferences'].window

        path = os.path.join(gajim.DATA_DIR, 'emoticons', emot_theme)
        if not os.path.exists(path):
            # It's maybe a user theme
            path = os.path.join(gajim.MY_EMOTS_PATH, emot_theme)
            if not os.path.exists(path):
                # theme doesn't exist, disable emoticons
                dialogs.WarningDialog(_('Emoticons disabled'),
                    _('Your configured emoticons theme has not been found, so '
                    'emoticons have been disabled.'),
                    transient_for=transient_for)
                gajim.config.set('emoticons_theme', '')
                return
        if self._init_emoticons(path, need_reload):
            dialogs.WarningDialog(_('Emoticons disabled'),
                    _('Your configured emoticons theme cannot been loaded. You '
                    'maybe need to update the format of emoticons.py file. See '
                    'http://trac.gajim.org/wiki/Emoticons for more details.'),
                    transient_for=transient_for)
            gajim.config.set('emoticons_theme', '')
            return
        if len(self.emoticons) == 0:
            # maybe old format of emoticons file, try to convert it
            try:
                import pprint
                import emoticons
                emots = emoticons.emoticons
                fd = open(os.path.join(path, 'emoticons.py'), 'w')
                fd.write('emoticons = ')
                pprint.pprint( dict([
                    (file_, [i for i in emots.keys() if emots[i] == file_])
                    for file_ in set(emots.values())]), fd)
                fd.close()
                del emoticons
                self._init_emoticons(path, need_reload=True)
            except Exception:
                pass
            if len(self.emoticons) == 0:
                dialogs.WarningDialog(_('Emoticons disabled'),
                    _('Your configured emoticons theme cannot been loaded. You '
                    'maybe need to update the format of emoticons.py file. See '
                    'http://trac.gajim.org/wiki/Emoticons for more details.'),
                    transient_for=transient_for)
                gajim.config.set('emoticons_theme', '')
        if self.emoticons_menu:
            self.emoticons_menu.destroy()
        self.emoticons_menu = self.prepare_emoticons_menu()

################################################################################
### Methods for opening new messages controls
################################################################################

    def join_gc_room(self, account, room_jid, nick, password, minimize=False,
                    is_continued=False):
        """
        Join the room immediately
        """

        if gajim.contacts.get_contact(account, room_jid) and \
        not gajim.contacts.get_contact(account, room_jid).is_groupchat():
            dialogs.ErrorDialog(_('This is not a group chat'),
                _('%s is not the name of a group chat.') % room_jid)
            return

        if not nick:
            nick = gajim.nicks[account]

        minimized_control = gajim.interface.minimized_controls[account].get(
            room_jid, None)

        if (self.msg_win_mgr.has_window(room_jid, account) or \
        minimized_control) and gajim.gc_connected[account][room_jid]:
            if self.msg_win_mgr.has_window(room_jid, account):
                gc_ctrl = self.msg_win_mgr.get_gc_control(room_jid, account)
                win = gc_ctrl.parent_win
                win.set_active_tab(gc_ctrl)
            else:
                self.roster.on_groupchat_maximized(None, room_jid, account)
            dialogs.ErrorDialog(_('You are already in group chat %s') % \
                room_jid)
            return

        invisible_show = gajim.SHOW_LIST.index('invisible')
        if gajim.connections[account].connected == invisible_show:
            dialogs.ErrorDialog(
                _('You cannot join a group chat while you are invisible'))
            return

        if minimized_control is None and not self.msg_win_mgr.has_window(
        room_jid, account):
            # Join new groupchat
            if minimize:
                # GCMIN
                contact = gajim.contacts.create_contact(jid=room_jid,
                    account=account, name=nick)
                gc_control = GroupchatControl(None, contact, account)
                gajim.interface.minimized_controls[account][room_jid] = \
                    gc_control
                self.roster.add_groupchat(room_jid, account)
            else:
                self.new_room(room_jid, nick, account,
                    is_continued=is_continued)
        elif minimized_control is None:
            # We are already in that groupchat
            gc_control = self.msg_win_mgr.get_gc_control(room_jid, account)
            gc_control.nick = nick
            gc_control.parent_win.set_active_tab(gc_control)

        # Connect
        gajim.connections[account].join_gc(nick, room_jid, password)
        if password:
            gajim.gc_passwords[room_jid] = password

    def new_room(self, room_jid, nick, account, is_continued=False):
        # Get target window, create a control, and associate it with the window
        # GCMIN
        contact = gajim.contacts.create_contact(jid=room_jid, account=account,
            name=nick)
        mw = self.msg_win_mgr.get_window(contact.jid, account)
        if not mw:
            mw = self.msg_win_mgr.create_window(contact, account,
                GroupchatControl.TYPE_ID)
        gc_control = GroupchatControl(mw, contact, account,
            is_continued=is_continued)
        mw.new_tab(gc_control)
        mw.set_active_tab(gc_control)

    def new_private_chat(self, gc_contact, account, session=None):
        conn = gajim.connections[account]
        if not session and gc_contact.get_full_jid() in conn.sessions:
            sessions = [s for s in conn.sessions[gc_contact.get_full_jid()].\
                values() if isinstance(s, ChatControlSession)]

            # look for an existing session with a chat control
            for s in sessions:
                if s.control:
                    session = s
                    break
            if not session and not len(sessions) == 0:
                # there are no sessions with chat controls, just take the first
                # one
                session = sessions[0]
        if not session:
            # couldn't find an existing ChatControlSession, just make a new one
            session = conn.make_new_session(gc_contact.get_full_jid(), None,
                'pm')

        contact = gc_contact.as_contact()
        if not session.control:
            message_window = self.msg_win_mgr.get_window(
                gc_contact.get_full_jid(), account)
            if not message_window:
                message_window = self.msg_win_mgr.create_window(contact,
                    account, message_control.TYPE_PM)

            session.control = PrivateChatControl(message_window, gc_contact,
                contact, account, session)
            message_window.new_tab(session.control)

        if gajim.events.get_events(account, gc_contact.get_full_jid()):
            # We call this here to avoid race conditions with widget validation
            session.control.read_queue()

        return session.control

    def new_chat(self, contact, account, resource=None, session=None):
        # Get target window, create a control, and associate it with the window
        type_ = message_control.TYPE_CHAT

        fjid = contact.jid
        if resource:
            fjid += '/' + resource

        mw = self.msg_win_mgr.get_window(fjid, account)
        if not mw:
            mw = self.msg_win_mgr.create_window(contact, account, type_,
                resource)

        chat_control = ChatControl(mw, contact, account, session, resource)

        mw.new_tab(chat_control)

        if len(gajim.events.get_events(account, fjid)):
            # We call this here to avoid race conditions with widget validation
            chat_control.read_queue()

        return chat_control

    def new_chat_from_jid(self, account, fjid, message=None):
        jid, resource = gajim.get_room_and_nick_from_fjid(fjid)
        contact = gajim.contacts.get_contact(account, jid, resource)
        added_to_roster = False
        if not contact:
            added_to_roster = True
            contact = self.roster.add_to_not_in_the_roster(account, jid,
                resource=resource)

        ctrl = self.msg_win_mgr.get_control(fjid, account)

        if not ctrl:
            ctrl = self.new_chat(contact, account,
                resource=resource)
            if len(gajim.events.get_events(account, fjid)):
                ctrl.read_queue()

        if message:
            buffer_ = ctrl.msg_textview.get_buffer()
            buffer_.set_text(message)
        mw = ctrl.parent_win
        mw.set_active_tab(ctrl)
        # For JEP-0172
        if added_to_roster:
            ctrl.user_nick = gajim.nicks[account]
        GLib.idle_add(mw.window.grab_focus)

        return ctrl

    def on_open_chat_window(self, widget, contact, account, resource=None,
    session=None):
        # Get the window containing the chat
        fjid = contact.jid

        if resource:
            fjid += '/' + resource

        ctrl = None

        if session:
            ctrl = session.control
        if not ctrl:
            win = self.msg_win_mgr.get_window(fjid, account)

            if win:
                ctrl = win.get_control(fjid, account)

        if not ctrl:
            ctrl = self.new_chat(contact, account, resource=resource,
                session=session)
            # last message is long time ago
            gajim.last_message_time[account][ctrl.get_full_jid()] = 0

        win = ctrl.parent_win

        win.set_active_tab(ctrl)

        if gajim.connections[account].is_zeroconf and \
        gajim.connections[account].status in ('offline', 'invisible'):
            ctrl = win.get_control(fjid, account)
            if ctrl:
                ctrl.got_disconnected()

################################################################################
### Other Methods
################################################################################

    def change_awn_icon_status(self, status):
        if not dbus_support.supported:
            # do nothing if user doesn't have D-Bus bindings
            return
        try:
            bus = dbus.SessionBus()
            if not 'com.google.code.Awn' in bus.list_names():
                # Awn is not installed
                return
        except Exception:
            return
        iconset = gajim.config.get('iconset')
        prefix = os.path.join(helpers.get_iconset_path(iconset), '32x32')
        if status in ('chat', 'away', 'xa', 'dnd', 'invisible', 'offline'):
            status = status + '.png'
        elif status == 'online':
            prefix = ''
            status = gtkgui_helpers.get_icon_path('gajim', 32)
        path = os.path.join(prefix, status)
        try:
            obj = bus.get_object('com.google.code.Awn', '/com/google/code/Awn')
            awn = dbus.Interface(obj, 'com.google.code.Awn')
            awn.SetTaskIconByName('Gajim', os.path.abspath(path))
        except Exception:
            pass

    def enable_music_listener(self):
        listener = MusicTrackListener.get()
        if not self.music_track_changed_signal:
            self.music_track_changed_signal = listener.connect(
                'music-track-changed', self.music_track_changed)
        track = listener.get_playing_track()
        self.music_track_changed(listener, track)

    def disable_music_listener(self):
        listener = MusicTrackListener.get()
        listener.disconnect(self.music_track_changed_signal)
        self.music_track_changed_signal = None

    def music_track_changed(self, unused_listener, music_track_info,
    account=None):
        if not account:
            accounts = gajim.connections.keys()
        else:
            accounts = [account]

        is_paused = hasattr(music_track_info, 'paused') and \
            music_track_info.paused == 0
        if not music_track_info or is_paused:
            artist = title = source = ''
        else:
            artist = music_track_info.artist
            title = music_track_info.title
            source = music_track_info.album
        for acct in accounts:
            if not gajim.account_is_connected(acct):
                continue
            if not gajim.connections[acct].pep_supported:
                continue
            if not gajim.config.get_per('accounts', acct, 'publish_tune'):
                continue
            if gajim.connections[acct].music_track_info == music_track_info:
                continue
            gajim.connections[acct].send_tune(artist, title, source)
            gajim.connections[acct].music_track_info = music_track_info

    def read_sleepy(self):
        """
        Check idle status and change that status if needed
        """
        if not self.sleeper.poll():
            # idle detection is not supported in that OS
            return False # stop looping in vain
        state = self.sleeper.getState()
        for account in gajim.connections:
            if account not in gajim.sleeper_state or \
            not gajim.sleeper_state[account]:
                continue
            if state == sleepy.STATE_AWAKE and \
            gajim.sleeper_state[account] in ('autoaway', 'autoxa'):
                # we go online
                self.roster.send_status(account, 'online',
                        gajim.status_before_autoaway[account])
                gajim.status_before_autoaway[account] = ''
                gajim.sleeper_state[account] = 'online'
            elif state == sleepy.STATE_AWAY and \
            gajim.sleeper_state[account] == 'online' and \
            gajim.config.get('autoaway'):
                # we save out online status
                gajim.status_before_autoaway[account] = \
                        gajim.connections[account].status
                # we go away (no auto status) [we pass True to auto param]
                auto_message = gajim.config.get('autoaway_message')
                if not auto_message:
                    auto_message = gajim.connections[account].status
                else:
                    auto_message = auto_message.replace('$S', '%(status)s')
                    auto_message = auto_message.replace('$T', '%(time)s')
                    auto_message = auto_message % {
                            'status': gajim.status_before_autoaway[account],
                            'time': gajim.config.get('autoawaytime')
                            }
                self.roster.send_status(account, 'away', auto_message,
                    auto=True)
                gajim.sleeper_state[account] = 'autoaway'
            elif state == sleepy.STATE_XA and \
            gajim.sleeper_state[account] in ('online', 'autoaway',
            'autoaway-forced') and gajim.config.get('autoxa'):
                # we go extended away [we pass True to auto param]
                auto_message = gajim.config.get('autoxa_message')
                if not auto_message:
                    auto_message = gajim.connections[account].status
                else:
                    auto_message = auto_message.replace('$S', '%(status)s')
                    auto_message = auto_message.replace('$T', '%(time)s')
                    auto_message = auto_message % {
                            'status': gajim.status_before_autoaway[account],
                            'time': gajim.config.get('autoxatime')
                            }
                self.roster.send_status(account, 'xa', auto_message, auto=True)
                gajim.sleeper_state[account] = 'autoxa'
        return True # renew timeout (loop for ever)

    def autoconnect(self):
        """
        Auto connect at startup
        """
        # dict of account that want to connect sorted by status
        shows = {}
        for a in gajim.connections:
            if gajim.config.get_per('accounts', a, 'autoconnect'):
                if gajim.config.get_per('accounts', a, 'restore_last_status'):
                    self.roster.send_status(a, gajim.config.get_per('accounts',
                        a, 'last_status'), helpers.from_one_line(
                        gajim.config.get_per('accounts', a, 'last_status_msg')))
                    continue
                show = gajim.config.get_per('accounts', a, 'autoconnect_as')
                if not show in gajim.SHOW_LIST:
                    continue
                if not show in shows:
                    shows[show] = [a]
                else:
                    shows[show].append(a)
        def on_message(message, pep_dict):
            if message is None:
                return
            for a in shows[show]:
                self.roster.send_status(a, show, message)
                self.roster.send_pep(a, pep_dict)
        for show in shows:
            message = self.roster.get_status_message(show, on_message)
        return False

    def show_systray(self):
        self.systray_enabled = True
        self.systray.show_icon()

    def hide_systray(self):
        self.systray_enabled = False
        self.systray.hide_icon()

    def on_launch_browser_mailer(self, widget, url, kind):
        helpers.launch_browser_mailer(kind, url)

    def process_connections(self):
        """
        Called each foo (200) miliseconds. Check for idlequeue timeouts
        """
        try:
            gajim.idlequeue.process()
        except Exception:
            # Otherwise, an exception will stop our loop
            timeout, in_seconds = gajim.idlequeue.PROCESS_TIMEOUT
            if in_seconds:
                GLib.timeout_add_seconds(timeout, self.process_connections)
            else:
                GLib.timeout_add(timeout, self.process_connections)
            raise
        return True # renew timeout (loop for ever)

    def save_config(self):
        err_str = parser.write()
        if err_str is not None:
            print(err_str, file=sys.stderr)
            # it is good to notify the user
            # in case he or she cannot see the output of the console
            dialogs.ErrorDialog(_('Could not save your settings and '
                'preferences'), err_str)
            sys.exit()

    def save_avatar_files(self, jid, photo, puny_nick = None, local = False):
        """
        Save an avatar to a separate file, and generate files for dbus
        notifications. An avatar can be given as a pixmap directly or as an
        decoded image
        """
        puny_jid = helpers.sanitize_filename(jid)
        path_to_file = os.path.join(gajim.AVATAR_PATH, puny_jid)
        if puny_nick:
            path_to_file = os.path.join(path_to_file, puny_nick)
        # remove old avatars
        for typ in ('jpeg', 'png'):
            if local:
                path_to_original_file = path_to_file + '_local'+  '.' + typ
            else:
                path_to_original_file = path_to_file + '.' + typ
            if os.path.isfile(path_to_original_file):
                os.remove(path_to_original_file)
        if local and photo:
            pixbuf = photo
            typ = 'png'
            extension = '_local.png' # save local avatars as png file
        else:
            pixbuf, typ = gtkgui_helpers.get_pixbuf_from_data(photo,
                want_type=True)
            if pixbuf is None:
                return
            extension = '.' + typ
            if typ not in ('jpeg', 'png'):
                gajim.log.debug('gtkpixbuf cannot save other than jpeg and '\
                    'png formats. saving %s\'avatar as png file (originaly %s)'\
                    % (jid, typ))
                typ = 'png'
                extension = '.png'
        path_to_original_file = path_to_file + extension
        try:
            pixbuf.savev(path_to_original_file, typ, [], [])
        except Exception as e:
            log.error('Error writing avatar file %s: %s' % (
                path_to_original_file, str(e)))
        # Generate and save the resized, color avatar
        pixbuf = gtkgui_helpers.get_scaled_pixbuf(pixbuf, 'notification')
        if pixbuf:
            path_to_normal_file = path_to_file + '_notif_size_colored' + \
                extension
            try:
                pixbuf.savev(path_to_normal_file, 'png', [], [])
            except Exception as e:
                log.error('Error writing avatar file %s: %s' % \
                    (path_to_original_file, str(e)))
            # Generate and save the resized, black and white avatar
            bwbuf = gtkgui_helpers.get_scaled_pixbuf(
                gtkgui_helpers.make_pixbuf_grayscale(pixbuf), 'notification')
            if bwbuf:
                path_to_bw_file = path_to_file + '_notif_size_bw' + extension
                try:
                    bwbuf.savev(path_to_bw_file, 'png', [], [])
                except Exception as e:
                    log.error('Error writing avatar file %s: %s' % \
                        (path_to_original_file, str(e)))

    def remove_avatar_files(self, jid, puny_nick = None, local = False):
        """
        Remove avatar files of a jid
        """
        puny_jid = helpers.sanitize_filename(jid)
        path_to_file = os.path.join(gajim.AVATAR_PATH, puny_jid)
        if puny_nick:
            path_to_file = os.path.join(path_to_file, puny_nick)
        for ext in ('.jpeg', '.png'):
            if local:
                ext = '_local' + ext
            path_to_original_file = path_to_file + ext
            if os.path.isfile(path_to_file + ext):
                os.remove(path_to_file + ext)
            if os.path.isfile(path_to_file + '_notif_size_colored' + ext):
                os.remove(path_to_file + '_notif_size_colored' + ext)
            if os.path.isfile(path_to_file + '_notif_size_bw' + ext):
                os.remove(path_to_file + '_notif_size_bw' + ext)

    def auto_join_bookmarks(self, account):
        """
        Autojoin bookmarked GCs that have 'auto join' on for this account
        """
        for bm in gajim.connections[account].bookmarks:
            if bm['autojoin'] in ('1', 'true'):
                jid = bm['jid']
                # Only join non-opened groupchats. Opened one are already
                # auto-joined on re-connection
                if not jid in gajim.gc_connected[account]:
                    # we are not already connected
                    minimize = bm['minimize'] in ('1', 'true')
                    self.join_gc_room(account, jid, bm['nick'],
                    bm['password'], minimize = minimize)
                elif jid in self.minimized_controls[account]:
                    # more or less a hack:
                    # On disconnect the minimized gc contact instances
                    # were set to offline. Reconnect them to show up in the
                    # roster.
                    self.roster.add_groupchat(jid, account)

    def add_gc_bookmark(self, account, name, jid, autojoin, minimize, password,
                    nick):
        """
        Add a bookmark for this account, sorted in bookmark list
        """
        bm = {
                'name': name,
                'jid': jid,
                'autojoin': autojoin,
                'minimize': minimize,
                'password': password,
                'nick': nick
        }
        place_found = False
        index = 0
        # check for duplicate entry and respect alpha order
        for bookmark in gajim.connections[account].bookmarks:
            if bookmark['jid'] == bm['jid']:
                dialogs.ErrorDialog(
                    _('Bookmark already set'),
                    _('Group Chat "%s" is already in your bookmarks.') % \
                    bm['jid'])
                return
            if bookmark['name'] > bm['name']:
                place_found = True
                break
            index += 1
        if place_found:
            gajim.connections[account].bookmarks.insert(index, bm)
        else:
            gajim.connections[account].bookmarks.append(bm)
        gajim.connections[account].store_bookmarks()
        self.roster.set_actions_menu_needs_rebuild()
        dialogs.InformationDialog(
            _('Bookmark has been added successfully'),
            _('You can manage your bookmarks via Actions menu in your roster.'))


    # does JID exist only within a groupchat?
    def is_pm_contact(self, fjid, account):
        bare_jid = gajim.get_jid_without_resource(fjid)

        gc_ctrl = self.msg_win_mgr.get_gc_control(bare_jid, account)

        if not gc_ctrl and \
        bare_jid in self.minimized_controls[account]:
            gc_ctrl = self.minimized_controls[account][bare_jid]

        return gc_ctrl and gc_ctrl.type_id == message_control.TYPE_GC

    def get_pep_icon(self, pep_obj):
        if isinstance(pep_obj, pep.UserMoodPEP):
            received_mood = pep_obj._pep_specific_data['mood']
            mood = received_mood if received_mood in pep.MOODS else 'unknown'
            return gtkgui_helpers.load_mood_icon(mood).get_pixbuf()
        elif isinstance(pep_obj, pep.UserTunePEP):
            path = os.path.join(gajim.DATA_DIR, 'emoticons', 'static', 'music.png')
            return gtk.gdk.pixbuf_new_from_file(path)
        elif isinstance(pep_obj, pep.UserActivityPEP):
            pep_ = pep_obj._pep_specific_data
            activity = pep_['activity']

            has_known_activity = activity in pep.ACTIVITIES
            has_known_subactivity = (has_known_activity  and ('subactivity' in
                pep_) and (pep_['subactivity'] in pep.ACTIVITIES[activity]))

            if has_known_activity:
                if has_known_subactivity:
                    subactivity = pep_['subactivity']
                    return gtkgui_helpers.load_activity_icon(activity,
                        subactivity).get_pixbuf()
                else:
                    return gtkgui_helpers.load_activity_icon(activity).\
                        get_pixbuf()
            else:
                return gtkgui_helpers.load_activity_icon('unknown').get_pixbuf()
        elif isinstance(pep_obj, pep.UserLocationPEP):
            icon = gtkgui_helpers.get_icon_pixmap('applications-internet',
                quiet=True)
            return icon

    def create_ipython_window(self):
        try:
            from ipython_view import IPythonView
        except ImportError:
            print('ipython_view not found')
            return
        from gi.repository import Pango

        if os.name == 'nt':
            font = 'Lucida Console 9'
        else:
            font = 'Luxi Mono 10'

        window = Gtk.Window()
        window.set_size_request(750, 550)
        window.set_resizable(True)
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        view = IPythonView()
        view.override_font(Pango.FontDescription(font))
        view.set_wrap_mode(Gtk.WrapMode.CHAR)
        sw.add(view)
        window.add(sw)
        window.show_all()
        def on_delete(win, event):
            win.hide()
            return True
        window.connect('delete_event', on_delete)
        view.updateNamespace({'gajim': gajim})
        gajim.ipython_window = window

    def run(self):
        if gajim.config.get('trayicon') != 'never':
            self.show_systray()

        self.roster = roster_window.RosterWindow()
        # Creating plugin manager
        import plugins
        gajim.plugin_manager = plugins.PluginManager()

        self.roster._before_fill()
        for account in gajim.connections:
            gajim.connections[account].load_roster_from_db()
        self.roster._after_fill()

        # get instances for windows/dialogs that will show_all()/hide()
        self.instances['file_transfers'] = dialogs.FileTransfersWindow()

        GLib.timeout_add(100, self.autoconnect)
        timeout, in_seconds = gajim.idlequeue.PROCESS_TIMEOUT
        if in_seconds:
            GLib.timeout_add_seconds(timeout, self.process_connections)
        else:
            GLib.timeout_add(timeout, self.process_connections)
        GLib.timeout_add_seconds(gajim.config.get(
                'check_idle_every_foo_seconds'), self.read_sleepy)

        # when using libasyncns we need to process resolver in regular intervals
        if resolver.USE_LIBASYNCNS:
            GLib.timeout_add(200, gajim.resolver.process)

        def remote_init():
            if gajim.config.get('remote_control'):
                try:
                    import remote_control
                    self.remote_ctrl = remote_control.Remote()
                except Exception:
                    pass
        GLib.timeout_add_seconds(5, remote_init)

    def __init__(self):
        gajim.interface = self
        gajim.thread_interface = ThreadInterface
        # This is the manager and factory of message windows set by the module
        self.msg_win_mgr = None
        self.jabber_state_images = {'16': {}, '24': {}, '32': {}, 'opened': {},
            'closed': {}}
        self.emoticons_menu = None
        # handler when an emoticon is clicked in emoticons_menu
        self.emoticon_menuitem_clicked = None
        self.minimized_controls = {}
        self.status_sent_to_users = {}
        self.status_sent_to_groups = {}
        self.gpg_passphrase = {}
        self.pass_dialog = {}
        self.db_error_dialog = None
        self.default_colors = {
                'inmsgcolor': gajim.config.get('inmsgcolor'),
                'outmsgcolor': gajim.config.get('outmsgcolor'),
                'inmsgtxtcolor': gajim.config.get('inmsgtxtcolor'),
                'outmsgtxtcolor': gajim.config.get('outmsgtxtcolor'),
                'statusmsgcolor': gajim.config.get('statusmsgcolor'),
                'urlmsgcolor': gajim.config.get('urlmsgcolor'),
                'markedmsgcolor': gajim.config.get('markedmsgcolor'),
        }

        self.handlers = {}
        self.roster = None
        self._invalid_XML_chars_re = None
        self._basic_pattern_re = None
        self._emot_and_basic_re = None
        self._sth_at_sth_dot_sth_re = None
        self.link_pattern_re = None
        self.invalid_XML_chars = None
        self.basic_pattern = None
        self.emot_and_basic = None
        self.sth_at_sth_dot_sth = None
        self.emot_only = None
        self.emoticons = []
        self.emoticons_animations = {}
        self.emoticons_images = {}

        cfg_was_read = parser.read()

        if not cfg_was_read:
            # enable plugin_installer by default when creating config file
            gajim.config.set_per('plugins', 'plugin_installer', 'active', True)

        gajim.logger.reset_shown_unread_messages()
        # override logging settings from config (don't take care of '-q' option)
        if gajim.config.get('verbose'):
            logging_helpers.set_verbose()

        # Is Gajim default app?
        if os.name != 'nt' and gajim.config.get('check_if_gajim_is_default'):
            gtkgui_helpers.possibly_set_gajim_as_xmpp_handler()

        for account in gajim.config.get_per('accounts'):
            if gajim.config.get_per('accounts', account, 'is_zeroconf'):
                gajim.ZEROCONF_ACC_NAME = account
                break
        # Is gnome configured to activate row on single click ?
        try:
            from gi.repository import GConf
            client = GConf.Client.get_default()
            click_policy = client.get_string(
                    '/apps/nautilus/preferences/click_policy')
            if click_policy == 'single':
                gajim.single_click = True
        except Exception:
            pass
        # add default status messages if there is not in the config file
        if len(gajim.config.get_per('statusmsg')) == 0:
            default = gajim.config.statusmsg_default
            for msg in default:
                gajim.config.add_per('statusmsg', msg)
                gajim.config.set_per('statusmsg', msg, 'message',
                    default[msg][0])
                gajim.config.set_per('statusmsg', msg, 'activity',
                    default[msg][1])
                gajim.config.set_per('statusmsg', msg, 'subactivity',
                    default[msg][2])
                gajim.config.set_per('statusmsg', msg, 'activity_text',
                    default[msg][3])
                gajim.config.set_per('statusmsg', msg, 'mood',
                    default[msg][4])
                gajim.config.set_per('statusmsg', msg, 'mood_text',
                    default[msg][5])
        #add default themes if there is not in the config file
        theme = gajim.config.get('roster_theme')
        if not theme in gajim.config.get_per('themes'):
            gajim.config.set('roster_theme', _('default'))
        if len(gajim.config.get_per('themes')) == 0:
            d = ['accounttextcolor', 'accountbgcolor', 'accountfont',
                'accountfontattrs', 'grouptextcolor', 'groupbgcolor',
                'groupfont', 'groupfontattrs', 'contacttextcolor',
                'contactbgcolor', 'contactfont', 'contactfontattrs',
                'bannertextcolor', 'bannerbgcolor']

            default = gajim.config.themes_default
            for theme_name in default:
                gajim.config.add_per('themes', theme_name)
                theme = default[theme_name]
                for o in d:
                    gajim.config.set_per('themes', theme_name, o,
                        theme[d.index(o)])
        # Add Tor proxy if there is not in the config
        if len(gajim.config.get_per('proxies')) == 0:
            default = gajim.config.proxies_default
            for proxy in default:
                gajim.config.add_per('proxies', proxy)
                gajim.config.set_per('proxies', proxy, 'type',
                    default[proxy][0])
                gajim.config.set_per('proxies', proxy, 'host',
                    default[proxy][1])
                gajim.config.set_per('proxies', proxy, 'port',
                    default[proxy][2])


        gajim.idlequeue = idlequeue.get_idlequeue()
        # resolve and keep current record of resolved hosts
        gajim.resolver = resolver.get_resolver(gajim.idlequeue)
        gajim.socks5queue = socks5.SocksQueue(gajim.idlequeue,
            self.handle_event_file_rcv_completed,
            self.handle_event_file_progress,
            self.handle_event_file_error)
        gajim.proxy65_manager = proxy65_manager.Proxy65Manager(gajim.idlequeue)
        gajim.default_session_type = ChatControlSession

        # Creating Network Events Controller
        from common import nec
        gajim.nec = nec.NetworkEventsController()
        gajim.notification = notify.Notification()

        self.create_core_handlers_list()
        self.register_core_handlers()

        if gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME, 'active') \
        and gajim.HAVE_ZEROCONF:
            gajim.connections[gajim.ZEROCONF_ACC_NAME] = \
                connection_zeroconf.ConnectionZeroconf(gajim.ZEROCONF_ACC_NAME)
        for account in gajim.config.get_per('accounts'):
            if not gajim.config.get_per('accounts', account, 'is_zeroconf') and\
            gajim.config.get_per('accounts', account, 'active'):
                gajim.connections[account] = Connection(account)

        # gtk hooks
#        Gtk.about_dialog_set_email_hook(self.on_launch_browser_mailer, 'mail')
#        Gtk.about_dialog_set_url_hook(self.on_launch_browser_mailer, 'url')
#        Gtk.link_button_set_uri_hook(self.on_launch_browser_mailer, 'url')

        self.instances = {}

        for a in gajim.connections:
            self.instances[a] = {'infos': {}, 'disco': {}, 'gc_config': {},
                'search': {}, 'online_dialog': {}, 'sub_request': {}}
            # online_dialog contains all dialogs that have a meaning only when
            # we are not disconnected
            self.minimized_controls[a] = {}
            gajim.contacts.add_account(a)
            gajim.groups[a] = {}
            gajim.gc_connected[a] = {}
            gajim.automatic_rooms[a] = {}
            gajim.newly_added[a] = []
            gajim.to_be_removed[a] = []
            gajim.nicks[a] = gajim.config.get_per('accounts', a, 'name')
            gajim.block_signed_in_notifications[a] = True
            gajim.sleeper_state[a] = 0
            gajim.encrypted_chats[a] = []
            gajim.last_message_time[a] = {}
            gajim.status_before_autoaway[a] = ''
            gajim.transport_avatar[a] = {}
            gajim.gajim_optional_features[a] = []
            gajim.caps_hash[a] = ''

        helpers.update_optional_features()
        # prepopulate data which we are sure of; note: we do not log these info
        for account in gajim.connections:
            gajimcaps = caps_cache.capscache[('sha-1',
                gajim.caps_hash[account])]
            gajimcaps.identities = [gajim.gajim_identity]
            gajimcaps.features = gajim.gajim_common_features + \
                gajim.gajim_optional_features[account]

        self.remote_ctrl = None

        if gajim.config.get('networkmanager_support') and \
        dbus_support.supported:
            import network_manager_listener

        if dbus_support.supported:
            import upower_listener
            import logind_listener

        # Handle gnome screensaver
        if dbus_support.supported:
            def gnome_screensaver_ActiveChanged_cb(active):
                if not active:
                    for account in gajim.connections:
                        if gajim.sleeper_state[account] == 'autoaway-forced':
                            # We came back online ofter gnome-screensaver
                            # autoaway
                            self.roster.send_status(account, 'online',
                                gajim.status_before_autoaway[account])
                            gajim.status_before_autoaway[account] = ''
                            gajim.sleeper_state[account] = 'online'
                    return
                if not gajim.config.get('autoaway'):
                    # Don't go auto away if user disabled the option
                    return
                for account in gajim.connections:
                    if account not in gajim.sleeper_state or \
                                    not gajim.sleeper_state[account]:
                        continue
                    if gajim.sleeper_state[account] == 'online':
                        # we save out online status
                        gajim.status_before_autoaway[account] = \
                                gajim.connections[account].status
                        # we go away (no auto status) [we pass True to auto
                        # param]
                        auto_message = gajim.config.get('autoaway_message')
                        if not auto_message:
                            auto_message = gajim.connections[account].status
                        else:
                            auto_message = auto_message.replace('$S',
                                '%(status)s')
                            auto_message = auto_message.replace('$T',
                                '%(time)s')
                            auto_message = auto_message % {
                                'status': gajim.status_before_autoaway[account],
                                'time': gajim.config.get('autoxatime')}
                        self.roster.send_status(account, 'away', auto_message,
                            auto=True)
                        gajim.sleeper_state[account] = 'autoaway-forced'

            try:
                bus = dbus.SessionBus()
                bus.add_signal_receiver(gnome_screensaver_ActiveChanged_cb,
                    'ActiveChanged', 'org.gnome.ScreenSaver')
            except Exception:
                pass

        self.show_vcard_when_connect = []

        self.sleeper = sleepy.Sleepy(
            gajim.config.get('autoawaytime') * 60, # make minutes to seconds
            gajim.config.get('autoxatime') * 60)

        gtkgui_helpers.make_jabber_state_images()

        self.systray_enabled = False

        import statusicon
        self.systray = statusicon.StatusIcon()

        pixs = []
        for size in (16, 32, 48, 64, 128):
            pix = gtkgui_helpers.get_icon_pixmap('gajim', size)
            if pix:
                pixs.append(pix)
        if pixs:
            # set the icon to all windows
            Gtk.Window.set_default_icon_list(pixs)

        self.init_emoticons()
        self.make_regexps()

        # get transports type from DB
        gajim.transport_type = gajim.logger.get_transports_type()

        # test is dictionnary is present for speller
        if gajim.config.get('use_speller'):
            lang = gajim.config.get('speller_language')
            if not lang:
                lang = gajim.LANG
            tv = Gtk.TextView()
            try:
                import gtkspell
                spell = gtkspell.Spell(tv, lang)
            except (ImportError, TypeError, RuntimeError, OSError):
                dialogs.AspellDictError(lang)

        if gajim.config.get('soundplayer') == '':
            # only on first time Gajim starts
            commands = ('paplay', 'aplay', 'play', 'ossplay')
            for command in commands:
                if helpers.is_in_path(command):
                    if command == 'paplay':
                        command += ' -n gajim'
                    if command in ('aplay', 'play'):
                        command += ' -q'
                    elif command == 'ossplay':
                        command += ' -qq'
                    gajim.config.set('soundplayer', command)
                    break

        self.last_ftwindow_update = 0

        self.music_track_changed_signal = None


class PassphraseRequest:
    def __init__(self, keyid):
        self.keyid = keyid
        self.callbacks = []
        self.dialog_created = False
        self.dialog = None
        self.passphrase = None
        self.completed = False

    def interrupt(self, account=None):
        if account:
            for (acct, cb) in self.callbacks:
                if acct == account:
                    self.callbacks.remove((acct, cb))
        else:
            self.callbacks = []
        if not len(self.callbacks):
            self.dialog.window.destroy()

    def run_callback(self, account, callback):
        gajim.connections[account].gpg_passphrase(self.passphrase)
        callback()

    def add_callback(self, account, cb):
        if self.completed:
            self.run_callback(account, cb)
        else:
            self.callbacks.append((account, cb))
            if not self.dialog_created:
                self.create_dialog(account)

    def complete(self, passphrase):
        self.passphrase = passphrase
        self.completed = True
        if passphrase is not None:
            GLib.timeout_add_seconds(30, gajim.interface.forget_gpg_passphrase,
                self.keyid)
        for (account, cb) in self.callbacks:
            self.run_callback(account, cb)
        self.callbacks = []

    def create_dialog(self, account):
        title = _('Passphrase Required')
        second = _('Enter OpenPGP key passphrase for key %(keyid)s (account '
            '%(account)s).') % {'keyid': self.keyid, 'account': account}

        def _cancel():
            # user cancelled, continue without GPG
            self.complete(None)

        def _ok(passphrase, checked, count):
            result = gajim.connections[account].test_gpg_passphrase(passphrase)
            if result == 'ok':
                # passphrase is good
                self.complete(passphrase)
                return
            elif result == 'expired':
                dialogs.ErrorDialog(_('OpenPGP key expired'),
                    _('Your OpenPGP key has expired, you will be connected to '
                    '%s without OpenPGP.') % account)
                # Don't try to connect with GPG
                gajim.connections[account].continue_connect_info[2] = False
                self.complete(None)
                return

            if count < 3:
                # ask again
                dialogs.PassphraseDialog(_('Wrong Passphrase'),
                    _('Please retype your OpenPGP passphrase or press Cancel.'),
                    ok_handler=(_ok, count + 1), cancel_handler=_cancel)
            else:
                # user failed 3 times, continue without GPG
                self.complete(None)

        self.dialog = dialogs.PassphraseDialog(title, second, ok_handler=(_ok,
            1), cancel_handler=_cancel)
        self.dialog_created = True


class ThreadInterface:
    def __init__(self, func, func_args=(), callback=None, callback_args=()):
        """
        Call a function in a thread
        """
        def thread_function(func, func_args, callback, callback_args):
            output = func(*func_args)
            if callback:
                GLib.idle_add(callback, output, *callback_args)

        Thread(target=thread_function, args=(func, func_args, callback,
                callback_args)).start()
