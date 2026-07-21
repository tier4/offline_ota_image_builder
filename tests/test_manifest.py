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
"""Tests for the offline OTA image manifest dataclasses (no third-party deps)."""

import json

from offline_ota_image_builder.configs import cfg
from offline_ota_image_builder.manifest import ImageMetadata, Manifest


def test_image_metadata_defaults():
    meta = ImageMetadata()
    assert meta.ecu_id == ""
    assert meta.image_version == ""
    assert meta.ota_metadata_version == cfg.DEFAULT_OTA_METADATA_VERSION


def test_image_metadata_custom_values():
    meta = ImageMetadata(ecu_id="autoware", image_version="v1.2.3")
    assert meta.ecu_id == "autoware"
    assert meta.image_version == "v1.2.3"
    # not explicitly given -> still the default
    assert meta.ota_metadata_version == cfg.DEFAULT_OTA_METADATA_VERSION


def test_manifest_defaults_match_config():
    manifest = Manifest()
    assert manifest.schema_version == cfg.MANIFEST_SCHEMA_VERSION
    assert manifest.image_layout_version == cfg.IMAGE_LAYOUT_VERSION
    assert manifest.build_timestamp == 0
    assert manifest.data_size == 0
    assert manifest.data_files_num == 0
    assert manifest.meta_size == 0
    assert manifest.image_meta == []


def test_manifest_image_meta_is_not_shared_between_instances():
    """Guards the field(default_factory=list) usage against a shared mutable default."""
    first, second = Manifest(), Manifest()
    first.image_meta.append(ImageMetadata(ecu_id="a"))
    assert second.image_meta == []


def test_export_to_json_is_valid_json_with_nested_image_meta():
    manifest = Manifest(
        build_timestamp=1700000000,
        data_size=123,
        data_files_num=4,
        meta_size=56,
        image_meta=[ImageMetadata(ecu_id="main", image_version="2024.1")],
    )

    dumped = manifest.export_to_json()
    assert isinstance(dumped, str)

    decoded = json.loads(dumped)
    assert decoded["schema_version"] == cfg.MANIFEST_SCHEMA_VERSION
    assert decoded["image_layout_version"] == cfg.IMAGE_LAYOUT_VERSION
    assert decoded["build_timestamp"] == 1700000000
    assert decoded["data_size"] == 123
    assert decoded["data_files_num"] == 4
    assert decoded["meta_size"] == 56

    assert len(decoded["image_meta"]) == 1
    entry = decoded["image_meta"][0]
    assert entry["ecu_id"] == "main"
    assert entry["image_version"] == "2024.1"
    assert entry["ota_metadata_version"] == cfg.DEFAULT_OTA_METADATA_VERSION
