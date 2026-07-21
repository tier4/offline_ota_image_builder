# Copyright 2022 TIER IV, INC. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Regression tests for the v1 resource-table iteration.

These exercise the real integration surface against the third-party
``ota-image-libs`` and ``simple-sqlite3-orm`` packages: building a resource
table with the ORM, serializing a ``CompressFilter`` into the DB, and reading
it back through :func:`iter_resource_table`.

If a dependency bump breaks the ORM API, the ``CompressFilter`` (msgpack)
serialization, or the resource-table schema, these tests will fail.

They are skipped (not errored) when the heavy dependencies are not installed,
so the pure-logic test suite still runs standalone.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

pytest.importorskip("ota_image_libs")
pytest.importorskip("simple_sqlite3_orm")

from ota_image_libs._resource_filter import CompressFilter  # noqa: E402
from ota_image_libs.v1.resource_table.schema import (  # noqa: E402
    ResourceTableManifest,
    ResourceTableManifestTypedDict,
)
from ota_image_libs.v1.resource_table.utils import ResourceTableDBHelper  # noqa: E402

from offline_ota_image_builder.ota_metadata.v1 import (  # noqa: E402
    DB_FNAME,
    iter_resource_table,
)


def _digest(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _make_db(tmp_path: Path, entries: list[ResourceTableManifest]) -> Path:
    db_f = tmp_path / DB_FNAME
    helper = ResourceTableDBHelper(db_f)
    helper.bootstrap_db()
    with helper.get_orm() as orm:
        orm.orm_insert_entries(entries)
    return db_f


def test_iter_plain_entries_yield_no_compressed_digest(tmp_path):
    d1, d2 = _digest(b"one"), _digest(b"two")
    db_f = _make_db(
        tmp_path,
        [
            ResourceTableManifest(
                resource_id=1, digest=d1, size=3, filter_applied=None
            ),
            ResourceTableManifest(
                resource_id=2, digest=d2, size=3, filter_applied=None
            ),
        ],
    )
    assert list(iter_resource_table(db_f)) == [(d1, None), (d2, None)]


def test_iter_compressed_entry_resolves_compressed_digest(tmp_path):
    origin = _digest(b"the original blob")
    compressed = _digest(b"the compressed blob")

    db_f = _make_db(
        tmp_path,
        [
            # the compressed origin: points at resource_id=2 for its compressed blob
            ResourceTableManifest(
                resource_id=1,
                digest=origin,
                size=100,
                filter_applied=CompressFilter(resource_id=2, compression_alg="zstd"),
            ),
            # the actual compressed blob, stored plainly
            ResourceTableManifest(
                resource_id=2, digest=compressed, size=40, filter_applied=None
            ),
        ],
    )

    result = list(iter_resource_table(db_f))
    assert result == [(origin, compressed), (compressed, None)]


def test_iter_empty_table_yields_nothing(tmp_path):
    db_f = _make_db(tmp_path, [])
    assert list(iter_resource_table(db_f)) == []


def test_iter_across_pagination_boundary(tmp_path):
    """iter_resource_table pages with batch_size=1024; cross that boundary."""
    n = 1100
    entries = [
        ResourceTableManifest(
            resource_id=i,
            digest=_digest(f"blob-{i}".encode()),
            size=i,
            filter_applied=None,
        )
        for i in range(1, n + 1)
    ]
    db_f = _make_db(tmp_path, entries)

    result = list(iter_resource_table(db_f))
    assert len(result) == n
    assert all(compressed is None for _, compressed in result)
    assert {origin for origin, _ in result} == {e.digest for e in entries}


def test_compress_filter_roundtrips_through_db(tmp_path):
    """The filter_applied column must survive a serialize -> store -> load cycle."""
    origin, compressed = _digest(b"orig"), _digest(b"comp")
    db_f = _make_db(
        tmp_path,
        [
            ResourceTableManifest(
                resource_id=1,
                digest=origin,
                size=10,
                filter_applied=CompressFilter(resource_id=2, compression_alg="zstd"),
            ),
            ResourceTableManifest(
                resource_id=2, digest=compressed, size=5, filter_applied=None
            ),
        ],
    )

    helper = ResourceTableDBHelper(db_f)
    with helper.get_orm() as orm:
        entry = orm.orm_select_entry(ResourceTableManifestTypedDict(resource_id=1))

    assert entry is not None
    assert isinstance(entry.filter_applied, CompressFilter)
    assert entry.filter_applied.resource_id == 2
    assert entry.filter_applied.compression_alg == "zstd"
