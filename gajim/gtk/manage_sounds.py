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

import os

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common.helpers import play_sound
from gajim.common.helpers import check_soundfile_path
from gajim.common.helpers import strip_soundfile_path
from gajim.common.i18n import _

from .builder import get_builder


class ManageSounds(Gtk.ApplicationWindow):
    def __init__(self, transient_for: Gtk.Window) -> None:
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_name('ManageSounds')
        self.set_default_size(400, 400)
        self.set_resizable(True)
        self.set_transient_for(transient_for)
        self.set_modal(True)
        self.set_title(_('Manage Sounds'))

        self._ui = get_builder('manage_sounds.ui')
        self.add(self._ui.manage_sounds)

        filter_ = Gtk.FileFilter()
        filter_.set_name(_('All files'))
        filter_.add_pattern('*')
        self._ui.filechooser.add_filter(filter_)

        filter_ = Gtk.FileFilter()
        filter_.set_name(_('Wav Sounds'))
        filter_.add_pattern('*.wav')
        self._ui.filechooser.add_filter(filter_)
        self._ui.filechooser.set_filter(filter_)

        self._fill_sound_treeview()

        self.connect('key-press-event', self._on_key_press)
        self._ui.connect_signals(self)

        self.show_all()

    @staticmethod
    def _on_row_changed(model: Gtk.TreeModel,
                        path: Gtk.TreePath,
                        iter_: Gtk.TreeIter
                        ) -> None:
        sound_event = model[iter_][3]
        app.settings.set_soundevent_setting(sound_event,
                                            'enabled',
                                            bool(model[path][0]))
        app.settings.set_soundevent_setting(sound_event,
                                            'path',
                                            model[iter_][2])

    def _on_toggle(self,
                   _cell: Gtk.CellRendererToggle,
                   path: Gtk.TreePath
                   ) -> None:
        if self._ui.filechooser.get_filename() is None:
            return
        model = self._ui.sounds_treeview.get_model()
        model[path][0] = not model[path][0]

    def _fill_sound_treeview(self) -> None:
        model = self._ui.sounds_treeview.get_model()
        model.clear()

        sounds_dict = {
            'attention_received': _('Attention Message Received'),
            'first_message_received': _('Message Received'),
            'contact_connected': _('Contact Connected'),
            'contact_disconnected': _('Contact Disconnected'),
            'message_sent': _('Message Sent'),
            'muc_message_highlight': _('Group Chat Message Highlight'),
            'muc_message_received': _('Group Chat Message Received'),
        }

        for sound_event, sound_name in sounds_dict.items():
            settings = app.settings.get_soundevent_settings(sound_event)
            model.append((settings['enabled'],
                          sound_name,
                          settings['path'],
                          sound_event))

    def _on_cursor_changed(self, treeview: Gtk.TreeView) -> None:
        model, iter_ = treeview.get_selection().get_selected()
        path_to_snd_file = check_soundfile_path(model[iter_][2])
        if path_to_snd_file is None:
            self._ui.filechooser.unselect_all()
        else:
            self._ui.filechooser.set_filename(str(path_to_snd_file))

    def _on_file_set(self, button: Gtk.FileChooserButton) -> None:
        model, iter_ = self._ui.sounds_treeview.get_selection().get_selected()

        filename = button.get_filename()
        directory = os.path.dirname(filename)
        app.settings.set('last_sounds_dir', directory)
        path_to_snd_file = strip_soundfile_path(filename)

        # set new path to sounds_model
        model[iter_][2] = str(path_to_snd_file)
        # set the sound to enabled
        model[iter_][0] = True

    def _on_clear(self, _button: Gtk.Button) -> None:
        self._ui.filechooser.unselect_all()
        model, iter_ = self._ui.sounds_treeview.get_selection().get_selected()
        model[iter_][2] = ''
        model[iter_][0] = False

    def _on_play(self, _button: Gtk.Button) -> None:
        model, iter_ = self._ui.sounds_treeview.get_selection().get_selected()
        snd_event_config_name = model[iter_][3]
        play_sound(snd_event_config_name, None, force=True)

    def _on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> None:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()
