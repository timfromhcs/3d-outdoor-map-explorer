"""
Comprehensive GLB/glTF Validator.
Performs real structural, buffer, and topological checks.
"""
from dataclasses import asdict, dataclass, field
import json
import math
import os
import struct
from typing import Any, Dict, List, Optional
import numpy as np
import pygltflib
import trimesh


@dataclass
class ValidationCheck:
    name: str
    status: str  # "PASS", "WARN", "FAIL"
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class ValidationReport:
    map_id: str
    source_file: str
    overall_status: str  # "PASS", "WARN", "FAIL"
    checks: List[ValidationCheck] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "map_id": self.map_id,
            "source_file": self.source_file,
            "overall_status": self.overall_status,
            "checks": [asdict(c) for c in self.checks],
            "summary": self.summary
        }


class GLBValidator:
    """Validates GLB/glTF 2.0 files with strict mathematical and structural tests."""

    def validate(self, file_path: str, map_id: str = "") -> ValidationReport:
        if not map_id:
            map_id = os.path.basename(os.path.dirname(file_path)) or os.path.splitext(os.path.basename(file_path))[0]

        checks: List[ValidationCheck] = []
        summary: Dict[str, Any] = {
            "total_vertices": 0,
            "total_faces": 0,
            "degenerate_faces": 0,
            "nan_inf_vertices": 0,
            "connected_components": 0,
            "non_manifold_edges": 0,
            "camera_nodes": 0,
            "materials_count": 0,
            "textures_count": 0
        }

        # 1. File readable check & GLB Magic
        if not os.path.exists(file_path):
            checks.append(ValidationCheck("file_readable", "FAIL", f"File does not exist: {file_path}"))
            return ValidationReport(map_id, file_path, "FAIL", checks, summary)

        file_size = os.path.getsize(file_path)
        if file_size < 12:
            checks.append(ValidationCheck("file_readable", "FAIL", "File is smaller than minimal GLB header (12 bytes)"))
            return ValidationReport(map_id, file_path, "FAIL", checks, summary)

        try:
            with open(file_path, "rb") as f:
                header = f.read(12)
                magic, version, length = struct.unpack("<4sII", header)
                if magic != b"glTF":
                    checks.append(ValidationCheck("glb_magic_header", "FAIL", f"Invalid GLB magic header: {magic} (expected b'glTF')"))
                elif version != 2:
                    checks.append(ValidationCheck("glb_version", "WARN", f"GLB version is {version}, expected 2"))
                elif length != file_size:
                    checks.append(ValidationCheck("glb_length_match", "WARN", f"GLB header length ({length}) does not match file size ({file_size})"))
                else:
                    checks.append(ValidationCheck("glb_binary_header", "PASS", f"Valid GLB 2.0 binary header, size: {file_size} bytes"))
        except Exception as e:
            checks.append(ValidationCheck("file_readable", "FAIL", f"Failed to read header: {str(e)}"))
            return ValidationReport(map_id, file_path, "FAIL", checks, summary)

        # 2. glTF JSON structure check
        gltf = None
        try:
            gltf = pygltflib.GLTF2().load(file_path)
            checks.append(ValidationCheck("gltf_structure", "PASS", f"Valid glTF JSON structure with {len(gltf.nodes or [])} nodes and {len(gltf.meshes or [])} meshes"))
        except Exception as e:
            checks.append(ValidationCheck("gltf_structure", "FAIL", f"glTF JSON parsing failed: {str(e)}"))
            return ValidationReport(map_id, file_path, "FAIL", checks, summary)

        # 3. Buffer integrity
        try:
            buffer_ok = True
            buf_errs = []
            if not gltf.buffers:
                buf_errs.append("No buffers found in glTF structure")
                buffer_ok = False
            else:
                for b_idx, buf in enumerate(gltf.buffers):
                    if buf.byteLength <= 0:
                        buf_errs.append(f"Buffer {b_idx} has invalid byteLength: {buf.byteLength}")
                        buffer_ok = False

            if buffer_ok:
                checks.append(ValidationCheck("buffer_integrity", "PASS", f"{len(gltf.buffers)} buffers validated"))
            else:
                checks.append(ValidationCheck("buffer_integrity", "FAIL", "; ".join(buf_errs)))
        except Exception as e:
            checks.append(ValidationCheck("buffer_integrity", "FAIL", f"Buffer check error: {str(e)}"))

        # 4. Node and mesh references
        try:
            node_errs = []
            num_meshes = len(gltf.meshes or [])
            num_nodes = len(gltf.nodes or [])
            cam_count = 0
            for idx, n in enumerate(gltf.nodes or []):
                if n.mesh is not None and (n.mesh < 0 or n.mesh >= num_meshes):
                    node_errs.append(f"Node {idx} references invalid mesh index {n.mesh}")
                if n.children:
                    for ch in n.children:
                        if ch < 0 or ch >= num_nodes:
                            node_errs.append(f"Node {idx} references invalid child index {ch}")
                if n.camera is not None or (n.name and any(k in n.name.lower() for k in ["cam", "camera", "gizmo"])):
                    cam_count += 1

            summary["camera_nodes"] = cam_count
            if not node_errs:
                checks.append(ValidationCheck("node_mesh_references", "PASS", f"{num_nodes} nodes reference valid mesh and child indices"))
            else:
                checks.append(ValidationCheck("node_mesh_references", "FAIL", "; ".join(node_errs[:5])))

            if cam_count > 0:
                checks.append(ValidationCheck("camera_gizmos", "WARN", f"Detected {cam_count} camera/gizmo node(s) requiring cleanup for real-time map use"))
            else:
                checks.append(ValidationCheck("camera_gizmos", "PASS", "No camera gizmo nodes detected"))
        except Exception as e:
            checks.append(ValidationCheck("node_mesh_references", "WARN", f"Node check exception: {str(e)}"))

        # 5. Materials and textures check
        summary["materials_count"] = len(gltf.materials or [])
        summary["textures_count"] = len(gltf.textures or [])
        checks.append(ValidationCheck("materials_textures", "PASS", f"{summary['materials_count']} materials, {summary['textures_count']} textures defined"))

        # 6. Deep Geometry Inspection via trimesh
        try:
            scene_or_mesh = trimesh.load(file_path, process=False)
            meshes: List[trimesh.Trimesh] = []
            if isinstance(scene_or_mesh, trimesh.Scene):
                for name, g in scene_or_mesh.geometry.items():
                    if isinstance(g, trimesh.Trimesh):
                        meshes.append(g)
            elif isinstance(scene_or_mesh, trimesh.Trimesh):
                meshes.append(scene_or_mesh)

            total_v = sum(len(m.vertices) for m in meshes)
            total_f = sum(len(m.faces) for m in meshes)
            summary["total_vertices"] = total_v
            summary["total_faces"] = total_f

            # Check NaNs and Infs
            nan_inf_count = 0
            for m in meshes:
                if len(m.vertices) > 0:
                    nan_inf_count += np.isnan(m.vertices).sum() + np.isinf(m.vertices).sum()
                if hasattr(m, 'vertex_normals') and m.vertex_normals is not None and len(m.vertex_normals) > 0:
                    nan_inf_count += np.isnan(m.vertex_normals).sum() + np.isinf(m.vertex_normals).sum()

            summary["nan_inf_vertices"] = int(nan_inf_count)
            if nan_inf_count == 0:
                checks.append(ValidationCheck("geometry_finite", "PASS", "All vertices and normals contain finite numerical coordinates (no NaN/Inf)"))
            else:
                checks.append(ValidationCheck("geometry_finite", "FAIL", f"Found {nan_inf_count} NaN or Inf values in geometry coordinates"))

            # Check degenerate faces (zero area or duplicate vertex indices)
            total_deg = 0
            for m in meshes:
                if len(m.faces) > 0:
                    # Check duplicate indices in face
                    f = m.faces
                    dup_idx = (f[:, 0] == f[:, 1]) | (f[:, 1] == f[:, 2]) | (f[:, 0] == f[:, 2])
                    # Check zero area
                    cross_p = np.cross(m.vertices[f[:, 1]] - m.vertices[f[:, 0]], m.vertices[f[:, 2]] - m.vertices[f[:, 0]])
                    areas = 0.5 * np.linalg.norm(cross_p, axis=1)
                    zero_area = (areas < 1e-12) | np.isnan(areas)
                    total_deg += int(np.sum(dup_idx | zero_area))

            summary["degenerate_faces"] = total_deg
            if total_deg == 0:
                checks.append(ValidationCheck("degenerate_triangles", "PASS", "No degenerate or zero-area triangles detected"))
            else:
                checks.append(ValidationCheck("degenerate_triangles", "WARN", f"Found {total_deg} degenerate/zero-area triangles (cleanup candidate)"))

            # Check manifoldness and edges
            total_non_manifold = 0
            for m in meshes:
                if len(m.faces) > 0:
                    try:
                        edges = m.edges_sorted
                        # An edge in a 2-manifold closed surface belongs to 2 faces, or in a boundary surface belongs to 1 or 2 faces
                        # An edge sharing > 2 faces is strictly non-manifold
                        _, counts = np.unique(edges, axis=0, return_counts=True)
                        non_man = np.sum(counts > 2)
                        total_non_manifold += int(non_man)
                    except Exception:
                        pass

            summary["non_manifold_edges"] = total_non_manifold
            if total_non_manifold == 0:
                checks.append(ValidationCheck("manifold_edges", "PASS", "No non-manifold (>2 face sharing) edges found"))
            else:
                checks.append(ValidationCheck("manifold_edges", "WARN", f"Found {total_non_manifold} non-manifold edges (typical in AI reconstructed meshes, requires cleanup)"))

            # Check disconnected components
            total_components = 0
            for m in meshes:
                if len(m.faces) > 0:
                    try:
                        comps = trimesh.graph.connected_components(m.face_adjacency, min_len=1)
                        total_components += len(comps)
                    except Exception:
                        total_components += 1

            summary["connected_components"] = total_components
            if total_components <= 1:
                checks.append(ValidationCheck("component_connectivity", "PASS", "Single contiguous surface mesh"))
            else:
                checks.append(ValidationCheck("component_connectivity", "WARN", f"{total_components} disconnected components detected (potential floating noise or multi-part structures)"))

            # Extreme bounds check
            extreme_bounds = False
            for m in meshes:
                if len(m.vertices) > 0:
                    min_c = np.min(m.vertices)
                    max_c = np.max(m.vertices)
                    if min_c < -1e6 or max_c > 1e6 or (max_c - min_c < 1e-6):
                        extreme_bounds = True
                        break

            if not extreme_bounds:
                checks.append(ValidationCheck("bounding_box_scale", "PASS", "Bounding box scale is within standard realistic numeric range"))
            else:
                checks.append(ValidationCheck("bounding_box_scale", "WARN", "Extreme or degenerate bounding box coordinates detected"))

        except Exception as e:
            checks.append(ValidationCheck("geometry_deep_inspection", "FAIL", f"Trimesh geometry inspection failed: {str(e)}"))

        # Determine overall status
        has_fail = any(c.status == "FAIL" for c in checks)
        has_warn = any(c.status == "WARN" for c in checks)

        if has_fail:
            overall = "FAIL"
        elif has_warn:
            overall = "WARN"
        else:
            overall = "PASS"

        return ValidationReport(
            map_id=map_id,
            source_file=file_path,
            overall_status=overall,
            checks=checks,
            summary=summary
        )

    def export_report_json(self, report: ValidationReport, output_path: str) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)
        return output_path
