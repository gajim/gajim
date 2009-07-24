import gtk
import gtkgui_helpers
import goocanvas
from common.xmpp import Node
from common import gajim

''' 
A whiteboard widget made for Gajim. Only has basic line tool that draws
SVG Paths. 
- Ummu
'''

class Whiteboard(object):
	def __init__(self, account, contact, session):
		print 'init'
		xml = gtkgui_helpers.get_glade('whiteboard_widget.glade',
			'whiteboard_hbox')
		self.hbox = xml.get_widget('whiteboard_hbox')
		self.canevas = goocanvas.Canvas()
		self.hbox.pack_start(self.canevas)
		self.hbox.reorder_child(self.canevas, 0)
		self.canevas.set_flags(gtk.CAN_FOCUS)
		xml.signal_autoconnect(self)

		self.root = self.canevas.get_root_item()

		# Events
		self.canevas.connect('button-press-event', self.button_press_event)
		self.canevas.connect('button-release-event', self.button_release_event)
		self.canevas.connect('motion-notify-event', self.motion_notify_event)

		# Config
		self.draw_tool = 'oval'
		self.line_width = 2

		# SVG Storage
		# TODO: get height width info
		self.image = SVGObject(self.root, session)

		# Temporary Variables for items
		self.item_temp = None
		self.item_temp_coords = (0,0)
		self.item_data = None

	def on_brush_button_clicked(self, widget):
		self.draw_tool = 'brush'

	def on_oval_button_clicked(self, widget):
		self.draw_tool = 'oval'

	def on_export_button_clicked(self, widget):
		self.image.print_xml()

	def button_press_event(self, widget, event):
		x = event.x
		y = event.y
		state = event.state
		self.item_temp_coords = (x,y)

		if self.draw_tool == 'brush':
			self.item_temp = goocanvas.Ellipse(parent=self.root,
				center_x=x,
				center_y=y,
				radius_x=1,
				radius_y=1,
				stroke_color='black',
				fill_color='black',
				line_width=self.line_width)
			self.item_data = 'M %s,%s L ' % (x, y)
			
		elif self.draw_tool == 'oval':
			self.item_data = True

	def motion_notify_event(self, widget, event):
		x = event.x
		y = event.y
		state = event.state
		if self.item_temp is not None:
			self.item_temp.remove()
			
		if self.item_data is not None:
			if self.draw_tool == 'brush':
				self.item_data = self.item_data + '%s,%s ' % (x, y)
				self.item_temp = goocanvas.Path(parent=self.root,
					data=self.item_data, line_width=self.line_width)
			elif self.draw_tool == 'oval':
				self.item_temp = goocanvas.Ellipse(parent=self.root,
					center_x=self.item_temp_coords[0] + (x - self.item_temp_coords[0]) / 2,
					center_y=self.item_temp_coords[1] + (y - self.item_temp_coords[1]) / 2,
					radius_x=abs(x - self.item_temp_coords[0]) / 2,
					radius_y=abs(y - self.item_temp_coords[1]) / 2,
					stroke_color='black',
					line_width=self.line_width)

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
			
		if self.draw_tool == 'oval':
			cx = self.item_temp_coords[0] + (x - self.item_temp_coords[0]) / 2
			cy = self.item_temp_coords[1] + (y - self.item_temp_coords[1]) / 2
			rx = abs(x - self.item_temp_coords[0]) / 2
			ry = abs(y - self.item_temp_coords[1]) / 2
			self.image.add_ellipse(cx, cy, rx, ry, self.line_width)

		self.item_data = None
		if self.item_temp is not None:
			self.item_temp.remove()
			self.item_temp = None

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
		
		rids = self.session.generate_rids(4)
		self.items[rids[0]] = {'type':'element', 'data':[node, goocanvas_obj]}
		self.items[rids[1]] = {'type':'attr', 'data':'d', 'parent':node}
		self.items[rids[2]] = {'type':'attr', 'data':'stroke-width', 'parent':node}
		self.items[rids[3]] = {'type':'attr', 'data':'stroke', 'parent':node}
		
		self.session.send_items(self.items, rids)
		
	def add_ellipse(self, cx, cy, rx, ry, line_width):
		''' adds the ellipse to the items listing, both minidom node and goocanvas
		object in a tuple '''

		goocanvas_obj = goocanvas.Ellipse(parent=self.root,
					center_x=cx,
					center_y=cy,
					radius_x=rx,
					radius_y=ry,
					stroke_color='black',
					line_width=line_width)

		node = self.g.addChild(name='ellipse')
		node.setAttr('cx', str(cx))
		node.setAttr('cy', str(cy))
		node.setAttr('rx', str(rx))
		node.setAttr('ry', str(ry))
		node.setAttr('stroke-width', str(line_width))
		node.setAttr('stroke', 'black')
		self.g.addChild(node=node)
		
		rids = self.session.generate_rids(7)
		self.items[rids[0]] = {'type':'element', 'data':[node, goocanvas_obj]}
		self.items[rids[1]] = {'type':'attr', 'data':'cx', 'parent':node}
		self.items[rids[2]] = {'type':'attr', 'data':'cy', 'parent':node}
		self.items[rids[3]] = {'type':'attr', 'data':'rx', 'parent':node}
		self.items[rids[4]] = {'type':'attr', 'data':'ry', 'parent':node}
		self.items[rids[5]] = {'type':'attr', 'data':'stroke-width', 'parent':node}
		self.items[rids[6]] = {'type':'attr', 'data':'stroke', 'parent':node}
		
		self.session.send_items(self.items, rids)
		
	def print_xml(self):
		file = open('whiteboardtest.svg','w')
		file.writelines(str(self.svg, True))
		file.close()
