# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# XEP-0313: Message Archive Management

from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone

import nbxmpp
from nbxmpp.errors import is_error
from nbxmpp.errors import MalformedStanzaError
from nbxmpp.errors import StanzaError
from nbxmpp.modules.util import raise_if_error
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.protocol import Message
from nbxmpp.structs import DiscoInfo
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import StanzaHandler
from nbxmpp.structs import StanzaIDData
from nbxmpp.task import Task
from nbxmpp.util import generate_id

from gajim.common import app
from gajim.common import types
from gajim.common.const import ArchiveState
from gajim.common.const import ClientState
from gajim.common.const import SyncThreshold
from gajim.common.events import ArchivingIntervalFinished
from gajim.common.events import FeatureDiscovered
from gajim.common.events import RawMamMessageReceived
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import as_task
from gajim.common.storage.archive import models as mod
from gajim.common.util.datetime import FIRST_UTC_DATETIME


class MAM(BaseModule):

    _nbxmpp_extends = 'MAM'
    _nbxmpp_methods = [
        'request_preferences',
        'set_preferences',
        'make_query',
    ]

    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._set_message_archive_info,
                          priority=42),
            StanzaHandler(name='message',
                          callback=self._mam_message_received,
                          priority=41),
        ]

        self.available = False
        self._mam_query_ids: dict[str, str] = {}

        # Holds archive jids where catch up was successful
        self._catch_up_finished: list[str] = []

        self._con.connect_signal('state-changed', self._on_client_state_changed)
        self._con.connect_signal('resume-failed', self._on_client_resume_failed)

    def pass_disco(self, info: DiscoInfo) -> None:
        if Namespace.MAM_2 not in info.features:
            return

        self.available = True
        self._log.info('Discovered MAM: %s', info.jid)

        app.ged.raise_event(
            FeatureDiscovered(account=self._account,
                              feature=Namespace.MAM_2))

    def _on_client_resume_failed(self,
                                 _client: types.Client,
                                 _signal_name: str
                                 ) -> None:
        self._reset_state()

    def _on_client_state_changed(self,
                                 _client: types.Client,
                                 _signal_name: str,
                                 state: ClientState
                                 ) -> None:
        if state.is_disconnected:
            self._reset_state()

    def _reset_state(self) -> None:
        self._mam_query_ids.clear()
        self._catch_up_finished.clear()

    def _remove_query_id(self, jid: JID) -> None:
        self._mam_query_ids.pop(jid, None)

    def is_catch_up_finished(self, jid: str) -> bool:
        return jid in self._catch_up_finished

    def _from_valid_archive(self,
                            _stanza: Message,
                            properties: MessageProperties
                            ) -> bool:
        if properties.type.is_groupchat:
            expected_archive = properties.jid
        else:
            expected_archive = self._con.get_own_jid()

        return properties.mam.archive.bare_match(expected_archive)

    @staticmethod
    def _get_stanza_id(properties: MessageProperties,
                       archive_jid: str
                       ) -> StanzaIDData | None:
        for stanza_id in properties.stanza_ids:
            if stanza_id.by == archive_jid:
                return stanza_id
        return None

    def _set_message_archive_info(self,
                                  _con: types.xmppClient,
                                  _stanza: Message,
                                  properties: MessageProperties
                                  ) -> None:
        if (properties.is_mam_message or
                properties.is_pubsub or
                properties.is_muc_subject):
            return

        if properties.type.is_groupchat:
            archive_jid = properties.jid.bare
            timestamp = properties.timestamp

            disco_info = app.storage.cache.get_last_disco_info(archive_jid)
            if disco_info is None:
                # This is the case on MUC creation
                # After MUC configuration we receive a configuration change
                # message before we had the chance to disco the new MUC
                return

            if disco_info.mam_namespace != Namespace.MAM_2:
                return

        else:
            if not self.available:
                return

            archive_jid = self._con.get_own_jid().bare
            timestamp = None

        if not properties.stanza_ids:
            return

        stanza_id = self._get_stanza_id(properties, archive_jid)
        if stanza_id is None:
            return

        if not self.is_catch_up_finished(archive_jid):
            return

        if timestamp is not None:
            timestamp = datetime.fromtimestamp(timestamp, timezone.utc)

        app.storage.archive.upsert_row(
            mod.MAMArchiveState(
                account_=self._account,
                remote_jid_=JID.from_string(archive_jid),
                to_stanza_id=stanza_id.id,
                to_stanza_ts=timestamp,
            )
        )

    def _mam_message_received(self,
                              _con: types.xmppClient,
                              stanza: Message,
                              properties: MessageProperties
                              ) -> None:

        if not properties.is_mam_message:
            return

        app.ged.raise_event(
            RawMamMessageReceived(account=self._account,
                                  stanza=stanza,
                                  properties=properties))

        if not self._from_valid_archive(stanza, properties):
            self._log.warning('Message from invalid archive %s',
                              properties.mam.archive)
            raise nbxmpp.NodeProcessed

        self._log.info('Received message from archive: %s',
                       properties.mam.archive)
        if not self._is_valid_request(properties):
            self._log.warning('Invalid MAM Message: unknown query id %s',
                              properties.mam.query_id)
            self._log.warning(stanza)
            raise nbxmpp.NodeProcessed

        stanza_id = self._get_stanza_id(properties, properties.mam.archive)
        if stanza_id is None:
            self._log.warning('Unable to determine stanza id')
            self._log.warning(stanza)
            raise nbxmpp.NodeProcessed

        if app.storage.archive.check_if_stanza_id_exists(
            self._account, properties.remote_jid, stanza_id.id):
            self._log.info('Received duplicated message from MAM: %s', stanza_id.id)
            raise nbxmpp.NodeProcessed

    def _is_valid_request(self, properties: MessageProperties) -> bool:
        valid_id = self._mam_query_ids.get(properties.mam.archive, None)
        return valid_id == properties.mam.query_id

    def _get_query_id(self, jid: str) -> str:
        query_id = generate_id()
        self._mam_query_ids[jid] = query_id
        return query_id

    def _get_query_params(self) -> tuple[str | None, datetime | None]:
        own_jid = self._con.get_own_jid().bare
        archive = app.storage.archive.get_mam_archive_state(
            self._account, own_jid)

        mam_id = None
        if archive is not None:
            mam_id = archive.to_stanza_id

        start_date = None
        if mam_id:
            self._log.info('Request archive: %s, after mam-id %s',
                           own_jid, mam_id)

        else:
            # First Start, we request the last week
            start_date = datetime.now(timezone.utc) - timedelta(days=7)
            self._log.info('Request archive: %s, after date %s',
                           own_jid, start_date)
        return mam_id, start_date

    def _get_muc_query_params(self,
                              jid: JID,
                              threshold: SyncThreshold
                              ) -> tuple[str | None, datetime | None]:

        archive = app.storage.archive.get_mam_archive_state(self._account, jid)
        mam_id = None
        start_date = None
        now = datetime.now(timezone.utc)

        if archive is None or archive.to_stanza_id is None:
            # First join
            start_date = now - timedelta(days=1)
            self._log.info('Request archive: %s, after date %s',
                           jid, start_date)

        elif threshold == SyncThreshold.NO_THRESHOLD:
            # Not our first join and no threshold set

            mam_id = archive.to_stanza_id
            self._log.info('Request archive: %s, after mam-id %s',
                           jid, archive.to_stanza_id)

        else:
            # Not our first join, check how much time elapsed since our
            # last join and check against threshold
            last = archive.to_stanza_ts
            if last is None:
                self._log.info('No last muc timestamp found: %s', jid)
                last = FIRST_UTC_DATETIME

            if now - last > timedelta(days=threshold):
                # To much time has elapsed since last join, apply threshold
                start_date = now - timedelta(days=threshold)
                self._log.info('Too much time elapsed since last join, '
                               'request archive: %s, after date %s, '
                               'threshold: %s', jid, start_date, threshold)

            else:
                # Request from last mam-id
                mam_id = archive.to_stanza_id
                self._log.info('Request archive: %s, after mam-id %s:',
                               jid, archive.to_stanza_id)

        return mam_id, start_date

    @as_task
    def request_archive_on_signin(self):
        _task = yield  # noqa: F841

        own_jid = self._con.get_own_jid().bare

        if own_jid in self._mam_query_ids:
            self._log.warning('request already running for %s', own_jid)
            return

        mam_id, start_date = self._get_query_params()

        result = yield self._execute_query(own_jid, mam_id, start_date)
        if is_error(result):
            if result.condition != 'item-not-found':
                self._log.warning(result)
                return

            self._log.warning(result)
            self._log.warning('Reset archive state: %s', own_jid)
            app.storage.archive.reset_mam_archive_state(
                self._account, result.jid)
            _, start_date = self._get_query_params()
            result = yield self._execute_query(result.jid, None, start_date)
            if is_error(result):
                self._log.warning(result)
                return

        if result.rsm.last is not None:
            # <last> is not provided if the requested page was empty
            # so this means we did not get anything hence we only need
            # to update the archive info if <last> is present
            app.storage.archive.upsert_row(
                mod.MAMArchiveState(
                    account_=self._account,
                    remote_jid_=result.jid,
                    to_stanza_id=result.rsm.last,
                    to_stanza_ts=datetime.now(timezone.utc),
                )
            )

        if start_date is not None:
            # Record the earliest timestamp we request from
            # the account archive. For the account archive we only
            # set start_date at the very first request.
            app.storage.archive.upsert_row(
                mod.MAMArchiveState(
                    account_=self._account,
                    remote_jid_=result.jid,
                    from_stanza_ts=start_date
                )
            )

    @as_task
    def request_archive_on_muc_join(self, jid: JID):
        _task = yield  # noqa: F841

        threshold = app.settings.get_group_chat_setting(self._account,
                                                        jid,
                                                        'sync_threshold')
        self._log.info('Threshold for %s: %s', jid, threshold)

        if threshold == SyncThreshold.NO_SYNC:
            return

        contact = self._get_contact(jid, groupchat=True)
        contact.notify('mam-sync-started')

        mam_id, start_date = self._get_muc_query_params(jid, threshold)

        result = yield self._execute_query(jid, mam_id, start_date)
        if is_error(result):
            if result.condition != 'item-not-found':
                self._log.warning(result)
                contact.notify('mam-sync-error', result.get_text())
                return

            self._log.warning(result)
            self._log.warning('Reset archive state: %s', jid)
            app.storage.archive.reset_mam_archive_state(
                self._account, result.jid)
            _, start_date = self._get_muc_query_params(jid, threshold)
            result = yield self._execute_query(result.jid, None, start_date)
            if is_error(result):
                self._log.warning(result)
                contact.notify('mam-sync-error', result.get_text())
                return

        if result.rsm.last is not None:
            # <last> is not provided if the requested page was empty
            # so this means we did not get anything hence we only need
            # to update the archive info if <last> is present
            app.storage.archive.upsert_row(
                mod.MAMArchiveState(
                    account_=self._account,
                    remote_jid_=result.jid,
                    to_stanza_id=result.rsm.last,
                    to_stanza_ts=datetime.now(timezone.utc)
                )
            )

        contact.notify('mam-sync-finished')

    @as_task
    def _execute_query(self,
                       jid: JID,
                       mam_id: str | None,
                       start_date: datetime | None
                       ):
        _task = yield  # noqa: F841

        if jid in self._catch_up_finished:
            self._catch_up_finished.remove(jid)

        queryid = self._get_query_id(jid)

        result = yield self.make_query(jid,
                                       queryid,
                                       after=mam_id,
                                       start=start_date)

        self._remove_query_id(result.jid)

        raise_if_error(result)

        while not result.complete:
            app.storage.archive.upsert_row(
                mod.MAMArchiveState(
                    account_=self._account,
                    remote_jid_=result.jid,
                    to_stanza_id=result.rsm.last,
                )
            )

            queryid = self._get_query_id(result.jid)

            result = yield self.make_query(result.jid,
                                           queryid,
                                           after=result.rsm.last,
                                           start=start_date)

            self._remove_query_id(result.jid)

            raise_if_error(result)

        self._catch_up_finished.append(result.jid)
        self._log.info('Request finished: %s, last mam id: %s',
                       result.jid, result.rsm.last)
        yield result

    def request_archive_interval(self,
                                 start_date: datetime,
                                 end_date: datetime,
                                 after: str | None = None,
                                 queryid: str | None = None
                                 ) -> str:

        jid = self._con.get_own_jid().bare

        if after is None:
            self._log.info('Request interval: %s, from %s to %s',
                           jid, start_date, end_date)
        else:
            self._log.info('Request page: %s, after %s', jid, after)

        if queryid is None:
            queryid = self._get_query_id(jid)
        self._mam_query_ids[jid] = queryid

        self.make_query(jid,
                        queryid,
                        after=after,
                        start=start_date,
                        end=end_date,
                        callback=self._on_interval_result,
                        user_data=(queryid, start_date, end_date))
        return queryid

    def _on_interval_result(self, task: Task) -> None:
        queryid, start_date, end_date = task.get_user_data()

        try:
            result = task.finish()
        except (StanzaError, MalformedStanzaError) as error:
            self._remove_query_id(error.jid)
            return

        self._remove_query_id(result.jid)

        if start_date:
            timestamp = start_date
        else:
            timestamp = ArchiveState.ALL

        if result.complete:
            self._log.info('Request finished: %s, last mam id: %s',
                           result.jid, result.rsm.last)
            app.storage.archive.upsert_row(
                mod.MAMArchiveState(
                    account_=self._account,
                    remote_jid_=result.jid,
                    from_stanza_ts=timestamp,
                )
            )

            app.ged.raise_event(ArchivingIntervalFinished(
                account=self._account,
                query_id=queryid))

        else:
            self.request_archive_interval(start_date,
                                          end_date,
                                          result.rsm.last,
                                          queryid)
