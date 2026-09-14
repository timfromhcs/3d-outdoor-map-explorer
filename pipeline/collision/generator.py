"""
Collision Geometry Generation module for 3D Outdoor Maps.
Generates lightweight physical collision meshes and convex hull decompositions.
"""
from dataclasses import asdict, dataclass, field
import json
import os
from typing import Any, Dict, List, Optional, Tuple
import fast_simplification
import numpy as np
import trimesh
from pipeline.config import CollisionConfig


@dataclass
class ConvexHullInfo:
    hull_id: int
    vertex_count: int
    face_count: int
    centroid: List[float]
    bounds: List[List[float]]


@dataclass
class CollisionReport:
    map_id: str
    method: str
    collision_source: str
    triangle_count: int
    vertex_count: int
    reduction_percentage: float
    bounds: List[List[float]]
    extents: List[float]
    convex_hulls_count: int
    hulls_info: List[ConvexHullInfo] = field(default_factory=list)
    output_collision_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["hulls_info"] = [asdict(h) for h in self.hulls_info]
        return data


class CollisionGenerator:
    """Generates physical collision representations for real-time game engines."""

    def __init__(self, config: Optional[CollisionConfig] = None):
        self.config = config or CollisionConfig()

    def generate_collision(
        self,
        clean_mesh: trimesh.Trimesh,
        output_collision_path: str,
        map_id: str = "",
        target_faces: Optional[int] = None
    ) -> Tuple[trimesh.Trimesh, CollisionReport]:
        if not map_id:
            map_id = "map"

        os.makedirs(os.path.dirname(os.path.abspath(output_collision_path)), exist_ok=True)

        f_before = len(clean_mesh.faces)
        target = target_faces or self.config.target_faces

        # 1. Generate simplified collision trimesh
        # Calculate reduction factor to hit target_faces (e.g. 2500 faces)
        if f_before > target:
            reduction = 1.0 - (target / f_before)
            reduction = max(0.05, min(0.98, reduction))
            v_simp, f_simp = fast_simplification.simplify(
                clean_mesh.vertices,
                clean_mesh.faces,
                target_reduction=reduction
            )
            col_mesh = trimesh.Trimesh(vertices=v_simp, faces=f_simp, process=False)
            # Secondary pass if QEM decimation was conservative
            if len(col_mesh.faces) > target * 1.1:
                r2 = 1.0 - (target / len(col_mesh.faces))
                if r2 > 0.05:
                    v_simp, f_simp = fast_simplification.simplify(
                        col_mesh.vertices,
                        col_mesh.faces,
                        target_reduction=r2
                    )
                    col_mesh = trimesh.Trimesh(vertices=v_simp, faces=f_simp, process=False)
        else:
            col_mesh = clean_mesh.copy()

        # Clean collision mesh (remove zero-area faces and ensure normals)
        try:
            col_mesh.remove_degenerate_faces()
            col_mesh.fix_normals()
        except Exception:
            pass

        # Give collision mesh a distinctive semi-transparent physics material color
        # Orange/Rust for collision: RGBA [244, 81, 30, 200]
        col_mesh.visual = trimesh.visual.ColorVisuals(
            face_colors=np.full((len(col_mesh.faces), 4), [244, 81, 30, 200], dtype=np.uint8)
        )

        col_mesh.export(output_collision_path, file_type="glb")

        f_after = len(col_mesh.faces)
        v_after = len(col_mesh.vertices)
        red_pct = round(100.0 * (1.0 - (f_after / max(1, f_before))), 2)

        # 2. Extract Convex Hulls of significant sub-structures / clusters
        hulls_info: List[ConvexHullInfo] = []
        try:
            # Cluster vertices or use connected components
            comps = trimesh.graph.connected_components(col_mesh.face_adjacency, min_len=10)
            for idx, c in enumerate(comps[:self.config.convex_hulls_max]):
                sub_faces = col_mesh.faces[c]
                sub_v_idx = np.unique(sub_faces)
                sub_verts = col_mesh.vertices[sub_v_idx]
                if len(sub_verts) >= 4:
                    sub_hull = trimesh.convex.convex_hull(sub_verts)
                    hulls_info.append(ConvexHullInfo(
                        hull_id=idx,
                        vertex_count=len(sub_hull.vertices),
                        face_count=len(sub_hull.faces),
                        centroid=[round(float(x), 4) for x in sub_hull.centroid],
                        bounds=[
                            [round(float(x), 4) for x in sub_hull.bounds[0]],
                            [round(float(x), 4) for x in sub_hull.bounds[1]]
                        ]
                    ))
        except Exception:
            pass

        report = CollisionReport(
            map_id=map_id,
            method="simplified_static_mesh_and_convex_hulls",
            collision_source="cleaned_map_mesh",
            triangle_count=f_after,
            vertex_count=v_after,
            reduction_percentage=red_pct,
            bounds=[
                [round(float(x), 4) for x in col_mesh.bounds[0]],
                [round(float(x), 4) for x in col_mesh.bounds[1]]
            ],
            extents=[round(float(x), 4) for x in col_mesh.extents],
            convex_hulls_count=len(hulls_info),
            hulls_info=hulls_info,
            output_collision_path=output_collision_path
        )

        return col_mesh, report
