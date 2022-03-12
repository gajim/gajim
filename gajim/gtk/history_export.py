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

from __future__ import annotations

from typing import cast
from typing import Optional

import logging
import time
from datetime import datetime
from pathlib import Path

from gi.repository import Gtk

from gajim.common import app
from gajim.common import configpaths
from gajim.common.const import KindConstant
from gajim.common.helpers import make_path_from_jid
from gajim.common.i18n import _
from gajim.common.storage.archive import MessageExportRow

from .assistant import Assistant
from .assistant import Page
from .assistant import ErrorPage
from .assistant import SuccessPage
from .assistant import ProgressPage
from .builder import get_builder

log = logging.getLogger('gajim.gui.history_export')


class HistoryExport(Assistant):
    def __init__(self, account: Optional[str] = None) -> None:
        Assistant.__init__(self)

        self.account = account

        self.add_button('export',
                        _('Export'),
                        complete=True,
                        css_class='suggested-action')
        self.add_button('close', _('Close'))
        self.add_button('back', _('Back'))
        self.set_button_visible_func(self._visible_func)

        self.add_pages({'start': SelectAccountDir(account)})

        progress_page = cast(ProgressPage, self.add_default_page('progress'))
        progress_page.set_title(_('Exporting History...'))
        progress_page.set_text(_('Exporting your messages...'))

        success_page = cast(SuccessPage, self.add_default_page('success'))
        success_page.set_title(_('Export Finished'))
        success_page.set_text(_('Your messages have been exported successfully'))

        error_page = cast(ErrorPage, self.add_default_page('error'))
        error_page.set_title(_('Error while Exporting'))
        error_page.set_text(_('An error occurred while exporting your messages'))

        self.connect('button-clicked', self._on_button_clicked)
        self.show_all()

    @staticmethod
    def _visible_func(_assistant: Assistant, page_name: str) -> list[str]:
        if page_name == 'start':
            return ['close', 'export']

        if page_name == 'progress':
            return []

        if page_name == 'success':
            return ['back', 'close']

        if page_name == 'error':
            return ['back', 'close']
        raise ValueError(f'page {page_name} unknown')

    def _on_button_clicked(self,
                           _assistant: Assistant,
                           button_name: str
                           ) -> None:
        if button_name == 'export':
            self.show_page('progress', Gtk.StackTransitionType.SLIDE_LEFT)
            self._on_export()

        elif button_name == 'back':
            self.show_page('start', Gtk.StackTransitionType.SLIDE_RIGHT)

        elif button_name == 'close':
            self.destroy()

    def _on_export(self) -> None:
        start_page = cast(SelectAccountDir, self.get_page('start'))
        account, directory = start_page.get_account_and_directory()

        current_time = datetime.now()
        time_str = current_time.strftime('%Y-%m-%d-%H-%M-%S')
        export_dir = Path(directory) / f'export_{time_str}'

        jids = app.storage.archive.get_conversation_jids(account)

        for jid in jids:
            messages = app.storage.archive.get_messages_for_export(account, jid)
            if not messages:
                continue

            file_path = make_path_from_jid(export_dir, jid)
            file_path.mkdir(parents=True, exist_ok=True)
            with open(file_path / 'history.txt', 'w', encoding='utf-8') as file:
                file.write(f'History for {jid}\n\n')
                for message in messages:
                    file.write(self._get_export_line(message))

        self.show_page('success', Gtk.StackTransitionType.SLIDE_LEFT)

    def _get_export_line(self, message: MessageExportRow) -> str:
        if message.kind in (KindConstant.SINGLE_MSG_RECV,
                            KindConstant.CHAT_MSG_RECV):
            name = message.jid
        elif message.kind in (KindConstant.SINGLE_MSG_SENT,
                              KindConstant.CHAT_MSG_SENT):
            name = _('You')
        elif message.kind == KindConstant.GC_MSG:
            name = message.contact_name
        else:
            raise ValueError('Unknown kind: %s' % message.kind)

        timestamp = ''
        try:
            timestamp = time.strftime(
                '%Y-%m-%d %H:%M:%S', time.localtime(message.time))
        except ValueError:
            pass

        return f'{timestamp} {name}: {message.message}\n'


class SelectAccountDir(Page):
    def __init__(self, account: Optional[str]) -> None:
        Page.__init__(self)
        self._account = account
        self._export_directory = str(configpaths.get('MY_DATA'))

        self.title = _('Export Chat History')

        self._ui = get_builder('history_export.ui')
        self.add(self._ui.select_account_box)
        self._ui.connect_signals(self)

        accounts = app.get_enabled_accounts_with_labels()
        liststore = cast(Gtk.ListStore, self._ui.account_combo.get_model())
        for acc in accounts:
            liststore.append(acc)

        if self._account is not None:
            self._ui.account_combo.set_active_id(self._account)
        else:
            self._ui.account_combo.set_active(0)

        self._ui.file_chooser_button.set_current_folder(self._export_directory)

        self._set_complete()

        self.show_all()

    def _on_account_changed(self, combobox: Gtk.ComboBox) -> None:
        account = combobox.get_active_id()
        self._account = account
        self._set_complete()

    def _set_complete(self) -> None:
        self.complete = bool(
            self._account is not None and
            self._export_directory is not None)
        self.update_page_complete()

    def _on_file_set(self, button: Gtk.FileChooserButton) -> None:
        uri = button.get_uri()
        assert uri is not None
        self._export_directory = uri.removeprefix('file://')

    def get_account_and_directory(self) -> tuple[str, str]:
        assert self._account is not None
        assert self._export_directory is not None
        return self._account, self._export_directory
