# this will go to src/common/xmpp later, for now it is in src/common
# -*- coding:utf-8 -*-
## src/common/dataforms.py
##
## Copyright (C) 2006-2007 Tomasz Melcer <liori AT exroot.org>
## Copyright (C) 2006-2008 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2007 Stephan Erb <steve-e AT h3c.de>
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

""" This module contains wrappers for different parts of data forms (JEP 0004). For information
how to use them, read documentation. """

import xmpp

# exceptions used in this module
class Error(Exception): pass	# base class
class UnknownDataForm(Error): pass	# when we get xmpp.Node which we do not understand
class WrongFieldValue(Error): pass	# when we get xmpp.Node which contains bad fields

# helper class to change class of already existing object
class ExtendedNode(xmpp.Node, object):
	@classmethod
	def __new__(cls,  *a, **b):
		if 'extend' not in b.keys() or not b['extend']:
			return object.__new__(cls)

		extend = b['extend']
		assert issubclass(cls, extend.__class__)
		extend.__class__ = cls
		return extend

# helper decorator to create properties in cleaner way
def nested_property(f):
	ret = f()
	p = {'doc': f.__doc__}
	for v in ('fget', 'fset', 'fdel', 'doc'):
		if v in ret.keys(): p[v]=ret[v]
	return property(**p)

# helper to create fields from scratch
def Field(typ, **attrs):
	''' Helper function to create a field of given type. '''
	f = {
		'boolean': BooleanField,
		'fixed': TextMultiField, # not editable, still can have multiple lines of text
		'hidden': StringField,
		'text-private': StringField,
		'text-single': StringField,
		'jid-multi': ListMultiField,
		'jid-single': ListSingleField,
		'list-multi': ListMultiField,
		'list-single': ListSingleField,
		'text-multi': TextMultiField,
	}[typ](typ=typ, **attrs)
	return f

def ExtendField(node):
	''' Helper function to extend a node to field of appropriate type. '''
	# when validation (XEP-122) will go in, we could have another classes
	# like DateTimeField - so that dicts in Field() and ExtendField() will
	# be different...
	typ=node.getAttr('type')
	f = {
		'boolean': BooleanField,
		'fixed': TextMultiField,
		'hidden': StringField,
		'text-private': StringField,
		'text-single': StringField,
		'jid-multi': ListMultiField,
		'jid-single': ListSingleField,
		'list-multi': ListMultiField,
		'list-single': ListSingleField,
		'text-multi': TextMultiField,
	}
	if typ not in f:
		typ = 'text-single'
	return f[typ](extend=node)

def ExtendForm(node):
	''' Helper function to extend a node to form of appropriate type. '''
	if node.getTag('reported') is not None:
		return MultipleDataForm(extend=node)
	else:
		return SimpleDataForm(extend=node)

class DataField(ExtendedNode):
	""" Keeps data about one field - var, field type, labels, instructions...
	Base class for different kinds of fields. Use Field() function to
	construct one of these. """
	def __init__(self, typ=None, var=None, value=None, label=None, desc=None, required=False,
		options=None, extend=None):

		if extend is None:
			ExtendedNode.__init__(self, 'field')

			self.type = typ
			self.var = var
			if value is not None:	self.value = value
			if label is not None:	self.label = label
			if desc  is not None:	self.desc = desc
			self.required = required
			self.options = options

	@nested_property
	def type():
		'''Type of field. Recognized values are: 'boolean', 'fixed', 'hidden', 'jid-multi',
		'jid-single', 'list-multi', 'list-single', 'text-multi', 'text-private',
		'text-single'. If you set this to something different, DataField will store
		given name, but treat all data as text-single.'''
		def fget(self):
			t = self.getAttr('type')
			if t is None: return 'text-single'
			return t
		def fset(self, value):
			assert isinstance(value, basestring)
			self.setAttr('type', value)
		return locals()

	@nested_property
	def var():
		'''Field identifier.'''
		def fget(self):
			return self.getAttr('var')
		def fset(self, value):
			assert isinstance(value, basestring)
			self.setAttr('var', value)
		def fdel(self):
			self.delAttr('var')
		return locals()

	@nested_property
	def label():
		'''Human-readable field name.'''
		def fget(self):
			return self.getAttr('label')
		def fset(self, value):
			assert isinstance(value, basestring)
			self.setAttr('label', value)
		def fdel(self):
			if self.getAttr('label'):
				self.delAttr('label')
		return locals()

	@nested_property
	def description():
		'''Human-readable description of field meaning.'''
		def fget(self):
			return self.getTagData('desc') or u''
		def fset(self, value):
			assert isinstance(value, basestring)
			if value == '':
				fdel(self)
			else:
				self.setTagData('desc', value)
		def fdel(self):
			t = self.getTag('desc')
			if t is not None:
				self.delChild(t)
		return locals()

	@nested_property
	def required():
		'''Controls whether this field required to fill. Boolean.'''
		def fget(self):
			return bool(self.getTag('required'))
		def fset(self, value):
			t = self.getTag('required')
			if t and not value:
				self.delChild(t)
			elif not t and value:
				self.addChild('required')
		return locals()

class BooleanField(DataField):
	@nested_property
	def value():
		'''Value of field. May contain True, False or None.'''
		def fget(self):
			v = self.getTagData('value')
			if v in ('0', 'false'): return False
			if v in ('1', 'true'): return True
			if v is None: return False # default value is False
			raise WrongFieldValue
		def fset(self, value):
			self.setTagData('value', value and '1' or '0')
		def fdel(self, value):
			t = self.getTag('value')
			if t is not None:
				self.delChild(t)
		return locals()

class StringField(DataField):
	''' Covers fields of types: fixed, hidden, text-private, text-single. '''
	@nested_property
	def value():
		'''Value of field. May be any unicode string.'''
		def fget(self):
			return self.getTagData('value') or u''
		def fset(self, value):
			assert isinstance(value, basestring)
			if value == '':
				return fdel(self)
			self.setTagData('value', value)
		def fdel(self):
			try:
				self.delChild(self.getTag('value'))
			except ValueError: # if there already were no value tag
				pass
		return locals()

class ListField(DataField):
	''' Covers fields of types: jid-multi, jid-single, list-multi, list-single. '''
	@nested_property
	def options():
		'''Options.'''
		def fget(self):
			options = []
			for element in self.getTags('option'):
				v = element.getTagData('value')
				if v is None: raise WrongFieldValue
				options.append((element.getAttr('label'), v))
			return options
		def fset(self, values):
			fdel(self)
			for value, label in values:
				self.addChild('option', {'label': label}).setTagData('value', value)
		def fdel(self):
			for element in self.getTags('option'):
				self.delChild(element)
		return locals()

	def iter_options(self):
		for element in self.iterTags('option'):
			v = element.getTagData('value')
			if v is None: raise WrongFieldValue
			l = element.getAttr('label')
			if not l:
				l = v
			yield (v, l)

class ListSingleField(ListField, StringField):
	'''Covers list-single and jid-single fields.'''
	pass

class ListMultiField(ListField):
	'''Covers list-multi and jid-multi fields.'''
	@nested_property
	def values():
		'''Values held in field.'''
		def fget(self):
			values = []
			for element in self.getTags('value'):
				values.append(element.getData())
			return values
		def fset(self, values):
			fdel(self)
			for value in values:
				self.addChild('value').setData(value)
		def fdel(self):
			for element in self.getTags('value'):
				self.delChild(element)
		return locals()

	def iter_values(self):
		for element in self.getTags('value'):
			yield element.getData()

class TextMultiField(DataField):
	@nested_property
	def value():
		'''Value held in field.'''
		def fget(self):
			value = u''
			for element in self.iterTags('value'):
				value += '\n' + element.getData()
			return value[1:]
		def fset(self, value):
			fdel(self)
			if value == '': return
			for line in value.split('\n'):
				self.addChild('value').setData(line)
		def fdel(self):
			for element in self.getTags('value'):
				self.delChild(element)
		return locals()

class DataRecord(ExtendedNode):
	'''The container for data fields - an xml element which has DataField
	elements as children.'''
	def __init__(self, fields=None, associated=None, extend=None):
		self.associated = associated
		self.vars = {}
		if extend is None:
			# we have to build this object from scratch
			xmpp.Node.__init__(self)

			if fields is not None: self.fields = fields
		else:
			# we already have xmpp.Node inside - try to convert all
			# fields into DataField objects
			if fields is None:
				for field in self.iterTags('field'):
					if not isinstance(field, DataField):
						ExtendField(field)
					self.vars[field.var] = field
			else:
				for field in self.getTags('field'):
					self.delChild(field)
				self.fields = fields

	@nested_property
	def fields():
		'''List of fields in this record.'''
		def fget(self):
			return self.getTags('field')
		def fset(self, fields):
			fdel(self)
			for field in fields:
				if not isinstance(field, DataField):
					ExtendField(extend=field)
				self.addChild(node=field)
		def fdel(self):
			for element in self.getTags('field'):
				self.delChild(element)
		return locals()

	def iter_fields(self):
		''' Iterate over fields in this record. Do not take associated
		into account. '''
		for field in self.iterTags('field'):
			yield field

	def iter_with_associated(self):
		''' Iterate over associated, yielding both our field and
		associated one together. '''
		for field in self.associated.iter_fields():
			yield self[field.var], field

	def __getitem__(self, item):
		return self.vars[item]

class DataForm(ExtendedNode):
	def __init__(self, type_=None, title=None, instructions=None, extend=None):
		if extend is None:
			# we have to build form from scratch
			xmpp.Node.__init__(self, 'x', attrs={'xmlns': xmpp.NS_DATA})

		if type_ is not None:		self.type_=type_
		if title is not None:		self.title=title
		if instructions is not None:	self.instructions=instructions

	@nested_property
	def type():
		''' Type of the form. Must be one of: 'form', 'submit', 'cancel', 'result'.
		'form' - this form is to be filled in; you will be able soon to do:
			filledform = DataForm(replyto=thisform)...'''
		def fget(self):
			return self.getAttr('type')
		def fset(self, type_):
			assert type_ in ('form', 'submit', 'cancel', 'result')
			self.setAttr('type', type_)
		return locals()

	@nested_property
	def title():
		''' Title of the form. Human-readable, should not contain any \\r\\n.'''
		def fget(self):
			return self.getTagData('title')
		def fset(self, title):
			self.setTagData('title', title)
		def fdel(self):
			try:
				self.delChild('title')
			except ValueError:
				pass
		return locals()

	@nested_property
	def instructions():
		''' Instructions for this form. Human-readable, may contain \\r\\n. '''
		# TODO: the same code is in TextMultiField. join them
		def fget(self):
			value = u''
			for valuenode in self.getTags('instructions'):
				value += '\n' + valuenode.getData()
			return value[1:]
		def fset(self, value):
			fdel(self)
			if value == '': return
			for line in value.split('\n'):
				self.addChild('instructions').setData(line)
		def fdel(self):
			for value in self.getTags('instructions'):
				self.delChild(value)
		return locals()

class SimpleDataForm(DataForm, DataRecord):
	def __init__(self, type_=None, title=None, instructions=None, fields=None, extend=None):
		DataForm.__init__(self, type_=type_, title=title, instructions=instructions, extend=extend)
		DataRecord.__init__(self, fields=fields, extend=self, associated=self)

	def get_purged(self):
		c = SimpleDataForm(extend=self)
		del c.title
		c.instructions = ''
		to_be_removed = []
		for f in c.iter_fields():
			if f.required:
				# Keep all required fields
				continue
			if (hasattr(f, 'value') and not f.value) or (hasattr(f, 'values') and \
			len(f.values) == 0):
				to_be_removed.append(f)
			else:
				del f.label
				del f.description
		for f in to_be_removed:
			c.delChild(f)
		return c

class MultipleDataForm(DataForm):
	def __init__(self, type_=None, title=None, instructions=None, items=None, extend=None):
		DataForm.__init__(self, type_=type_, title=title, instructions=instructions, extend=extend)
		# all records, recorded into DataRecords
		if extend is None:

			if items is not None: self.items = items
		else:
			# we already have xmpp.Node inside - try to convert all
			# fields into DataField objects
			if items is None:
				self.items = list(self.iterTags('item'))
			else:
				for item in self.getTags('item'):
					self.delChild(item)
				self.items = items
		reported_tag = self.getTag('reported')
		self.reported = DataRecord(extend = reported_tag)

	@nested_property
	def items():
		''' A list of all records. '''
		def fget(self):
			return list(self.iter_records())
		def fset(self, records):
			fdel(self)
			for record in records:
				if not isinstance(record, DataRecord):
					DataRecord(extend=record)
				self.addChild(node=record)
		def fdel(self):
			for record in self.getTags('item'):
				self.delChild(record)
		return locals()

	def iter_records(self):
		for record in self.getTags('item'):
			yield record

#	@nested_property
#	def reported():
#		''' DataRecord that contains descriptions of fields in records.'''
#		def fget(self):
#			return self.getTag('reported')
#		def fset(self, record):
#			try:
#				self.delChild('reported')
#			except:
#				pass
#
#			record.setName('reported')
#			self.addChild(node=record)
#		return locals()


# vim: se ts=3:
