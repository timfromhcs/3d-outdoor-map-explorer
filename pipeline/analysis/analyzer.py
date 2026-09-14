"""
Geometry Analysis module for 3D Outdoor Maps.
Extracts topographic, geometric, structural, and normal orientation metrics.
"""
from dataclasses import asdict, dataclass, field
import json
import os
from typing import Any, Dict, List, Optional
import numpy as np
import trimesh


@dataclass
class GeometryAnalysisReport:
    map_id: str
    vertex_count: int
    face_count: int
    bounding_box: List[List[float]]
    extents: List[float]  # [width_x, height_y, depth_z]
    centroid: List[float]
    surface_area: float
    convex_hull_volume: float
    is_watertight: bool
    euler_number: int
    normal_distribution: Dict[str, float]  # horizontal, upward, downward, vertical_walls, steep_slopes
    height_profile: Dict[str, float]  # min_y, max_y, mean_y, median_y, p10, p25, p75, p90
    components_analysis: Dict[str, Any]
    vertex_color_summary: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GeometryAnalyzer:
    """Analyzes geometric properties of 3D meshes."""

    def analyze(self, mesh_or_scene: Any, map_id: str = "") -> GeometryAnalysisReport:
        # Extract main mesh
        if isinstance(mesh_or_scene, trimesh.Scene):
            # Combine all non-gizmo meshes or take largest
            meshes = []
            for name, g in mesh_or_scene.geometry.items():
                if isinstance(g, trimesh.Trimesh) and len(g.vertices) > 30:
                    meshes.append(g)
            if not meshes:
                # Fallback to any geometry
                meshes = [g for g in mesh_or_scene.geometry.values() if isinstance(g, trimesh.Trimesh)]

            if len(meshes) == 1:
                mesh = meshes[0]
            elif len(meshes) > 1:
                mesh = trimesh.util.concatenate(meshes)
            else:
                mesh = trimesh.Trimesh()
        elif isinstance(mesh_or_scene, trimesh.Trimesh):
            mesh = mesh_or_scene
        elif isinstance(mesh_or_scene, str):
            loaded = trimesh.load(mesh_or_scene, process=False)
            return self.analyze(loaded, map_id=map_id or os.path.splitext(os.path.basename(mesh_or_scene))[0])
        else:
            raise ValueError(f"Unsupported geometry type: {type(mesh_or_scene)}")

        v_count = len(mesh.vertices)
        f_count = len(mesh.faces)

        if v_count == 0 or f_count == 0:
            return GeometryAnalysisReport(
                map_id=map_id,
                vertex_count=0,
                face_count=0,
                bounding_box=[[0, 0, 0], [0, 0, 0]],
                extents=[0, 0, 0],
                centroid=[0, 0, 0],
                surface_area=0.0,
                convex_hull_volume=0.0,
                is_watertight=False,
                euler_number=0,
                normal_distribution={},
                height_profile={},
                components_analysis={"total_components": 0}
            )

        bbox = [mesh.bounds[0].tolist(), mesh.bounds[1].tolist()]
        extents = [round(float(x), 4) for x in mesh.extents]
        centroid = [round(float(x), 4) for x in mesh.centroid]
        surface_area = round(float(mesh.area), 4)

        hull_vol = 0.0
        try:
            hull_vol = round(float(mesh.convex_hull.volume), 6)
        except Exception:
            hull_vol = 0.0

        is_watertight = bool(mesh.is_watertight)
        euler_number = int(mesh.euler_number)

        # Height profile (Y axis is up in standard glTF)
        y_coords = mesh.vertices[:, 1]
        height_profile = {
            "min_y": round(float(np.min(y_coords)), 4),
            "max_y": round(float(np.max(y_coords)), 4),
            "mean_y": round(float(np.mean(y_coords)), 4),
            "median_y": round(float(np.median(y_coords)), 4),
            "p10": round(float(np.percentile(y_coords, 10)), 4),
            "p25": round(float(np.percentile(y_coords, 25)), 4),
            "p75": round(float(np.percentile(y_coords, 75)), 4),
            "p90": round(float(np.percentile(y_coords, 90)), 4),
            "total_elevation_span": round(float(np.max(y_coords) - np.min(y_coords)), 4)
        }

        # Normal distribution
        # In glTF Y-up:
        # normal.y close to 1.0 => horizontal flat ground / floor
        # normal.y close to -1.0 => ceiling / bottom
        # abs(normal.y) < 0.3 => vertical walls, cliff sides
        # 0.3 <= normal.y < 0.8 => slopes / ramps
        fn = mesh.face_normals
        ny = fn[:, 1]
        total_faces = len(fn)

        upward_flat = np.sum(ny >= 0.707)  # slope <= 45 deg from horizontal ground
        downward = np.sum(ny <= -0.707)
        vertical_walls = np.sum(np.abs(ny) < 0.3)
        slopes = total_faces - (upward_flat + downward + vertical_walls)

        normal_distribution = {
            "ground_flat_ratio": round(float(upward_flat / total_faces), 4),
            "downward_ratio": round(float(downward / total_faces), 4),
            "vertical_walls_ratio": round(float(vertical_walls / total_faces), 4),
            "slopes_ratio": round(float(slopes / total_faces), 4),
            "mean_normal_abs_y": round(float(np.mean(np.abs(ny))), 4)
        }

        # Connected component breakdown
        comp_info = {"total_components": 1, "largest_component_faces": f_count, "small_isolated_components": 0}
        try:
            comps = trimesh.graph.connected_components(mesh.face_adjacency, min_len=1)
            comp_sizes = sorted([len(c) for c in comps], reverse=True)
            small_count = sum(1 for s in comp_sizes if s < max(50, int(0.005 * f_count)))
            comp_info = {
                "total_components": len(comps),
                "largest_component_faces": comp_sizes[0] if comp_sizes else f_count,
                "largest_component_ratio": round(float(comp_sizes[0] / f_count), 4) if comp_sizes else 1.0,
                "small_isolated_components": small_count,
                "top_5_component_sizes": comp_sizes[:5]
            }
        except Exception:
            pass

        # Vertex color summary
        vc_summary = None
        if hasattr(mesh.visual, "vertex_colors") and mesh.visual.vertex_colors is not None and len(mesh.visual.vertex_colors) > 0:
            colors = mesh.visual.vertex_colors[:, :3]
            vc_summary = {
                "has_vertex_colors": True,
                "mean_rgb": [round(float(c), 1) for c in np.mean(colors, axis=0)],
                "std_rgb": [round(float(c), 1) for c in np.std(colors, axis=0)]
            }

        return GeometryAnalysisReport(
            map_id=map_id,
            vertex_count=v_count,
            face_count=f_count,
            bounding_box=bbox,
            extents=extents,
            centroid=centroid,
            surface_area=surface_area,
            convex_hull_volume=hull_vol,
            is_watertight=is_watertight,
            euler_number=euler_number,
            normal_distribution=normal_distribution,
            height_profile=height_profile,
            components_analysis=comp_info,
            vertex_color_summary=vc_summary
        )

    def export_report_json(self, report: GeometryAnalysisReport, output_path: str) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)
        return output_path
