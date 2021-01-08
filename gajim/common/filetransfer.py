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

from typing import Dict

from gajim.common.helpers import Observable
from gajim.common.const import FTState

class FileTransfer(Observable):

    _state_descriptions = {}  # type: Dict[FTState, str]

    def __init__(self, account):
        Observable.__init__(self)

        self._account = account

        self._seen = 0
        self.size = 0

        self._state = None
        self._error_text = ''
        self._error_domain = None

    @property
    def account(self):
        return self._account

    @property
    def state(self):
        return self._state

    @property
    def seen(self):
        return self._seen

    @property
    def is_complete(self):
        if self.size == 0:
            return False
        return self._seen >= self.size

    @property
    def filename(self):
        raise NotImplementedError

    @property
    def error_text(self):
        return self._error_text

    @property
    def error_domain(self):
        return self._error_domain

    def get_state_description(self):
        return self._state_descriptions.get(self._state, '')

    def set_preparing(self):
        self._state = FTState.PREPARING
        self.notify('state-changed', FTState.PREPARING)

    def set_encrypting(self):
        self._state = FTState.ENCRYPTING
        self.notify('state-changed', FTState.ENCRYPTING)

    def set_decrypting(self):
        self._state = FTState.DECRYPTING
        self.notify('state-changed', FTState.DECRYPTING)

    def set_started(self):
        self._state = FTState.STARTED
        self.notify('state-changed', FTState.STARTED)

    def set_error(self, domain, text=''):
        self._error_text = text
        self._error_domain = domain
        self._state = FTState.ERROR
        self.notify('state-changed', FTState.ERROR)
        self.disconnect_signals()

    def set_cancelled(self):
        self._state = FTState.CANCELLED
        self.notify('state-changed', FTState.CANCELLED)
        self.disconnect_signals()

    def set_in_progress(self):
        self._state = FTState.IN_PROGRESS
        self.notify('state-changed', FTState.IN_PROGRESS)

    def set_finished(self):
        self._state = FTState.FINISHED
        self.notify('state-changed', FTState.FINISHED)
        self.disconnect_signals()

    def update_progress(self):
        self.notify('progress')

    def cancel(self):
        self.notify('cancel')
