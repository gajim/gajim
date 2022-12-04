from unittest.mock import MagicMock

from base64 import b64decode

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

import nbxmpp
from nbxmpp.modules.dataforms import extend_form

from gajim import gui
gui.init('gtk')

from gajim.gui.dataform import DataFormWidget
from gajim.common.const import CSSPriority
from gajim.common import app

from test.gtk import util
util.load_style('gajim.css', CSSPriority.APPLICATION)

image = '''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'''  # noqa

app.bob_cache['sha1+8f35fef110ffc5df08d579a50083ff9308fb6242'] = b64decode(image)  # noqa
app.css_config = MagicMock()
app.css_config.get_value = MagicMock(return_value='rgb(100, 100, 255)')

FORM = '''
<x xmlns='jabber:x:data' type='form'>
  <title>Bot Configuration</title>
  <instructions>Fill out this form to configure your new bot!</instructions>
  <field type='hidden'
         var='FORM_TYPE'>
    <value>jabber:bot</value>
  </field>
  <field type='fixed'><value>Section 1: Bot Info</value></field>
  <field type='text-single'
         label='The name of your bot'
         var='botname'>
    <required/>
  </field>
  <field type='text-multi'
         label='Helpful description of your bot'
         var='description'>
    <required/>
  </field>
  <field type='boolean'
         label='Public bot?'
         var='public'/>
  <field type='text-private'
         label='Password for special access'
         var='password'>
    <required/>
  </field>
  <field type='fixed'><value>Section 2: Features</value></field>
  <field type='list-multi'
         label='What features will the bot support?'
         var='features'>
    <option label='Contests'><value>contests</value></option>
    <option label='News'><value>news</value></option>
    <option label='Polls'><value>polls</value></option>
    <option label='Reminders'><value>reminders</value></option>
    <option label='Search'><value>search</value></option>
    <option label='Search1'><value>search1</value></option>
    <option label='Really long long long long long long long long entry'><value>longentry</value></option>
    <option label='Search3'><value>search3</value></option>
    <value>news</value>
    <value>search</value>
  </field>
  <field type='fixed'><value>Section 3: Subscriber List</value></field>
  <field type='list-single'
         label='Maximum number of subscribers'
         var='maxsubs'>
    <value>20</value>
    <option label='10'><value>10</value></option>
    <option label='20'><value>20</value></option>
    <option label='30'><value>30</value></option>
    <option label='50'><value>50</value></option>
    <option label='100'><value>100</value></option>
    <option label='None'><value>none</value></option>
  </field>
  <field type='fixed'><value>Section 4: Invitations</value></field>
  <field type='jid-multi'
         label='People to invite'
         var='invitelist'>
    <desc>Tell all your friends about your new bot!</desc>
    <required/>
  </field>
  <field var='ocr' type='text-single' label='Fill in what you see'>
    <media xmlns='urn:xmpp:media-element'>
      <uri type='image/png'>cid:sha1+8f35fef110ffc5df08d579a50083ff9308fb6242@bob.xmpp.org</uri>
    </media>
    <required/>
  </field>
</x>
'''  # noqa


class DataFormWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title='Data Form Test')
        self.set_default_size(600, 600)
        options = {
            'left-width': 100,
            'form-width': 435,
        }
        self._widget = DataFormWidget(
            extend_form(node=nbxmpp.Node(node=FORM)), options)
        self.add(self._widget)
        self.show()

win = DataFormWindow()
win.connect('destroy', Gtk.main_quit)
win.show_all()
Gtk.main()
