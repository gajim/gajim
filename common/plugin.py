#!/usr/bin/env python
##	common/plugin.py
##
## Gajim Team:
## 	- Yann Le Boulanger <asterix@crans.org>
## 	- Vincent Hanquez <tab@tuxfamily.org>
##
##	Copyright (C) 2003 Gajim Team
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

import common.thread

""" Plugin definitions """

class GajimPlugin:
    def __init__(self, name, queueIn, queueOut):
        """ queueIn is a queue to interact from the hub to the plugin """
        self.name = name
        self.queueIn = queueIn
        self.queueOut= queueOut
    # END __init__

    def load(self):
        self.thr = common.thread.GajimThread(self.name, self.queueIn, \
		self.queueOut)
    # END load
# END GajimPlugin
