# -*- coding:utf-8 -*-
## c14n.py
##
## Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
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

"""
XML canonicalisation methods (for XEP-0116)
"""

from simplexml import ustr

def c14n(node, is_buggy):
    s = "<" + node.name
    if node.namespace:
        if not node.parent or node.parent.namespace != node.namespace:
            s = s + ' xmlns="%s"' % node.namespace

    sorted_attrs = sorted(node.attrs.keys())
    for key in sorted_attrs:
        if not is_buggy and key == 'xmlns':
            continue
        val = ustr(node.attrs[key])
        # like XMLescape() but with whitespace and without &gt;
        s = s + ' %s="%s"' % ( key, normalise_attr(val) )
    s = s + ">"
    cnt = 0
    if node.kids:
        for a in node.kids:
            if (len(node.data)-1) >= cnt:
                s = s + normalise_text(node.data[cnt])
            s = s + c14n(a, is_buggy)
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
