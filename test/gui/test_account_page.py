# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later
# pyright: reportPrivateUsage=false

from __future__ import annotations

from typing import Any
from typing import cast

import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

from gi.repository import GLib

from gajim.gtk import account_page
from gajim.gtk.account_page import AccountPage


class AccountPageNavigationTest(unittest.TestCase):
    def test_background_operation_does_not_block_navigation(self) -> None:
        page = MagicMock(spec=AccountPage)
        page._has_operations.return_value = True
        callback = MagicMock()

        AccountPage.confirm_navigation(cast(Any, page), callback)

        callback.assert_called_once_with()
        page._navigate.assert_not_called()

    def test_idle_navigation_uses_navigation_guard(self) -> None:
        page = MagicMock(spec=AccountPage)
        page._has_operations.return_value = False
        callback = MagicMock()

        AccountPage.confirm_navigation(cast(Any, page), callback)

        callback.assert_not_called()
        page._navigate.assert_called_once_with(callback, callback)


class AvatarPublishStatusTest(unittest.TestCase):
    def test_status_is_delayed(self) -> None:
        page = MagicMock(spec=AccountPage)
        state = MagicMock()

        with patch.object(GLib, "timeout_add", return_value=42) as timeout_add:
            AccountPage._schedule_avatar_publish_status(
                cast(Any, page), cast(Any, state)
            )

        page._hide_avatar_publish_status.assert_called_once_with()
        timeout_add.assert_called_once_with(
            account_page._AVATAR_PUBLISH_STATUS_DELAY_MS,
            page._show_avatar_publish_status,
            state,
        )
        self.assertEqual(page._avatar_publish_status_timeout_id, 42)

    def test_status_is_shown_for_matching_publish(self) -> None:
        page = MagicMock(spec=AccountPage)
        state = MagicMock()
        page._avatar_publish = state

        result = AccountPage._show_avatar_publish_status(
            cast(Any, page), cast(Any, state)
        )

        self.assertEqual(result, GLib.SOURCE_REMOVE)
        self.assertIsNone(page._avatar_publish_status_timeout_id)
        page._avatar_publish_status.set_visible.assert_called_once_with(True)
