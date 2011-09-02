## plugins/whiteboard/whiteboard_widget.py
##
## Copyright (C) 2009 Jeff Ling <jeff.ummu AT gmail.com>
## Copyright (C) 2010 Yann Leboulanger <asterix AT lagaule.org>
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

import gtk
import gtkgui_helpers
try:
    import goocanvas
    HAS_GOOCANVAS = True
except:
    HAS_GOOCANVAS = False
from common.xmpp import Node
from common import gajim
from dialogs import FileChooserDialog

'''
A whiteboard widget made for Gajim.
- Ummu
'''

class Whiteboard(object):
    def __init__(self, account, contact, session, plugin):
        self.plugin = plugin
        file_path = plugin.local_file_path('whiteboard_widget.ui')
        xml = gtk.Builder()
        xml.set_translation_domain('gajim_plugins')
        xml.add_from_file(file_path)
        self.hbox = xml.get_object('whiteboard_hbox')
        self.canevas = goocanvas.Canvas()
        self.hbox.pack_start(self.canevas)
        self.hbox.reorder_child(self.canevas, 0)
        self.canevas.set_flags(gtk.CAN_FOCUS)
        self.fg_color_select_button = xml.get_object('fg_color_button')
        self.root = self.canevas.get_root_item()
        self.tool_buttons = []
        for tool in ('brush', 'oval', 'line', 'delete'):
            self.tool_buttons.append(xml.get_object(tool + '_button'))
        xml.get_object('brush_button').set_active(True)

        # Events
        self.canevas.connect('button-press-event', self.button_press_event)
        self.canevas.connect('button-release-event', self.button_release_event)
        self.canevas.connect('motion-notify-event', self.motion_notify_event)
        self.canevas.connect('item-created', self.item_created)

        # Config
        self.line_width = 2
        xml.get_object('size_scale').set_value(2)
        self.color = str(self.fg_color_select_button.get_color())

        # SVG Storage
        self.image = SVGObject(self.root, session)

        xml.connect_signals(self)

        # Temporary Variables for items
        self.item_temp = None
        self.item_temp_coords = (0, 0)
        self.item_data = None

        # Will be {ID: {type:'element', data:[node, goocanvas]}, ID2: {}} instance
        self.recieving = {}

    def on_tool_button_toggled(self, widget):
        for btn in self.tool_buttons:
            if btn == widget:
                continue
            btn.set_active(False)

    def on_brush_button_toggled(self, widget):
        if widget.get_active():
            self.image.draw_tool = 'brush'
            self.on_tool_button_toggled(widget)

    def on_oval_button_toggled(self, widget):
        if widget.get_active():
            self.image.draw_tool = 'oval'
            self.on_tool_button_toggled(widget)

    def on_line_button_toggled(self, widget):
        if widget.get_active():
            self.image.draw_tool = 'line'
            self.on_tool_button_toggled(widget)

    def on_delete_button_toggled(self, widget):
        if widget.get_active():
            self.image.draw_tool = 'delete'
            self.on_tool_button_toggled(widget)

    def on_clear_button_clicked(self, widget):
        self.image.clear_canvas()

    def on_export_button_clicked(self, widget):
        SvgChooserDialog(self.image.export_svg)

    def on_fg_color_button_color_set(self, widget):
        self.color = str(self.fg_color_select_button.get_color())

    def item_created(self, canvas, item, model):
        print 'item created'
        item.connect('button-press-event', self.item_button_press_events)

    def item_button_press_events(self, item, target_item, event):
        if self.image.draw_tool == 'delete':
            self.image.del_item(item)

    def on_size_scale_format_value(self, widget):
        self.line_width = int(widget.get_value())

    def button_press_event(self, widget, event):
        x = event.x
        y = event.y
        state = event.state
        self.item_temp_coords = (x, y)

        if self.image.draw_tool == 'brush':
            self.item_temp = goocanvas.Ellipse(parent=self.root,
                    center_x=x,
                    center_y=y,
                    radius_x=1,
                    radius_y=1,
                    stroke_color=self.color,
                    fill_color=self.color,
                    line_width=self.line_width)
            self.item_data = 'M %s,%s L ' % (x, y)

        elif self.image.draw_tool == 'oval':
            self.item_data = True

        if self.image.draw_tool == 'line':
            self.item_data = 'M %s,%s L' % (x, y)

    def motion_notify_event(self, widget, event):
        x = event.x
        y = event.y
        state = event.state
        if self.item_temp is not None:
            self.item_temp.remove()

        if self.item_data is not None:
            if self.image.draw_tool == 'brush':
                self.item_data = self.item_data + '%s,%s ' % (x, y)
                self.item_temp = goocanvas.Path(parent=self.root,
                        data=self.item_data, line_width=self.line_width,
                        stroke_color=self.color)
            elif self.image.draw_tool == 'oval':
                self.item_temp = goocanvas.Ellipse(parent=self.root,
                        center_x=self.item_temp_coords[0] + (x - self.item_temp_coords[0]) / 2,
                        center_y=self.item_temp_coords[1] + (y - self.item_temp_coords[1]) / 2,
                        radius_x=abs(x - self.item_temp_coords[0]) / 2,
                        radius_y=abs(y - self.item_temp_coords[1]) / 2,
                        stroke_color=self.color,
                        line_width=self.line_width)
            elif self.image.draw_tool == 'line':
                self.item_data = 'M %s,%s L' % self.item_temp_coords
                self.item_data = self.item_data + ' %s,%s' % (x, y)
                self.item_temp = goocanvas.Path(parent=self.root,
                        data=self.item_data, line_width=self.line_width,
                        stroke_color=self.color)

    def button_release_event(self, widget, event):
        x = event.x
        y = event.y
        state = event.state

        if self.image.draw_tool == 'brush':
            self.item_data = self.item_data + '%s,%s' % (x, y)
            if x == self.item_temp_coords[0] and y == self.item_temp_coords[1]:
                goocanvas.Ellipse(parent=self.root,
                        center_x=x,
                        center_y=y,
                        radius_x=1,
                        radius_y=1,
                        stroke_color=self.color,
                        fill_color=self.color,
                        line_width=self.line_width)
            self.image.add_path(self.item_data, self.line_width, self.color)

        if self.image.draw_tool == 'oval':
            cx = self.item_temp_coords[0] + (x - self.item_temp_coords[0]) / 2
            cy = self.item_temp_coords[1] + (y - self.item_temp_coords[1]) / 2
            rx = abs(x - self.item_temp_coords[0]) / 2
            ry = abs(y - self.item_temp_coords[1]) / 2
            self.image.add_ellipse(cx, cy, rx, ry, self.line_width, self.color)

        if self.image.draw_tool == 'line':
            self.item_data = 'M %s,%s L' % self.item_temp_coords
            self.item_data = self.item_data + ' %s,%s' % (x, y)
            if x == self.item_temp_coords[0] and y == self.item_temp_coords[1]:
                goocanvas.Ellipse(parent=self.root,
                        center_x=x,
                        center_y=y,
                        radius_x=1,
                        radius_y=1,
                        stroke_color='black',
                        fill_color='black',
                        line_width=self.line_width)
            self.image.add_path(self.item_data, self.line_width, self.color)

        if self.image.draw_tool == 'delete':
            pass

        self.item_data = None
        if self.item_temp is not None:
            self.item_temp.remove()
            self.item_temp = None

    def recieve_element(self, element):
        node = self.image.g.addChild(name=element.getAttr('name'))
        self.image.g.addChild(node=node)
        self.recieving[element.getAttr('rid')] = {'type':'element',
                                                  'data':[node],
                                                  'children':[]}

    def recieve_attr(self, element):
        node = self.recieving[element.getAttr('parent')]['data'][0]
        node.setAttr(element.getAttr('name'), element.getAttr('chdata'))

        self.recieving[element.getAttr('rid')] = {'type':'attr',
                                                  'data':element.getAttr('name'),
                                                  'parent':node}
        self.recieving[element.getAttr('parent')]['children'].append(element.getAttr('rid'))

    def apply_new(self):
        for x in self.recieving.keys():
            if self.recieving[x]['type'] == 'element':
                self.image.add_recieved(x, self.recieving)

        self.recieving = {}

class SvgChooserDialog(FileChooserDialog):
    def __init__(self, on_response_ok=None, on_response_cancel=None):
        '''
        Choose in which SVG file to store the image
        '''
        def on_ok(widget, callback):
            '''
            check if file exists and call callback
            '''
            path_to_file = self.get_filename()
            path_to_file = gtkgui_helpers.decode_filechooser_file_paths(
                (path_to_file,))[0]
            widget.destroy()
            callback(path_to_file)

        FileChooserDialog.__init__(self,
            title_text=_('Save Image as...'),
            action=gtk.FILE_CHOOSER_ACTION_SAVE,
            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN,
                gtk.RESPONSE_OK),
            current_folder='',
            default_response=gtk.RESPONSE_OK,
            on_response_ok=(on_ok, on_response_ok),
            on_response_cancel=on_response_cancel)

        filter_ = gtk.FileFilter()
        filter_.set_name(_('All files'))
        filter_.add_pattern('*')
        self.add_filter(filter_)

        filter_ = gtk.FileFilter()
        filter_.set_name(_('SVG Files'))
        filter_.add_pattern('*.svg')
        self.add_filter(filter_)
        self.set_filter(filter_)


class SVGObject():
    ''' A class to store the svg document and make changes to it.'''

    def __init__(self, root, session, height=300, width=300):
        # Will be {ID: {type:'element', data:[node, goocanvas]}, ID2: {}} instance
        self.items = {}
        self.root = root
        self.draw_tool = 'brush'

        # sxe session
        self.session = session

        # initialize svg document
        self.svg = Node(node='<svg/>')
        self.svg.setAttr('version', '1.1')
        self.svg.setAttr('height', str(height))
        self.svg.setAttr('width', str(width))
        self.svg.setAttr('xmlns', 'http://www.w3.org/2000/svg')
        # TODO: make this settable
        self.g = self.svg.addChild(name='g')
        self.g.setAttr('fill', 'none')
        self.g.setAttr('stroke-linecap', 'round')

    def add_path(self, data, line_width, color):
        ''' adds the path to the items listing, both minidom node and goocanvas
        object in a tuple '''

        goocanvas_obj = goocanvas.Path(parent=self.root, data=data,
                line_width=line_width, stroke_color=color)
        goocanvas_obj.connect('button-press-event', self.item_button_press_events)

        node = self.g.addChild(name='path')
        node.setAttr('d', data)
        node.setAttr('stroke-width', str(line_width))
        node.setAttr('stroke', color)
        self.g.addChild(node=node)

        rids = self.session.generate_rids(4)
        self.items[rids[0]] = {'type':'element', 'data':[node, goocanvas_obj], 'children':rids[1:]}
        self.items[rids[1]] = {'type':'attr', 'data':'d', 'parent':node}
        self.items[rids[2]] = {'type':'attr', 'data':'stroke-width', 'parent':node}
        self.items[rids[3]] = {'type':'attr', 'data':'stroke', 'parent':node}

        self.session.send_items(self.items, rids)

    def add_recieved(self, parent_rid, new_items):
        ''' adds the path to the items listing, both minidom node and goocanvas
        object in a tuple '''
        node = new_items[parent_rid]['data'][0]

        self.items[parent_rid] = new_items[parent_rid]
        for x in new_items[parent_rid]['children']:
            self.items[x] = new_items[x]

        if node.getName() == 'path':
            goocanvas_obj = goocanvas.Path(parent=self.root,
                            data=node.getAttr('d'),
                            line_width=int(node.getAttr('stroke-width')),
                            stroke_color=node.getAttr('stroke'))

        if node.getName() == 'ellipse':
            goocanvas_obj = goocanvas.Ellipse(parent=self.root,
                            center_x=float(node.getAttr('cx')),
                            center_y=float(node.getAttr('cy')),
                            radius_x=float(node.getAttr('rx')),
                            radius_y=float(node.getAttr('ry')),
                            stroke_color=node.getAttr('stroke'),
                            line_width=float(node.getAttr('stroke-width')))

        self.items[parent_rid]['data'].append(goocanvas_obj)
        goocanvas_obj.connect('button-press-event', self.item_button_press_events)

    def add_ellipse(self, cx, cy, rx, ry, line_width, stroke_color):
        ''' adds the ellipse to the items listing, both minidom node and goocanvas
        object in a tuple '''

        goocanvas_obj = goocanvas.Ellipse(parent=self.root,
                                center_x=cx,
                                center_y=cy,
                                radius_x=rx,
                                radius_y=ry,
                                stroke_color=stroke_color,
                                line_width=line_width)
        goocanvas_obj.connect('button-press-event', self.item_button_press_events)

        node = self.g.addChild(name='ellipse')
        node.setAttr('cx', str(cx))
        node.setAttr('cy', str(cy))
        node.setAttr('rx', str(rx))
        node.setAttr('ry', str(ry))
        node.setAttr('stroke-width', str(line_width))
        node.setAttr('stroke', stroke_color)
        self.g.addChild(node=node)

        rids = self.session.generate_rids(7)
        self.items[rids[0]] = {'type':'element', 'data':[node, goocanvas_obj], 'children':rids[1:]}
        self.items[rids[1]] = {'type':'attr', 'data':'cx', 'parent':node}
        self.items[rids[2]] = {'type':'attr', 'data':'cy', 'parent':node}
        self.items[rids[3]] = {'type':'attr', 'data':'rx', 'parent':node}
        self.items[rids[4]] = {'type':'attr', 'data':'ry', 'parent':node}
        self.items[rids[5]] = {'type':'attr', 'data':'stroke-width', 'parent':node}
        self.items[rids[6]] = {'type':'attr', 'data':'stroke', 'parent':node}

        self.session.send_items(self.items, rids)

    def del_item(self, item):
        rids = []
        for x in self.items.keys():
            if self.items[x]['type'] == 'element':
                if self.items[x]['data'][1] == item:
                    for y in self.items[x]['children']:
                        rids.append(y)
                        self.del_rid(y)
                    rids.append(x)
                    self.del_rid(x)
                    break
        self.session.del_item(rids)

    def clear_canvas(self):
        for x in self.items.keys():
            if self.items[x]['type'] == 'element':
                self.del_rid(x)

    def del_rid(self, rid):
        if self.items[rid]['type'] == 'element':
            self.items[rid]['data'][1].remove()
        del self.items[rid]

    def export_svg(self, filename):
        f = open(filename, 'w')
        f.writelines(str(self.svg))
        f.close()

    def item_button_press_events(self, item, target_item, event):
        self.del_item(item)
