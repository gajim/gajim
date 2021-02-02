

from gi.repository import Gtk

from gajim.common import app
from gajim.chat_control import ChatControl
from gajim.groupchat_control import GroupchatControl

from gajim.common.i18n import _


class ChatStack(Gtk.Stack):
    def __init__(self):
        Gtk.Stack.__init__(self)

        self.set_vexpand(True)
        self.set_hexpand(True)

        self.add_named(Gtk.Box(), 'empty')

        self.show_all()
        self._controls = {}

    def get_control(self, account, jid):
        try:
            return self._controls[(account, jid)]
        except KeyError:
            return None

    def get_controls(self, account=None):
        if account is None:
            for control in self._controls.values():
                yield control
            return

        for key, control in self._controls.items():
            if key[0] == account:
                yield control

    def add_chat(self, account, jid):
        if self._controls.get((account, jid)) is not None:
            # Control is already in the Stack
            return

        mw = self.get_toplevel()
        contact = app.contacts.create_contact(jid, account)
        chat_control = ChatControl(mw, contact, account, None, None)
        self._controls[(account, jid)] = chat_control
        self.add_named(chat_control.widget, f'{account}:{jid}')
        chat_control.widget.show_all()

    def add_group_chat(self, account, jid):
        if self._controls.get((account, jid)) is not None:
            return
        avatar_sha = app.storage.cache.get_muc_avatar_sha(jid)
        contact = app.contacts.create_contact(jid=jid,
                                              account=account,
                                              groups=[_('Group chats')],
                                              sub='none',
                                              avatar_sha=avatar_sha,
                                              groupchat=True)
        app.contacts.add_contact(account, contact)

        # muc_data = self._create_muc_data(account,
        #                                  room_jid,
        #                                  nick,
        #                                  password,
        #                                  None)

        mw = self.get_toplevel()
        control = GroupchatControl(mw, contact, None, account)
        self._controls[(account, jid)] = control
        self.add_named(control.widget, f'{account}:{jid}')
        control.widget.show_all()

    def remove_chat(self, account, jid):
        control = self._controls.pop((account, jid))
        self.remove(control.widget)
        control.shutdown()

    def show_chat(self, account, jid):
        self.set_visible_child_name(f'{account}:{jid}')

    def clear(self):
        self.set_visible_child_name('empty')

    def update(self, event):
        control = self.get_control(event.account, event.jid)

        typ = ''
        if event.properties.is_sent_carbon:
            typ = 'out'

        control.add_message(event.msgtxt,
                            typ,
                            tim=event.properties.timestamp,
                            subject=event.properties.subject,
                            displaymarking=event.displaymarking,
                            msg_log_id=event.msg_log_id,
                            message_id=event.properties.id,
                            correct_id=event.correct_id,
                            additional_data=event.additional_data)
