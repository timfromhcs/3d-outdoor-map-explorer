"""
Cleanup module for 3D Outdoor Maps.
Conservative, non-destructive cleaning of raw/AI-reconstructed 3D geometry.
"""
from dataclasses import asdict, dataclass, field
import json
import os
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import trimesh
from pipeline.config import CleanupConfig


@dataclass
class CleanupOperationReport:
    map_id: str
    camera_gizmos_removed: int
    duplicate_vertices_removed: int
    degenerate_faces_removed: int
    isolated_components_removed: int
    isolated_faces_removed: int
    normals_recomputed: bool
    vertices_before: int
    vertices_after: int
    faces_before: int
    faces_after: int
    reduction_percentage: float
    output_validated_path: str = ""
    output_clean_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MeshCleaner:
    """Performs conservative and robust cleaning of 3D map meshes."""

    def __init__(self, config: Optional[CleanupConfig] = None):
        self.config = config or CleanupConfig()

    def clean(self, source_path: str, output_validated_path: str, output_clean_path: str, map_id: str = "") -> Tuple[trimesh.Trimesh, CleanupOperationReport]:
        if not map_id:
            map_id = os.path.basename(os.path.dirname(source_path)) or os.path.splitext(os.path.basename(source_path))[0]

        os.makedirs(os.path.dirname(os.path.abspath(output_validated_path)), exist_ok=True)
        os.makedirs(os.path.dirname(os.path.abspath(output_clean_path)), exist_ok=True)

        # 1. Load scene or mesh
        loaded = trimesh.load(source_path, process=False)
        gizmos_removed = 0

        # Separate main world geometry from camera gizmos
        world_meshes: List[trimesh.Trimesh] = []
        if isinstance(loaded, trimesh.Scene):
            for name, geom in loaded.geometry.items():
                if isinstance(geom, trimesh.Trimesh):
                    # Check if camera frustum gizmo
                    is_gizmo = False
                    if len(geom.vertices) < 50 and any(k in name.lower() for k in ["cam", "camera", "gizmo", "1"]):
                        is_gizmo = True
                    elif "camera" in name.lower() or "gizmo" in name.lower():
                        is_gizmo = True

                    if is_gizmo and self.config.remove_camera_gizmos:
                        gizmos_removed += 1
                    else:
                        world_meshes.append(geom)

            if len(world_meshes) == 1:
                mesh = world_meshes[0].copy()
            elif len(world_meshes) > 1:
                mesh = trimesh.util.concatenate(world_meshes)
            else:
                mesh = trimesh.Trimesh()
        elif isinstance(loaded, trimesh.Trimesh):
            mesh = loaded.copy()
        else:
            raise ValueError(f"Unsupported geometry type: {type(loaded)}")

        # Save validated state (mesh without gizmos)
        mesh.export(output_validated_path, file_type="glb")

        v_before = len(mesh.vertices)
        f_before = len(mesh.faces)

        dup_v_removed = 0
        deg_f_removed = 0
        iso_comps_removed = 0
        iso_f_removed = 0

        # 2. Remove degenerate faces (repeated vertex indices or zero area)
        if self.config.remove_degenerate_faces and f_before > 0:
            faces = mesh.faces
            # Distinct indices
            valid_idx = (faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 0] != faces[:, 2])
            # Area test
            cross_p = np.cross(
                mesh.vertices[faces[:, 1]] - mesh.vertices[faces[:, 0]],
                mesh.vertices[faces[:, 2]] - mesh.vertices[faces[:, 0]]
            )
            areas = 0.5 * np.linalg.norm(cross_p, axis=1)
            valid_area = (areas > 1e-12) & ~np.isnan(areas)
            keep_mask = valid_idx & valid_area

            deg_f_removed = int(np.sum(~keep_mask))
            if deg_f_removed > 0:
                mesh.update_faces(keep_mask)
                mesh.remove_unreferenced_vertices()

        # 3. Remove duplicate vertices (merge close vertices)
        if self.config.remove_duplicate_vertices and len(mesh.vertices) > 0:
            v_prior = len(mesh.vertices)
            # trimesh merge_vertices preserves vertex colors if attached
            mesh.merge_vertices(merge_tex=True, merge_norm=True)
            dup_v_removed = v_prior - len(mesh.vertices)

        # 4. Remove small isolated floating noise components
        if self.config.remove_isolated_components and len(mesh.faces) > 0:
            try:
                comps = trimesh.graph.connected_components(mesh.face_adjacency, min_len=1)
                total_faces = len(mesh.faces)
                min_faces = max(self.config.min_component_faces, int(self.config.min_component_ratio * total_faces))

                # Identify components to keep
                keep_face_indices = []
                for c in comps:
                    if len(c) >= min_faces:
                        keep_face_indices.extend(c)
                    else:
                        iso_comps_removed += 1
                        iso_f_removed += len(c)

                if keep_face_indices and len(keep_face_indices) < total_faces:
                    face_mask = np.zeros(total_faces, dtype=bool)
                    face_mask[keep_face_indices] = True
                    mesh.update_faces(face_mask)
                    mesh.remove_unreferenced_vertices()
            except Exception:
                pass

        # 5. Rebuild normals & winding
        normals_done = False
        if self.config.rebuild_normals and len(mesh.faces) > 0:
            try:
                mesh.fix_normals()
                normals_done = True
            except Exception:
                pass

        v_after = len(mesh.vertices)
        f_after = len(mesh.faces)
        red_pct = round(100.0 * (1.0 - (f_after / max(1, f_before))), 2)

        # Save clean state
        mesh.export(output_clean_path, file_type="glb")

        report = CleanupOperationReport(
            map_id=map_id,
            camera_gizmos_removed=gizmos_removed,
            duplicate_vertices_removed=dup_v_removed,
            degenerate_faces_removed=deg_f_removed,
            isolated_components_removed=iso_comps_removed,
            isolated_faces_removed=iso_f_removed,
            normals_recomputed=normals_done,
            vertices_before=v_before,
            vertices_after=v_after,
            faces_before=f_before,
            faces_after=f_after,
            reduction_percentage=red_pct,
            output_validated_path=output_validated_path,
            output_clean_path=output_clean_path
        )

        return mesh, report
