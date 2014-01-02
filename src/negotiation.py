# -*- coding:utf-8 -*-
## src/negotiation.py
##
## Copyright (C) 2007-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
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

import gtkgui_helpers
import dataforms_widget

from common import dataforms
from common import gajim
import nbxmpp

def describe_features(features):
    """
    A human-readable description of the features that have been negotiated
    """
    if features['logging'] == 'may':
        return _('- messages will be logged')
    elif features['logging'] == 'mustnot':
        return _('- messages will not be logged')

class FeatureNegotiationWindow:
    def __init__(self, account, jid, session, form):
        self.account = account
        self.jid = jid
        self.form = form
        self.session = session

        self.xml = gtkgui_helpers.get_gtk_builder('data_form_window.ui', 'data_form_window')
        self.window = self.xml.get_object('data_form_window')

        config_vbox = self.xml.get_object('config_vbox')
        dataform = dataforms.ExtendForm(node = self.form)
        self.data_form_widget = dataforms_widget.DataFormWidget(dataform)
        self.data_form_widget.show()
        config_vbox.pack_start(self.data_form_widget, True, True, 0)

        self.xml.connect_signals(self)
        self.window.show_all()

    def on_ok_button_clicked(self, widget):
        acceptance = nbxmpp.Message(self.jid)
        acceptance.setThread(self.session.thread_id)
        feature = acceptance.NT.feature
        feature.setNamespace(nbxmpp.NS_FEATURE)

        form = self.data_form_widget.data_form
        form.setAttr('type', 'submit')

        feature.addChild(node=form)

        gajim.connections[self.account].send_stanza(acceptance)

        self.window.destroy()

    def on_cancel_button_clicked(self, widget):
        rejection = nbxmpp.Message(self.jid)
        rejection.setThread(self.session.thread_id)
        feature = rejection.NT.feature
        feature.setNamespace(nbxmpp.NS_FEATURE)

        x = nbxmpp.DataForm(typ='submit')
        x.addChild(node=nbxmpp.DataField('FORM_TYPE', value='urn:xmpp:ssn'))
        x.addChild(node=nbxmpp.DataField('accept', value='false', typ='boolean'))

        feature.addChild(node=x)

        gajim.connections[self.account].send_stanza(rejection)

        self.window.destroy()
