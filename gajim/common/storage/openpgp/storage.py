# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Iterable
from pathlib import Path

import pysequoia as pys
import sqlalchemy as sa
from nbxmpp.protocol import JID
from pysequoia import packet as pyspacket
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import gajim.common.storage.openpgp.models as mod
from gajim.common import app
from gajim.common import configpaths
from gajim.common.const import Trust
from gajim.common.storage.base import AlchemyStorage
from gajim.common.storage.base import timeit
from gajim.common.storage.base import VALUE_MISSING
from gajim.common.storage.base import ValueMissingT
from gajim.common.storage.base import with_session
from gajim.common.storage.openpgp.models import Account
from gajim.common.storage.openpgp.models import Base

CURRENT_USER_VERSION = 1

log = logging.getLogger("gajim.c.storage.openpgp")


class OpenPGPStorage(AlchemyStorage):
    def __init__(self, *, in_memory: bool = False, path: Path | None = None) -> None:
        if path is None:
            path = Path(configpaths.get("MY_DATA")) / "openpgp.db"

        AlchemyStorage.__init__(
            self,
            log,
            None if in_memory else path,
            pragma={
                "secure_delete": "on",
            },
        )

        self._account_pks: dict[str, int] = {}

    def _create_table(self, session: Session, engine: Engine) -> None:
        Base.metadata.create_all(engine)
        session.execute(sa.text(f"PRAGMA user_version={CURRENT_USER_VERSION}"))

    def _migrate(self) -> None:
        pass

    def _get_account_pk(self, session: Session, account: str) -> int:
        pk = self._account_pks.get(account)
        if pk is not None:
            return pk

        jid_str = app.get_jid_from_account(account)
        jid = JID.from_string(jid_str)

        pk = session.scalar(sa.select(Account.pk).where(Account.jid == jid))
        if pk is None:
            acc = Account(jid=jid)
            session.add(acc)
            session.flush()
            pk = acc.pk

        self._account_pks[account] = pk
        return pk

    @with_session
    @timeit
    def store_secret_key(
        self, session: Session, account: str, key: pys.Cert, backup_password: str | None
    ) -> None:
        assert key.secrets is not None

        fk_account_pk = self._get_account_pk(session, account)
        secret = mod.Secret(
            fk_account_pk=fk_account_pk,
            key=bytes(key.secrets),
            backup_password=backup_password,
        )
        log.info("Store secret key for %s", fk_account_pk)
        session.add(secret)

        try:
            session.commit()
        except Exception:
            log.exception("Unable to store secret key")

    @with_session
    @timeit
    def store_secret_key_backup_password(
        self, session: Session, account: str, backup_password: str
    ) -> None:
        log.info("Store secret key backup password for %s", account)

        fk_account_pk = self._get_account_pk(session, account)
        stmt = (
            sa.update(mod.Secret)
            .where(
                mod.Secret.fk_account_pk == fk_account_pk,
            )
            .values(backup_password=backup_password)
        )
        session.execute(stmt)

    @with_session
    @timeit
    def get_secret_key(
        self, session: Session, account: str
    ) -> tuple[mod.Secret, dt.datetime] | None:

        fk_account_pk = self._get_account_pk(session, account)
        stmt = sa.select(mod.Secret).where(mod.Secret.fk_account_pk == fk_account_pk)
        if row := session.scalar(stmt):
            date = None
            pile = pyspacket.PacketPile.from_bytes(row.key)
            for packet in pile:
                if packet.tag == pyspacket.Tag.SecretKey:
                    if date := packet.key_created:
                        break

            return row, date or dt.datetime(1990, 1, 1, tzinfo=dt.UTC)

        return None

    @with_session
    @timeit
    def store_public_key(
        self,
        session: Session,
        account: str,
        jid: JID,
        cert: pys.Cert,
        trust: Trust,
    ) -> None:

        fk_account_pk = self._get_account_pk(session, account)

        fingerprint = cert.fingerprint.upper()

        public = mod.Public(
            fk_account_pk=fk_account_pk,
            remote_jid=jid,
            key=cert,
            fingerprint=fingerprint,
            trust=trust,
        )
        log.info("Store public key for %s, %s, %s", jid, fingerprint, trust)
        session.add(public)

        try:
            session.commit()
        except IntegrityError:
            log.debug("Unable to store public key, key is already stored")

        except Exception:
            log.exception("Unable to store public key")

    @with_session
    @timeit
    def update_public_keys(
        self,
        session: Session,
        account: str,
        jid: JID,
        fingerprints: Iterable[str] | None = None,
        *,
        label: str | None | ValueMissingT = VALUE_MISSING,
        trust: Trust | ValueMissingT = VALUE_MISSING,
        active: bool | ValueMissingT = VALUE_MISSING,
        last_seen: dt.datetime | ValueMissingT = VALUE_MISSING,
    ) -> None:

        fk_account_pk = self._get_account_pk(session, account)

        values = {
            "label": label,
            "trust": trust,
            "active": active,
            "last_seen": last_seen,
        }
        values = {k: v for k, v in values.items() if v is not VALUE_MISSING}

        fingerprints = set(map(str.upper, fingerprints or set()))

        log.info("Update public key for %s, %s, %s", jid, fingerprints, values)

        stmt = sa.update(mod.Public).where(
            mod.Public.fk_account_pk == fk_account_pk,
            mod.Public.remote_jid == jid,
        )

        if fingerprints:
            stmt = stmt.where(mod.Public.fingerprint.in_(fingerprints))

        stmt = stmt.values(**values)
        session.execute(stmt)

    def get_public_key_from_secret(
        self, account: str, jid: JID, cert: pys.Cert
    ) -> mod.Public:

        return mod.Public(
            fk_account_pk=0,
            remote_jid=jid,
            key=cert,
            fingerprint=cert.fingerprint.upper(),
            trust=Trust.VERIFIED,
        )

    @with_session
    @timeit
    def get_public_key(
        self, session: Session, account: str, jid: JID, fingerprint: str
    ) -> mod.Public | None:

        fk_account_pk = self._get_account_pk(session, account)

        stmt = sa.select(mod.Public).where(
            mod.Public.fk_account_pk == fk_account_pk,
            mod.Public.remote_jid == jid,
            mod.Public.fingerprint == fingerprint.upper(),
        )
        return session.scalar(stmt)

    @with_session
    @timeit
    def get_public_keys(
        self,
        session: Session,
        account: str,
        jids: list[JID],
        *,
        trust: list[Trust] | None = None,
        only_active: bool = True,
    ) -> list[mod.Public]:

        fk_account_pk = self._get_account_pk(session, account)

        stmt = sa.select(mod.Public).where(
            mod.Public.fk_account_pk == fk_account_pk,
            mod.Public.remote_jid.in_(jids),
        )
        if trust is not None:
            stmt = stmt.where(mod.Public.trust.in_(trust))

        if only_active:
            stmt = stmt.where(mod.Public.active == only_active)

        return list(session.scalars(stmt).all())

    @with_session
    @timeit
    def remove_public_key(
        self, session: Session, account: str, jid: JID, fingerprint: str
    ) -> None:

        fk_account_pk = self._get_account_pk(session, account)

        stmt = sa.delete(mod.Public).where(
            mod.Public.fk_account_pk == fk_account_pk,
            mod.Public.remote_jid == jid,
            mod.Public.fingerprint == fingerprint.upper(),
        )
        session.execute(stmt)

    @timeit
    def get_known_fingerprints(
        self,
        account: str,
        jids: list[JID],
        *,
        trust: list[Trust] | None = None,
    ) -> set[str]:

        keys = self.get_public_keys(account, jids, trust=trust, only_active=False)
        return {k.fingerprint for k in keys}

    @with_session
    @timeit
    def remove_account(self, session: Session, account: str) -> None:
        fk_account_pk = self._get_account_pk(session, account)

        session.execute(sa.delete(Account).where(Account.pk == fk_account_pk))

        self._account_pks.pop(account)
