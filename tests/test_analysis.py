"""
Unit tests for Geometry Analyzer.
"""
import glob
import pytest
from pipeline.analysis.analyzer import GeometryAnalyzer


def test_analyzer_metrics():
    analyzer = GeometryAnalyzer()
    raw_files = sorted(glob.glob("Maps/*/*.glb"))
    assert len(raw_files) > 0

    report = analyzer.analyze(raw_files[0], map_id="test_map")
    assert report.vertex_count > 1000
    assert report.face_count > 1000
    assert len(report.bounding_box) == 2
    assert len(report.extents) == 3
    assert report.surface_area > 0.0

    # Height profile
    hp = report.height_profile
    assert "min_y" in hp and "max_y" in hp and "mean_y" in hp
    assert hp["max_y"] >= hp["min_y"]

    # Normal distribution
    nd = report.normal_distribution
    assert "mean_normal_abs_y" in nd
    assert 0.0 <= nd["mean_normal_abs_y"] <= 1.0
