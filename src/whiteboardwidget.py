import gtk
import goocanvas
from common.xmpp import Node
from common import gajim

#for sxe session
from random import choice
import string
import urllib

''' 
A whiteboard widget made for Gajim. Only has basic line tool that draws
SVG Paths. 
- Ummu
'''

class Whiteboard(goocanvas.Canvas):
	def __init__(self, account, contact):
		goocanvas.Canvas.__init__(self)
		self.set_flags(gtk.CAN_FOCUS)
		self.root = self.get_root_item()
		session = SXESession(account, contact)

		# Events
		self.connect('button-press-event', self.button_press_event)
		self.connect('button-release-event', self.button_release_event)
		self.connect('motion-notify-event', self.motion_notify_event)
		self.connect('key-press-event', self.key_press_event)

		# Config
		self.draw_tool = 'brush'
		self.line_width = 10

		# SVG Storage
		# TODO: get height width info
		self.image = SVGObject(self.root, session)

		# Temporary Variables for items
		self.item_temp = None
		self.item_temp_coords = (0,0)
		self.item_data = None


	def button_press_event(self, widget, event):
		x = event.x
		y = event.y
		state = event.state
		self.item_temp_coords = (x,y)

		if self.draw_tool == 'brush':
			self.item_data = 'M %s,%s ' % (x, y)
			self.item_temp = goocanvas.Ellipse(parent=self.root,
				center_x=x,
				center_y=y,
				radius_x=1,
				radius_y=1,
				stroke_color='black',
				fill_color='black',
				line_width=self.line_width)
			self.item_data = self.item_data + 'L '

	def motion_notify_event(self, widget, event):
		x = event.x
		y = event.y
		state = event.state
		if self.item_temp is not None:
			self.item_temp.remove()
			
		if self.draw_tool == 'brush':
			if self.item_data is not None:
				self.item_data = self.item_data + '%s,%s ' % (x, y)
				self.item_temp = goocanvas.Path(parent=self.root,
					data=self.item_data, line_width=self.line_width)

	def button_release_event(self, widget, event):
		x = event.x
		y = event.y
		state = event.state
		
		if self.draw_tool == 'brush':
			self.item_data = self.item_data + '%s,%s' % (x, y)
			if x == self.item_temp_coords[0] and y == self.item_temp_coords[1]:
				goocanvas.Ellipse(parent=self.root,
					center_x=x,
					center_y=y,
					radius_x=1,
					radius_y=1,
					stroke_color='black',
					fill_color='black',
					line_width=self.line_width)
			self.image.add_path(self.item_data, self.line_width)

		self.item_data = None
		if self.item_temp is not None:
			self.item_temp.remove()
			self.item_temp = None
	
	# TODO: get keypresses working
	def key_press_event(self, widget, event):
		print 'test'
		if event.keyval == 'p':
			self.image.print_xml()

class SVGObject():
	''' A class to store the svg document and make changes to it.'''

	def __init__(self, root, session, height=300, width=300):
		# Will be {ID: {type:'element', data:[node, goocanvas]}, ID2: {}} instance
		self.items = {}
		self.root = root
		
		# sxe session
		self.session = session
		
		# initialize svg document
		self.svg = Node(node='<svg/>')
		self.svg.setAttr('version', '1.1')
		self.svg.setAttr('height', str(height))
		self.svg.setAttr('width', str(width))
		self.svg.setAttr('xmlns', 'http://www.w3.org/2000/svg')
		# TODO: make this settable		
		self.g = self.svg.addChild(name='<g/>')
		self.g.setAttr('fill', 'none')
		self.g.setAttr('stroke-linecap', 'round')

	def add_path(self, data, line_width):
		''' adds the path to the items listing, both minidom node and goocanvas
		object in a tuple '''

		goocanvas_obj = goocanvas.Path(parent=self.root, data=data,
			line_width=line_width)

		node = self.g.addChild(name='path')
		node.setAttr('d', data)
		node.setAttr('stroke-width', str(line_width))
		node.setAttr('stroke', 'black')
		self.g.addChild(node=node)

		self.items[self.session.rid()] = {'type':'element', data:[node, goocanvas_obj]}
		self.items[self.session.rid()] = {'type':'attr', 'data':'d', 'parent':node}
		self.items[self.session.rid()] = {'type':'attr', 'data':'d', 'parent':node}
		self.items[self.session.rid()] = {'type':'attr', 'data':'d', 'parent':node}
		
	def print_xml(self):
		file = open('whiteboardtest.svg','w')
		file.writelines(str(self.svg, True))
		file.close()

class SXESession():
	''' stores all the sxe session methods and info'''
	def __init__(self, account, contact, sid=None):
		self.account = account
		self.contact = contact
		self.last_rid = 0
		
		# generate unique session ID
		if sid is None:
			chars = string.letters + string.digits
			self.sid = ''.join([choice(chars) for i in range(7)])
		else:
			self.sid = sid

	def rid(self):
		rid = str(self.last_rid)
		self.last_rid += 1
		return rid

	def connect(self):
		# connect to the message
		gajim.connections[self.account].send_whiteboard_connect(
			self.contact.get_full_jid(), self.sid)
	
	def encode(self, xml):
		# encodes it sendable string
		return 'data:text/xml,' + urllib.quote(xml)
