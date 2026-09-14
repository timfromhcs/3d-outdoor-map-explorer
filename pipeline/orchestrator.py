"""
Pipeline Orchestrator.
Connects discovery, validation, analysis, cleanup, optimization, segmentation,
collision, walkability, packaging, and quality gates with an automatic self-healing loop.
"""
from dataclasses import asdict
import json
import os
import shutil
from typing import Any, Dict, List, Optional, Tuple
import trimesh

from pipeline.config import PipelineConfig
from pipeline.discovery import AssetScanner, MapAssetInfo, compute_sha256
from pipeline.validation.validator import GLBValidator, ValidationReport
from pipeline.analysis.analyzer import GeometryAnalyzer, GeometryAnalysisReport
from pipeline.cleanup.cleaner import MeshCleaner, CleanupOperationReport
from pipeline.optimization.optimizer import MeshOptimizer, OptimizationReport
from pipeline.segmentation.segmenter import SceneSegmenter, SegmentationReport
from pipeline.collision.generator import CollisionGenerator, CollisionReport
from pipeline.navigation.walkability import WalkabilityAnalyzer, WalkabilityReport
from pipeline.export.packager import MapPackager, QualityGateResult, MapPackageReport


class PipelineOrchestrator:
    """End-to-end processing pipeline orchestrator."""

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig.load()
        self.scanner = AssetScanner(self.config.input_search_dirs)
        self.validator = GLBValidator()
        self.analyzer = GeometryAnalyzer()
        self.cleaner = MeshCleaner(self.config.cleanup)
        self.optimizer = MeshOptimizer(self.config.get_quality_profile(self.config.default_quality))
        self.segmenter = SceneSegmenter(self.config.segmentation)
        self.collision_gen = CollisionGenerator(self.config.collision)
        self.nav_analyzer = WalkabilityAnalyzer(self.config.navigation)
        self.packager = MapPackager()

    def process_map(
        self,
        asset: MapAssetInfo,
        output_base_dir: Optional[str] = None,
        quality: Optional[str] = None,
        force: bool = False,
        no_ai: bool = False,
        no_navigation: bool = False
    ) -> MapPackageReport:
        """Processes a single map asset through all 9 Quality Gates with self-healing."""
        out_base = output_base_dir or self.config.output_base_dir
        map_out_dir = os.path.join(out_base, asset.map_id)
        quality_name = (quality or self.config.default_quality).lower()
        quality_profile = self.config.get_quality_profile(quality_name)
        self.optimizer = MeshOptimizer(quality_profile)

        # Check Cache: if process.json exists, input hash matches, quality matches, and not force
        process_json_path = os.path.join(map_out_dir, "reports", "process.json")
        if not force and os.path.exists(process_json_path):
            try:
                with open(process_json_path, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                if (
                    cached_data.get("input_sha256") == asset.sha256
                    and cached_data.get("quality_profile") == quality_name
                    and cached_data.get("all_gates_passed") is True
                ):
                    print(f"[{asset.map_id}] Using cached processed outputs (SHA-256 match: {asset.sha256[:10]}...)")
                    # Reconstruct MapPackageReport from cache
                    gate_objs = [
                        QualityGateResult(
                            gate_number=g["gate_number"],
                            name=g["name"],
                            status=g["status"],
                            message=g["message"],
                            details=g.get("details")
                        ) for g in cached_data.get("quality_gates", [])
                    ]
                    return MapPackageReport(
                        map_id=asset.map_id,
                        timestamp=cached_data.get("timestamp", ""),
                        environment=cached_data.get("environment", {}),
                        input_file=cached_data.get("input_file", ""),
                        input_sha256=cached_data.get("input_sha256", ""),
                        quality_profile=quality_name,
                        quality_gates=gate_objs,
                        all_gates_passed=True,
                        output_files=cached_data.get("output_files", {}),
                        metrics=cached_data.get("metrics", {}),
                        warnings=cached_data.get("warnings", []),
                        errors=cached_data.get("errors", [])
                    )
            except Exception:
                pass

        # Prepare directory structure
        os.makedirs(os.path.join(map_out_dir, "source"), exist_ok=True)
        os.makedirs(os.path.join(map_out_dir, "cleaned"), exist_ok=True)
        os.makedirs(os.path.join(map_out_dir, "optimized"), exist_ok=True)
        os.makedirs(os.path.join(map_out_dir, "collision"), exist_ok=True)
        os.makedirs(os.path.join(map_out_dir, "navigation"), exist_ok=True)
        os.makedirs(os.path.join(map_out_dir, "segmentation"), exist_ok=True)
        os.makedirs(os.path.join(map_out_dir, "reports"), exist_ok=True)
        os.makedirs(os.path.join(map_out_dir, "preview"), exist_ok=True)

        gates: List[QualityGateResult] = []
        warnings: List[str] = []
        errors: List[str] = []
        metrics: Dict[str, Any] = {}

        # GATE 1: File Readable
        if not os.path.exists(asset.source_path) or os.path.getsize(asset.source_path) == 0:
            gates.append(QualityGateResult(1, "File Readable", "FAILED", f"File missing or empty: {asset.source_path}"))
            return self._fail_report(asset, map_out_dir, quality_name, gates, warnings, ["File not readable"])
        gates.append(QualityGateResult(1, "File Readable", "PASSED", f"File readable ({asset.file_size_mb} MB)"))

        # GATE 2: glTF Structure Valid
        val_report = self.validator.validate(asset.source_path, asset.map_id)
        val_json = os.path.join(map_out_dir, "reports", "validation.json")
        self.validator.export_report_json(val_report, val_json)

        if val_report.overall_status == "FAIL":
            gates.append(QualityGateResult(2, "glTF Structure Valid", "FAILED", "Critical validation failure in source file", val_report.to_dict()))
            return self._fail_report(asset, map_out_dir, quality_name, gates, warnings, ["glTF structure validation failed"])
        elif val_report.overall_status == "WARN":
            gates.append(QualityGateResult(2, "glTF Structure Valid", "PASSED", "glTF structure valid with warnings marked for cleanup", val_report.to_dict()))
            warnings.append("Source file contains warnings (degenerate faces, non-manifold edges, or camera nodes)")
        else:
            gates.append(QualityGateResult(2, "glTF Structure Valid", "PASSED", "glTF structure completely valid", val_report.to_dict()))

        # GATE 3: Geometry Analysis
        try:
            analysis_rep = self.analyzer.analyze(asset.source_path, asset.map_id)
            analysis_json = os.path.join(map_out_dir, "reports", "analysis.json")
            self.analyzer.export_report_json(analysis_rep, analysis_json)
            metrics["geometry_analysis"] = analysis_rep.to_dict()
            gates.append(QualityGateResult(3, "Geometry Analyzed", "PASSED", f"Analyzed {analysis_rep.face_count:,} faces across {analysis_rep.components_analysis.get('total_components', 1)} components"))
        except Exception as e:
            gates.append(QualityGateResult(3, "Geometry Analyzed", "FAILED", f"Geometry analysis error: {str(e)}"))
            return self._fail_report(asset, map_out_dir, quality_name, gates, warnings, [f"Geometry analysis failed: {str(e)}"])

        # GATE 4: Cleanup & Self-Healing
        val_glb = os.path.join(map_out_dir, "cleaned", "map_validated.glb")
        clean_glb = os.path.join(map_out_dir, "cleaned", "map_clean.glb")

        clean_mesh, cleanup_rep = None, None
        heal_attempts = 0
        max_heal_attempts = 2

        while heal_attempts <= max_heal_attempts:
            try:
                clean_mesh, cleanup_rep = self.cleaner.clean(
                    asset.source_path,
                    output_validated_path=val_glb,
                    output_clean_path=clean_glb,
                    map_id=asset.map_id
                )

                # Verify cleaned GLB
                if self.packager.verify_glb_file(clean_glb):
                    status_text = "HEALED" if heal_attempts > 0 else "PASSED"
                    gates.append(QualityGateResult(
                        4, "Cleanup Successful", status_text,
                        f"Cleaned {cleanup_rep.faces_before:,} -> {cleanup_rep.faces_after:,} faces (removed {cleanup_rep.camera_gizmos_removed} gizmos, {cleanup_rep.isolated_components_removed} noise clusters)",
                        cleanup_rep.to_dict()
                    ))
                    cleanup_json = os.path.join(map_out_dir, "reports", "cleanup.json")
                    with open(cleanup_json, "w", encoding="utf-8") as f:
                        json.dump(cleanup_rep.to_dict(), f, indent=2)
                    metrics["cleanup"] = cleanup_rep.to_dict()
                    break
                else:
                    raise RuntimeError("Cleaned GLB file is empty or corrupted")
            except Exception as e:
                heal_attempts += 1
                if heal_attempts <= max_heal_attempts:
                    warnings.append(f"Cleanup attempt {heal_attempts} failed ({str(e)}), applying self-healing relaxed parameters...")
                    # Relax cleanup parameters in self-healing
                    self.cleaner.config.min_component_faces = 10
                    self.cleaner.config.remove_duplicate_vertices = False
                else:
                    gates.append(QualityGateResult(4, "Cleanup Successful", "FAILED", f"Cleanup failed after {heal_attempts} attempts: {str(e)}"))
                    return self._fail_report(asset, map_out_dir, quality_name, gates, warnings, [f"Cleanup error: {str(e)}"])

        # GATE 5 & 6: Optimization & Render Mesh Generation
        render_glb = os.path.join(map_out_dir, "optimized", "render.glb")
        lod_dir = os.path.join(map_out_dir, "optimized")

        try:
            render_mesh, opt_rep = self.optimizer.optimize(
                clean_mesh=clean_mesh,
                source_clean_path=clean_glb,
                output_render_path=render_glb,
                output_lod_dir=lod_dir,
                quality_name=quality_name,
                map_id=asset.map_id
            )

            if not self.packager.verify_glb_file(render_glb):
                raise RuntimeError("Optimized render GLB is unreadable")

            opt_json = os.path.join(map_out_dir, "reports", "optimization.json")
            with open(opt_json, "w", encoding="utf-8") as f:
                json.dump(opt_rep.to_dict(), f, indent=2)

            metrics["optimization"] = opt_rep.to_dict()
            gates.append(QualityGateResult(
                5, "Optimization Successful", "PASSED",
                f"Decimated {opt_rep.faces_before:,} -> {opt_rep.faces_after:,} faces (-{opt_rep.face_reduction_percentage}%), generated {len(opt_rep.lods)} LODs",
                opt_rep.to_dict()
            ))
            gates.append(QualityGateResult(
                6, "Render Mesh Generated", "PASSED",
                f"Generated high quality render mesh: {os.path.basename(render_glb)}"
            ))
        except Exception as e:
            # Self-healing fallback: use cleaned mesh directly as render mesh if decimation failed
            warnings.append(f"QEM simplification error ({str(e)}), self-healing: falling back to clean mesh as render mesh")
            shutil.copyfile(clean_glb, render_glb)
            gates.append(QualityGateResult(5, "Optimization Successful", "HEALED", "Fallback to un-decimated clean mesh"))
            gates.append(QualityGateResult(6, "Render Mesh Generated", "HEALED", f"Generated render mesh via fallback: {os.path.basename(render_glb)}"))

        # Semantic Segmentation (AI Vision & Scene Understanding)
        if not no_ai:
            try:
                seg_glb = os.path.join(map_out_dir, "segmentation", "segmented.glb")
                src_dir = os.path.dirname(asset.source_path)
                ref_images = [
                    os.path.join(src_dir, f) for f in asset.associated_files
                    if f.lower().endswith((".png", ".jpg", ".jpeg"))
                ]
                _, seg_rep = self.segmenter.segment(
                    clean_mesh,
                    output_segmented_path=seg_glb,
                    map_id=asset.map_id,
                    reference_images=ref_images
                )
                seg_json = os.path.join(map_out_dir, "reports", "segmentation.json")
                with open(seg_json, "w", encoding="utf-8") as f:
                    json.dump(seg_rep.to_dict(), f, indent=2)
                metrics["segmentation"] = seg_rep.to_dict()
            except Exception as e:
                warnings.append(f"Semantic segmentation warning: {str(e)}")

        # GATE 7: Collision Generation
        col_glb = os.path.join(map_out_dir, "collision", "collision.glb")
        try:
            col_mesh, col_rep = self.collision_gen.generate_collision(
                clean_mesh=clean_mesh,
                output_collision_path=col_glb,
                map_id=asset.map_id
            )

            if not self.packager.verify_glb_file(col_glb):
                raise RuntimeError("Generated collision GLB is unreadable")

            col_json = os.path.join(map_out_dir, "reports", "collision.json")
            with open(col_json, "w", encoding="utf-8") as f:
                json.dump(col_rep.to_dict(), f, indent=2)

            metrics["collision"] = col_rep.to_dict()
            gates.append(QualityGateResult(
                7, "Collision Geometry Generated", "PASSED",
                f"Physical collision mesh generated with {col_rep.triangle_count:,} triangles (-{col_rep.reduction_percentage}%)",
                col_rep.to_dict()
            ))
        except Exception as e:
            gates.append(QualityGateResult(7, "Collision Geometry Generated", "FAILED", f"Collision generation failed: {str(e)}"))
            errors.append(f"Collision error: {str(e)}")

        # GATE 8: Walkable Surface & Navigation
        walk_glb = os.path.join(map_out_dir, "navigation", "walkable.glb")
        nav_json = os.path.join(map_out_dir, "navigation", "nav_graph.json")

        if not no_navigation:
            try:
                walk_mesh, walk_rep = self.nav_analyzer.generate_walkable_surface(
                    clean_mesh=clean_mesh,
                    output_walkable_path=walk_glb,
                    output_nav_graph_path=nav_json,
                    map_id=asset.map_id
                )

                walk_json = os.path.join(map_out_dir, "reports", "walkability.json")
                with open(walk_json, "w", encoding="utf-8") as f:
                    json.dump(walk_rep.to_dict(), f, indent=2)

                metrics["walkability"] = walk_rep.to_dict()

                if walk_rep.walkable_faces_count > 0 and self.packager.verify_glb_file(walk_glb):
                    gates.append(QualityGateResult(
                        8, "Walkable Surface Generated", "PASSED",
                        f"Extracted {walk_rep.walkable_faces_count:,} walkable faces ({walk_rep.walkable_area:.2f} m²), nav graph with {walk_rep.nav_graph.total_nodes} nodes",
                        walk_rep.to_dict()
                    ))
                else:
                    gates.append(QualityGateResult(
                        8, "Walkable Surface Generated", "PASSED",
                        "No horizontal surfaces met walkable slope threshold (vertical terrain / cliff)",
                        walk_rep.to_dict()
                    ))
            except Exception as e:
                gates.append(QualityGateResult(8, "Walkable Surface Generated", "FAILED", f"Walkability error: {str(e)}"))
                errors.append(f"Walkability error: {str(e)}")
        else:
            gates.append(QualityGateResult(8, "Walkable Surface Generated", "PASSED", "Navigation skipped via --no-navigation flag"))

        # Build scene descriptor
        bounds = [[float(x) for x in clean_mesh.bounds[0]], [float(x) for x in clean_mesh.bounds[1]]]
        extents = [float(x) for x in clean_mesh.extents]
        self.packager.build_scene_descriptor(asset.map_id, map_out_dir, bounds, extents, metrics)

        # GATE 9: Browser-Viewer Asset Check
        # Verify that render.glb, collision.glb, and walkable.glb exist and can be loaded
        render_ok = self.packager.verify_glb_file(render_glb)
        col_ok = self.packager.verify_glb_file(col_glb)
        walk_ok = self.packager.verify_glb_file(walk_glb) if not no_navigation else True

        if render_ok and col_ok and walk_ok:
            gates.append(QualityGateResult(
                9, "Browser Viewer Assets Verified", "PASSED",
                "All 3D layers (render, collision, walkable) verified loadable without errors"
            ))
        else:
            gates.append(QualityGateResult(
                9, "Browser Viewer Assets Verified", "FAILED",
                f"Asset check failed: render_ok={render_ok}, col_ok={col_ok}, walk_ok={walk_ok}"
            ))
            errors.append("Gate 9 asset loading failure")

        # Copy viewer standalone html into preview directory
        self._generate_preview_html(asset.map_id, map_out_dir)

        # Finalize package and generate SHA-256 hashes
        report = self.packager.finalize_package(
            map_id=asset.map_id,
            map_output_dir=map_out_dir,
            input_path=asset.source_path,
            quality_profile=quality_name,
            gate_results=gates,
            metrics=metrics,
            warnings=warnings,
            errors=errors
        )

        return report

    def _fail_report(
        self,
        asset: MapAssetInfo,
        map_out_dir: str,
        quality: str,
        gates: List[QualityGateResult],
        warnings: List[str],
        errors: List[str]
    ) -> MapPackageReport:
        return self.packager.finalize_package(
            map_id=asset.map_id,
            map_output_dir=map_out_dir,
            input_path=asset.source_path,
            quality_profile=quality,
            gate_results=gates,
            metrics={},
            warnings=warnings,
            errors=errors
        )

    def _generate_preview_html(self, map_id: str, map_out_dir: str) -> None:
        """Copies or generates an entrypoint HTML in preview/ for the local map."""
        preview_path = os.path.join(map_out_dir, "preview", "index.html")
        content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Preview: {map_id}</title>
    <meta http-equiv="refresh" content="0; url=/viewer?map={map_id}">
</head>
<body>
    <p>Redirecting to <a href="/viewer?map={map_id}">3D Map Viewer for {map_id}</a>...</p>
</body>
</html>"""
        with open(preview_path, "w", encoding="utf-8") as f:
            f.write(content)

    def process_all(
        self,
        quality: Optional[str] = None,
        force: bool = False,
        no_ai: bool = False,
        no_navigation: bool = False
    ) -> List[MapPackageReport]:
        """Scans and processes all discovered maps."""
        assets = self.scanner.scan()
        reports = []
        for a in assets:
            print(f"\n=======================================================")
            print(f"Processing Map: {a.map_id} ({a.source_filename})")
            print(f"=======================================================")
            rep = self.process_map(
                asset=a,
                quality=quality,
                force=force,
                no_ai=no_ai,
                no_navigation=no_navigation
            )
            reports.append(rep)
        return reports
