import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from gi.repository import Gtk, Gdk

from gajim.common import app
from gajim.common import configpaths
configpaths.init()
from gajim.common import caps_cache

from gajim.gtk.util import get_cursor
from gajim.conversation_textview import ConversationTextview
from gajim.gui_interface import Interface

caps_cache.capscache = MagicMock()
app.plugin_manager = MagicMock()
app.logger = MagicMock()
app.interface = Interface()

change_cursor = None
htmlview = ConversationTextview(None)


def on_textview_motion_notify_event(widget, event):
    """
    Change the cursor to a hand when we are over a mail or an url
    """
    global change_cursor
    w = htmlview.tv.get_window(Gtk.TextWindowType.TEXT)
    device = w.get_display().get_device_manager().get_client_pointer()
    pointer = w.get_device_position(device)
    x = pointer[1]
    y = pointer[2]
    tags = htmlview.tv.get_iter_at_location(x, y)[1].get_tags()
    if change_cursor:
        w.set_cursor(get_cursor('XTERM'))
        change_cursor = None
    for tag in tags:
        try:
            if tag.is_anchor:
                w.set_cursor(get_cursor('HAND2'))
                change_cursor = tag
        except Exception:
            pass

htmlview.tv.connect('motion_notify_event', on_textview_motion_notify_event)

def handler(texttag, widget, event, iter_, kind):
    if event.type == Gdk.EventType.BUTTON_PRESS:
        pass


htmlview.print_real_text(None, xhtml='<div>'
'<span style="color: red; text-decoration:underline">Hello</span><br/>\n'
  '  <img src="http://images.slashdot.org/topics/topicsoftware.gif"/><br/>\n'
'<span style="font-size: 500%; font-family: serif">World</span>\n'
  '</div>\n')
htmlview.print_real_text(None, xhtml='<hr />')
htmlview.print_real_text(None, xhtml='''
<body xmlns='http://www.w3.org/1999/xhtml'>
 <p xmlns='http://www.w3.org/1999/xhtml'>a:b
   <a href='http://google.com/' xmlns='http://www.w3.org/1999/xhtml'>Google
   </a>
 </p><br/>
</body>''')
htmlview.print_real_text(None, xhtml='''
 <body xmlns='http://www.w3.org/1999/xhtml'>
  <p style='font-size:large'>
        <span style='font-style: italic'>O
        <span style='font-size:larger'>M</span>G</span>,
        I&apos;m <span style='color:green'>green</span>
        with <span style='font-weight: bold'>envy</span>!
  </p>
 </body>
        ''')
htmlview.print_real_text(None, xhtml='<hr />')
htmlview.print_real_text(None, xhtml='''
<body xmlns='http://www.w3.org/1999/xhtml'>
        http://test.com/  testing links autolinkifying
</body>
        ''')
htmlview.print_real_text(None, xhtml='<hr />')
htmlview.print_real_text(None, xhtml='''
<body xmlns='http://www.w3.org/1999/xhtml'>
  <p>As Emerson said in his essay <span style='
    font-style: italic; background-color:cyan'>Self-Reliance</span>:</p>
  <p style='margin-left: 5px; margin-right: 2%'>
        &quot;A foolish consistency is the hobgoblin of little minds.&quot;
  </p>
</body>
        ''')
htmlview.print_real_text(None, xhtml='<hr />')
htmlview.print_real_text(None, xhtml='''
<body xmlns='http://www.w3.org/1999/xhtml'>
  <p style='text-align:center'>
    Hey, are you licensed to <a href='http://www.jabber.org/'>Jabber</a>?
  </p>
  <p style='text-align:right'>
    <img src='http://www.xmpp.org/images/psa-license.jpg'
    alt='A License to Jabber' width='50%' height='50%'/>
  </p>
</body>
        ''')
htmlview.print_real_text(None, xhtml='<hr />')
htmlview.print_real_text(None, xhtml='''
<body xmlns='http://www.w3.org/1999/xhtml'>
  <ul style='background-color:rgb(120,140,100)'>
   <li> One </li>
   <li> Two </li>
   <li> Three </li>
  </ul><hr /><pre style="background-color:rgb(120,120,120)">def fac(n):
def faciter(n,acc):
if n==0: return acc
return faciter(n-1, acc*n)
if n&lt;0: raise ValueError('Must be non-negative')
return faciter(n,1)</pre>
</body>
        ''')
htmlview.print_real_text(None, xhtml='<hr />')
htmlview.print_real_text(None, xhtml='''
<body xmlns='http://www.w3.org/1999/xhtml'>
 <ol style='background-color:rgb(120,140,100)'>
   <li> One </li>
   <li> Two is nested: <ul style='background-color:rgb(200,200,100)'>
                 <li> One </li>
                 <li style='font-size:50%'> Two </li>
                 <li style='font-size:200%'> Three </li>
                 <li style='font-size:9999pt'> Four </li>
                </ul></li>
   <li> Three </li></ol>
</body>
        ''')
htmlview.print_real_text(None, xhtml='<hr />')
htmlview.print_real_text(None, xhtml='''
<body xmlns='http://www.w3.org/1999/xhtml'>
<p>
  <strong>
    <a href='xmpp:example@example.org'>xmpp link</a>
  </strong>: </p>
<div xmlns='http://www.w3.org/1999/xhtml'>
  <cite style='margin: 7px;' title='xmpp:examples@example.org'>
    <p>
      <strong>examples@example.org wrote:</strong>
    </p>
    <p>this cite - bla bla bla, smile- :-)  …</p>
  </cite>
  <div>
    <p>some text</p>
  </div>
</div>
<p/>
<p>#232/1</p>
</body>
''')
htmlview.print_real_text(None, xhtml='<hr />')
htmlview.print_real_text(None, xhtml='''
<body xmlns='http://www.w3.org/1999/xhtml'>
<br/>
<img src='data:image/png;base64,R0lGODdhMAAwAPAAAAAAAP///ywAAAAAMAAw\
AAAC8IyPqcvt3wCcDkiLc7C0qwyGHhSWpjQu5yqmCYsapyuvUUlvONmOZtfzgFz\
ByTB10QgxOR0TqBQejhRNzOfkVJ+5YiUqrXF5Y5lKh/DeuNcP5yLWGsEbtLiOSp\
a/TPg7JpJHxyendzWTBfX0cxOnKPjgBzi4diinWGdkF8kjdfnycQZXZeYGejmJl\
ZeGl9i2icVqaNVailT6F5iJ90m6mvuTS4OK05M0vDk0Q4XUtwvKOzrcd3iq9uis\
F81M1OIcR7lEewwcLp7tuNNkM3uNna3F2JQFo97Vriy/Xl4/f1cf5VWzXyym7PH\
hhx4dbgYKAAA7' alt='Larry'/>
</body>
''')
htmlview.tv.show()
sw = Gtk.ScrolledWindow()
sw.set_property('hscrollbar-policy', Gtk.PolicyType.AUTOMATIC)
sw.set_property('vscrollbar-policy', Gtk.PolicyType.AUTOMATIC)
sw.set_property('border-width', 0)
sw.add(htmlview.tv)
sw.show()
frame = Gtk.Frame()
frame.set_shadow_type(Gtk.ShadowType.IN)
frame.show()
frame.add(sw)
win = Gtk.Window()
win.add(frame)
win.set_default_size(400, 300)
win.show_all()
win.connect('destroy', lambda win: Gtk.main_quit())
Gtk.main()
