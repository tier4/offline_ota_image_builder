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
"""Contract tests for the third-party API surface this project depends on.

They assert that the exact symbols / attributes / methods used by
``offline_ota_image_builder.ota_metadata.v1`` (and thus ``builder``) still
exist and have the expected shape. A dependency bump that renames, moves or
removes any of them will make these tests fail fast, before an actual build.

Skipped (not errored) when ``ota-image-libs`` is not installed.
"""

from __future__ import annotations

import importlib
from zipfile import ZipFile

import pytest

pytest.importorskip("ota_image_libs")


def test_builder_and_v1_modules_import():
    """Import-time regression: the specific symbols v1.py pulls in must resolve."""
    importlib.import_module("offline_ota_image_builder.ota_metadata.v1")
    importlib.import_module("offline_ota_image_builder.builder")


def test_ota_image_artifact_reader_surface(tmp_path):
    from ota_image_libs.v1.artifact.reader import OTAImageArtifactReader

    # an (empty) zip is enough to construct the reader; index parsing happens lazily
    empty_zip = tmp_path / "empty.zip"
    with ZipFile(empty_zip, "w"):
        pass

    reader = OTAImageArtifactReader(empty_zip)
    try:
        # attributes read by OTAImageHelper.__init__
        assert isinstance(reader._resource_dir, str)
        assert isinstance(reader._f, ZipFile)
        # methods called by OTAImageHelper
        for method in ("parse_index", "open_blob", "get_resource_table"):
            assert callable(getattr(reader, method))
    finally:
        reader.close()


def test_compress_filter_fields():
    from ota_image_libs._resource_filter import CompressFilter

    flt = CompressFilter(resource_id=7, compression_alg="zstd")
    # v1.py reads `.resource_id` directly off the filter
    assert flt.resource_id == 7
    assert flt.compression_alg == "zstd"


def test_resource_table_manifest_fields():
    from ota_image_libs.v1.resource_table.schema import ResourceTableManifest

    entry = ResourceTableManifest(
        resource_id=1, digest=b"\x00" * 32, size=1, filter_applied=None
    )
    assert entry.resource_id == 1
    assert entry.digest == b"\x00" * 32
    assert entry.filter_applied is None


def test_resource_table_db_helper_surface():
    from ota_image_libs.v1.resource_table.utils import ResourceTableDBHelper

    for method in ("get_orm", "bootstrap_db"):
        assert callable(getattr(ResourceTableDBHelper, method))


def test_orm_iteration_surface():
    from ota_image_libs.v1.resource_table.db import ResourceTableORM

    # iter_resource_table relies on the ORM being a context manager exposing these
    assert hasattr(ResourceTableORM, "__enter__")
    assert hasattr(ResourceTableORM, "__exit__")
    for method in ("orm_select_all_with_pagination", "orm_select_entry"):
        assert callable(getattr(ResourceTableORM, method))
