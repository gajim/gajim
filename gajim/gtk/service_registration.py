# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

import logging
from enum import IntEnum

from gi.repository import Gtk

from gajim.common import app
from gajim.common.modules import dataforms
from gajim.common.i18n import _
from gajim.gtk.dataform import DataFormWidget

log = logging.getLogger('gajim.gtk.registration')


class Page(IntEnum):
    REQUEST = 0
    FORM = 1
    SENDING = 2
    SUCCESS = 3
    ERROR = 4


class ServiceRegistration(Gtk.Assistant):
    def __init__(self, account, agent):
        Gtk.Assistant.__init__(self)

        self._con = app.connections[account]
        self._agent = agent
        self._account = account
        self._data_form_widget = None
        self._is_form = None

        self.set_application(app.app)
        self.set_resizable(True)
        self.set_position(Gtk.WindowPosition.CENTER)

        self.set_default_size(600, 400)
        self.get_style_context().add_class('dialog-margin')

        self._add_page(RequestPage())
        self._add_page(FormPage())
        self._add_page(SendingPage())
        self._add_page(SuccessfulPage())
        self._add_page(ErrorPage())

        self.connect('prepare', self._on_page_change)
        self.connect('cancel', self._on_cancel)
        self.connect('close', self._on_cancel)

        self._remove_sidebar()
        self.show_all()

    def _add_page(self, page):
        self.append_page(page)
        self.set_page_type(page, page.type_)
        self.set_page_title(page, page.title)
        self.set_page_complete(page, page.complete)

    def _remove_sidebar(self):
        main_box = self.get_children()[0]
        sidebar = main_box.get_children()[0]
        main_box.remove(sidebar)

    def _on_page_change(self, assistant, page):
        if self.get_current_page() == Page.REQUEST:
            self._con.get_module('Register').get_register_form(
                self._agent, self._on_get_success, self._on_error)
        elif self.get_current_page() == Page.SENDING:
            self._register()
            self.commit()

    def _on_get_success(self, form, is_form):
        log.info('Show Form page')
        self._is_form = is_form
        if is_form:
            dataform = dataforms.extend_form(node=form)
            self._data_form_widget = DataFormWidget(dataform)
        else:
            from gajim import config
            self._data_form_widget = config.FakeDataForm(form)

        page = self.get_nth_page(Page.FORM)
        page.pack_start(self._data_form_widget, True, True, 0)
        self._data_form_widget.show_all()
        self.set_current_page(Page.FORM)

    def _on_error(self, error_text):
        log.info('Show Error page')
        page = self.get_nth_page(Page.ERROR)
        page.set_text(error_text)
        self.set_current_page(Page.ERROR)

    def _on_cancel(self, widget):
        self.destroy()

    def _register(self):
        log.info('Show Sending page')
        if self._is_form:
            form = self._data_form_widget.get_submit_form()
        else:
            form = self._data_form_widget.get_infos()
            if 'instructions' in form:
                del form['instructions']
            if 'registered' in form:
                del form['registered']

        self._con.get_module('Register').register_agent(
            self._agent,
            form,
            self._is_form,
            self._on_register_success,
            self._on_error)

    def _on_register_success(self):
        log.info('Show Success page')
        self.set_current_page(Page.SUCCESS)


class RequestPage(Gtk.Box):

    type_ = Gtk.AssistantPageType.INTRO
    title = _('Register')
    complete = False

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(18)
        spinner = Gtk.Spinner()
        self.pack_start(spinner, True, True, 0)
        spinner.start()


class SendingPage(RequestPage):

    type_ = Gtk.AssistantPageType.PROGRESS
    title = _('Register')
    complete = False

    def __init__(self):
        super().__init__()


class FormPage(Gtk.Box):

    type_ = Gtk.AssistantPageType.INTRO
    title = _('Register')
    complete = True

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)


class SuccessfulPage(Gtk.Box):

    type_ = Gtk.AssistantPageType.SUMMARY
    title = _('Registration successful')
    complete = True

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(12)
        self.set_homogeneous(True)

        icon = Gtk.Image.new_from_icon_name('object-select-symbolic',
                                            Gtk.IconSize.DIALOG)
        icon.get_style_context().add_class('success-color')
        icon.set_valign(Gtk.Align.END)
        label = Gtk.Label(label=_('Registration successful'))
        label.get_style_context().add_class('bold16')
        label.set_valign(Gtk.Align.START)

        self.add(icon)
        self.add(label)


class ErrorPage(Gtk.Box):

    type_ = Gtk.AssistantPageType.SUMMARY
    title = _('Registration failed')
    complete = True

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(12)
        self.set_homogeneous(True)

        icon = Gtk.Image.new_from_icon_name('dialog-error-symbolic',
                                            Gtk.IconSize.DIALOG)
        icon.get_style_context().add_class('error-color')
        icon.set_valign(Gtk.Align.END)
        self._label = Gtk.Label()
        self._label.get_style_context().add_class('bold16')
        self._label.set_valign(Gtk.Align.START)

        self.add(icon)
        self.add(self._label)

    def set_text(self, text):
        self._label.set_text(text)
