from gi.repository import Gtk
import nbxmpp

from gajim.gtk.dataform import DataFormWidget
from gajim.common.modules.dataforms import extend_form
from gajim.common.const import CSSPriority

from test.gtk import util
util.load_style('gajim.css', CSSPriority.APPLICATION)

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
</x>
'''

class DataFormWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title="Data Form Test")
        self.set_default_size(600, 600)
        self._widget = DataFormWidget(extend_form(node=nbxmpp.Node(node=FORM)))
        self.add(self._widget)
        self.show()

win = DataFormWindow()
win.connect("destroy", Gtk.main_quit)
win.show_all()
Gtk.main()
