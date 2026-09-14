"""
Map Packaging and Quality Gate Management module.
Calculates SHA-256 hashes, generates scene.json, and enforces Quality Gates 1 through 9.
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
import platform
import sys
from typing import Any, Dict, List, Optional
import trimesh
from pipeline.discovery import compute_sha256


@dataclass
class QualityGateResult:
    gate_number: int
    name: str
    status: str  # "PASSED", "FAILED", "HEALED"
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class MapPackageReport:
    map_id: str
    timestamp: str
    environment: Dict[str, Any]
    input_file: str
    input_sha256: str
    quality_profile: str
    quality_gates: List[QualityGateResult]
    all_gates_passed: bool
    output_files: Dict[str, Dict[str, Any]]  # relative_name -> {path, sha256, size_bytes}
    metrics: Dict[str, Any]
    warnings: List[str]
    errors: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "map_id": self.map_id,
            "timestamp": self.timestamp,
            "environment": self.environment,
            "input_file": self.input_file,
            "input_sha256": self.input_sha256,
            "quality_profile": self.quality_profile,
            "quality_gates": [asdict(g) for g in self.quality_gates],
            "all_gates_passed": self.all_gates_passed,
            "output_files": self.output_files,
            "metrics": self.metrics,
            "warnings": self.warnings,
            "errors": self.errors
        }


class MapPackager:
    """Coordinates final map packaging, SHA-256 hashing, scene metadata, and quality gates."""

    @staticmethod
    def get_environment_info() -> Dict[str, Any]:
        return {
            "python_version": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "trimesh_version": getattr(trimesh, "__version__", "unknown"),
        }

    def verify_glb_file(self, glb_path: str) -> bool:
        """Verifies that a generated GLB file exists, has valid header, and can be loaded."""
        if not os.path.exists(glb_path) or os.path.getsize(glb_path) < 20:
            return False
        try:
            m = trimesh.load(glb_path, process=False)
            if isinstance(m, trimesh.Scene):
                return len(m.geometry) > 0
            elif isinstance(m, trimesh.Trimesh):
                return len(m.vertices) > 0
            return False
        except Exception:
            return False

    def build_scene_descriptor(
        self,
        map_id: str,
        output_dir: str,
        bounds: List[List[float]],
        extents: List[float],
        metrics: Dict[str, Any]
    ) -> str:
        """Generates scene.json for game engine import and 3D viewer consumption."""
        scene_data = {
            "map_id": map_id,
            "format_version": "1.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "bounds": {
                "min": bounds[0],
                "max": bounds[1],
                "extents": extents
            },
            "layers": {
                "render": {
                    "file": "optimized/render.glb",
                    "type": "visual_mesh",
                    "visible_by_default": True
                },
                "collision": {
                    "file": "collision/collision.glb",
                    "type": "physics_collision",
                    "visible_by_default": False
                },
                "walkable": {
                    "file": "navigation/walkable.glb",
                    "type": "navigation_surface",
                    "visible_by_default": False
                },
                "segmented": {
                    "file": "segmentation/segmented.glb",
                    "type": "semantic_segmentation",
                    "visible_by_default": False
                }
            },
            "navigation_graph": "navigation/nav_graph.json",
            "metrics": metrics
        }
        scene_path = os.path.join(output_dir, "scene.json")
        with open(scene_path, "w", encoding="utf-8") as f:
            json.dump(scene_data, f, indent=2)
        return scene_path

    def finalize_package(
        self,
        map_id: str,
        map_output_dir: str,
        input_path: str,
        quality_profile: str,
        gate_results: List[QualityGateResult],
        metrics: Dict[str, Any],
        warnings: List[str],
        errors: List[str]
    ) -> MapPackageReport:
        """Collects all generated files, hashes them, and writes reports/process.json."""
        output_files: Dict[str, Dict[str, Any]] = {}

        for root, _, files in os.walk(map_output_dir):
            for f in files:
                full_p = os.path.join(root, f)
                rel_p = os.path.relpath(full_p, map_output_dir).replace("\\", "/")
                # Skip the process.json itself while calculating hashes
                if rel_p == "reports/process.json":
                    continue
                size_b = os.path.getsize(full_p)
                f_hash = compute_sha256(full_p)
                output_files[rel_p] = {
                    "path": rel_p,
                    "sha256": f_hash,
                    "size_bytes": size_b
                }

        input_hash = compute_sha256(input_path) if os.path.exists(input_path) else ""
        all_passed = all(g.status in ["PASSED", "HEALED"] for g in gate_results)

        report = MapPackageReport(
            map_id=map_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            environment=self.get_environment_info(),
            input_file=os.path.basename(input_path),
            input_sha256=input_hash,
            quality_profile=quality_profile,
            quality_gates=gate_results,
            all_gates_passed=all_passed,
            output_files=output_files,
            metrics=metrics,
            warnings=warnings,
            errors=errors
        )

        process_json_path = os.path.join(map_output_dir, "reports", "process.json")
        os.makedirs(os.path.dirname(process_json_path), exist_ok=True)
        with open(process_json_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)

        return report
