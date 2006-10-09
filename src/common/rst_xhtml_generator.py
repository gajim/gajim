##	rst_xhtml_generator.py
##
## Copyright (C) 2006 Yann Le Boulanger <asterix@lagaule.org>
## Copyright (C) 2006 Nikos Kouremenos <kourem@gmail.com>
## Copyright (C) 2006 Santiago Gala
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

try:
	from docutils import io
	from docutils.core import Publisher
	from docutils.parsers.rst import roles
	from docutils import nodes,utils
	from docutils.parsers.rst.roles import set_classes
except:
	def create_xhtml(text):
		return None
else:
	def jep_reference_role(role, rawtext, text, lineno, inliner,
		options={}, content=[]):
		'''Role to make handy references to Jabber Enhancement Proposals (JEP).

	 	Use as :JEP:`71` (or jep, or jep-reference).
		Modeled after the sample in docutils documentation.
		'''

		jep_base_url = 'http://www.jabber.org/jeps/'
		jep_url = 'jep-%04d.html'
		try:
			jepnum = int(text)
			if jepnum <= 0:
				raise ValueError
		except ValueError:
			msg = inliner.reporter.error(
			'JEP number must be a number greater than or equal to 1; '
			'"%s" is invalid.' % text, line=lineno)
			prb = inliner.problematic(rawtext, rawtext, msg)
			return [prb], [msg]
		ref = jep_base_url + jep_url % jepnum
		set_classes(options)
		node = nodes.reference(rawtext, 'JEP ' + utils.unescape(text), refuri=ref,
			**options)
		return [node], []

	roles.register_canonical_role('jep-reference', jep_reference_role)
	from docutils.parsers.rst.languages.en import roles
	roles['jep-reference'] = 'jep-reference'
	roles['jep'] = 'jep-reference'

	class HTMLGenerator:
		'''Really simple HTMLGenerator starting from publish_parts.

		It reuses the docutils.core.Publisher class, which means it is *not*
		threadsafe.
		'''
		def __init__(self,
			settings_spec=None,
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


		def create_xhtml(self, text,
			destination=None,
			destination_path=None,
			enable_exit_status=None):
			''' Create xhtml for a fragment of IM dialog.
			We can use the source_name to store info about
			the message.'''
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
	print Generator.create_xhtml('''
test::

  >>> print 1
  1

*I* like it. It is for :JEP:`71`

this `` should    trigger`` should trigger the &nbsp; problem.

''')
	print Generator.create_xhtml('''
*test1

test2_
''')
