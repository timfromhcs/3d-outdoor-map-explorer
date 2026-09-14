"""
Unit tests for GLB Validator.
"""
import glob
import os
import pytest
from pipeline.validation.validator import GLBValidator


def test_validator_on_raw_glb():
    validator = GLBValidator()
    raw_files = sorted(glob.glob("Maps/*/*.glb"))
    assert len(raw_files) > 0

    report = validator.validate(raw_files[0])
    assert report.map_id in ["map1", "map2", "map3"]
    assert report.overall_status in ["PASS", "WARN"]

    # Verify check names exist
    check_names = {c.name for c in report.checks}
    expected = {
        "glb_binary_header",
        "gltf_structure",
        "buffer_integrity",
        "node_mesh_references",
        "materials_textures",
        "geometry_finite",
        "degenerate_triangles",
        "manifold_edges",
        "component_connectivity",
        "bounding_box_scale"
    }
    assert expected.issubset(check_names)


def test_validator_on_nonexistent_file():
    validator = GLBValidator()
    report = validator.validate("nonexistent_map.glb")
    assert report.overall_status == "FAIL"
    assert any(c.status == "FAIL" for c in report.checks)
