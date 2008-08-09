# mock notify module

notifications = []

def notify(event, jid, account, parameters, advanced_notif_num = None):
	notifications.append((event, jid, account, parameters, advanced_notif_num))

def get_advanced_notification(event, account, contact):
	return None

def get_show_in_roster(event, account, contact, session = None):
	return True

def get_show_in_systray(event, account, contact, type_ = None):
	return True

# vim: se ts=3: