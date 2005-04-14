import gtk
import gtk.glade
import version

from common import i18n

_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain(APP, i18n.DIR)
gtk.glade.textdomain(APP)

GTKGUI_GLADE='plugins/gtkgui/gtkgui.glade'

class Check_for_new_version_dialog:
	def __init__(self, plugin):
		self.plugin = plugin
		xml = gtk.glade.XML(GTKGUI_GLADE, 'new_version_available_dialog', APP)
		self.window = xml.get_widget('new_version_available_dialog')
		self.information_label = xml.get_widget('information_label')
		self.changes_textview = xml.get_widget('changes_textview')
		xml.signal_autoconnect(self)
		self.check_for_new_version()
		

	def on_new_version_available_dialog_delete_event(self, widget, event):
		self.window.destroy()

	def on_open_download_page_button_clicked(self, widget):
		url = 'http://www.gajim.org/downloads.php?lang='
		self.plugin.launch_browser_mailer('url', url)

	def check_for_new_version(self):
		'''parse online Changelog to find out last version
		and the changes for that latest version'''
		check_for_new_version_available = True
		if check_for_new_version_available:
			import urllib
			import version

			url = 'http://trac.gajim.org/file/trunk/Changelog?rev=latest&format=txt'
			changelog = urllib.urlopen(url)
			# format is Gajim version (date)
			first_line = changelog.readline()
			finish_version = first_line.find(' ', 6) # start search after 'Gajim'
			latest_version = first_line[6:finish_version]
			if latest_version > version.version:
				start_date = finish_version + 2 # one space and one (
				date = first_line[start_date:-2] # remove the last ) and \n
				text = 'Gajim ' + latest_version + ' was released in ' + date + '!'
				self.information_label.set_text(text)
				changes = ''
				while True:
					line = changelog.readline()
					if line.startswith('Gajim'):
						break
					else:
						if line != '\n':
							changes += line
				
				buf = self.changes_textview.get_buffer()
				buf.set_text(changes)
				self.window.show_all()
