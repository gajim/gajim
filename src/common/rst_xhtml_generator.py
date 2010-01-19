# -*- coding:utf-8 -*-
## src/common/rst_xhtml_generator.py
##
## Copyright (C) 2006 Santiago Gala
##                    Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006-2007 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2007 Jean-Marie Traissard <jim AT lapin.org>
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

try:
	from docutils import io
	from docutils.core import Publisher
	from docutils.parsers.rst import roles
	from docutils import nodes,utils
	from docutils.parsers.rst.roles import set_classes
except ImportError:
	print "Requires docutils 0.4 for set_classes to be available"
	def create_xhtml(text):
		return None
else:
	def pos_int_validator(text):
		"""
		Validates that text can be evaluated as a positive integer
		"""
		result = int(text)
		if result < 0:
			raise ValueError("Error: value '%(text)s' "
							"must be a positive integer")
		return result

	def generate_uri_role( role_name, aliases, anchor_text, base_url,
			interpret_url, validator):
		"""
		Create and register a uri based "interpreted role"

		Those are similar to the RFC, and PEP ones, and take
		role_name:
			name that will be registered
		aliases:
			list of alternate names
		anchor_text:
			text that will be used, together with the role
		base_url:
			base url for the link
		interpret_url:
			this, modulo the validated text, will be added to it
		validator:
			should return the validated text, or raise ValueError
		"""
		def uri_reference_role(role, rawtext, text, lineno, inliner,
			options={}, content=[]):
			try:
				valid_text = validator(text)
			except ValueError, e:
				msg = inliner.reporter.error( e.message % dict(text=text), line=lineno)
				prb = inliner.problematic(rawtext, rawtext, msg)
				return [prb], [msg]
			ref = base_url + interpret_url % valid_text
			set_classes(options)
			node = nodes.reference(rawtext, anchor_text + utils.unescape(text), refuri=ref,
					**options)
			return [node], []

		uri_reference_role.__doc__ = """Role to make handy references to URIs.

	 		Use as :%(role_name)s:`71` (or any of %(aliases)s).
			It will use %(base_url)s+%(interpret_url)s
			validator should throw a ValueError, containing optionally
			a %%(text)s format, if the interpreted text is not valid.
			""" % locals()
		roles.register_canonical_role(role_name, uri_reference_role)
		from docutils.parsers.rst.languages import en
		en.roles[role_name] = role_name
		for alias in aliases:
			en.roles[alias] = role_name

	generate_uri_role('xep-reference', ('jep', 'xep'),
				'XEP #', 'http://www.xmpp.org/extensions/', 'xep-%04d.html',
				pos_int_validator)
	generate_uri_role('gajim-ticket-reference', ('ticket','gtrack'),
				'Gajim Ticket #', 'http://trac.gajim.org/ticket/', '%d',
				pos_int_validator)

	class HTMLGenerator:
		"""
		Really simple HTMLGenerator starting from publish_parts

		It reuses the docutils.core.Publisher class, which means it is *not*
		threadsafe.
		"""
		def __init__(self, settings_spec=None,
				settings_overrides=dict(report_level=5, halt_level=5),
				config_section='general'):
			self.pub = Publisher(reader=None, parser=None, writer=None,
				settings=None,
				source_class=io.StringInput,
				destination_class=io.StringOutput)
			self.pub.set_components(reader_name='standalone',
				parser_name='restructuredtext',
				writer_name='html')
			# hack: JEP-0071 does not allow HTML char entities, so we hack our way
			# out of it.
			# &mdash; == u"\u2014"
			# a setting to only emit charater entities in the writer would be nice
			# FIXME: several &nbsp; are emitted, and they are explicitly forbidden
			# in the JEP
			# &nbsp; ==  u"\u00a0"
			self.pub.writer.translator_class.attribution_formats['dash'] = (
				u'\u2014', '')
			self.pub.process_programmatic_settings(settings_spec,
				settings_overrides,
				config_section)


		def create_xhtml(self, text, destination=None, destination_path=None,
				enable_exit_status=None):
			"""
			Create xhtml for a fragment of IM dialog. We can use the source_name
			to store info about the message
			"""
			self.pub.set_source(text, None)
			self.pub.set_destination(destination, destination_path)
			output = self.pub.publish(enable_exit_status=enable_exit_status)
			# kludge until we can get docutils to stop generating (rare) &nbsp;
			# entities
			return u'\u00a0'.join(self.pub.writer.parts['fragment'].strip().split(
				'&nbsp;'))

	Generator = HTMLGenerator()

	def create_xhtml(text):
		return Generator.create_xhtml(text)


if __name__ == '__main__':
	print "test 1\n", Generator.create_xhtml("""
test::

>>> print 1
1

*I* like it. It is for :JEP:`71`

this `` should    trigger`` should trigger the &nbsp; problem.

""")
	print "test 2\n", Generator.create_xhtml("""
*test1

test2_
""")
	print "test 3\n", Generator.create_xhtml(""":ticket:`316` implements :xep:`71`""")

# vim: se ts=3:
