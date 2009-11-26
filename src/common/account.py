# -*- coding:utf-8 -*-
## src/common/contacts.py
##
## Copyright (C) 2009 Stephan Erb <steve-e AT h3c.de>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

class Account(object):

	def __init__(self, name, contacts, gc_contacts):
		self.name = name
		self.contacts = contacts
		self.gc_contacts = gc_contacts

	def __repr__(self):
		return self.name

	def __hash__(self):
		return hash(self.name)
