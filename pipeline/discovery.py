"""
Asset Discovery module for 3D Outdoor Maps.
Scans folders automatically for 3D map files (.glb, .gltf, .fbx, .obj).
"""
from dataclasses import asdict, dataclass, field
import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import trimesh
import pygltflib


@dataclass
class MapAssetInfo:
    map_id: str
    source_filename: str
    source_path: str
    file_size_bytes: int
    file_size_mb: float
    sha256: str
    format: str
    vertex_count: int
    triangle_count: int
    material_count: int
    texture_count: int
    dimensions: List[float]
    bounding_box: List[List[float]]
    component_count: int
    associated_files: List[str] = field(default_factory=list)
    camera_gizmos_detected: bool = False
    validation_status: str = "PENDING"
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compute_sha256(file_path: str, chunk_size: int = 65536) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


class AssetScanner:
    """Scans for 3D map assets without requiring manual path entry."""

    SUPPORTED_EXTENSIONS = {".glb", ".gltf", ".obj", ".fbx"}

    def __init__(self, search_paths: Optional[List[str]] = None):
        if not search_paths:
            self.search_paths = ["Maps", "input", "."]
        else:
            self.search_paths = search_paths

    def scan(self, target_dir: Optional[str] = None) -> List[MapAssetInfo]:
        """Scan directories and return list of discovered map assets."""
        paths_to_check = [target_dir] if target_dir else self.search_paths
        discovered_maps: List[MapAssetInfo] = []
        visited_files = set()

        for base_path in paths_to_check:
            if not os.path.exists(base_path):
                continue

            for root, dirs, files in os.walk(base_path):
                # Ignore output, reports, venv, git, cache directories
                norm_root = os.path.normpath(root).lower()
                if any(ignored in norm_root.split(os.sep) for ignored in [
                    "output", "reports", ".venv", ".git", "node_modules", "__pycache__", ".pytest_cache"
                ]):
                    continue

                # Find 3D model files
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in self.SUPPORTED_EXTENSIONS:
                        full_path = os.path.abspath(os.path.join(root, f))
                        if full_path in visited_files:
                            continue
                        visited_files.add(full_path)

                        asset_info = self._analyze_file(full_path, root, f, ext)
                        if asset_info:
                            discovered_maps.append(asset_info)

        # Sort predictably by map_id
        discovered_maps.sort(key=lambda x: x.map_id)
        return discovered_maps

    def _analyze_file(self, full_path: str, root_dir: str, filename: str, ext: str) -> Optional[MapAssetInfo]:
        """Deeply inspect the discovered file and its surrounding assets."""
        try:
            file_size = os.path.getsize(full_path)
            file_hash = compute_sha256(full_path)

            # Determine map ID from parent directory or filename
            parent_dir_name = os.path.basename(root_dir)
            if parent_dir_name.lower() in ["maps", "input", "."]:
                map_id = os.path.splitext(filename)[0]
            else:
                map_id = parent_dir_name

            # Check associated files in same directory (e.g. ply, png, etc.)
            associated = []
            for sibling in os.listdir(root_dir):
                sib_path = os.path.join(root_dir, sibling)
                if os.path.isfile(sib_path) and sibling != filename:
                    associated.append(sibling)

            vertex_count = 0
            triangle_count = 0
            material_count = 0
            texture_count = 0
            dimensions = [0.0, 0.0, 0.0]
            bounding_box = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
            component_count = 0
            camera_gizmos = False
            notes = []

            # Low-level glTF inspection if applicable
            if ext in [".glb", ".gltf"]:
                try:
                    gltf = pygltflib.GLTF2().load(full_path)
                    material_count = len(gltf.materials) if gltf.materials else 0
                    texture_count = len(gltf.textures) if gltf.textures else 0
                    for node in (gltf.nodes or []):
                        if node.name and any(k in node.name.lower() for k in ["cam", "camera", "gizmo"]):
                            camera_gizmos = True
                except Exception as e:
                    notes.append(f"pygltflib parse warning: {str(e)}")

            # Trimesh geometry inspection
            try:
                loaded = trimesh.load(full_path, process=False)
                if isinstance(loaded, trimesh.Scene):
                    total_v = 0
                    total_f = 0
                    all_bounds_min = []
                    all_bounds_max = []
                    for name, geom in loaded.geometry.items():
                        if isinstance(geom, trimesh.Trimesh):
                            total_v += len(geom.vertices)
                            total_f += len(geom.faces)
                            all_bounds_min.append(geom.bounds[0])
                            all_bounds_max.append(geom.bounds[1])
                            # Check if tiny camera frustum
                            if len(geom.vertices) < 30 and any(k in name.lower() for k in ["cam", "gizmo", "1"]):
                                camera_gizmos = True

                    vertex_count = total_v
                    triangle_count = total_f

                    if all_bounds_min and all_bounds_max:
                        import numpy as np
                        b_min = np.min(all_bounds_min, axis=0).tolist()
                        b_max = np.max(all_bounds_max, axis=0).tolist()
                        bounding_box = [b_min, b_max]
                        dimensions = [round(b_max[i] - b_min[i], 4) for i in range(3)]

                    component_count = len(loaded.geometry)
                elif isinstance(loaded, trimesh.Trimesh):
                    vertex_count = len(loaded.vertices)
                    triangle_count = len(loaded.faces)
                    bounding_box = [loaded.bounds[0].tolist(), loaded.bounds[1].tolist()]
                    dimensions = [round(loaded.extents[i], 4) for i in range(3)]
                    component_count = 1
            except Exception as e:
                notes.append(f"Geometry parse error: {str(e)}")

            return MapAssetInfo(
                map_id=map_id,
                source_filename=filename,
                source_path=full_path,
                file_size_bytes=file_size,
                file_size_mb=round(file_size / (1024 * 1024), 2),
                sha256=file_hash,
                format=ext.upper().replace(".", ""),
                vertex_count=vertex_count,
                triangle_count=triangle_count,
                material_count=material_count,
                texture_count=texture_count,
                dimensions=dimensions,
                bounding_box=bounding_box,
                component_count=component_count,
                associated_files=associated,
                camera_gizmos_detected=camera_gizmos,
                validation_status="PENDING",
                notes=notes
            )
        except Exception as e:
            return None

    def export_inventory_json(self, assets: List[MapAssetInfo], output_path: str) -> str:
        import json
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        data = {
            "total_maps": len(assets),
            "maps": [a.to_dict() for a in assets]
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return output_path

    def export_inventory_markdown(self, assets: List[MapAssetInfo], output_path: str) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        lines = [
            "# 3D Map Asset Inventory",
            "",
            f"**Total Discovered Maps:** {len(assets)}",
            "",
            "| Map ID | Source File | Size (MB) | Vertices | Triangles | Dimensions (X, Y, Z) | SHA-256 (Prefix) |",
            "|---|---|---|---|---|---|---|"
        ]
        for a in assets:
            dims = f"{a.dimensions[0]:.2f} x {a.dimensions[1]:.2f} x {a.dimensions[2]:.2f}"
            sha_pref = a.sha256[:10] + "..."
            lines.append(f"| `{a.map_id}` | `{a.source_filename}` | {a.file_size_mb} MB | {a.vertex_count:,} | {a.triangle_count:,} | `{dims}` | `{sha_pref}` |")

        lines.append("")
        lines.append("## Detailed Map Breakdown")
        for a in assets:
            lines.append(f"### Map: `{a.map_id}`")
            lines.append(f"- **Path:** `{a.source_path}`")
            lines.append(f"- **Format:** {a.format}")
            lines.append(f"- **File Size:** {a.file_size_bytes:,} bytes ({a.file_size_mb} MB)")
            lines.append(f"- **SHA-256:** `{a.sha256}`")
            lines.append(f"- **Vertices:** {a.vertex_count:,}")
            lines.append(f"- **Triangles:** {a.triangle_count:,}")
            lines.append(f"- **Materials:** {a.material_count}")
            lines.append(f"- **Textures:** {a.texture_count}")
            lines.append(f"- **Bounding Box:** `Min: {a.bounding_box[0]}`, `Max: {a.bounding_box[1]}`")
            lines.append(f"- **Camera Gizmos Detected:** {a.camera_gizmos_detected}")
            lines.append(f"- **Associated Sibling Files:** {', '.join(a.associated_files) if a.associated_files else 'None'}")
            if a.notes:
                lines.append(f"- **Notes:** {'; '.join(a.notes)}")
            lines.append("")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return output_path
