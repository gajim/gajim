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

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Gio
from gi.repository import GObject

from nbxmpp.client import Client
from nbxmpp.protocol import JID
from nbxmpp.protocol import validate_domainpart
from nbxmpp.const import Mode
from nbxmpp.const import StreamError
from nbxmpp.const import ConnectionProtocol
from nbxmpp.const import ConnectionType
from nbxmpp.errors import StanzaError
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import RegisterStanzaError

from gajim.common import app
from gajim.common import configpaths
from gajim.common import helpers
from gajim.common.nec import NetworkEvent
from gajim.common.helpers import open_uri
from gajim.common.helpers import validate_jid
from gajim.common.helpers import get_proxy
from gajim.common.i18n import _
from gajim.common.const import SASL_ERRORS
from gajim.common.const import GIO_TLS_ERRORS

from .assistant import Assistant
from .assistant import Page
from .assistant import SuccessPage
from .assistant import ErrorPage
from .dataform import DataFormWidget
from .util import get_builder
from .util import open_window
from .util import get_color_for_account
from .util import get_app_window

log = logging.getLogger('gajim.gui.account_wizard')


class AccountWizard(Assistant):
    def __init__(self):
        Assistant.__init__(self, height=500)

        self._destroyed = False

        self.add_button('signup', _('Sign Up'), complete=True,
                        css_class='suggested-action')
        self.add_button('connect', _('Connect'), css_class='suggested-action')
        self.add_button('next', _('Next'), css_class='suggested-action')
        self.add_button('login', _('Log In'), complete=True,
                        css_class='suggested-action')
        self.add_button('back', _('Back'))

        self.add_pages({'login': Login(),
                        'signup': Signup(),
                        'advanced': AdvancedSettings(),
                        'security-warning': SecurityWarning(),
                        'form': Form(),
                        'redirect': Redirect(),
                        'success': Success(),
                        'error': Error(),
                        })

        self._progress = self.add_default_page('progress')

        self.get_page('login').connect('clicked', self._on_button_clicked)
        self.connect('button-clicked', self._on_assistant_button_clicked)
        self.connect('page-changed', self._on_page_changed)
        self.connect('destroy', self._on_destroy)

        self.show_all()

        self.update_proxy_list()

        self._client = None
        self._method = 'login'

    def get_currenct_method(self):
        return self._method

    def _on_button_clicked(self, _page, button_name):
        if button_name == 'login':
            if self.get_page('login').is_advanced():
                self.show_page('advanced',
                               Gtk.StackTransitionType.SLIDE_LEFT)
            else:
                self._test_credentials()

        elif button_name == 'signup':
            self.show_page('signup', Gtk.StackTransitionType.SLIDE_LEFT)

    def _on_assistant_button_clicked(self, _assistant, button_name):
        page = self.get_current_page()

        if button_name == 'login':
            if page == 'advanced':
                self._test_credentials()

            elif page == 'security-warning':
                if self.get_page('security-warning').trust_certificate:
                    app.cert_store.add_certificate(
                        self.get_page('security-warning').cert)
                self._test_credentials(ignore_all_errors=True)

        elif button_name == 'signup':
            if page == 'signup':
                if self.get_page('signup').is_advanced():
                    self.show_page('advanced',
                                   Gtk.StackTransitionType.SLIDE_LEFT)

                elif self.get_page('signup').is_anonymous():
                    self._test_anonymous_server()

                else:
                    self._register_with_server()

            elif page == 'advanced':
                if self.get_page('signup').is_anonymous():
                    self._test_anonymous_server()
                else:
                    self._register_with_server()

            elif page == 'security-warning':
                if self.get_page('security-warning').trust_certificate:
                    app.cert_store.add_certificate(
                        self.get_page('security-warning').cert)

                if self.get_page('signup').is_anonymous():
                    self._test_anonymous_server(ignore_all_errors=True)

                else:
                    self._register_with_server(ignore_all_errors=True)

            elif page == 'form':
                self._show_progress_page(_('Creating Account...'),
                                         _('Trying to create account...'))
                self._submit_form()

        elif button_name == 'connect':
            if page == 'success':
                app.interface.enable_account(self.get_page('success').account)
                self.destroy()

        elif button_name == 'back':
            if page == 'signup':
                self.show_page('login', Gtk.StackTransitionType.SLIDE_RIGHT)

            elif page in ('advanced', 'error', 'security-warning'):
                if (page == 'error' and
                        self._method == 'signup' and
                        self.get_page('form').has_form):
                    self.show_page('form', Gtk.StackTransitionType.SLIDE_RIGHT)
                else:
                    self.show_page(self._method,
                                   Gtk.StackTransitionType.SLIDE_RIGHT)

            elif page == 'form':
                self.show_page('signup', Gtk.StackTransitionType.SLIDE_RIGHT)
                self.get_page('form').remove_form()
                self._disconnect()

            elif page == 'redirect':
                self.show_page('login', Gtk.StackTransitionType.SLIDE_RIGHT)

    def _on_page_changed(self, _assistant, page_name):
        if page_name == 'signup':
            self._method = page_name
            self.get_page('signup').focus()

        elif page_name == 'login':
            self._method = page_name
            self.get_page('login').focus()

        elif page_name == 'form':
            self.get_page('form').focus()

    def update_proxy_list(self):
        self.get_page('advanced').update_proxy_list()

    def _get_base_client(self,
                         domain,
                         username,
                         mode,
                         advanced,
                         ignore_all_errors):

        client = Client(log_context='Account Wizard')
        client.set_domain(domain)
        client.set_username(username)
        client.set_mode(mode)
        client.set_ignore_tls_errors(ignore_all_errors)
        client.set_accepted_certificates(
            app.cert_store.get_certificates())

        if advanced:
            custom_host = self.get_page('advanced').get_custom_host()
            if custom_host is not None:
                client.set_custom_host(*custom_host)

            proxy_name = self.get_page('advanced').get_proxy()
            proxy_data = get_proxy(proxy_name)
            if proxy_data is not None:
                client.set_proxy(proxy_data)

        client.subscribe('disconnected', self._on_disconnected)
        client.subscribe('connection-failed', self._on_connection_failed)
        client.subscribe('stanza-sent', self._on_stanza_sent)
        client.subscribe('stanza-received', self._on_stanza_received)
        return client

    def _disconnect(self):
        if self._client is None:
            return
        self._client.remove_subscriptions()
        self._client.disconnect()
        self._client = None

    @staticmethod
    def _on_stanza_sent(_client, _signal_name, stanza):
        app.nec.push_incoming_event(NetworkEvent('stanza-sent',
                                                 account='AccountWizard',
                                                 stanza=stanza))

    @staticmethod
    def _on_stanza_received(_client, _signal_name, stanza):
        app.nec.push_incoming_event(NetworkEvent('stanza-received',
                                                 account='AccountWizard',
                                                 stanza=stanza))

    def _test_credentials(self, ignore_all_errors=False):
        self._show_progress_page(_('Connecting...'),
                                 _('Connecting to server...'))
        address, password = self.get_page('login').get_credentials()
        jid = JID.from_string(address)
        advanced = self.get_page('login').is_advanced()

        self._client = self._get_base_client(
            jid.domain,
            jid.localpart,
            Mode.LOGIN_TEST,
            advanced,
            ignore_all_errors)

        self._client.set_password(password)
        self._client.subscribe('login-successful', self._on_login_successful)

        self._client.connect()

    def _test_anonymous_server(self, ignore_all_errors=False):
        self._show_progress_page(_('Connecting...'),
                                 _('Connecting to server...'))
        domain = self.get_page('signup').get_server()
        advanced = self.get_page('signup').is_advanced()

        self._client = self._get_base_client(
            domain,
            None,
            Mode.ANONYMOUS_TEST,
            advanced,
            ignore_all_errors)

        self._client.subscribe('anonymous-supported',
                               self._on_anonymous_supported)
        self._client.connect()

    def _register_with_server(self, ignore_all_errors=False):
        self._show_progress_page(_('Connecting...'),
                                 _('Connecting to server...'))
        domain = self.get_page('signup').get_server()
        advanced = self.get_page('signup').is_advanced()

        self._client = self._get_base_client(
            domain,
            None,
            Mode.REGISTER,
            advanced,
            ignore_all_errors)

        self._client.subscribe('connected', self._on_connected)

        self._client.connect()

    def _on_login_successful(self, client, _signal_name):
        account = self._generate_account_name(client.domain)
        proxy_name = None
        if client.proxy is not None:
            proxy_name = self.get_page('advanced').get_proxy()

        app.interface.create_account(account,
                                     client.username,
                                     client.domain,
                                     client.password,
                                     proxy_name,
                                     client.custom_host)
        self.get_page('success').set_account(account)
        self.show_page('success', Gtk.StackTransitionType.SLIDE_LEFT)

    def _on_connected(self, client, _signal_name):
        client.get_module('Register').request_register_form(
            callback=self._on_register_form)

    def _on_anonymous_supported(self, client, _signal_name):
        account = self._generate_account_name(client.domain)
        proxy_name = None
        if client.proxy is not None:
            proxy_name = self.get_page('advanced').get_proxy()

        app.interface.create_account(account,
                                     None,
                                     client.domain,
                                     client.password,
                                     proxy_name,
                                     client.custom_host,
                                     anonymous=True)
        self.get_page('success').set_account(account)
        self.show_page('success', Gtk.StackTransitionType.SLIDE_LEFT)

    def _on_disconnected(self, client, _signal_name):
        domain, error, text = client.get_error()
        if domain == StreamError.SASL:
            if error == 'anonymous-not-supported':
                self._show_error_page(_('Anonymous login not supported'),
                                      _('Anonymous login not supported'),
                                      _('This server does not support '
                                        'anonymous login.'))
            else:
                self._show_error_page(_('Authentication failed'),
                                      SASL_ERRORS.get(error),
                                      text or '')

        elif domain == StreamError.BAD_CERTIFICATE:
            self.get_page('security-warning').set_warning(
                self._client.domain, *self._client.peer_certificate)
            self.show_page('security-warning',
                           Gtk.StackTransitionType.SLIDE_LEFT)

        elif domain == StreamError.REGISTER:
            if error == 'register-not-supported':
                self._show_error_page(_('Signup not allowed'),
                                      _('Signup not allowed'),
                                      _('This server does not allow signup.'))

        elif domain == StreamError.STREAM:
            # The credential test often ends with a stream error, because
            # after auth there should be a stream restart but nbxmpp ends
            # the stream with </stream> which is considered not-well-formed
            # by the server. This ignores all stream errors if we already
            # know that we succeeded.
            if self.get_current_page() != 'success':
                self._show_error_page(_('Error'), _('Error'), text or error)

        else:
            self._show_error_page(_('Error'), _('Error'), text or error)

        self.get_page('form').remove_form()
        self._client.destroy()
        self._client = None

    def _on_connection_failed(self, _client, _signal_name):
        self._show_error_page(_('Connection failed'),
                              _('Connection failed'),
                              _('Gajim was not able to reach the server. '
                                'Make sure your XMPP address is correct.'))
        self._client.destroy()
        self._client = None

    def _show_error_page(self, title, heading, text):
        self.get_page('error').set_title(title)
        self.get_page('error').set_heading(heading)
        self.get_page('error').set_text(text or '')
        self.show_page('error', Gtk.StackTransitionType.SLIDE_LEFT)

    def _show_progress_page(self, title, text):
        self._progress.set_title(title)
        self._progress.set_text(text)
        self.show_page('progress', Gtk.StackTransitionType.SLIDE_LEFT)

    @staticmethod
    def _generate_account_name(domain):
        i = 1
        while domain in app.settings.get_accounts():
            domain = domain + str(i)
            i += 1
        return domain

    def _on_register_form(self, task):
        try:
            result = task.finish()
        except (StanzaError, MalformedStanzaError) as error:
            self._show_error_page(_('Error'),
                                  _('Error'),
                                  error.get_text())
            self._disconnect()
            return

        if result.bob_data is not None:
            algo_hash = result.bob_data.cid.split('@')[0]
            app.bob_cache[algo_hash] = result.bob_data.data

        form = result.form
        if result.form is None:
            form = result.fields_form

        if form is not None:
            self.get_page('form').add_form(form)

        elif result.oob_url is not None:
            self.get_page('redirect').set_redirect(result.oob_url,
                                                   result.instructions)
            self.show_page('redirect', Gtk.StackTransitionType.SLIDE_LEFT)
            self._disconnect()
            return

        self.show_page('form', Gtk.StackTransitionType.SLIDE_LEFT)

    def _submit_form(self):
        self.get_page('progress').set_text(_('Account is being created'))
        self.show_page('progress', Gtk.StackTransitionType.SLIDE_LEFT)

        form = self.get_page('form').get_submit_form()
        self._client.get_module('Register').submit_register_form(
            form,
            callback=self._on_register_result)

    def _on_register_result(self, task):
        try:
            task.finish()
        except RegisterStanzaError as error:
            self._set_error_text(error)
            if error.type != 'modify':
                self.get_page('form').remove_form()
                self._disconnect()
                return

            register_data = error.get_data()
            form = register_data.form
            if register_data.form is None:
                form = register_data.fields_form

            if form is not None:
                self.get_page('form').add_form(form)

            else:
                self.get_page('form').remove_form()
                self._disconnect()
            return

        except (StanzaError, MalformedStanzaError) as error:
            self._set_error_text(error)
            self.get_page('form').remove_form()
            self._disconnect()
            return

        username, password = self.get_page('form').get_credentials()
        account = self._generate_account_name(self._client.domain)

        proxy_name = None
        if self._client.proxy is not None:
            proxy_name = self.get_page('advanced').get_proxy()

        app.interface.create_account(account,
                                     username,
                                     self._client.domain,
                                     password,
                                     proxy_name,
                                     self._client.custom_host)

        self.get_page('success').set_account(account)
        self.show_page('success', Gtk.StackTransitionType.SLIDE_LEFT)
        self.get_page('form').remove_form()
        self._disconnect()

    def _set_error_text(self, error):
        error_text = error.get_text()
        if not error_text:
            error_text = _('The server rejected the registration '
                           'without an error message')
        self._show_error_page(_('Error'), _('Error'), error_text)

    def _on_destroy(self, *args):
        self._disconnect()
        self._destroyed = True


class Login(Page):

    __gsignals__ = {
        'clicked': (GObject.SignalFlags.RUN_LAST, None, (str,)),
    }

    def __init__(self):
        Page.__init__(self)
        self.title = _('Add Account')

        self._ui = get_builder('account_wizard.ui')
        self._ui.log_in_address_entry.connect(
            'activate', self._on_address_entry_activate)
        self._ui.log_in_address_entry.connect(
            'changed', self._on_address_changed)
        self._ui.log_in_password_entry.connect(
            'changed', self._set_complete)
        self._ui.log_in_password_entry.connect(
            'activate', self._on_password_entry_activate)
        self._create_server_completion()

        self._ui.log_in_button.connect('clicked', self._on_login)
        self._ui.sign_up_button.connect('clicked', self._on_signup)

        self.pack_start(self._ui.login_box, True, True, 0)
        self.show_all()

    def focus(self):
        self._ui.log_in_address_entry.grab_focus()

    def _on_login(self, *args):
        self.emit('clicked', 'login')

    def _on_signup(self, *args):
        self.emit('clicked', 'signup')

    def _create_server_completion(self):
        # Parse servers.json
        file_path = configpaths.get('DATA') / 'other' / 'servers.json'
        self._servers = helpers.load_json(file_path, default=[])

        # Create a separate model for the address entry, because it will
        # be updated with our localpart@
        address_model = Gtk.ListStore(str)
        for server in self._servers:
            address_model.append((server,))
        self._ui.log_in_address_entry.get_completion().set_model(address_model)

    def _on_address_changed(self, entry):
        self._update_completion(entry)
        self._set_complete()

    def _update_completion(self, entry):
        text = entry.get_text()
        if '@' not in text:
            self._show_icon(False)
            return
        text = text.split('@', 1)[0]

        model = entry.get_completion().get_model()
        model.clear()

        for server in self._servers:
            model.append(['%s@%s' % (text, server)])

    def _show_icon(self, show):
        icon = 'dialog-warning-symbolic' if show else None
        self._ui.log_in_address_entry.set_icon_from_icon_name(
            Gtk.EntryIconPosition.SECONDARY, icon)

    def _on_address_entry_activate(self, _widget):
        GLib.idle_add(self._ui.log_in_password_entry.grab_focus)

    def _on_password_entry_activate(self, _widget):
        if self._ui.log_in_button.get_sensitive():
            self._ui.log_in_button.activate()

    def _validate_jid(self, address):
        if not address:
            self._show_icon(False)
            return False

        try:
            jid = validate_jid(address, type_='bare')
            if jid.resource:
                raise ValueError
        except ValueError:
            self._show_icon(True)
            self._ui.log_in_address_entry.set_icon_tooltip_text(
                Gtk.EntryIconPosition.SECONDARY, _('Invalid Address'))
            return False

        self._show_icon(False)
        return True

    def _set_complete(self, *args):
        address = self._validate_jid(self._ui.log_in_address_entry.get_text())
        password = self._ui.log_in_password_entry.get_text()
        self._ui.log_in_button.set_sensitive(address and password)

    def is_advanced(self):
        return self._ui.login_advanced_checkbutton.get_active()

    def get_credentials(self):
        data = (self._ui.log_in_address_entry.get_text(),
                self._ui.log_in_password_entry.get_text())
        return data


class Signup(Page):
    def __init__(self):
        Page.__init__(self)
        self.complete = False
        self.title = _('Create New Account')

        self._ui = get_builder('account_wizard.ui')
        self._ui.server_comboboxtext_sign_up_entry.set_activates_default(True)
        self._create_server_completion()

        self._ui.recommendation_link1.connect(
            'activate-link', self._on_activate_link)
        self._ui.recommendation_link2.connect(
            'activate-link', self._on_activate_link)
        self._ui.visit_server_button.connect('clicked',
                                             self._on_visit_server)
        self._ui.server_comboboxtext_sign_up_entry.connect(
            'changed', self._set_complete)

        self.pack_start(self._ui.signup_grid, True, True, 0)

        self.show_all()

    def focus(self):
        self._ui.server_comboboxtext_sign_up_entry.grab_focus()

    def _create_server_completion(self):
        # Parse servers.json
        file_path = configpaths.get('DATA') / 'other' / 'servers.json'
        servers = helpers.load_json(file_path, default=[])

        # Create servers_model for comboboxes and entries
        servers_model = Gtk.ListStore(str)
        for server in servers:
            servers_model.append((server,))

        # Sign up combobox and entry
        self._ui.server_comboboxtext_sign_up.set_model(servers_model)
        self._ui.server_comboboxtext_sign_up_entry.get_completion().set_model(
            servers_model)

    def _on_visit_server(self, _widget):
        server = self._ui.server_comboboxtext_sign_up_entry.get_text().strip()
        server = 'https://' + server
        open_uri(server)
        return Gdk.EVENT_STOP

    def _set_complete(self, *args):
        try:
            self.get_server()
        except Exception:
            self.complete = False
            self._ui.visit_server_button.set_visible(False)
        else:
            self.complete = True
            self._ui.visit_server_button.set_visible(True)

        self.update_page_complete()

    def is_anonymous(self):
        return self._ui.sign_up_anonymously.get_active()

    def is_advanced(self):
        return self._ui.sign_up_advanced_checkbutton.get_active()

    def get_server(self):
        return validate_domainpart(
            self._ui.server_comboboxtext_sign_up_entry.get_text())

    @staticmethod
    def _on_activate_link(_label, uri):
        # We have to use this, because the default GTK handler
        # is not cross-platform compatible
        open_uri(uri)
        return Gdk.EVENT_STOP

    def get_visible_buttons(self):
        return ['back', 'signup']

    def get_default_button(self):
        return 'signup'


class AdvancedSettings(Page):
    def __init__(self):
        Page.__init__(self)
        self.title = _('Advanced settings')
        self.complete = False

        self._ui = get_builder('account_wizard.ui')
        self._ui.manage_proxies_button.connect('clicked',
                                               self._on_proxy_manager)
        self._ui.proxies_combobox.connect('changed', self._set_complete)
        self._ui.custom_host_entry.connect('changed', self._set_complete)
        self._ui.custom_port_entry.connect('changed', self._set_complete)
        self.pack_start(self._ui.advanced_grid, True, True, 0)

        self.show_all()

    @staticmethod
    def _on_proxy_manager(_widget):
        app.app.activate_action('manage-proxies')

    def update_proxy_list(self):
        model = Gtk.ListStore(str)
        self._ui.proxies_combobox.set_model(model)
        proxies = app.settings.get_proxies()
        proxies.insert(0, _('No Proxy'))
        for proxy in proxies:
            model.append([proxy])
        self._ui.proxies_combobox.set_active(0)

    def get_proxy(self):
        active = self._ui.proxies_combobox.get_active()
        return self._ui.proxies_combobox.get_model()[active][0]

    def get_custom_host(self):
        host = self._ui.custom_host_entry.get_text()
        port = self._ui.custom_port_entry.get_text()
        if not host or not port:
            return None

        con_type = self._ui.con_type_combo.get_active_text()

        protocol = ConnectionProtocol.TCP
        if host.startswith('ws://') or host.startswith('wss://'):
            protocol = ConnectionProtocol.WEBSOCKET

        return ('%s:%s' % (host, port),
                protocol,
                ConnectionType(con_type))

    def _show_host_icon(self, show):
        icon = 'dialog-warning-symbolic' if show else None
        self._ui.custom_host_entry.set_icon_from_icon_name(
            Gtk.EntryIconPosition.SECONDARY, icon)

    def _show_port_icon(self, show):
        icon = 'dialog-warning-symbolic' if show else None
        self._ui.custom_port_entry.set_icon_from_icon_name(
            Gtk.EntryIconPosition.SECONDARY, icon)

    def _validate_host(self):
        host = self._ui.custom_host_entry.get_text()
        if host.startswith('ws://') or host.startswith('wss://'):
            # We have no method for validating websocket URIs
            self._show_host_icon(False)
            return True

        try:
            validate_domainpart(host)
        except Exception:
            self._show_host_icon(True)
            self._ui.custom_host_entry.set_icon_tooltip_text(
                Gtk.EntryIconPosition.SECONDARY, _('Invalid domain name'))
            return False

        self._show_host_icon(False)
        return True

    def _validate_port(self):
        port = self._ui.custom_port_entry.get_text()
        if not port:
            self._show_port_icon(False)
            return False

        try:
            port = int(port)
        except Exception:
            self._show_port_icon(True)
            self._ui.custom_port_entry.set_icon_tooltip_text(
                Gtk.EntryIconPosition.SECONDARY, _('Must be a port number'))
            return False

        if port not in range(0, 65535):
            self._show_port_icon(True)
            self._ui.custom_port_entry.set_icon_tooltip_text(
                Gtk.EntryIconPosition.SECONDARY,
                _('Port must be a number between 0 and 65535'))
            return False

        self._show_port_icon(False)
        return True

    def _is_custom_host_set(self):
        host = bool(self._ui.custom_host_entry.get_text())
        port = bool(self._ui.custom_port_entry.get_text())
        return host or port

    def _is_proxy_set(self):
        return self._ui.proxies_combobox.get_active() != 0

    def _set_complete(self, *args):
        self.complete = False
        if self._is_proxy_set():
            self.complete = True

        if self._is_custom_host_set():
            port_valid = self._validate_port()
            host_valid = self._validate_host()
            self.complete = port_valid and host_valid

        self.update_page_complete()

    def get_visible_buttons(self):
        return ['back', self.get_toplevel().get_currenct_method()]

    def get_default_button(self):
        return self.get_toplevel().get_currenct_method()


class SecurityWarning(Page):
    def __init__(self):
        Page.__init__(self)
        self.title = _('Security Warning')
        self._cert = None
        self._domain = None

        self._ui = get_builder('account_wizard.ui')
        self.pack_start(self._ui.security_warning_box, True, True, 0)
        self._ui.view_cert_button.connect('clicked', self._on_view_cert)
        self.show_all()

    @property
    def cert(self):
        return self._cert

    def set_warning(self, domain, cert, errors):
        # Clear list
        self._cert = cert
        self._domain = domain
        self._ui.error_list.foreach(self._ui.error_list.remove)

        unknown_error = _('Unknown TLS error \'%s\'')
        for error in errors:
            error_text = GIO_TLS_ERRORS.get(error, unknown_error % error)
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            image = Gtk.Image.new_from_icon_name('dialog-warning-symbolic',
                                                 Gtk.IconSize.LARGE_TOOLBAR)
            image.get_style_context().add_class('warning-color')
            label = Gtk.Label(label=error_text)
            label.set_line_wrap(True)
            label.set_xalign(0)
            label.set_selectable(True)
            box.add(image)
            box.add(label)
            box.show_all()
            self._ui.error_list.add(box)

        self._ui.trust_cert_checkbutton.set_visible(
            Gio.TlsCertificateFlags.UNKNOWN_CA in errors)

    def _on_view_cert(self, _button):
        open_window('CertificateDialog',
                    account=self._domain,
                    transient_for=self.get_toplevel(),
                    cert=self._cert)

    @property
    def trust_certificate(self):
        return self._ui.trust_cert_checkbutton.get_active()

    def get_visible_buttons(self):
        return ['back', self.get_toplevel().get_currenct_method()]

    def get_default_button(self):
        return 'back'


class Form(Page):
    def __init__(self):
        Page.__init__(self)
        self.set_valign(Gtk.Align.FILL)
        self.complete = False
        self.title = _('Create Account')
        self._current_form = None

        heading = Gtk.Label(label=_('Create Account'))
        heading.get_style_context().add_class('large-header')
        heading.set_max_width_chars(30)
        heading.set_line_wrap(True)
        heading.set_halign(Gtk.Align.CENTER)
        heading.set_justify(Gtk.Justification.CENTER)
        self.pack_start(heading, False, True, 0)

        self.show_all()

    @property
    def has_form(self):
        return self._current_form is not None

    def _on_is_valid(self, _widget, is_valid):
        self.complete = is_valid
        self.update_page_complete()

    def add_form(self, form):
        self.remove_form()

        options = {'hide-fallback-fields': True,
                   'entry-activates-default': True}
        self._current_form = DataFormWidget(form, options)
        self._current_form.connect('is-valid', self._on_is_valid)
        self._current_form.validate()
        self.pack_start(self._current_form, True, True, 0)
        self._current_form.show_all()

    def get_credentials(self):
        return (self._current_form.get_form()['username'].value,
                self._current_form.get_form()['password'].value)

    def get_submit_form(self):
        return self._current_form.get_submit_form()

    def remove_form(self):
        if self._current_form is None:
            return

        self.remove(self._current_form)
        self._current_form.destroy()
        self._current_form = None

    def focus(self):
        self._current_form.focus_first_entry()

    def get_visible_buttons(self):
        return ['back', 'signup']

    def get_default_button(self):
        return 'signup'


class Redirect(Page):
    def __init__(self):
        Page.__init__(self)
        self.title = _('Redirect')
        self._link = None

        self._ui = get_builder('account_wizard.ui')
        self.pack_start(self._ui.redirect_box, True, True, 0)
        self._ui.link_button.connect('clicked', self._on_link_button)
        self.show_all()

    def set_redirect(self, link, instructions):
        if instructions is None:
            instructions = _('Register on the Website')
        self._ui.instructions.set_text(instructions)
        self._link = link

    def _on_link_button(self, _button):
        open_uri(self._link)

    def get_visible_buttons(self):
        return ['back']


class Success(SuccessPage):
    def __init__(self):
        SuccessPage.__init__(self)
        self.set_title(_('Account Added'))
        self.set_heading(_('Account has been added successfully'))

        self._account = None
        self._our_jid = None
        self._label = None
        self._color = None

        self._ui = get_builder('account_wizard.ui')
        self.pack_start(self._ui.account_label_box, True, True, 0)

        self._provider = self._add_css_provider()

        self._ui.account_name_entry.connect('changed', self._on_name_changed)
        self._ui.account_color_button.connect('color-set', self._on_color_set)

        self.show_all()

    def set_account(self, account):
        self._account = account
        self._our_jid = app.get_jid_from_account(account)
        self._ui.badge_preview.set_text(self._our_jid)
        rgba = Gdk.RGBA()
        rgba.parse(get_color_for_account(self._our_jid))
        self._ui.account_color_button.set_rgba(rgba)
        self._color = rgba.to_string()
        self._set_badge_color(self._color)

    @property
    def account(self):
        return self._account

    def _add_css_provider(self):
        context = self._ui.badge_preview.get_style_context()
        provider = Gtk.CssProvider()
        context.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
        return provider

    def _on_name_changed(self, entry):
        self._label = entry.get_text()
        self._ui.badge_preview.set_text(self._label or self._our_jid)
        self._save_config()

    def _on_color_set(self, button):
        rgba = button.get_rgba()
        self._color = rgba.to_string()
        self._set_badge_color(self._color)
        self._save_config()

    def _set_badge_color(self, color):
        css = '.badge { background-color: %s; font-size: 100%%; }' % color
        self._provider.load_from_data(bytes(css.encode()))

    def _save_config(self):
        app.settings.set_account_setting(
            self._account, 'account_color', self._color)
        if self._label:
            app.settings.set_account_setting(
                self._account, 'account_label', self._label)
        app.css_config.refresh()
        window = get_app_window('AccountsWindow')
        if window is not None:
            window.update_account_label(self._account)

    def get_visible_buttons(self):
        return ['connect']


class Error(ErrorPage):
    def __init__(self):
        ErrorPage.__init__(self)
        self.set_heading(_('An error occurred during account creation'))

    def get_visible_buttons(self):
        return ['back']
