# this will go to src/common/xmpp later, for now it is in src/common

import xmpp

# Helpers, to handle multi-element values like field values of instructions elements

def get_multiple_tag_value(node, childname):
	""" Join by u'/n' all occurences of childname in node, as described in JEP-0004 for value data for
	*-multi fields."""
	assert isinstance(node, xmpp.Node)
	assert isinstance(childname, basestring)

	nodes = node.getTags(childname)
	values = (node.getData().decode('utf-8') for node in nodes)	# using python2.4 iterators
	return u"\n".join(values)

def set_multiple_tag_value(node, childname, value):
	""" Set children nodes to value, splitting lines between different nodes, as described in JEP-0004
	for value data for *-multi fields. If you try to set the value to None, all tag values will be
	deleted. """
	assert isinstance(node, xmpp.Node)
	assert isinstance(childname, basestring)
	assert isinstance(value, basestring) or value is None

	del_multiple_tag_value(node, childname)

	if value is None: return

	values = value.split(u'\n')
	nodes = (xmpp.Node(childname, payload=[value.encode('utf-8')]) for value in values)# using python2.4 iterators
	for new in nodes:
		node.addChild(node=new)

def del_multiple_tag_value(node, childname):
	""" Delete a value from node, when the value is splitted between many childname elements inside
	node, as described in JEP-0004 for value for *-multi fields. It also removes every instance of
	childname in node.
	"""

	while node.delChild(childname):
		pass

def iter_elements(node, childname):
	""" Iterate over childname children of node element. """
	for element in node.getChildren():
		if isinstance(element, xmpp.Node) and element.getName()==childname:
			yield element

(DATAFORM_SINGLE, DATAFORM_MULTIPLE) = range(2)

class RecordDoesNotContainRequiredField(Exception): pass
class BadDataFormNode(Exception): pass

class DataForm(xmpp.Node, object):
	""" Data form as described in JEP-0004. """

	def __init__(self, typ=None, title=None, instructions=None, fields=None, records=None, node=None, tofill=None):
		""" Create new node, based on the node given by 'node' parameter, or new.
		You can prefill some form properties, look at their description for meaning.

		You can also set 'tofill' to DataForm to get a form of type 'submit' with the
		same fields as in the form given, but without unnecessary data like
		instructions or title. Also the type will be set to 'submit' by default."""
		assert (isinstance(node, xmpp.Node) or node is None)
		assert (isinstance(tofill, DataForm) or tofill is None)
		assert not (node is not None and tofill is not None)

		assert typ in (None, 'form', 'submit', 'cancel', 'return')
		assert isinstance(title, basestring) or title is None
		assert isinstance(instructions, basestring) or instructions is None
		assert (fields is None or fields.__iter__)

		xmpp.Node.__init__(self, 'x', node=node)
		self.setNamespace(xmpp.NS_DATA)

		if tofill is not None:
			self._mode = tofill.mode
			self.fields = tofill.fields
			self.records = tofill.records
			self.type = 'submit'
		elif node is not None:
			# if there is <reported/> element, the form contains multiple records
			if self.getTag('reported') is not None:
				# in multiple-record forms there must not be any fields not in <items/>
				if self.getTag('field') is not None: raise BadDataNodeForm
				self._mode = DATAFORM_MULTIPLE

				# change every <field/> to DataField object
				for item in iter_elements(self, 'item'):
					for field in iter_elements(item, 'field'):
						field.delChild(field)
						field.addChild(node=DataField(node=field))
			else:
				self._mode = DATAFORM_SINGLE

				# change every <field/> to DataField object
				for field in self.getChildren():
					if not isinstance(field, xmpp.Node): continue
					if not field.getName()=='field': continue
					self.delChild(field)
					self.addChild(node=DataField(node=field)
		else: # neither tofill nor node has a Node
			if typ is None: typ='result'
			if records is not None and len(records)>1:
				self._mode = DATAFORM_MULTIPLE
			else:
				self._mode = DATAFORM_SINGLE

		if typ is not None: self.type = typ
		if title is not None: self.title = title
		if instructions is not None: self.instructions = instructions
		if fields is not None: self.fields = fields
		if records is not None: self.records = records

	def get_type(self):
		return self.getAttr('type')

	def set_type(self, type):
		assert type in ('form', 'submit', 'cancel', 'result')
		self.setAttr('type', type)

	type = property(get_type, set_type, None,
		"""Form type, one of:
		'form', when it is meant to complete,
		'submit', when it is meant to transport completed form,
		'cancel', when it is meant to cancel the process,
		'result', when it is meant to provide some data. (the default)""")

	def get_title(self):
		return self.getTagData('title')

	def set_title(self, title):
		self.setTagData('title')

	def del_title(self):
		self.delChild('title')

	title = property(get_title, set_title, del_title,
		"Form title, in unicode, from <title/> element.")

	def get_instructions(self):
		return get_multiple_tag_value(self, 'instructions')

	def set_instructions(self, data):
		assert isinstance(data, basestring)
		set_multiple_tag_value(self, 'instructions', data)

	def del_instructions(self):
		del_multiple_tag_value(self, 'instructions')

	instructions = property(get_instructions, set_instructions, None,
		"Instructions how to fill the form, in unicode, from <instructions/> element.")

	def get_mode(self):
		return self._mode

	def set_mode(self, mode):
		assert mode in (DATAFORM_SINGLE, DATAFORM_MULTIPLE)
		assert self.getTag('field') is None
		assert self.getTag('reported') is None
		assert self.getTag('item') is None
		self._mode = mode

	mode = property(get_mode, set_mode, None,
		"""Data form mode: DATAFORM_SINGLE or DATAFORM_MULTIPLE, if the form contains
		more than one record of data. Changing mode is allowed as long as there is no
		values in form.""")

	def iter_records(self):
		if self.mode is DATAFORM_SINGLE:
			yield DataRecord(self)
		else:
			for item in self.getChildren():
				if not isinstance(item, xmpp.Node): continue
				if not item.getName()=='item': continue
				yield DataRecord(item)

	def get_records(self):
		if self.mode is DATAFORM_SINGLE:
			return [DataRecord(self),]
		else:
			items = []
			for node in self.getChildren():
				if not isinstance(node, xmpp.Node): continue
				if not node.getName()=='item': continue
				items.append(DataRecord(node))
			return items

	def set_records(self, records):
		if self.mode is DATAFORM_SINGLE:
			assert len(records)==1

			record = records[0]
			assert isinstance(record, dict)
			for name, value in record.iteritems():
				self[name]=value
		else:
			self.del_records(self)
			for record in records:
				assert isinstance(record, dict)
				newitem = self.addChild('item', node=record)

	def del_records(self):
		if self.mode is DATAFORM_SINGLE:
			# removing values from every field
			for field in self.iter_fields():
				del_multiple_tag_value(field, "value")
		else:
			# removing all <items/> elements
			del_multiple_tag_value(self, "items")

	records = property(get_records, set_records, del_records,
		"""Records kept in this form; if in DATAFORM_SINGLE mode, there will be exactly
		one record, otherwise there might be more or less records.""")

	def get_fields(self):
		if self.mode is DATAFORM_SINGLE:
			container = self
		else:
			container = self.getTag("recorded")

		return container.getTags("field")

	def set_fields(self, fields):
		if self.mode is DATAFORM_SINGLE:
			del_multiple_tag_value(self, "field")
			for field in fields:
				assert isinstance(field, DataField)
				self.addChild(node=field)
		else:
			assert len(self.records)==0
			self.delChild('recorded')
			self.addChild('recorded', None, fields)

	def del_fields(self):
		if self.mode is DATAFORM_SINGLE:
			del_multiple_tag_value(self, "field")
		else:
			self.delChild('recorded')
	
	fields = property(get_fields, set_fields, del_fields,
		"""Fields in this form; a list; if in DATAFORM_SINGLE mode, you should not
		set their values directly.""")

class DataField(xmpp.Node, object):
	def __init__(self, typ='text-single', desc=None, required=None, value=None, options=None, node=None):
		assert typ in ('boolean', 'fixed', 'hidden', 'jid-multi', 'jid-single', 'list-multi',
			'list-single', 'text-multi', 'text-private', 'text-single', None)
		
		xmpp.Node.__init__(self, 'field', node=node)
		if desc is not None: self.description = desc
		if required is not None: self.required = required
		if value is not None: self.value = value
		if options is not None: self.options = options

	def get_type(self):
		# JEP says that if we don't understand field name, we should treat it as text-single
		t = self.getAttr('type')
		if t not in ('boolean', 'fixed', 'hidden', 'jid-multi', 'jid-single', 'list-multi',
			'list-single', 'text-multi', 'text-private'):
			return 'text-single'
		else:
			return t

	def set_type(self, typ):
		assert typ in ('boolean', 'fixed', 'hidden', 'jid-multi', 'jid-single', 'list-multi',
			'list-single', 'text-multi', 'text-private', 'text-single')

		if typ!='text-single':
			self.setAttr('type', typ)
		else:
			self.delAttr('type')

	type = property(get_type, set_type, None,
		""" Field type. One of: 'boolean', 'fixed', 'hidden', 'jid-multi', 'jid-single',
		'list-multi', 'list-single', 'text-multi', 'text-private', 'text-single'.""")

	def get_var(self):
		return self.getAttr('var')

	def set_var(self, var):
		self.setAttr('var', var)

	def del_var(self):
		self.delAttr('var')

	var = property(get_var, set_var, del_var,
		""" Field name. """)

	def get_label(self):
		return self.getAttr('label')

	def set_label(self, label):
		self.setAttr('label', label)

	def del_label(self):
		self.delAttr('label')

	label = property(get_label, set_label, del_label,
		""" Human-readable name for field. """)

	def get_description(self):
		return self.getTagData('desc')

	def set_description(self, desc):
		self.setTagData('desc', desc)

	def del_description(self):
		self.delChild('desc')

	description = property(get_description, set_description, del_description,
		""" A natural-language description of the field. It should not contain
		newlines. """)

	def get_required(self):
		return self.getTag('required') is not None

	def set_required(self, req):
		assert req in (True, False)

		if self.getTag('required') is not None:
			if req is False:
				self.delChild('required')
		else:
			if req is True:
				self.addChild('required')

	required = property(get_required, set_required, None,
		""" If this is set to True, the field is required for form to be valid. """)

	def get_value(self):
		if self.type in ('boolean',):
			if self.getTagData('value') in (1, 'true'):
				return True
			else:
				return False

		elif self.type in ('fixed','text-multi'):
			return get_multiple_tag_value(self, 'value')

		elif self.type in ('jid-multi', 'list-multi'):
			return [value.getData() for value in self.getTags('value')]
		
		elif self.type in ('hidden', 'jid-single', 'list-single', 'text-single', 'text-private'):
			return self.getTagData('value')

	def set_value(self, value):
		if self.type in ('boolean',):
			if value:
				self.setTagData('value', '1')
			else:
				self.setTagData('value', '0')

		elif self.type in ('fixed','text-multi'):
			set_multiple_tag_value(self, 'value', value)

		elif self.type in ('jid-multi', 'list-multi'):
			del_multiple_tag_value(self, 'value')
			for item in self.value:
				self.addChild('value', None, (item,))

		elif self.type in ('hidden', 'jid-single', 'list-single', 'text-single', 'text-private'):
			self.setTagData('value', value)

	def del_value(self):
		del_multiple_tag_value(self, 'value')

	value = property(get_value, set_value, del_value,
		""" The value of field. Depending on the type, it is a boolean, a unicode string or a list
		of stings. """)

	def get_options(self):
		return [tag.getData() for tag in self.getTags('option')]

	def set_options(self, options):
		assert options.__iter__

		del_multiple_tag_value(self, 'option')
		for option in options:
			assert isinstance(option, basestring)
			self.addChild('option', None, (option,))

	def del_options(self):
		del_multiple_tag_value(self, 'option')

	options = property(get_options, set_options, del_options,
		""" Options to choose between in list-* fields. """)

class DataRecord(xmpp.Node, dict):
	""" Class to store fields. May be used as temporary storage (for example when reading a list of
	fields from DataForm in DATAFORM_SINGLE mode), may be used as permanent storage place (for example
	for DataForms in DATAFORM_MULTIPLE mode)."""
	def __init__(self, fields=None, node=None):
		assert (fields is None) or (node is None)
		assert (fields is None) or (fields.__iter__)
		assert (node is None) or (isinstance(node, xmpp.Node))

		dict.__init__(self)
		xmpp.Node.__init__(self, node=node)
		if fields is not None:
			for field in fields:
				assert isinstance(field, DataField)
				self.addChild(node=field)
				self[field.name] = field

	# if there will be ever needed access to all fields as a list, write it here, in form of property

	def iter_fields(self):
		for field in self.getChildren():
			if not isinstance(field, xmpp.DataField): continue
			yield field
