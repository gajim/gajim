# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of OMEMO Gajim Plugin.
#
# OMEMO Gajim Plugin is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# OMEMO Gajim Plugin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OMEMO Gajim Plugin. If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from collections import defaultdict

from gajim.common import app

from gajim.common.modules.omemobackend.util import UNACKNOWLEDGED_COUNT


class DeviceManager:
    def __init__(self) -> None:
        self.__device_store: dict[str, set[int]] = defaultdict(set)
        self.__muc_member_store: dict[str, set[str]] = defaultdict(set)

        reg_id = self._storage.getLocalRegistrationId()
        if reg_id is None:
            raise ValueError('No own device found')

        self.__own_device = reg_id
        self.add_device(self._own_jid, self.__own_device)
        self._log.info('Our device id: %s', self.__own_device)

        for jid, device in self._storage.getActiveDeviceTuples():
            self._log.info('Load device from storage: %s - %s', jid, device)
            self.add_device(jid, device)

    def update_devicelist(self, jid: str, devicelist: list[int]) -> None:
        for device in list(devicelist):
            if device == self.own_device:
                continue
            count = self._storage.getUnacknowledgedCount(jid, device)
            if count > UNACKNOWLEDGED_COUNT:
                self._log.warning('Ignore device because of %s unacknowledged'
                                  ' messages: %s %s', count, jid, device)
                devicelist.remove(device)

        self.__device_store[jid] = set(devicelist)
        self._log.info('Saved devices for %s', jid)
        self._storage.setActiveState(jid, devicelist)

    def add_muc_member(self, room_jid: str, jid: str) -> None:
        self._log.info('Saved MUC member %s %s', room_jid, jid)
        self.__muc_member_store[room_jid].add(jid)

    def remove_muc_member(self, room_jid: str, jid: str) -> None:
        self._log.info('Removed MUC member %s %s', room_jid, jid)
        self.__muc_member_store[room_jid].discard(jid)

    def get_muc_members(self,
                        room_jid: str,
                        without_self: bool = True
                        ) -> set[str]:

        members = set(self.__muc_member_store[room_jid])
        if without_self:
            members.discard(self._own_jid)
        return members

    def add_device(self, jid: str, device: int) -> None:
        self.__device_store[jid].add(device)

    def remove_device(self, jid: str, device: int) -> None:
        self.__device_store[jid].discard(device)
        self._storage.setInactive(jid, device)

    def get_devices(self, jid: str, without_self: bool = False) -> set[int]:
        devices = set(self.__device_store[jid])
        if without_self:
            devices.discard(self.own_device)
        return devices

    def get_devices_for_encryption(self, jid: str) -> set[tuple[str, int]]:
        devices_for_encryption: list[tuple[str, int]] = []

        client = app.get_client(self._account)
        contact = client.get_module('Contacts').get_contact(jid)
        if contact.is_groupchat:
            devices_for_encryption = self._get_devices_for_muc_encryption(jid)
        else:
            devices_for_encryption = self._get_devices_for_encryption(jid)

        if not devices_for_encryption:
            raise NoDevicesFound

        devices_for_encryption += self._get_own_devices_for_encryption()
        return set(devices_for_encryption)

    def _get_devices_for_muc_encryption(self,
                                        jid: str
                                        ) -> list[tuple[str, int]]:

        devices_for_encryption: list[tuple[str, int]] = []
        for jid_ in self.__muc_member_store[jid]:
            devices_for_encryption += self._get_devices_for_encryption(jid_)
        return devices_for_encryption

    def _get_own_devices_for_encryption(self) -> list[tuple[str, int]]:
        devices_for_encryption: list[tuple[str, int]] = []
        own_devices = self.get_devices(self._own_jid, without_self=True)
        for device in own_devices:
            if self._storage.isTrusted(self._own_jid, device):
                devices_for_encryption.append((self._own_jid, device))
        return devices_for_encryption

    def _get_devices_for_encryption(self, jid: str) -> list[tuple[str, int]]:
        devices_for_encryption: list[tuple[str, int]] = []
        devices = self.get_devices(jid)

        for device in devices:
            if self._storage.isTrusted(jid, device):
                devices_for_encryption.append((jid, device))
        return devices_for_encryption

    @property
    def own_device(self) -> int:
        return self.__own_device

    @property
    def devices_for_publish(self) -> set[int]:
        devices = self.get_devices(self._own_jid)
        if self.own_device not in devices:
            devices.add(self.own_device)
        return devices

    @property
    def is_own_device_published(self) -> bool:
        return self.own_device in self.get_devices(self._own_jid)


class NoDevicesFound(Exception):
    pass
