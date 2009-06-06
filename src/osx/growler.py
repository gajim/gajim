import sys, os
from growl.Growl import GrowlNotifier
from common import gajim


if sys.platform != "darwin":
	raise ImportError("System platform is not OS/X")


GENERIC_NOTIF = _('Generic')
notifications = [
	_('Contact Signed In'), _('Contact Signed Out'), _('New Message'),
	_('New Single Message'), _('New Private Message'), _('New E-mail'),
	_('File Transfer Request'), _('File Transfer Error'),
	_('File Transfer Completed'), _('File Transfer Stopped'),
	_('Groupchat Invitation'), _('Contact Changed Status'),
	_('Connection Failed'), GENERIC_NOTIF
	]

growler = None



def init():
	global growler
	icon = open(os.path.join(gajim.DATA_DIR, "pixmaps", "gajim.icns"), "r")
	growler = GrowlNotifier(applicationName = "Gajim",
							notifications = notifications,
							applicationIcon = icon.read(),
							notify_cb = notifyCB)
	growler.register()
	return


def notify(event_type, jid, account, msg_type, path_to_image, title, text):
	if not event_type in notifications:
		event_type = GENERIC_NOTIF
	if not text:
		text = gajim.get_name_from_jid(account, jid) # default value of text
	text = filterString(text)
	if not title:
		title = event_type
	title = filterString(title)
	if not path_to_image:
		path_to_image = os.path.abspath(
			os.path.join(gajim.DATA_DIR, 'pixmaps', 'events',
						 'chat_msg_recv.png')) # img to display
	icon = open(path_to_image, "r")
	context = [account, jid, msg_type]
	growler.notify(event_type, title, text, icon.read(), False, None,
				   context)
	return


def notifyCB(data):
	gajim.interface.handle_event(data[0], data[1], data[2])


def filterString(string):
	string = string.replace("&quot;", "'")
	return string


# vim: se ts=3:
