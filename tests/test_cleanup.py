"""
Unit tests for Mesh Cleaner.
"""
import os
import pytest
import trimesh
from pipeline.cleanup.cleaner import MeshCleaner
from pipeline.config import CleanupConfig


def test_cleanup_gizmos_and_noise(tmp_path):
    cleaner = MeshCleaner(CleanupConfig(
        remove_camera_gizmos=True,
        remove_degenerate_faces=True,
        remove_isolated_components=True,
        min_component_faces=20
    ))

    val_glb = str(tmp_path / "val.glb")
    clean_glb = str(tmp_path / "clean.glb")

    mesh, rep = cleaner.clean(
        source_path=r"Maps\map3\glbscene_All_camTrue_meshTrue.glb",
        output_validated_path=val_glb,
        output_clean_path=clean_glb,
        map_id="map3_test"
    )

    assert os.path.exists(val_glb)
    assert os.path.exists(clean_glb)
    assert rep.camera_gizmos_removed == 1
    assert rep.isolated_components_removed > 0
    assert rep.faces_after <= rep.faces_before
    assert len(mesh.faces) == rep.faces_after
