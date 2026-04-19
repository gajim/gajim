# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Iterable
from collections.abc import Sequence
from pathlib import Path

import pysequoia as pys
import sqlalchemy as sa
from nbxmpp.protocol import JID
from pysequoia import packet as pyspacket
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import gajim.common.storage.openpgp.models as mod
from gajim.common import configpaths
from gajim.common.const import Trust
from gajim.common.storage.base import AlchemyStorage
from gajim.common.storage.base import timeit
from gajim.common.storage.base import VALUE_MISSING
from gajim.common.storage.base import ValueMissingT
from gajim.common.storage.base import with_session
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

    def _create_table(self, session: Session, engine: Engine) -> None:
        Base.metadata.create_all(engine)
        session.execute(sa.text(f"PRAGMA user_version={CURRENT_USER_VERSION}"))

    def _migrate(self) -> None:
        pass

    @with_session
    @timeit
    def store_secret_key(self, session: Session, jid: JID, key: pys.Cert) -> None:
        secret = mod.Secret(jid=jid, key=key)
        log.info("Store secret key for %s", jid)
        session.add(secret)

        try:
            session.commit()
        except Exception:
            log.exception("Unable to store secret key")

    @with_session
    @timeit
    def get_secret_key(
        self, session: Session, jid: JID
    ) -> tuple[pys.Cert, dt.datetime] | None:
        stmt = sa.select(mod.Secret).where(mod.Secret.jid == jid)
        if row := session.scalar(stmt):
            date = None
            pile = pyspacket.PacketPile.from_bytes(str(row.key).encode())
            for packet in pile:
                if packet.tag == pyspacket.Tag.PublicKey:
                    if date := packet.key_created:
                        break

            return row.key, date or dt.datetime(1990, 1, 1, tzinfo=dt.UTC)

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

        fingerprint = cert.fingerprint.upper()

        public = mod.Public(
            account=account,
            jid=jid,
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
            mod.Public.account == account,
            mod.Public.jid == jid,
        )

        if fingerprints:
            stmt = stmt.where(mod.Public.fingerprint.in_(fingerprints))

        stmt = stmt.values(**values)
        session.execute(stmt)

    @with_session
    @timeit
    def get_public_key(
        self, session: Session, account: str, jid: JID, fingerprint: str
    ) -> mod.Public | None:
        stmt = sa.select(mod.Public).where(
            mod.Public.account == account,
            mod.Public.jid == jid,
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
    ) -> Sequence[mod.Public]:
        stmt = sa.select(mod.Public).where(
            mod.Public.account == account,
            mod.Public.jid.in_(jids),
        )
        if trust is not None:
            stmt = stmt.where(mod.Public.trust.in_(trust))

        if only_active:
            stmt = stmt.where(mod.Public.active == only_active)

        return session.scalars(stmt).all()

    @with_session
    @timeit
    def remove_public_key(
        self, session: Session, account: str, jid: JID, fingerprint: str
    ) -> None:
        stmt = sa.delete(mod.Public).where(
            mod.Public.account == account,
            mod.Public.jid == jid,
            mod.Public.fingerprint == fingerprint.upper(),
        )
        session.execute(stmt)

    @with_session
    @timeit
    def get_known_fingerprints(
        self,
        session: Session,
        account: str,
        jids: list[JID],
        *,
        trust: list[Trust] | None = None,
    ) -> set[str]:

        keys = self.get_public_keys(account, jids, trust=trust, only_active=False)
        return {k.fingerprint for k in keys}
