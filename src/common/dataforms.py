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

	try:
		while node.delChild(childname):
			pass
	except ValueError:
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

		assert typ in (None, 'form', 'submit', 'cancel', 'result')
		assert isinstance(title, basestring) or title is None
		assert isinstance(instructions, basestring) or instructions is None
		assert (fields is None or fields.__iter__)

		xmpp.Node.__init__(self, 'x', node=node)
		self.setNamespace(xmpp.NS_DATA)

		if tofill is not None:
			self._mode = tofill.mode
			self.fields = (field for field in tofill.fields if field.type!='fixed')
			self.records = tofill.records
			self.type = 'submit'
			for field in self.iter_fields():
				field.required=False
				del field.label
				del field.options
				del field.description
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
				toadd=[]
				for field in self.getChildren():
					if not isinstance(field, xmpp.Node): continue
					if not field.getName()=='field': continue
					toadd.append(DataField(node=field))

				del_multiple_tag_value(self, 'field')

				for field in toadd:
					self.addChild(node=field)
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
		self.setTagData('title', title)

	def del_title(self):
		try:
			self.delChild('title')
		except ValueError:
			pass

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
			yield DataRecord(node=self)
		else:
			for item in self.getChildren():
				if not isinstance(item, xmpp.Node): continue
				if not item.getName()=='item': continue
				yield DataRecord(node=item)

	def get_records(self):
		if self.mode is DATAFORM_SINGLE:
			return [DataRecord(node=self),]
		else:
			items = []
			for node in self.getChildren():
				if not isinstance(node, xmpp.Node): continue
				if not node.getName()=='item': continue
				items.append(DataRecord(node=node))
			return items

	def set_records(self, records):
		if self.mode is DATAFORM_SINGLE:
			assert len(records)==1

			record = records[0]
			assert isinstance(record, DataRecord)
			for field in record.iter_fields():
				self[field.var]=field.value
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
			try:
				self.delChild('recorded')
			except ValueError:
				pass
			self.addChild('recorded', {}, fields)

	def del_fields(self):
		if self.mode is DATAFORM_SINGLE:
			del_multiple_tag_value(self, "field")
		else:
			try:
				self.delChild('recorded')
			except ValueError:
				pass

	def iter_fields(self):
		if self.mode is DATAFORM_SINGLE:
			container = self
		else:
			container = self.getTag("recorded")

		for child in container.getChildren():
			if isinstance(child, DataField):
				yield child

	fields = property(get_fields, set_fields, del_fields,
		"""Fields in this form; a list; if in DATAFORM_SINGLE mode, you should not
		set their values directly.""")

	def __getitem__(self, var):
		for field in self.iter_fields():
			if field.var==var:
				return field.value
		raise KeyError, "This form does not contain %r field." % var

	def __setitem__(self, var, value):
		for field in self.iter_fields():
			if field.var==var:
				field.value=value
				return
		raise KeyError, "This form does not contain %r field." % var

	def __contains__(self, name):
		for field in self.iter_fields():
			if field.var==name:
				return True
		else:
			return False

class DataField(xmpp.Node, object):
	def __init__(self, typ=None,var=None, value=None, label=None, desc=None,
		required=None, options=None, node=None):

		assert typ in ('boolean', 'fixed', 'hidden', 'jid-multi', 'jid-single', 'list-multi',
			'list-single', 'text-multi', 'text-private', 'text-single',None)
		
		xmpp.Node.__init__(self, 'field', node=node)
		if typ is not None: self.type = typ
		if var is not None: self.var = var
		if label is not None: self.label = label
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
			try:
				self.delAttr('type')
			except KeyError:
				pass

	type = property(get_type, set_type, None,
		""" Field type. One of: 'boolean', 'fixed', 'hidden', 'jid-multi', 'jid-single',
		'list-multi', 'list-single', 'text-multi', 'text-private', 'text-single'.""")

	def get_var(self):
		return self.getAttr('var')

	def set_var(self, var):
		self.setAttr('var', var)

	def del_var(self):
		try:
			self.delAttr('var')
		except KeyError:
			pass

	var = property(get_var, set_var, del_var,
		""" Field name. """)

	def get_label(self):
		return self.getAttr('label')

	def set_label(self, label):
		self.setAttr('label', label)

	def del_label(self):
		try:
			self.delAttr('label')
		except KeyError:
			pass

	label = property(get_label, set_label, del_label,
		""" Human-readable name for field. """)

	def get_description(self):
		return self.getTagData('desc')

	def set_description(self, desc):
		self.setTagData('desc', desc)

	def del_description(self):
		try:
			self.delChild('desc')
		except ValueError:
			pass

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

	def iter_values(self):
		assert self.type in ('list-single', 'list-multi', 'jid-multi')

		for element in self.getChildren():
			if not isinstance(element, xmpp.Node): continue
			if not element.getName()=='value': continue
			yield element.getData().decode('utf-8')

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

		elif self.type in ('hidden', 'jid-single', 'list-single', 'text-single', 'text-private') or True:
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
			for item in value:
				self.addChild('value', {}, (item,))

		elif self.type in ('hidden', 'jid-single', 'list-single', 'text-single', 'text-private'):
			self.setTagData('value', value)

	def del_value(self):
		del_multiple_tag_value(self, 'value')

	value = property(get_value, set_value, del_value,
		""" The value of field. Depending on the type, it is a boolean, a unicode string or a list
		of stings. """)

	def iter_options(self):
		""" Yields a pair: label, value """
		for element in self.getChildren():
			if not isinstance(element, xmpp.Node): continue
			if not element.getName()=='option': continue
			try:
				yield element.getAttr('label'), element.getTag('value').getData()
			except TypeError:
				raise BadDataFormNode

	def get_options(self):
		""" Returns a list of tuples: (label, value). """
		return [(tag.getAttr('label'), tag.getTag('value').getData()) for tag in self.getTags('option')]

	def set_options(self, options):
		""" Options need to be a list of tuples (label, value), both unicode. """
		assert options.__iter__

		del_multiple_tag_value(self, 'option')
		for option in options:
			assert option[0] is None or isinstance(option[0], unicode)
			assert isinstance(option[1], unicode)
			if option[0] is None:
				attr={}
			else:
				attr={'label': option[0].encode('utf-8')}
			self.addChild('option', attr, (xmpp.Node('value', {}, (option[1].encode('utf-8'),)),))

	def del_options(self):
		del_multiple_tag_value(self, 'option')

	options = property(get_options, set_options, del_options,
		""" Options to choose between in list-* fields. """)

class DataRecord(xmpp.Node):
	""" Class to store fields. May be used as temporary storage (for example when reading a list of
	fields from DataForm in DATAFORM_SINGLE mode), may be used as permanent storage place (for example
	for DataForms in DATAFORM_MULTIPLE mode). It expects that every <field/> element is actually
	a DataField instance."""
	def __init__(self, fields=None, node=None):
		assert (fields is None) or (node is None)
		assert (fields is None) or (fields.__iter__)
		assert (node is None) or (isinstance(node, xmpp.Node))

		self.vars = {}

		xmpp.Node.__init__(self, node=node)

		if node is not None:
			for field in node.getTags('field'):
				assert isinstance(field, DataField)
				self.vars[field.var] = field

		if fields is not None:
			for field in fields:
				assert isinstance(field, DataField)
				self.addChild(node=field)
				self.vars[field.var] = field

	# if there will be ever needed access to all fields as a list, write it here, in form of property

	def iter_fields(self):
		for field in self.getChildren():
			if not isinstance(field, xmpp.DataField): continue
			yield field

	def __getitem__(self, item):
		return self.vars[item]
