"""
Mesh Optimization module for 3D Outdoor Maps.
Performs Garland-Heckbert QEM decimation, LOD generation, and vertex color preservation.
"""
from dataclasses import asdict, dataclass, field
import json
import os
from typing import Any, Dict, List, Optional, Tuple
import fast_simplification
import numpy as np
from scipy.spatial import cKDTree
import trimesh
from pipeline.config import QualityTarget


@dataclass
class LODInfo:
    level: int
    faces: int
    vertices: int
    reduction_percentage: float
    output_path: str


@dataclass
class OptimizationReport:
    map_id: str
    quality_profile: str
    vertices_before: int
    vertices_after: int
    faces_before: int
    faces_after: int
    face_reduction_percentage: float
    file_size_before_bytes: int
    file_size_after_bytes: int
    file_size_reduction_percentage: float
    lods: List[LODInfo] = field(default_factory=list)
    output_render_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["lods"] = [asdict(lod) for lod in self.lods]
        return data


class MeshOptimizer:
    """Optimizes 3D meshes for real-time rendering and prepares multi-level LODs."""

    def __init__(self, target_profile: Optional[QualityTarget] = None):
        self.profile = target_profile or QualityTarget(
            render_ratio=0.45,
            collision_ratio=0.08,
            max_render_faces=150000,
            max_collision_faces=4000
        )

    def simplify_mesh(self, mesh: trimesh.Trimesh, target_reduction: float) -> trimesh.Trimesh:
        """
        Simplify mesh using Garland-Heckbert QEM while preserving vertex colors.
        target_reduction: float between 0.0 and 1.0 (e.g. 0.50 means remove 50% of faces).
        """
        if target_reduction <= 0.01 or len(mesh.faces) < 500:
            return mesh.copy()

        # Target reduction is fraction of faces to delete
        target_reduction = min(0.99, max(0.01, target_reduction))

        # Perform fast QEM decimation
        v_out, f_out = fast_simplification.simplify(
            mesh.vertices,
            mesh.faces,
            target_reduction=target_reduction
        )

        # Re-attach vertex colors via KDTree nearest neighbor
        new_visual = None
        if hasattr(mesh.visual, "vertex_colors") and mesh.visual.vertex_colors is not None and len(mesh.visual.vertex_colors) > 0:
            tree = cKDTree(mesh.vertices)
            _, indices = tree.query(v_out)
            new_colors = mesh.visual.vertex_colors[indices]
            new_visual = trimesh.visual.ColorVisuals(vertex_colors=new_colors)

        decimated = trimesh.Trimesh(
            vertices=v_out,
            faces=f_out,
            visual=new_visual,
            process=False
        )

        try:
            decimated.fix_normals()
        except Exception:
            pass

        return decimated

    def optimize(
        self,
        clean_mesh: trimesh.Trimesh,
        source_clean_path: str,
        output_render_path: str,
        output_lod_dir: Optional[str] = None,
        quality_name: str = "medium",
        map_id: str = ""
    ) -> Tuple[trimesh.Trimesh, OptimizationReport]:
        if not map_id:
            map_id = os.path.basename(os.path.dirname(output_render_path)) or "map"

        os.makedirs(os.path.dirname(os.path.abspath(output_render_path)), exist_ok=True)
        if output_lod_dir:
            os.makedirs(output_lod_dir, exist_ok=True)

        v_before = len(clean_mesh.vertices)
        f_before = len(clean_mesh.faces)
        size_before = os.path.getsize(source_clean_path) if os.path.exists(source_clean_path) else 0

        # Calculate target reduction for render mesh
        # e.g., if render_ratio is 0.45, target_reduction = 1.0 - 0.45 = 0.55
        target_render_faces = int(f_before * self.profile.render_ratio)
        if target_render_faces > self.profile.max_render_faces:
            target_render_faces = self.profile.max_render_faces

        target_reduction = 1.0 - (target_render_faces / max(1, f_before))
        target_reduction = max(0.0, min(0.95, target_reduction))

        # Simplify for main render mesh
        if target_reduction > 0.05:
            render_mesh = self.simplify_mesh(clean_mesh, target_reduction)
        else:
            render_mesh = clean_mesh.copy()

        # Export optimized render mesh
        render_mesh.export(output_render_path, file_type="glb")

        v_after = len(render_mesh.vertices)
        f_after = len(render_mesh.faces)
        size_after = os.path.getsize(output_render_path) if os.path.exists(output_render_path) else 0

        face_red_pct = round(100.0 * (1.0 - (f_after / max(1, f_before))), 2)
        size_red_pct = round(100.0 * (1.0 - (size_after / max(1, size_before))), 2) if size_before > 0 else 0.0

        # Generate LODs (LOD0 = render_mesh, LOD1 = 50% of LOD0, LOD2 = 25% of LOD0)
        lods: List[LODInfo] = [
            LODInfo(
                level=0,
                faces=f_after,
                vertices=v_after,
                reduction_percentage=0.0,
                output_path=output_render_path
            )
        ]

        if output_lod_dir:
            # LOD1
            lod1_mesh = self.simplify_mesh(render_mesh, 0.50)
            lod1_path = os.path.join(output_lod_dir, "render_lod1.glb")
            lod1_mesh.export(lod1_path, file_type="glb")
            lods.append(LODInfo(
                level=1,
                faces=len(lod1_mesh.faces),
                vertices=len(lod1_mesh.vertices),
                reduction_percentage=round(100.0 * (1.0 - len(lod1_mesh.faces) / max(1, f_after)), 2),
                output_path=lod1_path
            ))

            # LOD2
            lod2_mesh = self.simplify_mesh(lod1_mesh, 0.50)
            lod2_path = os.path.join(output_lod_dir, "render_lod2.glb")
            lod2_mesh.export(lod2_path, file_type="glb")
            lods.append(LODInfo(
                level=2,
                faces=len(lod2_mesh.faces),
                vertices=len(lod2_mesh.vertices),
                reduction_percentage=round(100.0 * (1.0 - len(lod2_mesh.faces) / max(1, f_after)), 2),
                output_path=lod2_path
            ))

        report = OptimizationReport(
            map_id=map_id,
            quality_profile=quality_name,
            vertices_before=v_before,
            vertices_after=v_after,
            faces_before=f_before,
            faces_after=f_after,
            face_reduction_percentage=face_red_pct,
            file_size_before_bytes=size_before,
            file_size_after_bytes=size_after,
            file_size_reduction_percentage=size_red_pct,
            lods=lods,
            output_render_path=output_render_path
        )

        return render_mesh, report
