import gtkgui_helpers
import dataforms_widget

from common import dataforms

class FeatureNegotiationWindow:
	'''FeatureNegotiotionWindow class'''
	def __init__(self, account, jid, thread_id, form):
		self.account = account
		self.jid = jid
		self.form = form

		self.xml = gtkgui_helpers.get_glade('data_form_window.glade', 'data_form_window')
		self.window = self.xml.get_widget('data_form_window')

		config_vbox = self.xml.get_widget('config_vbox')
		dataform = dataforms.ExtendForm(node = self.form)
		self.data_form_widget = dataforms_widget.DataFormWidget(dataform)
		self.data_form_widget.show()
		config_vbox.pack_start(self.data_form_widget)

		self.xml.signal_autoconnect(self)
		self.window.show_all()
