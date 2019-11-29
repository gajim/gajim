import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from gajim.common.const import CSSPriority

from gajim.gtk.assistant import Assistant

from test.gtk import util
util.load_style('gajim.css', CSSPriority.APPLICATION)


class TestAssistant(Assistant):
    def __init__(self):
        Assistant.__init__(self)

        self.add_pages({'start': Start(),
                        'progress': Progress()})

        error = self.add_default_page('error')
        error.set_title('Error')
        error.set_heading('Error Heading')
        error.set_text('This is the error text')

        success = self.add_default_page('success')
        success.set_title('Success')
        success.set_heading('Success Heading')
        success.set_text('This is the success text')

        self.add_button('forward', 'Forward', 'suggested-action')
        self.add_button('close', 'Close', 'destructive-action')
        self.add_button('back', 'Back')

        self.set_button_visible_func(self._visible_func)

        self.connect('button-clicked', self._on_button_clicked)
        self.connect('page-changed', self._on_page_changed)

        self.show_all()

    @staticmethod
    def _visible_func(_assistant, page_name):
        if page_name == 'start':
            return ['forward']

        if page_name == 'progress':
            return ['forward', 'back']

        if page_name == 'success':
            return ['forward', 'back']

        if page_name == 'error':
            return ['back', 'close']
        raise ValueError('page %s unknown' % page_name)

    def _on_button_clicked(self, _assistant, button_name):
        page = self.get_current_page()
        if button_name == 'forward':
            if page == 'start':
                self.show_page('progress', Gtk.StackTransitionType.SLIDE_LEFT)
            elif page == 'progress':
                self.show_page('success', Gtk.StackTransitionType.SLIDE_LEFT)
            elif page == 'success':
                self.show_page('error', Gtk.StackTransitionType.SLIDE_LEFT)
            return

        if button_name == 'back':
            if page == 'progress':
                self.show_page('start')
            if page == 'success':
                self.show_page('progress')
            if page == 'error':
                self.show_page('success')
            return

        if button_name == 'close':
            self.destroy()

    def _on_page_changed(self, _assistant, page_name):
        if page_name == 'start':
            self.set_default_button('forward')

        elif page_name == 'progress':
            self.set_default_button('forward')

        elif page_name == 'success':
            self.set_default_button('forward')

        elif page_name == 'error':
            self.set_default_button('back')


class Progress(Gtk.Box):

    title = 'Progress'

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(18)
        self.set_valign(Gtk.Align.CENTER)
        label = Gtk.Label(label='Test label...')
        label.set_max_width_chars(50)
        label.set_line_wrap(True)
        label.set_halign(Gtk.Align.CENTER)
        label.set_justify(Gtk.Justification.CENTER)
        spinner = Gtk.Spinner()
        self.pack_start(label, False, True, 0)
        self.pack_start(spinner, False, True, 0)
        spinner.start()
        self.show_all()


class Start(Gtk.Box):

    title = 'Start'

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(18)
        self.set_valign(Gtk.Align.CENTER)
        heading = Gtk.Label(label='Test Assistant')
        heading.get_style_context().add_class('large-header')

        label1 = Gtk.Label(label='This is label 1 with some text')
        label1.set_max_width_chars(50)
        label1.set_line_wrap(True)
        label1.set_halign(Gtk.Align.CENTER)
        label1.set_justify(Gtk.Justification.CENTER)
        label1.set_margin_bottom(24)

        label2 = Gtk.Label(label='This is label 2 with some more text')
        label2.set_max_width_chars(50)
        label2.set_line_wrap(True)
        label2.set_halign(Gtk.Align.CENTER)
        label2.set_justify(Gtk.Justification.CENTER)

        self._server = Gtk.CheckButton.new_with_mnemonic('A fancy checkbox')
        self._server.set_halign(Gtk.Align.CENTER)

        self.pack_start(heading, False, True, 0)
        self.pack_start(label1, False, True, 0)
        self.pack_start(label2, False, True, 0)
        self.pack_start(self._server, False, True, 0)
        self.show_all()


win = TestAssistant()
win.connect('destroy', Gtk.main_quit)
win.show_all()
Gtk.main()
