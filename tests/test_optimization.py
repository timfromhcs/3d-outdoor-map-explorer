"""
Unit tests for Mesh Optimizer and LOD generator.
"""
import os
import pytest
import trimesh
from pipeline.cleanup.cleaner import MeshCleaner
from pipeline.optimization.optimizer import MeshOptimizer
from pipeline.config import QualityTarget


def test_optimizer_and_lods(tmp_path):
    cleaner = MeshCleaner()
    clean_mesh, _ = cleaner.clean(
        r"Maps\map3\glbscene_All_camTrue_meshTrue.glb",
        str(tmp_path / "val.glb"),
        str(tmp_path / "clean.glb"),
        "map3"
    )

    optimizer = MeshOptimizer(QualityTarget(
        render_ratio=0.50,
        collision_ratio=0.10,
        max_render_faces=100000,
        max_collision_faces=3000
    ))

    render_glb = str(tmp_path / "render.glb")
    lod_dir = str(tmp_path / "lods")

    render_mesh, rep = optimizer.optimize(
        clean_mesh=clean_mesh,
        source_clean_path=str(tmp_path / "clean.glb"),
        output_render_path=render_glb,
        output_lod_dir=lod_dir,
        quality_name="medium",
        map_id="map3"
    )

    assert os.path.exists(render_glb)
    assert len(rep.lods) == 3
    assert rep.faces_after < rep.faces_before
    assert rep.face_reduction_percentage > 40.0
    # Check vertex colors preserved
    assert hasattr(render_mesh.visual, "vertex_colors")
