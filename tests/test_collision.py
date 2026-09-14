"""
Unit tests for Collision Generator.
"""
import os
import pytest
import trimesh
from pipeline.cleanup.cleaner import MeshCleaner
from pipeline.collision.generator import CollisionGenerator


def test_collision_generation(tmp_path):
    cleaner = MeshCleaner()
    clean_mesh, _ = cleaner.clean(
        r"Maps\map3\glbscene_All_camTrue_meshTrue.glb",
        str(tmp_path / "val.glb"),
        str(tmp_path / "clean.glb"),
        "map3"
    )

    col_gen = CollisionGenerator()
    col_glb = str(tmp_path / "col.glb")
    col_mesh, rep = col_gen.generate_collision(
        clean_mesh=clean_mesh,
        output_collision_path=col_glb,
        map_id="map3",
        target_faces=2000
    )

    assert os.path.exists(col_glb)
    assert rep.triangle_count <= 2500
    assert rep.reduction_percentage > 90.0
    assert len(rep.bounds) == 2
    assert len(rep.extents) == 3
