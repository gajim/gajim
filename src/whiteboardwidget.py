import gtk
import goocanvas
from xml.dom.minidom import Document

""" 
A whiteboard widget made for Gajim. Only has basic line tool that draws
SVG Paths. 
- Ummu
"""

class Whiteboard(goocanvas.Canvas):
    def __init__(self):
        goocanvas.Canvas.__init__(self)
        self.set_flags(gtk.CAN_FOCUS)
        self.root = self.get_root_item()
        
        # Events
        self.connect("button-press-event", self.button_press_event)
        self.connect("button-release-event", self.button_release_event)
        self.connect("motion-notify-event", self.motion_notify_event)
        self.connect("key-press-event", self.key_press_event)
        
        # Config
        self.draw_tool = 'brush'
        self.line_width = 3
        
        # SVG Storage
        #TODO: get height width info
        self.image = SVGObject(self.root)
        
        # Temporary Variables for items
        self.item_temp = None
        self.item_data = None
        

        
    def button_press_event(self, widget, event):
        x = event.x
        y = event.y
        state = event.state
        
        if self.draw_tool == 'brush':
            self.item_data = 'M %s,%s L ' % (x, y)
            self.item_temp = goocanvas.Path(parent = self.root,
                                            data = self.item_data + 'z',
                                            line_width = self.line_width)
            self.request_update()
        
    def motion_notify_event(self, widget, event):
        x = event.x
        y = event.y
        state = event.state
        if self.item_temp is not None:
            self.item_temp.remove()
            
        if self.draw_tool == 'brush':
            if self.item_data is not None:
                self.item_data = self.item_data + '%s,%s ' % (x, y)
                self.item_temp = goocanvas.Path(parent = self.root,
                                                data = self.item_data,
                                                line_width = self.line_width)
    
    def button_release_event(self, widget, event):
        x = event.x
        y = event.y
        state = event.state
        
        if self.draw_tool == 'brush':
            self.item_data = self.item_data + '%s,%s' % (x, y)
            self.image.add_path(self.item_data, self.line_width)
                    
        self.item_data = None
        if self.item_temp is not None:
            self.item_temp.remove()
            self.item_temp = None
            
    def key_press_event(self, widget, event):
        print 'test'
        if event.keyval == 'p':
            self.image.print_xml()
            
class SVGObject():
    ''' A class to store the svg document and make changes to it.
    Stores items in a tuple that's (minidom node, goocanvas object).'''
    
    def __init__(self, root, height = 1000, width = 1000):
        self.items = []
        self.root = root
        
        # initialize svg document
        self.doc = Document()
        self.svg = self.doc.createElement('svg')
        self.svg.setAttribute('version', '1.1')
        self.svg.setAttribute('height', str(height))
        self.svg.setAttribute('width', str(width))
        self.svg.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
        self.doc.appendChild(self.svg)
        #TODO: make this settable        
        self.g = self.doc.createElement('g')
        self.g.setAttribute('fill', 'none')
        self.g.setAttribute('stroke-linecap', 'round')
        self.svg.appendChild(self.g)
        
    def add_path(self, data, line_width):
        ''' adds the path to the items listing, both minidom node and goocanvas
        object in a tuple '''
        
        goocanvas_obj = self.items.append(goocanvas.Path(parent = self.root,
                                    data = data,
                                    line_width = line_width))
        
        minidom_obj = self.doc.createElement('path')
        minidom_obj.setAttribute('d', data)
        minidom_obj.setAttribute('stroke-width', str(line_width))
        minidom_obj.setAttribute('stroke', 'black')
        self.g.appendChild(minidom_obj)
        
        self.items.append((minidom_obj, goocanvas_obj))
        self.print_xml()
        
    def print_xml(self):
        file = open('whiteboardtest.svg','w')
        file.writelines(self.doc.toprettyxml('  '))
        file.close()

        
def main():
    window = gtk.Window()
    window.set_events(gtk.gdk.EXPOSURE_MASK
                        | gtk.gdk.LEAVE_NOTIFY_MASK
                        | gtk.gdk.BUTTON_PRESS_MASK
                        | gtk.gdk.POINTER_MOTION_MASK
                        | gtk.gdk.KEY_PRESS_MASK)
    board = Whiteboard()
    window.add(board)
    window.connect("destroy", gtk.main_quit)
    window.show_all()

    gtk.main()
    
if __name__ == "__main__":
    main()
