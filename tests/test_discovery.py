"""
Unit tests for Asset Discovery module.
"""
import os
import pytest
from pipeline.discovery import AssetScanner, compute_sha256


def test_asset_scanner_discovers_all_maps():
    scanner = AssetScanner(["Maps"])
    maps = scanner.scan()
    assert len(maps) >= 3
    map_ids = [m.map_id for m in maps]
    assert "map1" in map_ids
    assert "map2" in map_ids
    assert "map3" in map_ids


def test_map_asset_properties():
    scanner = AssetScanner(["Maps"])
    maps = scanner.scan()
    for m in maps:
        assert m.file_size_bytes > 100000
        assert m.vertex_count > 1000
        assert m.triangle_count > 1000
        assert len(m.sha256) == 64
        assert m.format == "GLB"
        assert m.camera_gizmos_detected is True
        assert len(m.bounding_box) == 2


def test_sha256_computation(tmp_path):
    test_file = tmp_path / "test.bin"
    test_file.write_bytes(b"hello 3d map pipeline")
    h = compute_sha256(str(test_file))
    assert isinstance(h, str)
    assert len(h) == 64
