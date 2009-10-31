#!/usr/bin/python

import types

class VerboseClassType(type):
	indent = ''

	def __init__(cls, name, bases, dict):
		super(VerboseClassType, cls).__init__(cls, name, bases, dict)
		new = {}
		print 'Initializing new class %s:' % cls
		for fname, fun in dict.iteritems():
			wrap = hasattr(fun, '__call__')
			print '%s%s is %s, we %s wrap it.' % \
				(cls.__class__.indent, fname, fun, wrap and 'will' or "won't")
			if not wrap: continue
			setattr(cls, fname, cls.wrap(name, fname, fun))

	def wrap(cls, name, fname, fun):
		def verbose(*a, **b):
			args = ', '.join(map(repr, a)+map(lambda x:'%s=%r'%x, b.iteritems()))
			print '%s%s.%s(%s):' % (cls.__class__.indent, name, fname, args)
			cls.__class__.indent += '|   '
			r = fun(*a, **b)
			cls.__class__.indent = cls.__class__.indent[:-4]
			print '%s+=%r' % (cls.__class__.indent, r)
			return r
		verbose.__name__ = fname
		return verbose

def nested_property(f):
	ret = f()
	p = {}
	for v in ('fget', 'fset', 'fdel', 'doc'):
		if v in ret: p[v]=ret[v]
	return property(**p)
