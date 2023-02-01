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

from typing import Optional

from gajim.common.const import FTState
from gajim.common.helpers import Observable


class FileTransfer(Observable):

    _state_descriptions: dict[FTState, str] = {}

    def __init__(self, account: str) -> None:
        Observable.__init__(self)

        self._account = account

        self._progress = 0

        self._state = FTState.INIT
        self._error_text: str = ''
        self._error_domain: Optional[str] = None

    @property
    def account(self) -> str:
        return self._account

    @property
    def state(self) -> FTState:
        return self._state

    @property
    def filename(self) -> str:
        raise NotImplementedError

    @property
    def error_text(self) -> str:
        return self._error_text

    @property
    def error_domain(self) -> Optional[str]:
        return self._error_domain

    def get_progress(self) -> float:
        return self._progress

    def set_progress(self, progress: float) -> None:
        self._progress = progress
        self.update_progress()

    def get_state_description(self) -> str:
        return self._state_descriptions.get(self._state, '')

    def set_preparing(self) -> None:
        self._state = FTState.PREPARING
        self.notify('state-changed', FTState.PREPARING)

    def set_encrypting(self) -> None:
        self._state = FTState.ENCRYPTING
        self.notify('state-changed', FTState.ENCRYPTING)

    def set_decrypting(self) -> None:
        self._state = FTState.DECRYPTING
        self.notify('state-changed', FTState.DECRYPTING)

    def set_started(self) -> None:
        self._state = FTState.STARTED
        self.notify('state-changed', FTState.STARTED)

    def set_error(self, domain: str, text: str = '') -> None:
        self._error_text = text
        self._error_domain = domain
        self._state = FTState.ERROR
        self.notify('state-changed', FTState.ERROR)
        self.disconnect_signals()

    def set_cancelled(self) -> None:
        self._state = FTState.CANCELLED
        self.notify('state-changed', FTState.CANCELLED)
        self.disconnect_signals()

    def set_in_progress(self) -> None:
        self._state = FTState.IN_PROGRESS
        self.notify('state-changed', FTState.IN_PROGRESS)

    def set_finished(self) -> None:
        self._state = FTState.FINISHED
        self.notify('state-changed', FTState.FINISHED)
        self.disconnect_signals()

    def update_progress(self) -> None:
        self.notify('progress')

    def cancel(self) -> None:
        self.notify('cancel')
