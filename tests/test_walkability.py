"""
Unit tests for Walkability and Navigation Graph.
"""
import json
import os
import pytest
from pipeline.cleanup.cleaner import MeshCleaner
from pipeline.navigation.walkability import WalkabilityAnalyzer


def test_walkable_surface_and_nav_graph(tmp_path):
    cleaner = MeshCleaner()
    clean_mesh, _ = cleaner.clean(
        r"Maps\map3\glbscene_All_camTrue_meshTrue.glb",
        str(tmp_path / "val.glb"),
        str(tmp_path / "clean.glb"),
        "map3"
    )

    nav_analyzer = WalkabilityAnalyzer()
    walk_glb = str(tmp_path / "walk.glb")
    nav_json = str(tmp_path / "nav.json")

    walk_mesh, rep = nav_analyzer.generate_walkable_surface(
        clean_mesh=clean_mesh,
        output_walkable_path=walk_glb,
        output_nav_graph_path=nav_json,
        map_id="map3"
    )

    assert os.path.exists(walk_glb)
    assert os.path.exists(nav_json)
    assert rep.status in ["VERIFIED", "PARTIAL"]
    assert rep.nav_graph.total_nodes > 0

    with open(nav_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "nodes" in data and "edges" in data
    assert len(data["nodes"]) == rep.nav_graph.total_nodes
