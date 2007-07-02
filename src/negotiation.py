import gtkgui_helpers
import dataforms_widget

from common import dataforms
from common import gajim
from common import xmpp

def describe_features(features):
	'''a human-readable description of the features that have been negotiated'''
	if features['logging'] == 'may':
		return '- messages will be logged'
	elif features['logging'] == 'mustnot':
		return '- messages will not be logged'

class FeatureNegotiationWindow:
	'''FeatureNegotiotionWindow class'''
	def __init__(self, account, jid, session, form):
		self.account = account
		self.jid = jid
		self.form = form
		self.session = session

		self.xml = gtkgui_helpers.get_glade('data_form_window.glade', 'data_form_window')
		self.window = self.xml.get_widget('data_form_window')

		config_vbox = self.xml.get_widget('config_vbox')
		dataform = dataforms.ExtendForm(node = self.form)
		self.data_form_widget = dataforms_widget.DataFormWidget(dataform)
		self.data_form_widget.show()
		config_vbox.pack_start(self.data_form_widget)

		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def on_ok_button_clicked(self, widget):
		acceptance = xmpp.Message(self.jid)
		acceptance.setThread(self.session.thread_id)
		feature = acceptance.NT.feature
		feature.setNamespace(xmpp.NS_FEATURE)

		form = self.data_form_widget.data_form
		form.setAttr('type', 'submit')

		feature.addChild(node=form)

		gajim.connections[self.account].send_stanza(acceptance)

		self.window.destroy()

	def on_cancel_button_clicked(self, widget):
		# XXX determine whether to reveal presence

		rejection = xmpp.Message(self.jid)
		rejection.setThread(self.session.thread_id)
		feature = rejection.NT.feature
		feature.setNamespace(xmpp.NS_FEATURE)

		x = xmpp.DataForm(typ='submit')
		x.addChild(node=xmpp.DataField('FORM_TYPE', value='urn:xmpp:ssn'))
		x.addChild(node=xmpp.DataField('accept', value='false', typ='boolean'))

		feature.addChild(node=x)

		# XXX optional <body/>

		gajim.connections[self.account].send_stanza(rejection)

		self.window.destroy()
