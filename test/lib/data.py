# -*- coding: utf-8 -*-
account1 = 'acc1'
account2 = 'Cool"chârßéµö'
account3 = 'dingdong.org'

contacts = {}
contacts[account1] = {
        'myjid@'+account1: {
                          'ask': None, 'groups': [], 'name': None, 'resources': {},
                          'subscription': 'both'},
        'default1@gajim.org': {
                          'ask': None, 'groups': [], 'name': None, 'resources': {},
                          'subscription': 'both'},
        'default2@gajim.org': {
                          'ask': None, 'groups': ['GroupA',], 'name': None, 'resources': {},
                          'subscription': 'both'},
        'Cool"chârßéµö@gajim.org': {
                          'ask': None, 'groups': ['<Cool"chârßéµö', 'GroupB'],
                          'name': None, 'resources': {}, 'subscription': 'both'},
        'samejid@gajim.org': {
                          'ask': None, 'groups': ['GroupA',], 'name': None, 'resources': {},
                          'subscription': 'both'}
}
contacts[account2] = {
        'myjid@'+account2: {
                          'ask': None, 'groups': [], 'name': None, 'resources': {},
                          'subscription': 'both'},
        'default3@gajim.org': {
                          'ask': None, 'groups': ['GroupC',], 'name': None, 'resources': {},
                          'subscription': 'both'},
        'asksubfrom@gajim.org': {
                          'ask': 'subscribe', 'groups': ['GroupA',], 'name': None,
                          'resources': {}, 'subscription': 'from'},
        'subto@gajim.org': {
                          'ask': None, 'groups': ['GroupB'], 'name': None, 'resources': {},
                          'subscription': 'to'},
        'samejid@gajim.org': {
                          'ask': None, 'groups': ['GroupA', 'GroupB'], 'name': None,
                          'resources': {}, 'subscription': 'both'}
}
contacts[account3] = {
        #'guypsych0\\40h.com@msn.dingdong.org': {
        #                 'ask': None, 'groups': [], 'name': None, 'resources': {},
        #                 'subscription': 'both'},
        'guypsych0%h.com@msn.delx.cjb.net': {
                          'ask': 'subscribe', 'groups': [], 'name': None,
                          'resources': {}, 'subscription': 'from'},
        #'guypsych0%h.com@msn.jabber.wiretrip.org': {
        #                 'ask': None, 'groups': [], 'name': None, 'resources': {},
        #                 'subscription': 'to'},
        #'guypsycho\\40g.com@gtalk.dingdong.org': {
        #                 'ask': None, 'groups': [], 'name': None,
        #                 'resources': {}, 'subscription': 'both'}
}

# We have contacts that are not in roster but only specified in the metadata
metacontact_data = [
        [{'account': account3,
          'jid': 'guypsych0\\40h.com@msn.dingdong.org',
          'order': 0},
         {'account': account3,
          'jid': 'guypsych0%h.com@msn.delx.cjb.net',
          'order': 0},
         {'account': account3,
          'jid': 'guypsych0%h.com@msn.jabber.wiretrip.org',
          'order': 0},
         {'account': account3,
          'jid': 'guypsycho\\40g.com@gtalk.dingdong.org',
          'order': 0}],

        [{'account': account1,
          'jid': 'samejid@gajim.org',
          'order': 0},
         {'account': account2,
          'jid': 'samejid@gajim.org',
          'order': 0}]
        ]
