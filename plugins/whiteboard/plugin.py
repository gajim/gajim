## plugins/whiteboard/plugin.py
##
## Copyright (C) 2009 Jeff Ling <jeff.ummu AT gmail.com>
## Copyright (C) 2010 Yann Leboulanger <asterix AT lagaule.org>
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

'''
Whiteboard plugin.

:author: Yann Leboulanger <asterix@lagaule.org>
:since: 1st November 2010
:copyright: Copyright (2010) Yann Leboulanger <asterix@lagaule.org>
:license: GPL
'''


from common import helpers
from common import gajim
from plugins import GajimPlugin
from plugins.plugin import GajimPluginException
from plugins.helpers import log_calls, log
import common.xmpp
import gtk
import chat_control
from common import ged
from common.jingle_session import JingleSession
from common.jingle_content import JingleContent
from common.jingle_transport import JingleTransport, TransportType
import dialogs
from whiteboard_widget import Whiteboard, HAS_GOOCANVAS
from common import xmpp
from common import caps_cache

NS_JINGLE_XHTML = 'urn:xmpp:tmp:jingle:apps:xhtml'
NS_JINGLE_SXE = 'urn:xmpp:tmp:jingle:transports:sxe'
NS_SXE = 'urn:xmpp:sxe:0'

class WhiteboardPlugin(GajimPlugin):
    @log_calls('WhiteboardPlugin')
    def init(self):
        self.description = _('Shows a whiteboard in chat.'
            ' python-pygoocanvas is required.')
        self.config_dialog = None
        self.events_handlers = {
            'jingle-request-received': (ged.GUI1, self._nec_jingle_received),
            'jingle-connected-received': (ged.GUI1, self._nec_jingle_connected),
            'jingle-disconnected-received': (ged.GUI1,
                self._nec_jingle_disconnected),
            'raw-message-received': (ged.GUI1, self._nec_raw_message),
        }
        self.gui_extension_points = {
            'chat_control_base' : (self.connect_with_chat_control,
                self.disconnect_from_chat_control),
            'chat_control_base_update_toolbar': (self.update_button_state,
                None),
        }
        self.controls = []
        self.sid = None

    @log_calls('WhiteboardPlugin')
    def _compute_caps_hash(self):
        for a in gajim.connections:
            gajim.caps_hash[a] = caps_cache.compute_caps_hash([
                gajim.gajim_identity], gajim.gajim_common_features + \
                gajim.gajim_optional_features[a])
            # re-send presence with new hash
            connected = gajim.connections[a].connected
            if connected > 1 and gajim.SHOW_LIST[connected] != 'invisible':
                gajim.connections[a].change_status(gajim.SHOW_LIST[connected],
                    gajim.connections[a].status)

    @log_calls('WhiteboardPlugin')
    def activate(self):
        if not HAS_GOOCANVAS:
            raise GajimPluginException('python-pygoocanvas is missing!')
        if NS_JINGLE_SXE not in gajim.gajim_common_features:
            gajim.gajim_common_features.append(NS_JINGLE_SXE)
        if NS_SXE not in gajim.gajim_common_features:
            gajim.gajim_common_features.append(NS_SXE)
        self._compute_caps_hash()

    @log_calls('WhiteboardPlugin')
    def deactivate(self):
        if NS_JINGLE_SXE in gajim.gajim_common_features:
            gajim.gajim_common_features.remove(NS_JINGLE_SXE)
        if NS_SXE in gajim.gajim_common_features:
            gajim.gajim_common_features.remove(NS_SXE)
        self._compute_caps_hash()

    @log_calls('WhiteboardPlugin')
    def connect_with_chat_control(self, control):
        if isinstance(control, chat_control.ChatControl):
            base = Base(self, control)
            self.controls.append(base)

    @log_calls('WhiteboardPlugin')
    def disconnect_from_chat_control(self, chat_control):
        for base in self.controls:
            base.disconnect_from_chat_control()
        self.controls = []

    @log_calls('WhiteboardPlugin')
    def update_button_state(self, control):
        for base in self.controls:
            if base.chat_control == control:
                if control.contact.supports(NS_JINGLE_SXE) and \
                control.contact.supports(NS_SXE):
                    base.button.set_sensitive(True)
                    tooltip_text = _('Show whiteboard')
                else:
                    base.button.set_sensitive(False)
                    tooltip_text = _('Client on the other side '
                        'does not support the whiteboard')
                base.button.set_tooltip_text(tooltip_text)

    @log_calls('WhiteboardPlugin')
    def show_request_dialog(self, account, fjid, jid, sid, content_types):
        def on_ok():
            session = gajim.connections[account].get_jingle_session(fjid, sid)
            self.sid = session.sid
            if not session.accepted:
                session.approve_session()
            for content in content_types:
                session.approve_content(content)
            for _jid in (fjid, jid):
                ctrl = gajim.interface.msg_win_mgr.get_control(_jid, account)
                if ctrl:
                    break
            if not ctrl:
                # create it
                gajim.interface.new_chat_from_jid(account, jid)
                ctrl = gajim.interface.msg_win_mgr.get_control(jid, account)
            session = session.contents[('initiator', 'xhtml')]
            ctrl.draw_whiteboard(session)

        def on_cancel():
            session = gajim.connections[account].get_jingle_session(fjid, sid)
            session.decline_session()

        contact = gajim.contacts.get_first_contact_from_jid(account, jid)
        if contact:
            name = contact.get_shown_name()
        else:
            name = jid
        pritext = _('Incoming Whiteboard')
        sectext = _('%(name)s (%(jid)s) wants to start a whiteboard with '
            'you. Do you want to accept?') % {'name': name, 'jid': jid}
        dialog = dialogs.NonModalConfirmationDialog(pritext, sectext=sectext,
            on_response_ok=on_ok, on_response_cancel=on_cancel)
        dialog.popup()

    @log_calls('WhiteboardPlugin')
    def _nec_jingle_received(self, obj):
        if not HAS_GOOCANVAS:
            return
        content_types = set(c[0] for c in obj.contents)
        if 'xhtml' not in content_types:
            return
        self.show_request_dialog(obj.conn.name, obj.fjid, obj.jid, obj.sid,
            content_types)

    @log_calls('WhiteboardPlugin')
    def _nec_jingle_connected(self, obj):
        if not HAS_GOOCANVAS:
            return
        account = obj.conn.name
        ctrl = (gajim.interface.msg_win_mgr.get_control(obj.fjid, account)
            or gajim.interface.msg_win_mgr.get_control(obj.jid, account))
        if not ctrl:
            return
        session = gajim.connections[obj.conn.name].get_jingle_session(obj.fjid,
            obj.sid)

        if ('initiator', 'xhtml') not in session.contents:
            return

        session = session.contents[('initiator', 'xhtml')]
        ctrl.draw_whiteboard(session)

    @log_calls('WhiteboardPlugin')
    def _nec_jingle_disconnected(self, obj):
        for base in self.controls:
            if base.sid == obj.sid:
                base.stop_whiteboard(reason = obj.reason)

    @log_calls('WhiteboardPlugin')
    def _nec_raw_message(self, obj):
        if not HAS_GOOCANVAS:
            return
        if obj.stanza.getTag('sxe', namespace=NS_SXE):
            account = obj.conn.name

            try:
                fjid = helpers.get_full_jid_from_iq(obj.stanza)
            except helpers.InvalidFormat:
                obj.conn.dispatch('ERROR', (_('Invalid Jabber ID'),
                    _('A message from a non-valid JID arrived, it has been '
                      'ignored.')))

            jid = gajim.get_jid_without_resource(fjid)
            ctrl = (gajim.interface.msg_win_mgr.get_control(fjid, account)
                or gajim.interface.msg_win_mgr.get_control(jid, account))
            if not ctrl:
                return
            sxe = obj.stanza.getTag('sxe')
            if not sxe:
                return
            sid = sxe.getAttr('session')
            if (jid, sid) not in obj.conn._sessions:
                pass
#                newjingle = JingleSession(con=self, weinitiate=False, jid=jid, sid=sid)
#                self.addJingle(newjingle)

            # we already have such session in dispatcher...
            session = obj.conn.get_jingle_session(fjid, sid)
            cn = session.contents[('initiator', 'xhtml')]
            error = obj.stanza.getTag('error')
            if error:
                action = 'iq-error'
            else:
                action = 'edit'

            cn.on_stanza(obj.stanza, sxe, error, action)
#        def __editCB(self, stanza, content, error, action):
            #new_tags = sxe.getTags('new')
            #remove_tags = sxe.getTags('remove')

            #if new_tags is not None:
                ## Process new elements
                #for tag in new_tags:
                    #if tag.getAttr('type') == 'element':
                        #ctrl.whiteboard.recieve_element(tag)
                    #elif tag.getAttr('type') == 'attr':
                        #ctrl.whiteboard.recieve_attr(tag)
                #ctrl.whiteboard.apply_new()

            #if remove_tags is not None:
                ## Delete rids
                #for tag in remove_tags:
                    #target = tag.getAttr('target')
                    #ctrl.whiteboard.image.del_rid(target)

            # Stop propagating this event, it's handled
            return True


class Base(object):
    def __init__(self, plugin, chat_control):
        self.plugin = plugin
        self.chat_control = chat_control
        self.chat_control.draw_whiteboard = self.draw_whiteboard
        self.contact = self.chat_control.contact
        self.account = self.chat_control.account
        self.jid = self.contact.get_full_jid()
        self.create_buttons()
        self.whiteboard = None
        self.sid = None

    def create_buttons(self):
        # create whiteboard button
        actions_hbox = self.chat_control.xml.get_object('actions_hbox')
        self.button = gtk.ToggleButton(label=None, use_underline=True)
        self.button.set_property('relief', gtk.RELIEF_NONE)
        self.button.set_property('can-focus', False)
        img = gtk.Image()
        img_path = self.plugin.local_file_path('whiteboard.png')
        pixbuf = gtk.gdk.pixbuf_new_from_file(img_path)
        iconset = gtk.IconSet(pixbuf=pixbuf)
        factory = gtk.IconFactory()
        factory.add('whiteboard', iconset)
        img_path = self.plugin.local_file_path('brush_tool.png')
        pixbuf = gtk.gdk.pixbuf_new_from_file(img_path)
        iconset = gtk.IconSet(pixbuf=pixbuf)
        factory.add('brush_tool', iconset)
        img_path = self.plugin.local_file_path('line_tool.png')
        pixbuf = gtk.gdk.pixbuf_new_from_file(img_path)
        iconset = gtk.IconSet(pixbuf=pixbuf)
        factory.add('line_tool', iconset)
        img_path = self.plugin.local_file_path('oval_tool.png')
        pixbuf = gtk.gdk.pixbuf_new_from_file(img_path)
        iconset = gtk.IconSet(pixbuf=pixbuf)
        factory.add('oval_tool', iconset)
        factory.add_default()
        img.set_from_stock('whiteboard', gtk.ICON_SIZE_MENU)
        self.button.set_image(img)
        send_button = self.chat_control.xml.get_object('send_button')
        send_button_pos = actions_hbox.child_get_property(send_button,
            'position')
        actions_hbox.add_with_properties(self.button, 'position',
            send_button_pos - 1, 'expand', False)
        id_ = self.button.connect('toggled', self.on_whiteboard_button_toggled)
        self.chat_control.handlers[id_] = self.button
        self.button.show()

    def draw_whiteboard(self, content):
        hbox = self.chat_control.xml.get_object('chat_control_hbox')
        if len(hbox.get_children()) == 1:
            self.whiteboard = Whiteboard(self.account, self.contact, content,
                self.plugin)
            # set minimum size
            self.whiteboard.hbox.set_size_request(300, 0)
            hbox.pack_start(self.whiteboard.hbox, expand=False, fill=False)
            self.whiteboard.hbox.show_all()
            self.button.set_active(True)
            content.control = self
            self.sid = content.session.sid

    def on_whiteboard_button_toggled(self, widget):
        """
        Popup whiteboard
        """
        if widget.get_active():
            if not self.whiteboard:
                self.start_whiteboard()
        else:
            self.stop_whiteboard()

    def start_whiteboard(self):
        conn = gajim.connections[self.chat_control.account]
        jingle = JingleSession(conn, weinitiate=True, jid=self.jid)
        self.sid = jingle.sid
        conn._sessions[jingle.sid] = jingle
        content = JingleWhiteboard(jingle)
        content.control = self
        jingle.add_content('xhtml', content)
        jingle.start_session()

    def stop_whiteboard(self, reason=None):
        conn = gajim.connections[self.chat_control.account]
        self.sid = None
        session = conn.get_jingle_session(self.jid, media='xhtml')
        if session:
            session.end_session()
        self.button.set_active(False)
        if reason:
            txt = _('Whiteboard stopped: %(reason)s') % {'reason': reason}
            self.chat_control.print_conversation(txt, 'info')
        if not self.whiteboard:
            return
        hbox = self.chat_control.xml.get_object('chat_control_hbox')
        if self.whiteboard.hbox in hbox.get_children():
            if hasattr(self.whiteboard, 'hbox'):
                hbox.remove(self.whiteboard.hbox)
                self.whiteboard = None

    def disconnect_from_chat_control(self):
        actions_hbox = self.chat_control.xml.get_object('actions_hbox')
        actions_hbox.remove(self.button)

class JingleWhiteboard(JingleContent):
    ''' Jingle Whiteboard sessions consist of xhtml content'''
    def __init__(self, session, transport=None):
        if not transport:
            transport = JingleTransportSXE()
        JingleContent.__init__(self, session, transport)
        self.media = 'xhtml'
        self.negotiated = True # there is nothing to negotiate
        self.last_rid = 0
        self.callbacks['session-accept'] += [self._sessionAcceptCB]
        self.callbacks['session-terminate'] += [self._stop]
        self.callbacks['session-terminate-sent'] += [self._stop]
        self.callbacks['edit'] = [self._EditCB]

    def _EditCB(self, stanza, content, error, action):
        new_tags = content.getTags('new')
        remove_tags = content.getTags('remove')

        if new_tags is not None:
            # Process new elements
            for tag in new_tags:
                if tag.getAttr('type') == 'element':
                    self.control.whiteboard.recieve_element(tag)
                elif tag.getAttr('type') == 'attr':
                    self.control.whiteboard.recieve_attr(tag)
            self.control.whiteboard.apply_new()

        if remove_tags is not None:
            # Delete rids
            for tag in remove_tags:
                target = tag.getAttr('target')
                self.control.whiteboard.image.del_rid(target)

    def _sessionAcceptCB(self, stanza, content, error, action):
        log.debug('session accepted')
        self.session.connection.dispatch('WHITEBOARD_ACCEPTED',
            (self.session.peerjid, self.session.sid))

    def generate_rids(self, x):
        # generates x number of rids and returns in list
        rids = []
        for x in range(x):
            rids.append(str(self.last_rid))
            self.last_rid += 1
        return rids

    def send_whiteboard_node(self, items, rids):
        # takes int rid and dict items and sends it as a node
        # sends new item
        jid = self.session.peerjid
        sid = self.session.sid
        message = xmpp.Message(to=jid)
        sxe = message.addChild(name='sxe', attrs={'session': sid},
            namespace=NS_SXE)

        for x in rids:
            if items[x]['type'] == 'element':
                parent = x
                attrs = {'rid': x,
                     'name': items[x]['data'][0].getName(),
                     'type': items[x]['type']}
                sxe.addChild(name='new', attrs=attrs)
            if items[x]['type'] == 'attr':
                attr_name = items[x]['data']
                chdata = items[parent]['data'][0].getAttr(attr_name)
                attrs = {'rid': x,
                     'name': attr_name,
                     'type': items[x]['type'],
                     'chdata': chdata,
                     'parent': parent}
                sxe.addChild(name='new', attrs=attrs)
        self.session.connection.connection.send(message)

    def delete_whiteboard_node(self, rids):
        message = xmpp.Message(to=self.session.peerjid)
        sxe = message.addChild(name='sxe', attrs={'session': self.session.sid},
            namespace=NS_SXE)

        for x in rids:
            sxe.addChild(name='remove', attrs = {'target': x})
        self.session.connection.connection.send(message)

    def send_items(self, items, rids):
        # recieves dict items and a list of rids of items to send
        # TODO: is there a less clumsy way that doesn't involve passing
        # whole list
        self.send_whiteboard_node(items, rids)

    def del_item(self, rids):
        self.delete_whiteboard_node(rids)

    def encode(self, xml):
        # encodes it sendable string
        return 'data:text/xml,' + urllib.quote(xml)

    def _fill_content(self, content):
        content.addChild(NS_JINGLE_XHTML + ' description')

    def _stop(self, *things):
        pass

    def __del__(self):
        pass

def get_content(desc):
    return JingleWhiteboard

common.jingle_content.contents[NS_JINGLE_XHTML] = get_content

class JingleTransportSXE(JingleTransport):
    def __init__(self):
        JingleTransport.__init__(self, TransportType.streaming)

    def make_transport(self, candidates=None):
        transport = JingleTransport.make_transport(self, candidates)
        transport.setNamespace(NS_JINGLE_SXE)
        transport.setTagData('host', 'TODO')
        return transport

common.jingle_transport.transports[NS_JINGLE_SXE] = JingleTransportSXE
