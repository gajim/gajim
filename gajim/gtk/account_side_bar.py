
from gi.repository import Gtk
from gajim.common.const import AvatarSize
from gajim.common import app


class AccountSideBar(Gtk.ListBox):
    def __init__(self):
        Gtk.ListBox.__init__(self)
        self.set_vexpand(True)
        self.set_valign(Gtk.Align.END)
        self.get_style_context().add_class('account-sidebar')

        self._accounts = list(app.connections.keys())
        for account in self._accounts:
            self.add_account(account)

    def add_account(self, account):
        self.add(Account(account))

    def remove_account(self, account):
        pass


class Account(Gtk.ListBoxRow):
    def __init__(self, account):
        Gtk.ListBoxRow.__init__(self)
        self.get_style_context().add_class('account-sidebar-item')

        self._account = account
        self._jid = app.get_jid_from_account(account)
        contact = app.contacts.create_contact(self._jid, account)

        scale = self.get_scale_factor()
        surface = app.interface.get_avatar(contact,
                                           AvatarSize.ACCOUNT_SIDE_BAR,
                                           scale)
        self._image = Gtk.Image.new_from_surface(surface)

        account_color_bar = Gtk.Box()
        account_color_bar.set_size_request(6, -1)
        account_class = app.css_config.get_dynamic_class(account)
        account_color_bar.get_style_context().add_class(account_class)
        account_color_bar.get_style_context().add_class(
            'account-identifier-bar')

        account_box = Gtk.Box(spacing=6)
        account_box.add(account_color_bar)
        account_box.add(self._image)

        self.add(account_box)
        self.show_all()
