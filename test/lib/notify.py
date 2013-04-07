# mock notify module

from common import gajim
from common import ged

notifications = []

class Notification:
    def _nec_notification(self, obj):
        global notifications
        notifications.append(obj)

    def clean(self):
        global notifications
        notifications = []
        gajim.ged.remove_event_handler('notification', ged.GUI2,
            self._nec_notification)

    def __init__(self):
        gajim.ged.register_event_handler('notification', ged.GUI2,
            self._nec_notification)


def notify(event, jid, account, parameters, advanced_notif_num = None):
    notifications.append((event, jid, account, parameters, advanced_notif_num))

def get_advanced_notification(event, account, contact):
    return None

def get_show_in_roster(event, account, contact, session = None):
    return True

def get_show_in_systray(event, account, contact, type_ = None):
    return True
