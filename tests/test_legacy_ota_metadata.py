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
"""Tests for the legacy (v1 text based) OTA metadata parser.

This module has no third-party dependencies, so these tests keep passing
regardless of how the ota-image-libs / simple-sqlite3-orm versions change.
"""

import base64
import json

import pytest

from offline_ota_image_builder.ota_metadata.legacy import (
    METADATA_JWT,
    MetadataJWTParser,
    MetadataJWTPayloadInvalid,
    MetaFieldDescriptor,
    MetaFile,
    MetafilesV1,
    _MetadataJWTClaimsLayout,
    de_escape,
    parse_regulars_from_txt,
)

# ------ regulars.txt parsing ------ #


def test_parse_regulars_full_format():
    """New format line with size, inode and compressed_alg fields."""
    reg = parse_regulars_from_txt(
        "0644,1000,1000,1,deadbeef,'/path/to/file',1234,42,zst"
    )
    assert reg.mode == 0o644  # octal string decoded as base-8
    assert reg.uid == 1000
    assert reg.gid == 1000
    assert reg.nlink == 1
    assert reg.sha256hash == bytes.fromhex("deadbeef")
    assert reg.path == "/path/to/file"
    assert reg.size == 1234
    assert reg.inode == 42
    assert reg.compressed_alg == "zst"


def test_parse_regulars_legacy_format_without_optional_fields():
    """Old CSV format without size/inode/compressed_alg (see NOTE in source)."""
    reg = parse_regulars_from_txt("0755,0,0,2,deadbeef,'/etc/hosts'")
    assert reg.mode == 0o755
    assert reg.nlink == 2
    assert reg.path == "/etc/hosts"
    # optional fields fall back to their defaults
    assert reg.size == 0
    assert reg.inode == 0
    assert reg.compressed_alg == ""


def test_parse_regulars_with_size_only():
    reg = parse_regulars_from_txt("0644,0,0,1,deadbeef,'/a',500")
    assert reg.size == 500
    assert reg.inode == 0
    assert reg.compressed_alg == ""


def test_parse_regulars_unescapes_single_quote_in_path():
    # a path containing an escaped single quote: /weird'name
    line = "0644,0,0,1,deadbeef,'/weird'\\''name'"
    reg = parse_regulars_from_txt(line)
    assert reg.path == "/weird'name"


def test_parse_regulars_invalid_line_raises():
    with pytest.raises(AssertionError):
        parse_regulars_from_txt("this is not a valid regulars.txt line")


def test_de_escape():
    assert de_escape("a'\\''b") == "a'b"
    assert de_escape("/normal/path") == "/normal/path"
    assert de_escape("") == ""


# ------ metafiles enum ------ #


def test_metafiles_v1_values():
    assert MetafilesV1.REGULAR_FNAME.value == "regulars.txt"
    assert MetafilesV1.DIRECTORY_FNAME.value == "dirs.txt"
    assert MetafilesV1.SYMBOLICLINK_FNAME.value == "symlinks.txt"
    assert MetafilesV1.PERSISTENT_FNAME.value == "persistents.txt"
    # str-Enum: members compare equal to their string value
    assert MetafilesV1.REGULAR_FNAME == "regulars.txt"


def test_metadata_jwt_constant():
    assert METADATA_JWT == "metadata.jwt"


# ------ metadata.jwt claims parsing ------ #


def _valid_claims():
    return [
        {"version": 1},
        {"total_regular_size": "2048"},
        {"rootfs_directory": "data"},
        {"compressed_rootfs_directory": "data.zst"},
        {"certificate": "cert.pem", "hash": "c0ffee"},
        {"directory": "dirs.txt", "hash": "d1"},
        {"symboliclink": "symlinks.txt", "hash": "s1"},
        {"regular": "regulars.txt", "hash": "r1"},
        {"persistent": "persistents.txt", "hash": "p1"},
    ]


def test_parse_payload_populates_all_fields():
    meta = _MetadataJWTClaimsLayout.parse_payload(json.dumps(_valid_claims()).encode())

    assert meta.version == 1
    # total_regular_size arrives as a string but is converted to int
    assert meta.total_regular_size == 2048
    assert isinstance(meta.total_regular_size, int)
    assert meta.rootfs_directory == "data"
    assert meta.compressed_rootfs_directory == "data.zst"
    assert meta.certificate == MetaFile(file="cert.pem", hash="c0ffee")
    assert meta.regular == MetaFile(file="regulars.txt", hash="r1")
    assert meta.directory == MetaFile(file="dirs.txt", hash="d1")


def test_parse_payload_applies_defaults_for_optional_fields():
    claims = [c for c in _valid_claims() if not ({"total_regular_size"} & c.keys())]
    claims = [c for c in claims if "compressed_rootfs_directory" not in c]
    meta = _MetadataJWTClaimsLayout.parse_payload(json.dumps(claims).encode())
    assert meta.total_regular_size == 0
    assert meta.compressed_rootfs_directory == ""


def test_parse_payload_missing_must_set_field_raises():
    claims = [c for c in _valid_claims() if "regular" not in c]
    with pytest.raises(MetadataJWTPayloadInvalid):
        _MetadataJWTClaimsLayout.parse_payload(json.dumps(claims).encode())


@pytest.mark.parametrize("payload", ["[]", "{}", '{"version": 1}'])
def test_parse_payload_rejects_non_list_or_empty(payload):
    with pytest.raises(MetadataJWTPayloadInvalid):
        _MetadataJWTClaimsLayout.parse_payload(payload.encode())


def test_get_img_metafiles_yields_the_four_metafiles():
    meta = _MetadataJWTClaimsLayout.parse_payload(json.dumps(_valid_claims()).encode())
    metafiles = list(meta.get_img_metafiles())
    assert metafiles == [
        MetaFile(file="dirs.txt", hash="d1"),
        MetaFile(file="symlinks.txt", hash="s1"),
        MetaFile(file="regulars.txt", hash="r1"),
        MetaFile(file="persistents.txt", hash="p1"),
    ]


# ------ MetaFieldDescriptor behaviour ------ #


def test_descriptor_check_is_target_claim():
    descriptor = _MetadataJWTClaimsLayout.version
    assert isinstance(descriptor, MetaFieldDescriptor)
    assert descriptor.check_is_target_claim({"version": 1}) is True
    assert descriptor.check_is_target_claim({"other": 1}) is False
    assert descriptor.check_is_target_claim("not-a-dict") is False


def test_descriptor_rejects_non_dict_assignment():
    layout = _MetadataJWTClaimsLayout()
    with pytest.raises(ValueError):
        layout.version = "not-a-dict"


def test_descriptor_metafile_requires_hash():
    layout = _MetadataJWTClaimsLayout()
    with pytest.raises(ValueError):
        # missing the "hash" key for a MetaFile field
        layout.certificate = {"certificate": "cert.pem"}


# ------ MetadataJWTParser: base64url splitting ------ #


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode()


def test_metadata_jwt_parser_splits_header_payload_signature():
    header = json.dumps({"alg": "ES256", "typ": "JWT"}).encode()
    payload = json.dumps(_valid_claims()).encode()
    signature = b"\x01\x02\x03\x04"

    header_b64, payload_b64 = _b64url(header), _b64url(payload)
    jwt = f"{header_b64}.{payload_b64}.{_b64url(signature)}"

    parser = MetadataJWTParser(jwt, certs_dir="")
    assert parser.header_bytes == header
    assert parser.payload_bytes == payload
    assert parser.metadata_signature == signature
    assert parser.metadata_bytes == f"{header_b64}.{payload_b64}".encode()

    meta = parser.get_otametadata()
    assert meta.version == 1
    assert meta.regular == MetaFile(file="regulars.txt", hash="r1")
