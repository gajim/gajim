# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

import time

import nbxmpp
from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import GLib

from gajim.common import app
from gajim.common import ged
from gajim.common.const import Option, OptionKind, OptionType
from gajim.gtk import ErrorDialog
from gajim.gtk import util
from gajim.gtk.util import get_builder
from gajim.gtk.util import get_image_button
from gajim.options_dialog import OptionsDialog


UNDECLARED = 'http://www.gajim.org/xmlns/undeclared'


class XMLConsoleWindow(Gtk.Window):
    def __init__(self, account):
        Gtk.Window.__init__(self)
        self.account = account
        self.enabled = True
        self.presence = True
        self.message = True
        self.iq = True
        self.stream = True
        self.incoming = True
        self.outgoing = True
        self.filter_dialog = None

        glade_objects = ['textview', 'input', 'scrolled_input', 'headerbar',
                         'scrolled', 'actionbar', 'paned', 'box', 'menubutton']
        self.builder = get_builder('xml_console_window.ui')
        for obj in glade_objects:
            setattr(self, obj, self.builder.get_object(obj))

        self.set_titlebar(self.headerbar)
        jid = app.get_jid_from_account(account)
        self.headerbar.set_subtitle(jid)
        self.set_default_size(600, 600)
        self.add(self.box)

        self.paned.set_position(self.paned.get_property('max-position'))

        button = get_image_button(
            'edit-clear-all-symbolic', _('Clear'))
        button.connect('clicked', self.on_clear)
        self.actionbar.pack_start(button)

        button = get_image_button(
            'applications-system-symbolic', _('Filter'))
        button.connect('clicked', self.on_filter_options)
        self.actionbar.pack_start(button)

        button = get_image_button(
            'document-edit-symbolic', _('XML Input'), toggle=True)
        button.connect('toggled', self.on_input)
        self.actionbar.pack_start(button)

        button = get_image_button('emblem-ok-symbolic', _('Send'))
        button.connect('clicked', self.on_send)
        self.actionbar.pack_end(button)

        self.actionbar.pack_start(self.menubutton)

        self.create_tags()
        self.show_all()

        self.scrolled_input.hide()
        self.menubutton.hide()

        self.connect("destroy", self.on_destroy)
        self.connect('key_press_event', self.on_key_press_event)
        self.builder.connect_signals(self)

        app.ged.register_event_handler(
            'stanza-received', ged.GUI1, self._nec_stanza_received)
        app.ged.register_event_handler(
            'stanza-sent', ged.GUI1, self._nec_stanza_sent)

    def create_tags(self):
        buffer_ = self.textview.get_buffer()
        in_color = app.config.get('inmsgcolor')
        out_color = app.config.get('outmsgcolor')

        tags = ['presence', 'message', 'stream', 'iq']

        tag = buffer_.create_tag('incoming')
        tag.set_property('foreground', in_color)
        tag = buffer_.create_tag('outgoing')
        tag.set_property('foreground', out_color)

        for tag_name in tags:
            buffer_.create_tag(tag_name)

    def on_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def on_row_activated(self, listbox, row):
        text = row.get_child().get_text()
        input_text = None
        if text == 'Presence':
            input_text = (
                '<presence>\n'
                '<show></show>\n'
                '<status></status>\n'
                '<priority></priority>\n'
                '</presence>')
        elif text == 'Message':
            input_text = (
                '<message to="" type="">\n'
                '<body></body>\n'
                '</message>')
        elif text == 'Iq':
            input_text = (
                '<iq to="" type="">\n'
                '<query xmlns=""></query>\n'
                '</iq>')

        if input_text is not None:
            buffer_ = self.input.get_buffer()
            buffer_.set_text(input_text)
            self.input.grab_focus()

    def on_send(self, *args):
        if app.connections[self.account].connected <= 1:
            # if offline or connecting
            ErrorDialog(
                _('Connection not available'),
                _('Please make sure you are connected with "%s".') %
                self.account)
            return
        buffer_ = self.input.get_buffer()
        begin_iter, end_iter = buffer_.get_bounds()
        stanza = buffer_.get_text(begin_iter, end_iter, True)
        if stanza:
            try:
                node = nbxmpp.Protocol(node=stanza)
                if node.getNamespace() == UNDECLARED:
                    node.setNamespace(nbxmpp.NS_CLIENT)
            except Exception as error:
                ErrorDialog(_('Invalid Node'), str(error))
                return
            app.connections[self.account].connection.send(node)
            buffer_.set_text('')

    def on_input(self, button, *args):
        if button.get_active():
            self.paned.get_child2().show()
            self.menubutton.show()
            self.input.grab_focus()
        else:
            self.paned.get_child2().hide()
            self.menubutton.hide()

    def on_filter_options(self, *args):
        if self.filter_dialog:
            self.filter_dialog.present()
            return
        options = [
            Option(OptionKind.SWITCH, 'Presence',
                   OptionType.VALUE, self.presence,
                   callback=self.on_option, data='presence'),

            Option(OptionKind.SWITCH, 'Message',
                   OptionType.VALUE, self.message,
                   callback=self.on_option, data='message'),

            Option(OptionKind.SWITCH, 'Iq', OptionType.VALUE, self.iq,
                   callback=self.on_option, data='iq'),

            Option(OptionKind.SWITCH, 'Stream\nManagement',
                   OptionType.VALUE, self.stream,
                   callback=self.on_option, data='stream'),

            Option(OptionKind.SWITCH, 'In', OptionType.VALUE, self.incoming,
                   callback=self.on_option, data='incoming'),

            Option(OptionKind.SWITCH, 'Out', OptionType.VALUE, self.outgoing,
                   callback=self.on_option, data='outgoing'),
        ]

        self.filter_dialog = OptionsDialog(self, 'Filter',
                                           Gtk.DialogFlags.DESTROY_WITH_PARENT,
                                           options, self.account)
        self.filter_dialog.connect('destroy', self.on_filter_destroyed)

    def on_filter_destroyed(self, win):
        self.filter_dialog = None

    def on_clear(self, *args):
        self.textview.get_buffer().set_text('')

    def on_destroy(self, *args):
        del app.interface.instances[self.account]['xml_console']
        app.ged.remove_event_handler(
            'stanza-received', ged.GUI1, self._nec_stanza_received)
        app.ged.remove_event_handler(
            'stanza-sent', ged.GUI1, self._nec_stanza_sent)

    def on_enable(self, switch, param):
        self.enabled = switch.get_active()

    def on_option(self, value, data):
        setattr(self, data, value)
        value = not value
        table = self.textview.get_buffer().get_tag_table()
        tag = table.lookup(data)
        if data in ('incoming', 'outgoing'):
            if value:
                tag.set_priority(table.get_size() - 1)
            else:
                tag.set_priority(0)
        tag.set_property('invisible', value)

    def _nec_stanza_received(self, obj):
        if obj.conn.name != self.account:
            return
        self.print_stanza(obj.stanza_str, 'incoming')

    def _nec_stanza_sent(self, obj):
        if obj.conn.name != self.account:
            return
        self.print_stanza(obj.stanza_str, 'outgoing')

    def print_stanza(self, stanza, kind):
        # kind must be 'incoming' or 'outgoing'
        if not self.enabled:
            return
        if not stanza:
            return

        at_the_end = util.at_the_end(self.scrolled)

        buffer_ = self.textview.get_buffer()
        end_iter = buffer_.get_end_iter()

        type_ = kind
        if stanza.startswith('<presence'):
            type_ = 'presence'
        elif stanza.startswith('<message'):
            type_ = 'message'
        elif stanza.startswith('<iq'):
            type_ = 'iq'
        elif stanza.startswith('<r') or stanza.startswith('<a'):
            type_ = 'stream'

        stanza = '<!-- {kind} {time} -->\n{stanza}\n\n'.format(
            kind=kind.capitalize(),
            time=time.strftime('%c'),
            stanza=stanza.replace('><', '>\n<'))
        buffer_.insert_with_tags_by_name(end_iter, stanza, type_, kind)

        if at_the_end:
            GLib.idle_add(util.scroll_to_end, self.scrolled)
