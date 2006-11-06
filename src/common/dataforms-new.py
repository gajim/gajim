# this will go to src/common/xmpp later, for now it is in src/common
""" This module contains wrappers for different parts of data forms (JEP 0004). For information
how to use them, read documentation. """

import xmpp

# exceptions used in this module
class Error(Exception): pass	# base class
class UnknownDataForm(Error): pass	# when we get xmpp.Node which we do not understand
class WrongFieldValue(Error): pass	# when we get xmpp.Node which contains bad fields

# helper class to change class of already existing object
class Extends(object):
	def __new__(cls, *a, **b):
		print 'Extends.__new__'
		if 'extend' not in b.keys():
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
		if v in ret: p[v]=ret[v]
	return property(**p)

# helper to create fields from scratch
def Field(typ, **attrs):
	f = {
		'boolean': BooleanField,
		'fixed': StringField,
		'hidden': StringField,
		'text-private': StringField,
		'text-single': StringField,
		'jid-multi': ListField,
		'jid-single': ListField,
		'list-multi': ListField,
		'list-single': ListField,
		'text-multi': TextMultiField,
	}[typ]
	for key, value in attrs.iteritems():
		f.setattr(key, value)
	return f

class DataField(Extends, xmpp.Node):
	""" Keeps data about one field - var, field type, labels, instructions... """
	def __init__(self, typ=None, var=None, value=None, label=None, desc=None, required=None,
		options=None, extend=None):

		if extend is None:
			super(DataField, self).__init__(self, 'field')

			self.type = typ
			self.var = var
			self.value = value
			self.label = label
			self.desc = desc
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
			return boolean(self.getTag('required'))
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
			if v is None: return None
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
			t = self.getTag('value')
			if t is not None:
				self.delChild(t)
		return locals()

class ListField(DataField):
	''' Covers fields of types: jid-multi, jid-single, list-multi, list-single. '''
	@nested_property
	def values():
		'''Values held in field.'''
		def fget(self):
			values = []
			for element in iter_elements(self, 'value'):
				values.append(element.getData())
			return values
		def fset(self, values):
			fdel(self)
			for value in values:
				self.addChild('value').setData(value)
		def fdel(self):
			for element in iter_elements(self, 'value'):
				self.delChild(element)
		return locals()
	
	def iter_values():
		for element in iter_elements(self, 'value'):
			yield element.getData()
	
	@nested_property
	def options():
		'''Options.'''
		def fget(self):
			options = []
			for element in iter_elements(self, 'option'):
				v = element.getTagData('value')
				if v is None: raise WrongFieldValue
				options.append((element.getAttr('label'), v))
			return options
		def fset(self, values):
			fdel(self)
			for label, value in values:
				self.addChild('option', {'label': label}).setTagData('value', value)
		def fdel(self):
			for element in iter_elements(self, 'option'):
				self.delChild(element)
		return locals()

	def iter_options(self):
		for element in iter_elements(self, 'option'):
			v = element.getTagData('value')
			if v is None: raise WrongFieldValue
			yield (element.getAttr('label'), v)

class TextMultiField(DataField):
	@nested_property
	def value():
		'''Value held in field.'''
		def fget(self):
			value = u''
			for element in iter_elements(self, 'value'):
				value += '\n' + element.getData()
			return value[1:]
		def fset(self, value):
			fdel(self)
			if value == '': return
			for line in value.split('\n'):
				self.addChild('value').setData(line)
		def fdel(self):
			for element in iter_elements(self, 'value'):
				self.delChild(element)
		return locals()

class DataRecord(Extends, xmpp.Node):
	'''The container for data fields - an xml element which has DataField
	elements as children.'''
	def __init__(self, fields=None, associated=None, extend=None):
		self.associated = None
		self.vars = {}
		if extend is None:
			# we have to build this object from scratch
			xmpp.Node.__init__(self)

			if fields is not None: self.fields = fields
			if associated is not None: self.associated = associated
		else:
			# we already have xmpp.Node inside - try to convert all
			# fields into DataField objects
			for field in self.iterTags('field'):
				if not isinstance(field, DataField):
					DataField(extend=field)
				self.vars[field.var] = field

	@nested_property
	def fields():
		'''List of fields in this record.'''
		def fget(self):
			return self.getTags('field')
		def fset(self, fields):
			fdel(self)
			for field in fields:
				if not isinstance(field, DataField):
					DataField(extend=field)
				self.addChild(node=field)
		def fdel(self):
			for element in self.iterTags('field'):
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

class DataForm(Extends, DataRecord):
	def __init__(self, replyto=None, extends=None):
		pass

	@nested_property
	def type():
		''' Type of the form. Must be one of: 'form', 'submit', 'cancel', 'result'.
		'form' - this form is to be filled in; you can do:
			filledform = DataForm(replyto=thisform)...'''
		def fget(self):
			return self.getAttr('type')
		def fset(self):
			assert type in ('form', 'submit', 'cancel', 'result')
			self.setAttr('type', type)
		return locals()

	@nested_property
	def title():
		''' Title of the form. Human-readable, should not contain any \\r\\n.'''
		def fget(self):
			return self.getTagData('title')
		def fset(self):
			self.setTagData('title', title)
		def fdel(self):
			try:
				self.delChild('title')
			except ValueError:
				pass

	@nested_property
	def instructions():
		''' Instructions for this form. Human-readable, may contain \\r\\n. '''
		# TODO: the same code is in TextMultiField. join them
		def fget(self):
			value = u''
			for value in self.iterTags('value'):
				value += '\n' + value.getData()
			return value[1:]
		def fset(self, value):
			fdel(self)
			if value == '': return
			for line in value.split('\n'):
				self.addChild('value').setData(line)
		def fdel(self):
			for value in self.iterTags('value'):
				self.delChild(value)

class SimpleDataForm(DataForm):
	pass

class MultipleDataForm(DataForm):
	def __init__(self):
		# all records, recorded into DataRecords

	@nested_property
	def records():
		''' A list of all records. '''
		
