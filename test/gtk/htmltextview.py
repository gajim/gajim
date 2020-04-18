from unittest.mock import MagicMock

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from gajim.common import app
from gajim.common import configpaths
configpaths.init()
from gajim.common.helpers import AdditionalDataDict

from gajim.conversation_textview import ConversationTextview
from gajim.gui_interface import Interface

app.plugin_manager = MagicMock()
app.logger = MagicMock()
app.cert_store = MagicMock()
app.interface = Interface()


XHTML = [
    '''
    <div>
        <span style="color: red; text-decoration:underline">Hello</span>
        <br/>\n
        <img src="http://images.slashdot.org/topics/topicsoftware.gif"/>
        <br/>\n
        <span style="font-size: 500%; font-family: serif">World</span>\n
    </div>
    ''',

    '''
    <hr />
    ''',

    '''
    <body xmlns='http://www.w3.org/1999/xhtml'>
        <p xmlns='http://www.w3.org/1999/xhtml'>Look here 
            <a href='http://google.com/'>Google</a>
        </p>
        <br/>
    </body>
    ''',

    '''
    <hr />
    ''',

    '''
    <body xmlns='http://www.w3.org/1999/xhtml'>
        <p style='font-size:large'>
            <span style='font-style: italic'>O
            <span style='font-size:larger'>M</span>G
            </span>, I&apos;m <span style='color:green'>green</span> with 
            <span style='font-weight: bold'>envy</span>!
        </p>
    </body>
    ''',

    '''
    <hr />
    ''',

    '''
    <body xmlns='http://www.w3.org/1999/xhtml'>
        <p>
            As Emerson said in his essay 
            <span style='font-style: italic; background-color:cyan'>
            Self-Reliance</span>:
        </p>
        <p style='margin-left: 5px; margin-right: 2%'>
            &quot;A foolish consistency is the hobgoblin of little minds.&quot;
        </p>
    </body>
    ''',

    '''
    <hr />
    ''',

    '''
    <body xmlns='http://www.w3.org/1999/xhtml'>
        <p style='text-align:center'>
            Hey, are you licensed to <a href='http://www.jabber.org/'>Jabber</a>?
        </p>
        <p style='text-align:right'>
            <img src='http://www.xmpp.org/images/psa-license.jpg'
                alt='A License to Jabber' width='50%' height='50%'/>
        </p>
    </body>
    ''',

    '''
    <hr />
    ''',

    '''
    <body xmlns='http://www.w3.org/1999/xhtml'>
        <ul style='background-color:rgb(120,140,100)'>
            <li> One </li>
            <li> Two </li>
            <li> Three </li>
        </ul>
        <hr />
        <pre style="background-color:rgb(120,120,120)">def fac(n):
        def faciter(n,acc):
        if n==0: return acc
        return faciter(n-1, acc*n)
        if n&lt;0: raise ValueError('Must be non-negative')
        return faciter(n,1)</pre>
    </body>
    ''',

    '''
    <hr />
    ''',

    '''
    <body xmlns='http://www.w3.org/1999/xhtml'>
        <ol style='background-color:rgb(120,140,100)'>
            <li> One </li>
            <li>
                Two is nested: 
                <ul style='background-color:rgb(200,200,100)'>
                    <li> One </li>
                    <li style='font-size:50%'> Two </li>
                    <li style='font-size:200%'> Three </li>
                    <li style='font-size:9999pt'> Four </li>
                </ul>
            </li>
            <li> Three </li>
        </ol>
    </body>
    ''',

    '''
    <hr />
    ''',

    '''
    <body xmlns='http://www.w3.org/1999/xhtml'>
        <p>
            <strong>
            <a href='xmpp:example@example.org'>xmpp link</a>
            </strong>: 
        </p>
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
    ''',

    '''
    <hr />
    ''',

    '''
    <body xmlns='http://www.w3.org/1999/xhtml'>
        <img src='data:image/png;base64,R0lGODdhMAAwAPAAAAAAAP///ywAAAAAMAAw\
            AAAC8IyPqcvt3wCcDkiLc7C0qwyGHhSWpjQu5yqmCYsapyuvUUlvONmOZtfzgFz\
            ByTB10QgxOR0TqBQejhRNzOfkVJ+5YiUqrXF5Y5lKh/DeuNcP5yLWGsEbtLiOSp\
            a/TPg7JpJHxyendzWTBfX0cxOnKPjgBzi4diinWGdkF8kjdfnycQZXZeYGejmJl\
            ZeGl9i2icVqaNVailT6F5iJ90m6mvuTS4OK05M0vDk0Q4XUtwvKOzrcd3iq9uis\
            F81M1OIcR7lEewwcLp7tuNNkM3uNna3F2JQFo97Vriy/Xl4/f1cf5VWzXyym7PH\
            hhx4dbgYKAAA7' alt='Larry'/>
    </body>
    ''',

]


class TextviewWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title="Textview Test")
        self.set_default_size(600, 600)

        self._textview = ConversationTextview(None)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(self._textview.tv)
        self.add(scrolled)
        self.show()
        self._print_xhtml()

    def _print_xhtml(self):
        for xhtml in XHTML:
            additional_data = AdditionalDataDict()
            additional_data.set_value('gajim', 'xhtml', xhtml)
            self._textview.print_real_text(None, additional_data=additional_data)
            self._textview.print_real_text('\n')

win = TextviewWindow()
win.connect("destroy", Gtk.main_quit)
win.show_all()
Gtk.main()
