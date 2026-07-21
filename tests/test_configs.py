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
"""Tests pinning the image layout config constants (no third-party deps).

These values define the on-disk offline OTA image layout, so any accidental
change to them is a breaking change and should be caught here.
"""

from offline_ota_image_builder.configs import BaseConfig, cfg


def test_cfg_is_baseconfig_instance():
    assert isinstance(cfg, BaseConfig)


def test_manifest_related_constants():
    assert cfg.MANIFEST_JSON == "manifest.json"
    assert cfg.MANIFEST_SCHEMA_VERSION == 1
    assert cfg.IMAGE_LAYOUT_VERSION == 1
    assert cfg.DEFAULT_OTA_METADATA_VERSION == 1


def test_output_layout_constants():
    assert cfg.OUTPUT_WORKDIR == "output"
    assert cfg.OUTPUT_DATA_DIR == "data"
    assert cfg.OUTPUT_META_DIR == "meta"
    assert cfg.IMAGE_UNARCHIVE_WORKDIR == "images"


def test_misc_constants():
    assert cfg.OTA_IMAGE_COMPRESSION_ALG == "zst"
    assert cfg.EXTERNAL_CACHE_DEV_FSLABEL == "ota_cache_src"
