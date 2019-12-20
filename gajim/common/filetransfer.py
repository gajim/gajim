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


from gajim.common.helpers import Observable
from gajim.common.const import FTState

class FileTransfer(Observable):
    def __init__(self, account):
        Observable.__init__(self)

        self._account = account

        self._seen = 0
        self.size = 0

        self._state = None
        self._error_text = ''

    @property
    def account(self):
        return self._account

    @property
    def seen(self):
        return self._seen

    @property
    def is_complete(self):
        if self.size == 0:
            return False
        return self._seen >= self.size

    def set_preparing(self):
        self._state = FTState.PREPARING
        self.notify('state-changed', FTState.PREPARING)

    def set_encrypting(self):
        self._state = FTState.ENCRYPTING
        self.notify('state-changed', FTState.ENCRYPTING)

    def set_started(self):
        self._state = FTState.STARTED
        self.notify('state-changed', FTState.STARTED)

    def set_error(self, text=''):
        self._error_text = text
        self._state = FTState.ERROR
        self.notify('state-changed', FTState.ERROR)
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
