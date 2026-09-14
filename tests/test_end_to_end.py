"""
End-to-end integration test running full pipeline on real map.
"""
import os
import pytest
from pipeline.config import PipelineConfig
from pipeline.discovery import AssetScanner
from pipeline.orchestrator import PipelineOrchestrator


def test_full_pipeline_end_to_end_on_real_map(tmp_path):
    config = PipelineConfig.load()
    orchestrator = PipelineOrchestrator(config)

    scanner = AssetScanner(["Maps"])
    maps = scanner.scan()
    assert len(maps) >= 1
    target = next((m for m in maps if m.map_id == "map3"), maps[0])

    out_dir = str(tmp_path / "output")
    report = orchestrator.process_map(
        asset=target,
        output_base_dir=out_dir,
        quality="medium",
        force=True
    )

    # 1. Check all gates passed
    assert report.all_gates_passed is True
    assert len(report.quality_gates) == 9
    for g in report.quality_gates:
        assert g.status in ["PASSED", "HEALED"]

    # 2. Check output directory structure
    map_dir = os.path.join(out_dir, target.map_id)
    expected_files = [
        os.path.join(map_dir, "cleaned", "map_clean.glb"),
        os.path.join(map_dir, "cleaned", "map_validated.glb"),
        os.path.join(map_dir, "optimized", "render.glb"),
        os.path.join(map_dir, "collision", "collision.glb"),
        os.path.join(map_dir, "navigation", "walkable.glb"),
        os.path.join(map_dir, "navigation", "nav_graph.json"),
        os.path.join(map_dir, "reports", "process.json"),
        os.path.join(map_dir, "reports", "analysis.json"),
        os.path.join(map_dir, "reports", "validation.json"),
        os.path.join(map_dir, "reports", "cleanup.json"),
        os.path.join(map_dir, "reports", "optimization.json"),
        os.path.join(map_dir, "reports", "collision.json"),
        os.path.join(map_dir, "reports", "walkability.json"),
        os.path.join(map_dir, "scene.json"),
        os.path.join(map_dir, "preview", "index.html"),
    ]

    for p in expected_files:
        assert os.path.exists(p), f"Missing expected output file: {p}"
        assert os.path.getsize(p) > 0, f"File is empty: {p}"

    # 3. Check SHA-256 in report
    assert len(report.input_sha256) == 64
    assert len(report.output_files) >= 10
    for rel_path, file_meta in report.output_files.items():
        assert len(file_meta["sha256"]) == 64
        assert file_meta["size_bytes"] > 0
