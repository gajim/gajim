from simplexml import ustr

# XML canonicalisation methods (for XEP-0116)
def c14n(node):
	s = "<" + node.name
	if node.namespace:
		if not node.parent or node.parent.namespace != node.namespace:
			s = s + ' xmlns="%s"' % node.namespace

	sorted_attrs = sorted(node.attrs.keys())
	for key in sorted_attrs:
		val = ustr(node.attrs[key])
		# like XMLescape() but with whitespace and without &gt;
		s = s + ' %s="%s"' % ( key, normalise_attr(val) )
	s = s + ">"
	cnt = 0
	if node.kids:
		for a in node.kids:
			if (len(node.data)-1) >= cnt:
				s = s + normalise_text(node.data[cnt])
			s = s + c14n(a)
			cnt=cnt+1
	if (len(node.data)-1) >= cnt: s = s + normalise_text(node.data[cnt])
	if not node.kids and s.endswith('>'):
		s=s[:-1]+' />'
	else:
		s = s + "</" + node.name + ">"
	return s.encode('utf-8')

def normalise_attr(val):
	return val.replace('&', '&amp;').replace('<', '&lt;').replace('"', '&quot;').replace('\t', '&#x9;').replace('\n', '&#xA;').replace('\r', '&#xD;')

def normalise_text(val):
	return val.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\r', '&#xD;')


# vim: se ts=3: