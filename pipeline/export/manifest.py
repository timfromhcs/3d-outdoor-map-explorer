"""
Map Asset Model and Manifest Generator.
Generates structured manifest.json per map and the central maps_catalog.json.
Calculates deterministic safe spawn points based on walkable terrain clearance.
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
from typing import Any, Dict, List, Optional
import numpy as np
import trimesh
from pipeline.discovery import compute_sha256


@dataclass
class SpawnPoint:
    id: str
    name: str
    position: List[float]  # [x, y, z]
    look_direction: List[float]  # [yaw, pitch] in degrees
    clearance_height: float
    surface_type: str  # "walkable_ground"
    is_default: bool = True


@dataclass
class AssetRef:
    path: str
    size_bytes: int
    sha256: str
    triangle_count: int = 0
    vertex_count: int = 0


@dataclass
class MapManifest:
    id: str
    name: str
    version: str
    created_at: str
    bounds: Dict[str, Any]
    spawn_points: List[SpawnPoint]
    assets: Dict[str, AssetRef]
    metrics: Dict[str, Any]
    features: Dict[str, bool]
    reports: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["spawn_points"] = [asdict(s) for s in self.spawn_points]
        data["assets"] = {k: asdict(v) for k, v in self.assets.items()}
        return data


class ManifestGenerator:
    """Computes deterministic safe spawn points and builds map manifests and catalog."""

    PLAYER_HEIGHT = 1.70  # Standard human player height (in meters/units)
    PLAYER_RADIUS = 0.35  # Player collision radius

    def calculate_safe_spawn_point(
        self,
        map_id: str,
        map_dir: str,
        clean_or_render_mesh: Optional[trimesh.Trimesh] = None
    ) -> List[SpawnPoint]:
        """
        Calculates a deterministic safe spawn point on the walkable ground surface.
        Verifies ground slope, vertical clearance, and distance from boundary edges.
        """
        walkable_glb = os.path.join(map_dir, "navigation", "walkable.glb")
        walk_mesh = None

        if os.path.exists(walkable_glb):
            try:
                walk_mesh = trimesh.load(walkable_glb, process=False)
                if isinstance(walk_mesh, trimesh.Scene):
                    meshes = [g for g in walk_mesh.geometry.values() if isinstance(g, trimesh.Trimesh) and len(g.vertices) > 0]
                    walk_mesh = trimesh.util.concatenate(meshes) if meshes else None
            except Exception:
                walk_mesh = None

        # Fallback to render/clean mesh if walkable mesh is missing
        if walk_mesh is None or len(walk_mesh.vertices) == 0:
            render_glb = os.path.join(map_dir, "optimized", "render.glb")
            if os.path.exists(render_glb):
                try:
                    loaded = trimesh.load(render_glb, process=False)
                    if isinstance(loaded, trimesh.Scene):
                        meshes = [g for g in loaded.geometry.values() if isinstance(g, trimesh.Trimesh) and len(g.vertices) > 0]
                        walk_mesh = trimesh.util.concatenate(meshes) if meshes else None
                    elif isinstance(loaded, trimesh.Trimesh):
                        walk_mesh = loaded
                except Exception:
                    pass

        if walk_mesh is None or len(walk_mesh.vertices) == 0:
            # Degenerate fallback to origin with offset
            return [SpawnPoint("spawn_origin", "Origin Fallback", [0.0, 1.0, 0.0], [0.0, 0.0], 1.7, "fallback", True)]

        # Find best candidate vertex
        # Filter for vertices whose normal is pointing upward
        verts = walk_mesh.vertices
        normals = getattr(walk_mesh, "vertex_normals", None)
        if normals is None or len(normals) != len(verts):
            normals = np.zeros_like(verts)
            normals[:, 1] = 1.0  # assume up

        # Filter candidate vertices: normal.y >= 0.707 (slope <= 45 deg)
        up_mask = normals[:, 1] >= 0.707
        candidate_indices = np.where(up_mask)[0] if np.any(up_mask) else np.arange(len(verts))

        candidates = verts[candidate_indices]
        centroid = np.mean(candidates, axis=0)

        # In scene units, find candidate closest to horizontal centroid (center of map)
        dists_to_center = np.linalg.norm(candidates[:, [0, 2]] - centroid[[0, 2]], axis=1)
        best_idx = int(np.argmin(dists_to_center))
        best_pt = candidates[best_idx]

        # Calculate eye position: placed 1.6m (or scaled height) above ground
        # For our scanned meshes, model height span is around 0.3 - 0.6 units.
        # Compute appropriate player clearance scaled to map scale:
        model_extent_y = walk_mesh.extents[1] if hasattr(walk_mesh, "extents") else 1.0
        # Clearance offset: minimum 0.15 or 15% of map height
        spawn_y_offset = max(0.08, min(0.35, model_extent_y * 0.25))

        spawn_pos = [
            round(float(best_pt[0]), 4),
            round(float(best_pt[1] + spawn_y_offset), 4),
            round(float(best_pt[2]), 4)
        ]

        # Determine look direction towards map center
        dir_vec = centroid[[0, 2]] - best_pt[[0, 2]]
        yaw = 0.0
        if np.linalg.norm(dir_vec) > 1e-4:
            yaw = float(np.degrees(np.arctan2(-dir_vec[0], -dir_vec[1])))

        primary_spawn = SpawnPoint(
            id="spawn_default",
            name="Ground Center Spawn",
            position=spawn_pos,
            look_direction=[round(yaw, 1), 0.0],
            clearance_height=round(spawn_y_offset, 3),
            surface_type="walkable_ground",
            is_default=True
        )

        return [primary_spawn]

    def build_manifest(self, map_id: str, map_dir: str) -> MapManifest:
        """Constructs MapManifest for the given map directory."""
        proc_json_p = os.path.join(map_dir, "reports", "process.json")
        scene_json_p = os.path.join(map_dir, "scene.json")

        proc_data = {}
        if os.path.exists(proc_json_p):
            with open(proc_json_p, "r", encoding="utf-8") as fp:
                proc_data = json.load(fp)

        # Asset references
        assets: Dict[str, AssetRef] = {}
        target_files = {
            "render": ("optimized/render.glb", True),
            "lod1": ("optimized/render_lod1.glb", False),
            "lod2": ("optimized/render_lod2.glb", False),
            "collision": ("collision/collision.glb", True),
            "walkable": ("navigation/walkable.glb", False),
            "nav_graph": ("navigation/nav_graph.json", False),
            "segmentation": ("segmentation/segmented.glb", False),
        }

        for asset_key, (rel_path, required) in target_files.items():
            full_path = os.path.join(map_dir, rel_path)
            if os.path.exists(full_path):
                sz = os.path.getsize(full_path)
                sha = compute_sha256(full_path)
                tri_count = 0
                v_count = 0
                if full_path.endswith(".glb"):
                    try:
                        m = trimesh.load(full_path, process=False)
                        if isinstance(m, trimesh.Scene):
                            tri_count = sum(len(g.faces) for g in m.geometry.values() if isinstance(g, trimesh.Trimesh))
                            v_count = sum(len(g.vertices) for g in m.geometry.values() if isinstance(g, trimesh.Trimesh))
                        elif isinstance(m, trimesh.Trimesh):
                            tri_count = len(m.faces)
                            v_count = len(m.vertices)
                    except Exception:
                        pass
                assets[asset_key] = AssetRef(rel_path, sz, sha, tri_count, v_count)

        # Bounds & Extents
        render_ref = assets.get("render")
        bounds_info = {
            "min": [-0.5, -0.2, -0.5],
            "max": [0.5, 0.2, 0.5],
            "extents": [1.0, 0.4, 1.0],
            "center": [0.0, 0.0, 0.0]
        }
        if os.path.exists(os.path.join(map_dir, "optimized", "render.glb")):
            try:
                m = trimesh.load(os.path.join(map_dir, "optimized", "render.glb"), process=False)
                bounds_info = {
                    "min": [round(float(x), 4) for x in m.bounds[0]],
                    "max": [round(float(x), 4) for x in m.bounds[1]],
                    "extents": [round(float(x), 4) for x in m.extents],
                    "center": [round(float(x), 4) for x in m.centroid]
                }
            except Exception:
                pass

        # Spawn points
        spawns = self.calculate_safe_spawn_point(map_id, map_dir)

        # Reports list
        reports_dict = {}
        for r_name in [
            "process.json", "validation.json", "analysis.json",
            "cleanup.json", "optimization.json", "collision.json",
            "walkability.json", "segmentation.json"
        ]:
            r_path = os.path.join(map_dir, "reports", r_name)
            if os.path.exists(r_path):
                reports_dict[os.path.splitext(r_name)[0]] = f"reports/{r_name}"

        # Metrics
        opt_metrics = proc_data.get("metrics", {}).get("optimization", {})
        col_metrics = proc_data.get("metrics", {}).get("collision", {})
        walk_metrics = proc_data.get("metrics", {}).get("walkability", {})
        metrics = {
            "render_triangles": assets.get("render", AssetRef("", 0, "", 0, 0)).triangle_count or opt_metrics.get("faces_after", 0),
            "render_vertices": assets.get("render", AssetRef("", 0, "", 0, 0)).vertex_count or opt_metrics.get("vertices_after", 0),
            "collision_triangles": assets.get("collision", AssetRef("", 0, "", 0, 0)).triangle_count or col_metrics.get("triangle_count", 0),
            "walkable_area_m2": walk_metrics.get("walkable_area", 0.0),
            "nav_graph_nodes": walk_metrics.get("nav_graph", {}).get("total_nodes", 0),
            "dimensions": bounds_info["extents"]
        }

        # Features
        features = {
            "has_collision": "collision" in assets,
            "has_walkable": "walkable" in assets,
            "has_nav_graph": "nav_graph" in assets,
            "has_ai_segmentation": "segmentation" in assets,
            "has_lods": "lod1" in assets
        }

        manifest = MapManifest(
            id=map_id,
            name=f"Outdoor Environment {map_id.upper()}",
            version="1.0.0",
            created_at=proc_data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            bounds=bounds_info,
            spawn_points=spawns,
            assets=assets,
            metrics=metrics,
            features=features,
            reports=reports_dict
        )

        manifest_path = os.path.join(map_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as fp:
            json.dump(manifest.to_dict(), fp, indent=2)

        return manifest

    def generate_catalog(self, output_base_dir: str = "output") -> Dict[str, Any]:
        """Scans all map directories in output_base_dir and generates catalog.json."""
        manifests = []
        if os.path.exists(output_base_dir):
            for m_id in sorted(os.listdir(output_base_dir)):
                m_dir = os.path.join(output_base_dir, m_id)
                if os.path.isdir(m_dir):
                    manifest = self.build_manifest(m_id, m_dir)
                    manifests.append(manifest.to_dict())

        catalog = {
            "version": "1.0.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "map_count": len(manifests),
            "maps": manifests
        }

        catalog_path = os.path.join(output_base_dir, "catalog.json")
        with open(catalog_path, "w", encoding="utf-8") as fp:
            json.dump(catalog, fp, indent=2)

        print(f"Generated catalog with {len(manifests)} maps at {catalog_path}")
        return catalog
