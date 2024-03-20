import tempfile
from unittest.mock import MagicMock

from gi.repository import Gdk
from gi.repository import Gtk
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common import configpaths
from gajim.common.const import AvatarSize
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import ContactSettings
from gajim.common.preview import PreviewManager
from gajim.common.settings import Settings
from gajim.common.storage.archive import models as mod
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageState
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.archive.storage import MessageArchiveStorage
from gajim.common.storage.events.storage import EventStorage
from gajim.common.util.datetime import utc_now

from gajim.gtk.avatar import generate_default_avatar
from gajim.gtk.control import ChatControl

ACCOUNT = 'me@test.tld'
FROM_JID = 'contact@test.tld'
BASE_TIMESTAMP = 1672531200


class ConversationViewTest(Gtk.ApplicationWindow):
    def __init__(self) -> None:
        Gtk.ApplicationWindow.__init__(self)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_size_request(800, 800)
        self.set_title('Test ConversationView')

        self._chat_control = ChatControl()
        app.settings.set('hide_groupchat_occupants_list', True)

        contact = self._get_contact()
        self._chat_control.switch_contact(contact)

        jump_to_button = Gtk.Button(label='Jump to 500')
        jump_to_button.connect('clicked', self._on_jump_to_clicked)
        button_box = Gtk.Box(
            spacing=6,
            halign=Gtk.Align.CENTER,
            margin_bottom=6)
        button_box.add(jump_to_button)

        box = Gtk.Box(spacing=6, orientation=Gtk.Orientation.VERTICAL)
        box.add(self._chat_control.widget)
        box.add(button_box)
        self.add(box)

        self.show_all()
        self.connect('key-press-event', self._on_key_press_event)

    def _get_contact(self) -> BareContact:
        contact = MagicMock(spec='BareContact')
        contact.connect = MagicMock()
        contact.account = ACCOUNT
        contact.jid = FROM_JID
        contact.name = 'Test Contact'
        contact.is_groupchat = False
        avatar = generate_default_avatar(
            'T',
            (0.2, 0.1, 0.7),
            AvatarSize.ROSTER,
            1)
        contact.get_avatar = MagicMock(return_value=avatar)
        contact.settings = ContactSettings(ACCOUNT, JID.from_string(ACCOUNT))
        return contact

    def _on_key_press_event(self,
                            _widget: Gtk.Widget,
                            event: Gdk.EventKey
                            ) -> None:

        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _on_jump_to_clicked(self, _button: Gtk.Button) -> None:
        # BASE_TIMESTAMP + 500
        self._chat_control.scroll_to_message(500, utc_now())


def add_archive_messages() -> None:
    remote_jid = JID.from_string(FROM_JID)
    timestamp = BASE_TIMESTAMP
    for num in range(1000):
        message_data = mod.Message(
            account_=ACCOUNT,
            remote_jid_=remote_jid,
            type=MessageType.CHAT,
            direction=ChatDirection.INCOMING,
            timestamp=utc_now(),
            state=MessageState.ACKNOWLEDGED,
            resource=None,
            text=str(num),
            id=str(num),
            stanza_id=str(num),
        )

        app.storage.archive.insert_object(message_data)

        timestamp += 1


app.get_client = MagicMock()
app.window = MagicMock()

app.settings = Settings(in_memory=True)
app.settings.init()
app.settings.add_account(ACCOUNT)

app.storage.events = EventStorage()
app.storage.events.init()

app.storage.archive = MessageArchiveStorage(in_memory=True)
app.storage.archive.init()
add_archive_messages()

configpaths.set_separation(True)
configpaths.set_config_root(tempfile.gettempdir())
configpaths.init()

app.preview_manager = PreviewManager()

win = ConversationViewTest()
win.connect('destroy', Gtk.main_quit)
win.show_all()

Gtk.main()
