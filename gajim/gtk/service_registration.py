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

        self.set_default_size(500, 300)
        self.get_style_context().add_class('dialog-margin')

        request = RequestPage()
        self.append_page(request)
        self.set_page_type(request, Gtk.AssistantPageType.INTRO)

        form = FormPage()
        self.append_page(form)
        self.set_page_type(form, Gtk.AssistantPageType.INTRO)
        self.set_page_complete(form, True)

        sending = SendingPage()
        self.append_page(sending)
        self.set_page_type(sending, Gtk.AssistantPageType.PROGRESS)

        success = SuccessfulPage()
        self.append_page(success)
        self.set_page_type(success, Gtk.AssistantPageType.SUMMARY)
        self.set_page_complete(success, True)

        error = ErrorPage()
        self.append_page(error)
        self.set_page_type(error, Gtk.AssistantPageType.SUMMARY)
        self.set_page_complete(error, True)

        self.connect('prepare', self._on_page_change)
        self.connect('cancel', self._on_cancel)
        self.connect('close', self._on_cancel)

        self.show_all()

    def _on_page_change(self, assistant, page):
        if self.get_current_page() == Page.REQUEST:
            self._con.get_module('Register').get_register_form(
                self._agent, self._on_get_success, self._on_error)
        elif self.get_current_page() == Page.SENDING:
            self._register()
            self.commit()
            pass

    def _on_get_success(self, form, is_form):
        log.info('Show Form page')
        self._is_form = is_form
        if is_form:
            from gajim import dataforms_widget
            dataform = dataforms.ExtendForm(node=form)
            self._data_form_widget = dataforms_widget.DataFormWidget(dataform)
            if self._data_form_widget.title:
                self.set_title('%s - Gajim' % self._data_form_widget.title)
        else:
            if 'registered' in form:
                self.set_title(_('Edit %s') % self._agent)
            else:
                self.set_title(_('Register to %s') % self._agent)
            from gajim import config
            self._data_form_widget = config.FakeDataForm(form)

        page = self.get_nth_page(Page.FORM)
        page.pack_start(self._data_form_widget, True, True, 0)
        self._data_form_widget.show()
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
            form = self._data_form_widget.data_form
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
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_spacing(18)
        spinner = Gtk.Spinner()
        self.pack_start(spinner, True, True, 0)
        spinner.start()


class SendingPage(RequestPage):
    def __init__(self):
        super().__init__()


class FormPage(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)


class SuccessfulPage(Gtk.Box):
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
