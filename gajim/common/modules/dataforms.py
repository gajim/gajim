# Copyright (C) 2006-2007 Tomasz Melcer <liori AT exroot.org>
# Copyright (C) 2006-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2007 Stephan Erb <steve-e AT h3c.de>
#
# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

# XEP-0004: Data Forms

import nbxmpp

from gajim.common import helpers


# exceptions used in this module
class Error(Exception):
    pass


# when we get nbxmpp.Node which we do not understand
class UnknownDataForm(Error):
    pass


# when we get nbxmpp.Node which contains bad fields
class WrongFieldValue(Error):
    pass


# helper class to change class of already existing object
class ExtendedNode(nbxmpp.Node, object):
    @classmethod
    def __new__(cls, *a, **b):
        if 'extend' not in b.keys() or not b['extend']:
            return object.__new__(cls)

        extend = b['extend']
        assert issubclass(cls, extend.__class__)
        extend.__class__ = cls
        return extend


# helper to create fields from scratch
def Field(typ, **attrs):
    ''' Helper function to create a field of given type. '''
    f = {
        'boolean': BooleanField,
        'fixed': StringField,
        'hidden': StringField,
        'text-private': StringField,
        'text-single': StringField,
        'jid-multi': JidMultiField,
        'jid-single': JidSingleField,
        'list-multi': ListMultiField,
        'list-single': ListSingleField,
        'text-multi': TextMultiField,
    }[typ](typ=typ, **attrs)
    return f


def ExtendField(node):
    """
    Helper function to extend a node to field of appropriate type
    """
    # when validation (XEP-122) will go in, we could have another classes
    # like DateTimeField - so that dicts in Field() and ExtendField() will
    # be different...
    typ = node.getAttr('type')
    f = {
        'boolean': BooleanField,
        'fixed': StringField,
        'hidden': StringField,
        'text-private': StringField,
        'text-single': StringField,
        'jid-multi': JidMultiField,
        'jid-single': JidSingleField,
        'list-multi': ListMultiField,
        'list-single': ListSingleField,
        'text-multi': TextMultiField,
    }
    if typ not in f:
        typ = 'text-single'
    return f[typ](extend=node)


def ExtendForm(node):
    """
    Helper function to extend a node to form of appropriate type
    """
    if node.getTag('reported') is not None:
        return MultipleDataForm(extend=node)
    else:
        return SimpleDataForm(extend=node)


class DataField(ExtendedNode):
    """
    Keeps data about one field - var, field type, labels, instructions... Base
    class for different kinds of fields. Use Field() function to construct one
    of these
    """

    def __init__(self, typ=None, var=None, value=None, label=None, desc=None,
                 required=False, options=None, extend=None):

        if extend is None:
            ExtendedNode.__init__(self, 'field')

            self.type_ = typ
            self.var = var
            if value is not None:
                self.value = value
            if label is not None:
                self.label = label
            if desc is not None:
                self.desc = desc
            self.required = required
            self.options = options

    @property
    def type_(self):
        """
        Type of field. Recognized values are: 'boolean', 'fixed', 'hidden',
        'jid-multi', 'jid-single', 'list-multi', 'list-single', 'text-multi',
        'text-private', 'text-single'. If you set this to something different,
        DataField will store given name, but treat all data as text-single
        """
        t = self.getAttr('type')
        if t is None:
            return 'text-single'
        return t

    @type_.setter
    def type_(self, value):
        assert isinstance(value, str)
        self.setAttr('type', value)

    @property
    def var(self):
        """
        Field identifier
        """
        return self.getAttr('var')

    @var.setter
    def var(self, value):
        assert isinstance(value, str)
        self.setAttr('var', value)

    @var.deleter
    def var(self):
        self.delAttr('var')

    @property
    def label(self):
        """
        Human-readable field name
        """
        label_ = self.getAttr('label')
        if not label_:
            label_ = self.var
        return label_

    @label.setter
    def label(self, value):
        assert isinstance(value, str)
        self.setAttr('label', value)

    @label.deleter
    def label(self):
        if self.getAttr('label'):
            self.delAttr('label')

    @property
    def description(self):
        """
        Human-readable description of field meaning
        """
        return self.getTagData('desc') or ''

    @description.setter
    def description(self, value):
        assert isinstance(value, str)
        if value == '':
            del self.description
        else:
            self.setTagData('desc', value)

    @description.deleter
    def description(self):
        t = self.getTag('desc')
        if t is not None:
            self.delChild(t)

    @property
    def required(self):
        """
        Controls whether this field required to fill. Boolean
        """
        return bool(self.getTag('required'))

    @required.setter
    def required(self, value):
        t = self.getTag('required')
        if t and not value:
            self.delChild(t)
        elif not t and value:
            self.addChild('required')

    @property
    def media(self):
        """
        Media data
        """
        media = self.getTag('media', namespace=nbxmpp.NS_DATA_MEDIA)
        if media:
            return Media(media)

    @media.setter
    def media(self, value):
        del self.media
        self.addChild(node=value)

    @media.deleter
    def media(self):
        t = self.getTag('media')
        if t is not None:
            self.delChild(t)

    def is_valid(self):
        return True


class Uri(nbxmpp.Node):
    def __init__(self, uri_tag):
        nbxmpp.Node.__init__(self, node=uri_tag)

    @property
    def type_(self):
        """
        uri type
        """
        return self.getAttr('type')

    @type_.setter
    def type_(self, value):
        self.setAttr('type', value)

    @type_.deleter
    def type_(self):
        self.delAttr('type')

    @property
    def uri_data(self):
        """
        uri data
        """
        return self.getData()

    @uri_data.setter
    def uri_data(self, value):
        self.setData(value)

    @uri_data.deleter
    def uri_data(self):
        self.setData(None)


class Media(nbxmpp.Node):
    def __init__(self, media_tag):
        nbxmpp.Node.__init__(self, node=media_tag)

    @property
    def uris(self):
        """
        URIs of the media element.
        """
        return map(Uri, self.getTags('uri'))

    @uris.setter
    def uris(self, value):
        del self.uris
        for uri in value:
            self.addChild(node=uri)

    @uris.deleter
    def uris(self):
        for element in self.getTags('uri'):
            self.delChild(element)


class BooleanField(DataField):
    @property
    def value(self):
        """
        Value of field. May contain True, False or None
        """
        v = self.getTagData('value')
        if v in ('0', 'false'):
            return False
        if v in ('1', 'true'):
            return True
        if v is None:
            return False  # default value is False
        raise WrongFieldValue

    @value.setter
    def value(self, value):
        self.setTagData('value', value and '1' or '0')

    @value.deleter
    def value(self):
        t = self.getTag('value')
        if t is not None:
            self.delChild(t)


class StringField(DataField):
    """
    Covers fields of types: fixed, hidden, text-private, text-single
    """

    @property
    def value(self):
        """
        Value of field. May be any string
        """
        return self.getTagData('value') or ''

    @value.setter
    def value(self, value):
        assert isinstance(value, str)
        if value == '' and not self.required:
            del self.value
            return
        self.setTagData('value', value)

    @value.deleter
    def value(self):
        try:
            self.delChild(self.getTag('value'))
        except ValueError:  # if there already were no value tag
            pass


class ListField(DataField):
    """
    Covers fields of types: jid-multi, jid-single, list-multi, list-single
    """

    @property
    def options(self):
        """
        Options
        """
        options = []
        for element in self.getTags('option'):
            v = element.getTagData('value')
            if v is None:
                raise WrongFieldValue
            label = element.getAttr('label')
            if not label:
                label = v
            options.append((label, v))
        return options

    @options.setter
    def options(self, values):
        del self.options
        for value, label in values:
            self.addChild('option',
                          {'label': label}).setTagData('value', value)

    @options.deleter
    def options(self):
        for element in self.getTags('option'):
            self.delChild(element)

    def iter_options(self):
        for element in self.iterTags('option'):
            v = element.getTagData('value')
            if v is None:
                raise WrongFieldValue
            label = element.getAttr('label')
            if not label:
                label = v
            yield (v, label)


class ListSingleField(ListField, StringField):
    """
    Covers list-single field
    """
    def is_valid(self):
        if not self.required:
            return True
        if not self.value:
            return False
        return True


class JidSingleField(ListSingleField):
    """
    Covers jid-single fields
    """
    def is_valid(self):
        if self.value:
            try:
                helpers.parse_jid(self.value)
                return True
            except Exception:
                return False
        if self.required:
            return False
        return True


class ListMultiField(ListField):
    """
    Covers list-multi fields
    """

    @property
    def values(self):
        """
        Values held in field
        """
        values = []
        for element in self.getTags('value'):
            values.append(element.getData())
        return values

    @values.setter
    def values(self, values):
        del self.values
        for value in values:
            self.addChild('value').setData(value)

    @values.deleter
    def values(self):
        for element in self.getTags('value'):
            self.delChild(element)

    def iter_values(self):
        for element in self.getTags('value'):
            yield element.getData()

    def is_valid(self):
        if not self.required:
            return True
        if not self.values:
            return False
        return True


class JidMultiField(ListMultiField):
    """
    Covers jid-multi fields
    """
    def is_valid(self):
        if len(self.values):
            for value in self.values:
                try:
                    helpers.parse_jid(value)
                except Exception:
                    return False
            return True
        if self.required:
            return False
        return True


class TextMultiField(DataField):
    @property
    def value(self):
        """
        Value held in field
        """
        value = ''
        for element in self.iterTags('value'):
            value += '\n' + element.getData()
        return value[1:]

    @value.setter
    def value(self, value):
        del self.value
        if value == '':
            return
        for line in value.split('\n'):
            self.addChild('value').setData(line)

    @value.deleter
    def value(self):
        for element in self.getTags('value'):
            self.delChild(element)


class DataRecord(ExtendedNode):
    """
    The container for data fields - an xml element which has DataField elements
    as children
    """
    def __init__(self, fields=None, associated=None, extend=None):
        self.associated = associated
        self.vars = {}
        if extend is None:
            # we have to build this object from scratch
            nbxmpp.Node.__init__(self)

            if fields is not None:
                self.fields = fields
        else:
            # we already have nbxmpp.Node inside - try to convert all
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

    @property
    def fields(self):
        """
        List of fields in this record
        """
        return self.getTags('field')

    @fields.setter
    def fields(self, fields):
        del self.fields
        for field in fields:
            if not isinstance(field, DataField):
                ExtendField(field)
            self.addChild(node=field)

    @fields.deleter
    def fields(self):
        for element in self.getTags('field'):
            self.delChild(element)

    def iter_fields(self):
        """
        Iterate over fields in this record. Do not take associated into account
        """
        for field in self.iterTags('field'):
            yield field

    def iter_with_associated(self):
        """
        Iterate over associated, yielding both our field and associated one
        together
        """
        for field in self.associated.iter_fields():
            yield self[field.var], field

    def __getitem__(self, item):
        return self.vars[item]

    def is_valid(self):
        for f in self.iter_fields():
            if not f.is_valid():
                return False
        return True


class DataForm(ExtendedNode):
    def __init__(self, type_=None, title=None, instructions=None, extend=None):
        if extend is None:
            # we have to build form from scratch
            nbxmpp.Node.__init__(self, 'x', attrs={'xmlns': nbxmpp.NS_DATA})

        if type_ is not None:
            self.type_ = type_
        if title is not None:
            self.title = title
        if instructions is not None:
            self.instructions = instructions

    @property
    def type_(self):
        """
        Type of the form. Must be one of: 'form', 'submit', 'cancel', 'result'.
        'form' - this form is to be filled in; you will be able soon to do:
        filledform = DataForm(replyto=thisform)
        """
        return self.getAttr('type')

    @type_.setter
    def type_(self, type_):
        assert type_ in ('form', 'submit', 'cancel', 'result')
        self.setAttr('type', type_)

    @property
    def title(self):
        """
        Title of the form

        Human-readable, should not contain any \\r\\n.
        """
        return self.getTagData('title')

    @title.setter
    def title(self, title):
        self.setTagData('title', title)

    @title.deleter
    def title(self):
        try:
            self.delChild('title')
        except ValueError:
            pass

    @property
    def instructions(self):
        """
        Instructions for this form

        Human-readable, may contain \\r\\n.
        """
        # TODO: the same code is in TextMultiField. join them
        value = ''
        for valuenode in self.getTags('instructions'):
            value += '\n' + valuenode.getData()
        return value[1:]

    @instructions.setter
    def instructions(self, value):
        del self.instructions
        if value == '':
            return
        for line in value.split('\n'):
            self.addChild('instructions').setData(line)

    @instructions.deleter
    def instructions(self):
        for value in self.getTags('instructions'):
            self.delChild(value)


class SimpleDataForm(DataForm, DataRecord):
    def __init__(self, type_=None, title=None, instructions=None, fields=None,
                 extend=None):
        DataForm.__init__(self, type_=type_, title=title,
                          instructions=instructions, extend=extend)
        DataRecord.__init__(self, fields=fields, extend=self, associated=self)

    def get_purged(self):
        c = SimpleDataForm(extend=self)
        del c.title
        c.instructions = ''
        to_be_removed = []
        for f in c.iter_fields():
            if f.required:
                # add <value> if there is not
                if hasattr(f, 'value') and not f.value:
                    f.value = ''
                # Keep all required fields
                continue
            if ((hasattr(f, 'value') and not f.value and f.value != 0) or
                    (hasattr(f, 'values') and len(f.values) == 0)):
                to_be_removed.append(f)
            else:
                del f.label
                del f.description
                del f.media
        for f in to_be_removed:
            c.delChild(f)
        return c


class MultipleDataForm(DataForm):
    def __init__(self, type_=None, title=None, instructions=None, items=None,
                 extend=None):
        DataForm.__init__(self, type_=type_, title=title,
                          instructions=instructions, extend=extend)
        # all records, recorded into DataRecords
        if extend is None:
            if items is not None:
                self.items = items
        else:
            # we already have nbxmpp.Node inside - try to convert all
            # fields into DataField objects
            if items is None:
                self.items = list(self.iterTags('item'))
            else:
                for item in self.getTags('item'):
                    self.delChild(item)
                self.items = items
        reported_tag = self.getTag('reported')
        self.reported = DataRecord(extend=reported_tag)

    @property
    def items(self):
        """
        A list of all records
        """
        return list(self.iter_records())

    @items.setter
    def items(self, records):
        del self.items
        for record in records:
            if not isinstance(record, DataRecord):
                DataRecord(extend=record)
            self.addChild(node=record)

    @items.deleter
    def items(self):
        for record in self.getTags('item'):
            self.delChild(record)

    def iter_records(self):
        for record in self.getTags('item'):
            yield record

#    @property
#    def reported(self):
#        """
#        DataRecord that contains descriptions of fields in records
#        """
#        return self.getTag('reported')
#
#    @reported.setter
#    def reported(self, record):
#        try:
#            self.delChild('reported')
#        except:
#            pass
#
#        record.setName('reported')
#        self.addChild(node=record)
