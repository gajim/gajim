# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import Literal
from typing import overload

import logging

from gi.repository import Gtk
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import RegisterStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.protocol import JID
from nbxmpp.task import Task

from gajim.common import app
from gajim.common.i18n import _

from gajim.gtk.assistant import Assistant
from gajim.gtk.assistant import ErrorPage
from gajim.gtk.assistant import Page
from gajim.gtk.assistant import ProgressPage
from gajim.gtk.assistant import SuccessPage
from gajim.gtk.dataform import DataFormWidget

log = logging.getLogger('gajim.gtk.service_registration')


class ServiceRegistration(Assistant):
    def __init__(self, account: str, address: JID) -> None:
        Assistant.__init__(self, width=600, height=400)
        self.account = account

        self._client = app.get_client(account)
        self._service = address

        self.add_button('register', _('Register'), 'suggested-action')
        self.add_button('close', _('Close'))
        self.add_button('back', _('Back'))

        self.set_button_visible_func(self._visible_func)

        self.add_pages({
            'form': Form(),
        })

        self.add_default_page('error')
        self.add_default_page('progress')
        self.add_default_page('success')

        self.get_page('error').set_title(_('Registration failed'))
        self.get_page('error').set_heading(_('Registration failed'))

        self.connect('button-clicked', self._on_button_clicked)

        self.show_all()

        self._request_form()

    @overload
    def get_page(self, name: Literal['form']) -> Form:
        ...

    @overload
    def get_page(self, name: Literal['success']) -> SuccessPage:
        ...

    @overload
    def get_page(self, name: Literal['error']) -> ErrorPage:
        ...

    @overload
    def get_page(self, name: Literal['progress']) -> ProgressPage:
        ...

    def get_page(self, name: str) -> Page:
        return self._pages[name]

    @staticmethod
    def _visible_func(_assistant: Assistant, page_name: str) -> list[str]:
        if page_name == 'form':
            return ['close', 'register']

        if page_name == 'progress':
            return []

        if page_name == 'success':
            return ['close']

        if page_name == 'error':
            return ['back', 'close']
        raise ValueError(f'page {page_name} unknown')

    def _on_button_clicked(self, _page: Gtk.Widget, button_name: str) -> None:
        if button_name == 'register':
            self._register()

        if button_name == 'back':
            self.show_page('form', Gtk.StackTransitionType.SLIDE_RIGHT)

        if button_name == 'close':
            self.destroy()

    def _request_form(self) -> None:
        self.get_page('progress').set_title(_('Requesting Register Form'))
        self.get_page('progress').set_text(
            _('Requesting register form from server…'))
        self.show_page('progress')

        self._client.get_module('Register').request_register_form(
            self._service, callback=self._on_register_form)

    def _on_register_form(self, task: Task) -> None:
        try:
            result = task.finish()
        except (StanzaError, MalformedStanzaError) as error:
            self.get_page('error').set_text(error.get_text())
            self.show_page('error')
            return

        form = result.form
        if result.form is None:
            form = result.fields_form

        self.get_page('form').add_form(form)
        self.show_page('form')

    def _register(self) -> None:
        self.get_page('progress').set_title(_('Registering…'))
        self.get_page('progress').set_text(_('Registering…'))
        self.show_page('progress')

        form = self.get_page('form').get_submit_form()
        self._client.get_module('Register').submit_register_form(
            form,
            self._service,
            callback=self._on_register_result)

    def _on_register_result(self, task: Task) -> None:
        try:
            task.finish()
        except (StanzaError,
                MalformedStanzaError,
                RegisterStanzaError) as error:
            self.get_page('error').set_text(error.get_text())
            self.show_page('error')
            return

        self.get_page('success').set_title(_('Registration successful'))
        self.get_page('success').set_text(_('Registration successful'))
        self.show_page('success')


class Form(Page):
    def __init__(self) -> None:
        Page.__init__(self)
        self.title = _('Register')
        self.complete = False

        self._dataform_widget: DataFormWidget | None = None
        self.show_all()

    def add_form(self, form: Any) -> None:
        self.remove_form()

        options = {
            'form-width': 350,
            'entry-activates-default': True
        }
        self._dataform_widget = DataFormWidget(form, options)
        self._dataform_widget.set_propagate_natural_height(True)
        self._dataform_widget.connect('is-valid', self._on_is_valid)
        self._dataform_widget.validate()
        self._dataform_widget.show_all()
        self.add(self._dataform_widget)

    def _on_is_valid(self, _widget: DataFormWidget, is_valid: bool) -> None:
        self.complete = is_valid
        self.update_page_complete()

    def get_submit_form(self) -> Any:
        assert self._dataform_widget is not None
        return self._dataform_widget.get_submit_form()

    def remove_form(self) -> None:
        if self._dataform_widget is None:
            return

        self.remove(self._dataform_widget)
        self._dataform_widget.destroy()
        self._dataform_widget = None

    def get_default_button(self) -> str:
        return 'register'
