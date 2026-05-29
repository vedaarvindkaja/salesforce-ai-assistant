# ============================================================
# PYTHON CODE
# ============================================================
"""Flat extraction cache (Option A, ADR-pending).

Stores raw Tooling API records as JSON blobs, keyed by
(org_key, metadata_type, record_id). The intelligence layer reads
deserialized dicts back out; it does NOT run SQL joins. This is a
cache, not a graph — PostgreSQL replaces it around Week 10.

Connection lifecycle: one connection per operation (see ADR-004).
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite
from pydantic import BaseModel

# Two statements: the table plus a lookup index on the human-friendly name.
# record_id (the Salesforce Id) is the durable primary key; display_name is
# a best-effort convenience column (see _display_name below for why "best-effort").
_SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata_cache (
    org_key        TEXT NOT NULL,
    metadata_type  TEXT NOT NULL,
    record_id      TEXT NOT NULL,
    display_name   TEXT,
    payload        TEXT NOT NULL,
    fetched_at     TEXT NOT NULL,
    PRIMARY KEY (org_key, metadata_type, record_id)
);
CREATE INDEX IF NOT EXISTS idx_metadata_cache_lookup
    ON metadata_cache (org_key, metadata_type, display_name);
"""

# Different Tooling SObjects expose their human name under different fields
# (ApexClass.Name, FlowDefinition.DeveloperName, ValidationRule.ValidationName...).
# And per your FlowDefinition.MasterLabel saga, the "nice" label is sometimes
# null even when it exists in the UI. So display_name is BEST-EFFORT only —
# never a key, never required. record_id (the SF Id) is always the source of truth.
_DISPLAY_NAME_FIELDS = ("DeveloperName", "Name", "ValidationName", "MasterLabel")


def _display_name(record: BaseModel) -> str | None:
    """First non-empty name-ish field, or None. Best-effort by design."""
    for attr in _DISPLAY_NAME_FIELDS:
        value = getattr(record, attr, None)
        if value:
            return str(value)
    return None


class MetadataCache:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)

    async def init_schema(self) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.executescript(_SCHEMA)
            await db.commit()

    async def put(
        self,
        *,
        org_key: str,
        metadata_type: str,
        records: Iterable[BaseModel],
    ) -> int:
        """Upsert records. Re-running an extraction overwrites in place
        rather than duplicating — same idea as a Salesforce upsert on an
        external Id."""
        now = datetime.now(timezone.utc).isoformat()
        rows = [
            (
                org_key,
                metadata_type,
                record.Id,                  # every Tooling SObject has Id; fail loud if not
                _display_name(record),
                record.model_dump_json(),
                now,
            )
            for record in records
        ]
        if not rows:
            return 0
        async with aiosqlite.connect(self._db_path) as db:
            await db.executemany(
                """
                INSERT INTO metadata_cache
                    (org_key, metadata_type, record_id, display_name, payload, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (org_key, metadata_type, record_id)
                DO UPDATE SET
                    display_name = excluded.display_name,
                    payload      = excluded.payload,
                    fetched_at   = excluded.fetched_at
                """,
                rows,
            )
            await db.commit()
        return len(rows)

    async def get(
        self,
        *,
        org_key: str,
        metadata_type: str,
        display_name: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = "SELECT payload FROM metadata_cache WHERE org_key = ? AND metadata_type = ?"
        params: list[Any] = [org_key, metadata_type]
        if display_name is not None:
            sql += " AND display_name = ?"
            params.append(display_name)
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(sql, params) as cursor:
                fetched = await cursor.fetchall()
        return [json.loads(row[0]) for row in fetched]

    async def get_one(
        self,
        *,
        org_key: str,
        metadata_type: str,
        record_id: str,
    ) -> dict[str, Any] | None:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                """
                SELECT payload FROM metadata_cache
                WHERE org_key = ? AND metadata_type = ? AND record_id = ?
                """,
                (org_key, metadata_type, record_id),
            ) as cursor:
                row = await cursor.fetchone()
        return json.loads(row[0]) if row else None

    async def clear(
        self,
        *,
        org_key: str,
        metadata_type: str | None = None,
    ) -> int:
        sql = "DELETE FROM metadata_cache WHERE org_key = ?"
        params: list[Any] = [org_key]
        if metadata_type is not None:
            sql += " AND metadata_type = ?"
            params.append(metadata_type)
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(sql, params)
            await db.commit()
            return cursor.rowcount

    async def stats(self, *, org_key: str) -> dict[str, int]:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                """
                SELECT metadata_type, COUNT(*) FROM metadata_cache
                WHERE org_key = ?
                GROUP BY metadata_type
                """,
                (org_key,),
            ) as cursor:
                rows = await cursor.fetchall()
        return {row[0]: row[1] for row in rows}


# ============================================================
# APEX EQUIVALENT (for comparison)
# ============================================================
# A Salesforce dev caching org metadata would reach for either Platform
# Cache or a custom object. Mapping to the custom-object version:
#
#    // Custom object Metadata_Cache__c with fields:
#    //   Org_Key__c, Metadata_Type__c, Record_Id__c (External Id, Unique),
#    //   Display_Name__c, Payload__c (Long Text), Fetched_At__c
#
#    public with sharing class MetadataCache {
#
#        // put() -> upsert on the external Id. ON CONFLICT DO UPDATE in
#        // SQLite is conceptually identical to upsert by external Id.
#        public Integer put(List<Metadata_Cache__c> rows) {
#            upsert rows Record_Id__c;   // external-Id upsert = our PK upsert
#            return rows.size();
#        }
#
#        // get() -> SOQL with bind variables (our ? placeholders)
#        public List<Metadata_Cache__c> get(String orgKey, String type) {
#            return [
#                SELECT Payload__c FROM Metadata_Cache__c
#                WHERE Org_Key__c = :orgKey AND Metadata_Type__c = :type
#            ];
#        }
#
#        // stats() -> aggregate SOQL
#        public Map<String, Integer> stats(String orgKey) {
#            Map<String, Integer> out = new Map<String, Integer>();
#            for (AggregateResult ar : [
#                SELECT Metadata_Type__c t, COUNT(Id) c
#                FROM Metadata_Cache__c WHERE Org_Key__c = :orgKey
#                GROUP BY Metadata_Type__c
#            ]) {
#                out.put((String) ar.get('t'), (Integer) ar.get('c'));
#            }
#            return out;
#        }
#    }
#
# Concept mapping:
# - ON CONFLICT DO UPDATE         -> upsert by External Id field
# - executemany(rows)             -> bulk upsert List<sObject> (one DML, not N)
# - SELECT ? params (bind)        -> SOQL :bindVariable
# - model_dump_json()             -> JSON.serialize(record)
# - GROUP BY + COUNT(*)           -> aggregate SOQL / AggregateResult
# - per-op connection (ADR-004)   -> Apex has no persistent connection; each
#                                    transaction is naturally stateless, which
#                                    is *why* the per-op model feels familiar
# ============================================================