##	common/gajim.py
##
## Gajim Team:
## - Yann Le Boulanger <asterix@lagaule.org>
## - Vincent Hanquez <tab@snarc.org>
## - Nikos Kouremenos <kourem@gmail.com>
##
##	Copyright (C) 2003-2005 Gajim Team
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 2 only.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##

import os
import logging
import common.config
import common.logger

version = '0.8'
config = common.config.Config()
connections = {}
verbose = False

h = logging.StreamHandler()
f = logging.Formatter('%(asctime)s %(name)s: %(message)s', '%d %b %Y %H:%M:%S')
h.setFormatter(f)
log = logging.getLogger('Gajim')
log.addHandler(h)

logger = common.logger.Logger()
DATA_DIR = '../data'
LANG = os.getenv('LANG') # en_US, fr_FR, el_GR etc..
if LANG:
	LANG = LANG[:2] # en, fr, el etc..
else:
	LANG = 'en'

last_message_time = {} # list of time of the latest incomming message
							# {acct1: {jid1: time1, jid2: time2}, }
encrypted_chats = {} # list of encrypted chats {acct1: [jid1, jid2], ..}
