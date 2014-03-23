##      common/zeroconf/roster_zeroconf.py
##
## Copyright (C) 2006 Stefan Bethge <stefan@lanpartei.de>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim.  If not, see <http://www.gnu.org/licenses/>.
##


from common.zeroconf import zeroconf

class Roster:
    def __init__(self, zeroconf):
        self._data = None
        self.zeroconf = zeroconf                 # our zeroconf instance
        self.version = ''
        self.received_from_server = True

    def update_roster(self):
        for val in self.zeroconf.contacts.values():
            self.setItem(val[zeroconf.C_NAME])

    def getRoster(self):
        if self._data is None:
            self._data = {}
            self.update_roster()
        return self

    def getDiffs(self):
        """
        Update the roster with new data and return dict with jid -> new status
        pairs to do notifications and stuff
        """
        diffs = {}
        old_data = self._data.copy()
        self.update_roster()
        for key in old_data.keys():
            if key in self._data:
                if old_data[key] != self._data[key]:
                    diffs[key] = self._data[key]['status']
        return diffs

    def setItem(self, jid, name='', groups=''):
        contact = self.zeroconf.get_contact(jid)
        if not contact:
            return

        host, address, port = contact[4:7]
        txt = contact[8]

        self._data[jid]={}
        self._data[jid]['ask'] = 'none'
        self._data[jid]['subscription'] = 'both'
        self._data[jid]['groups'] = []
        self._data[jid]['resources'] = {}
        self._data[jid]['address'] = address
        self._data[jid]['host'] = host
        self._data[jid]['port'] = port
        txt_dict = self.zeroconf.txt_array_to_dict(txt)
        status = txt_dict.get('status', '')
        if not status:
            status = 'avail'
        nm = txt_dict.get('1st', '')
        if 'last' in txt_dict:
            if nm != '':
                nm += ' '
            nm += txt_dict['last']
        if nm:
            self._data[jid]['name'] = nm
        else:
            self._data[jid]['name'] = jid
        if status == 'avail':
            status = 'online'
        self._data[jid]['txt_dict'] = txt_dict
        if 'msg' not in self._data[jid]['txt_dict']:
            self._data[jid]['txt_dict']['msg'] = ''
        self._data[jid]['status'] = status
        self._data[jid]['show'] = status

    def setItemMulti(self, items):
        for i in items:
            self.setItem(jid=i['jid'], name=i['name'], groups=i['groups'])

    def delItem(self, jid):
        if jid in self._data:
            del self._data[jid]

    def getItem(self, jid):
        if jid in self._data:
            return self._data[jid]

    def __getitem__(self, jid):
        return self._data[jid]

    def getItems(self):
        # Return list of all [bare] JIDs that the roster currently tracks.
        return self._data.keys()

    def keys(self):
        return self._data.keys()

    def getRaw(self):
        return self._data

    def getResources(self, jid):
        return {}

    def getGroups(self, jid):
        return self._data[jid]['groups']

    def getName(self, jid):
        if jid in self._data:
            return self._data[jid]['name']

    def getStatus(self, jid):
        if jid in self._data:
            return self._data[jid]['status']

    def getMessage(self, jid):
        if jid in self._data:
            return self._data[jid]['txt_dict']['msg']

    def getShow(self, jid):
        return self.getStatus(jid)

    def getPriority(self, jid):
        return 5

    def getSubscription(self, jid):
        return 'both'

    def Subscribe(self, jid):
        pass

    def Unsubscribe(self, jid):
        pass

    def Authorize(self, jid):
        pass

    def Unauthorize(self, jid):
        pass
